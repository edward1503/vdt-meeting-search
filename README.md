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

The benchmark reports `precision@k`, `recall@k`, `mrr@k`, `ndcg@k`, `full_support_recall@k`, latency percentiles, and QPS. The dashboard benchmark page now treats the full-corpus 200-query dev run as a project-progress pilot for `es_bm25`, `tv_dense`, `tv_filtered_hybrid`, and `tv_hybrid`, with legacy nano/Elasticsearch results shown separately. Use the full `beir/hotpotqa/test` split with 7,405 queries before making BEIR/paper-comparable claims.

## Docker Development Stack

Run the local embedding service plus Elasticsearch, Redis, FastAPI, and the React/Vite dashboard together:

```bash
./start.sh
```

`start.sh` keeps PyTorch and SentenceTransformers on the host GPU, warms both the HotpotQA BGE model and the VimQA BKAI model through `http://localhost:8010`, then starts the Docker Compose runtime. This avoids installing GPU/PyTorch dependencies inside the API container while still letting Docker call the host embedding service at `host.docker.internal:8010`.

The older PowerShell helper is still available for lightweight local development:

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

### Demo Cache Warmup

For a low-latency demo, start the full demo runtime with a longer search cache TTL, then warm the first 50 queries for each dataset through the public API:

```powershell
$env:SEARCH_CACHE_TTL_SECONDS = "86400"
.\start.sh
python scripts/warm_demo_cache.py --api-url http://localhost:8001 --datasets hotpotqa,vimqa --limit 50 --top-k 10 --metadata-demo --verify-cache-hit
```

The warmup command does not write Redis keys directly. It calls `/datasets/{dataset_id}/search`, so it uses the same cache key and default retrieval method as the dashboard. HotpotQA warms with the profile default `tv_hybrid`; VimQA warms with the profile default `es_bm25`. `--metadata-demo` also warms curated semantic metadata queries with `semantic_metadata=true` and no `query_id`, matching the way a presenter types those queries in the Search tab.

If a demo needs a cheaper HotpotQA path, override the method explicitly:

```powershell
python scripts/warm_demo_cache.py --api-url http://localhost:8001 --datasets hotpotqa --method hotpotqa=es_bm25 --limit 50 --top-k 10 --metadata-demo --verify-cache-hit
```

To add one-off metadata-mode queries without editing the script, pass `--metadata-query` as `dataset::query`:

```powershell
python scripts/warm_demo_cache.py --api-url http://localhost:8001 --datasets hotpotqa --limit 0 --metadata-query "hotpotqa::find documents about ozone modified after 2024-02-03" --verify-cache-hit
```

## Dataset-First Runtime

The dashboard exposes HotpotQA and VimQA as dataset workspaces from one API/frontend runtime.

- `GET /datasets` lists available dataset profiles.
- Dataset-scoped endpoints live under `/datasets/{dataset_id}/...`, for example `/datasets/hotpotqa/search` and `/datasets/vimqa/search`.
- The React UI uses a dataset selector, then routes Search, Queries, Benchmarks, Indexes, Metadata, History, and Status through the active dataset profile.
- Legacy endpoints `/stats`, `/queries`, `/benchmark`, and `/search` remain HotpotQA-compatible during migration.
- The UI is a query and inspection surface only. It does not create, delete, rebuild, or edit Elasticsearch indexes or metadata schemas.

Dataset flow:

```text
Select VimQA
-> Queries calls GET /datasets/vimqa/queries
-> Run Default sends POST /datasets/vimqa/search with method es_bm25
-> Benchmark calls GET /datasets/vimqa/benchmarks and emphasizes recall/MRR/nDCG
-> Metadata displays filters unsupported
```

```text
Select HotpotQA
-> Queries calls GET /datasets/hotpotqa/queries
-> Search calls POST /datasets/hotpotqa/search with HotpotQA methods
-> Benchmark calls GET /datasets/hotpotqa/benchmarks and emphasizes full-support recall
-> Metadata displays supported filter fields
```

Runtime modes:

| Mode | Services | Use |
| --- | --- | --- |
| UI/API lightweight | frontend + api | Inspect profiles and static benchmark/query artifacts; search may fail without indexes. |
| Search runtime | frontend + api + elasticsearch + redis + embedding service when dense/TurboVec is used | Run interactive search. |
| Index/benchmark runtime | elasticsearch + scripts | Build indexes and benchmark artifacts. |
| Full demo runtime | frontend + api + elasticsearch + redis + embedding service + prepared HotpotQA/VimQA indexes | Side-by-side HotpotQA/VimQA workspace demo. |

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

The dashboard query browser uses `beir/hotpotqa/dev` and the checked-in fallback file `evaluation/results/hotpotqa_full_dev_queries.tsv`. The `/queries` API is paginated with `limit`, `offset`, and `search` parameters, and the frontend defaults to 10 queries per page so Docker runtime stays on the full HotpotQA profile without loading the whole query set into the browser.
