# HotpotQA Elasticsearch Retrieval Baseline

This project implements an Elasticsearch-only baseline for the VDT Hybrid Information Retrieval task on HotpotQA multi-hop retrieval.

The active baseline methods are:

- `es_bm25`: Elasticsearch lexical retrieval over `title^2` and `content`.
- `es_dense`: Elasticsearch kNN retrieval over BGE embeddings.
- `es_hybrid`: BM25 and dense candidates fused with Reciprocal Rank Fusion.
- `es_iterative_hybrid`: two-hop Elasticsearch hybrid retrieval with query expansion from first-hop evidence.

Legacy local retrieval baselines have been removed from the active code path.

## Setup

```bash
pip install -r requirements.txt
```

## Elasticsearch Pipeline

```bash
docker compose up -d elasticsearch
python scripts/stage_hotpotqa.py --dataset nano-beir/hotpotqa --output-dir artifacts/nano/staging --docs-per-file 2000
python scripts/es_hotpotqa.py create-index --index hotpotqa_nano_v1 --alias hotpotqa_nano_current --reset
python scripts/es_hotpotqa.py ingest --index hotpotqa_nano_v1 --staging-dir artifacts/nano/staging --progress-dir artifacts/nano/progress --batch-size 64
python scripts/es_hotpotqa.py validate --index hotpotqa_nano_current --expected-count 5090
```

## Benchmark

```bash
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_current --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_iterative.json --run-dir evaluation/runs/iterative
```

The benchmark reports `precision@k`, `recall@k`, `mrr@k`, `ndcg@k`, `full_support_recall@k`, latency percentiles, and QPS.

## API Demo

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Open the static frontend:

```text
frontend/index.html
```

## Docs

- `docs/baseline/report-baseline.md`: technical report and benchmark results.
- `docs/baseline/elasticsearch-baseline.md`: lean Elasticsearch commands and policy.
