# HotpotQA Full-Corpus TurboVec Retrieval

This project implements a full-corpus HotpotQA retrieval demo with Elasticsearch BM25, TurboVec dense search, Redis caching, and a React dashboard.

The active demo methods are:

- `es_bm25`: Elasticsearch lexical retrieval over `title^2` and `content`.
- `tv_dense`: TurboVec dense retrieval over the full HotpotQA `.tvim` artifact.
- `tv_hybrid`: BM25 and TurboVec dense candidates fused with Reciprocal Rank Fusion.
- `tv_filtered_hybrid`: BM25-candidate-filtered TurboVec hybrid retrieval.

The active Docker profile uses `beir/hotpotqa/dev` queries and qrels against the full `hotpotqa_full_bm25_current` document index. Nano HotpotQA is no longer part of the runtime/demo default.

## Setup

```bash
pip install -r requirements.txt
```

## Elasticsearch Pipeline

```bash
docker compose up -d elasticsearch
python scripts/stage_hotpotqa.py --dataset beir/hotpotqa --output-dir artifacts/hotpotqa_full/staging --docs-per-file 50000
python scripts/es_hotpotqa.py create-index --index hotpotqa_full_bm25_v1 --alias hotpotqa_full_bm25_current --reset
python scripts/es_hotpotqa.py ingest --index hotpotqa_full_bm25_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress --batch-size 256
python scripts/es_hotpotqa.py validate --index hotpotqa_full_bm25_current --expected-count 5233329
```

## Benchmark

```bash
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_current --methods es_bm25,tv_dense,tv_hybrid --top-k 10 --max-queries 200 --candidate-k 50 --num-candidates 50 --rrf-k 30 --output evaluation/results/hotpotqa_full/tv_full_200.json --run-dir evaluation/runs/hotpotqa_full
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

The frontend container uses Vite hot reload with `./frontend:/app` and a Docker named volume for `/app/node_modules`. The API container uses Uvicorn reload with bind-mounted Python source. Redis caches repeated `/search` responses using `REDIS_URL` and `SEARCH_CACHE_TTL_SECONDS`. TurboVec search loads the mounted full `.tvim` artifact from `./artifacts`, and query embeddings call the local embedding service at `http://host.docker.internal:8010/embed`, so PyTorch and SentenceTransformers stay outside the Docker API image.

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
- `docs/baseline/paraphrase-robustness-report.md`: 50-query paraphrase robustness benchmark report.

## Query Set

The dashboard query browser uses `beir/hotpotqa/dev` and the checked-in fallback file `evaluation/results/hotpotqa_full_dev_queries.tsv`. This keeps Docker runtime on the full HotpotQA profile even though the API image intentionally does not install `ir_datasets`.
