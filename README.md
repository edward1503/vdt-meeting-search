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

## Docker Development Stack

Run the local embedding service plus Elasticsearch, Redis, FastAPI, and the React/Vite dashboard together:

```bash
.\scripts\docker-dev.ps1
```

Or use the helper scripts:

```powershell
.\scripts\docker-dev.ps1
```

```bash
sh scripts/docker-dev.sh
```

Open:

- Frontend dashboard: `http://localhost:3001`
- FastAPI docs: `http://localhost:8001/docs`
- Elasticsearch: `http://localhost:9200`
- Redis: internal Compose service `redis:6379`

The frontend container uses Vite hot reload with `./frontend:/app` and a Docker named volume for `/app/node_modules`. The API container uses Uvicorn reload with bind-mounted Python source. Redis caches repeated `/search` responses using `REDIS_URL` and `SEARCH_CACHE_TTL_SECONDS`. Dense and hybrid search call the local embedding service at `http://host.docker.internal:8010/embed`, so PyTorch and SentenceTransformers stay outside the Docker API image.

## API Demo

Without Docker, run the API and frontend separately:

```bash
python scripts/embedding_server.py --host 0.0.0.0 --port 8010`r`nuvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000`r`ncd frontend
npm install
npm run dev
```

Open `http://localhost:3001`.

## Docs

- `docs/baseline/report-baseline.md`: technical report and benchmark results.
- `docs/baseline/elasticsearch-baseline.md`: lean Elasticsearch commands and policy.
