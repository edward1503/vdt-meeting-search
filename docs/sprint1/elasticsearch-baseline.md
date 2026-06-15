# Elasticsearch Baseline

## Pipeline

```text
ir_datasets
  -> EDA/preflight
  -> staging JSONL cache
  -> embed + bulk ingest into Elasticsearch
  -> validate index
  -> BM25/dense/hybrid/iterative hybrid search
  -> benchmark qrels
```

## Baseline Policy

- Elasticsearch is the only search backend.
- One HotpotQA doc maps to one ES doc and one vector.
- Staging JSONL and `.done` markers are the only ingest cache.
- Redis, queues, and multi-node cluster setup are outside the baseline.

## Commands

```bash
docker compose up -d elasticsearch
python scripts/eda_hotpotqa_ingest.py --dataset beir/hotpotqa --sample-docs 100000
python scripts/stage_hotpotqa.py --dataset beir/hotpotqa --output-dir artifacts/hotpotqa_full/staging
python scripts/es_hotpotqa.py create-index --index hotpotqa_docs_v1 --alias hotpotqa_docs_current --reset
python scripts/es_hotpotqa.py ingest --index hotpotqa_docs_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress
python scripts/es_hotpotqa.py validate --index hotpotqa_docs_current --expected-count 5233329
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_docs_current --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 100
```

## Nano Smoke

```bash
python scripts/stage_hotpotqa.py --dataset nano-beir/hotpotqa --output-dir artifacts/nano/staging --docs-per-file 2000
python scripts/es_hotpotqa.py create-index --index hotpotqa_nano_v1 --alias hotpotqa_nano_current --reset
python scripts/es_hotpotqa.py ingest --index hotpotqa_nano_v1 --staging-dir artifacts/nano/staging --progress-dir artifacts/nano/progress --max-files 1 --batch-size 64
python scripts/es_hotpotqa.py validate --index hotpotqa_nano_current --expected-count 2000
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_current --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --max-queries 10 --output evaluation/results/es_nano_smoke.json --run-dir evaluation/runs
```

## ES Iterative Hybrid

`es_iterative_hybrid` là baseline multi-hop explicit trên Elasticsearch:

```text
query -> es_hybrid hop 1 -> top first_hop_k docs
query + hop1 title/text prefix -> es_hybrid hop 2 per hop1 doc
hop1 + hop2 rankings -> RRF -> top-k
```

Cấu hình nano tuned hiện dùng `first_hop_k=5`, `second_hop_k=10`, `context_chars=256`, `candidate_k=100`, `num_candidates=100`, `rrf_k=30`.

Kết quả benchmark đủ 5,090 docs và 50 queries nằm ở:

```text
evaluation/results/es_nano_iterative.json
```
