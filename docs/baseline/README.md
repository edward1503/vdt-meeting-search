# Baseline: Elasticsearch Hybrid Multi-hop Retrieval trên HotpotQA

Baseline active hiện tại chỉ dùng **Elasticsearch**. Các baseline local cũ đã được xoá khỏi code path và artifact kết quả active.

## Dataset

| Thành phần | Giá trị |
|------------|---------|
| Dataset benchmark | `nano-beir/hotpotqa` |
| Documents | 5,090 |
| Queries | 50 |
| Qrels | 100 |
| Task | multi-hop evidence retrieval |

HotpotQA cần retrieve đủ supporting documents, nên metric quan trọng nhất ngoài Recall/nDCG là `full_support_recall@k`.

## Pipeline

```text
ir_datasets
  -> normalize docs
  -> staging JSONL shards
  -> encode embedding_text bằng BGE small
  -> bulk ingest Elasticsearch
  -> validate index count
  -> ES BM25 / dense / hybrid / iterative hybrid
  -> benchmark qrels
```

## Cấu hình index và embedding

| Cấu hình | Giá trị |
|---|---|
| Chunking | Không chunk |
| Granularity | 1 HotpotQA doc = 1 ES doc = 1 vector |
| `content` | `title + text` |
| `embedding_text` | `content`, chỉ dùng để encode, không index vào ES |
| Embedding model | `BAAI/bge-small-en-v1.5` |
| Dimension | 384 |
| Normalize embeddings | Có |
| ES vector field | `embedding` |
| ES vector similarity | `cosine` |
| Shards / replicas | 1 primary shard, 0 replicas |

## Search methods

| Method | Mô tả |
|--------|-------|
| `es_bm25` | Elasticsearch `multi_match` trên `title^2` và `content` |
| `es_dense` | Elasticsearch kNN trên vector `embedding` |
| `es_hybrid` | BM25 + dense ES candidates, fuse bằng RRF |
| `es_iterative_hybrid` | Hop 1 dùng `es_hybrid`, hop 2 expand query từ top evidence rồi RRF fuse |

## Cấu hình benchmark tuned

| Tham số | Giá trị |
|---|---:|
| `top_k` | 10 |
| `candidate_k` | 100 |
| `num_candidates` | 100 |
| `rrf_k` | 30 |
| `first_hop_k` | 5 |
| `second_hop_k` | 10 |
| `context_chars` | 256 |

## Kết quả hiện tại

| Method | Precision@10 | Recall@10 | MRR@10 | nDCG@10 | Full-support Recall@10 | p50 latency | QPS |
|--------|--------------|-----------|--------|---------|-------------------------|-------------|-----|
| `es_bm25` | 0.176 | 0.88 | 0.9072 | 0.8188 | 0.76 | 68.0733 ms | 10.6676 |
| `es_dense` | 0.172 | 0.86 | 0.8872 | 0.8191 | 0.74 | 82.3391 ms | 0.9256 |
| `es_hybrid` | 0.182 | 0.91 | 0.9253 | 0.8631 | 0.82 | 142.0170 ms | 6.8969 |
| `es_iterative_hybrid` | 0.180 | 0.90 | 0.9033 | 0.8341 | 0.82 | 1119.7100 ms | 0.8408 |

`es_hybrid` là cấu hình tốt nhất hiện tại theo quality/latency. `es_iterative_hybrid` là baseline multi-hop explicit để debug evidence chain, nhưng latency cao hơn nhiều.

## Reproduce

```bash
docker compose up -d elasticsearch
python scripts/stage_hotpotqa.py --dataset nano-beir/hotpotqa --output-dir artifacts/nano/staging --docs-per-file 2000
python scripts/es_hotpotqa.py create-index --index hotpotqa_nano_v1 --alias hotpotqa_nano_current --reset
python scripts/es_hotpotqa.py ingest --index hotpotqa_nano_v1 --staging-dir artifacts/nano/staging --progress-dir artifacts/nano/progress --batch-size 64
python scripts/es_hotpotqa.py validate --index hotpotqa_nano_current --expected-count 5090
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_current --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_iterative.json --run-dir evaluation/runs/iterative
```
