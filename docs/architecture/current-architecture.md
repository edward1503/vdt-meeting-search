# Current Architecture

Last updated: 2026-06-16

This document describes the current architecture of `vdt-meeting-search`. The active system is a full-corpus HotpotQA retrieval demo: Elasticsearch serves BM25 and document hydration, TurboVec serves dense retrieval over the full 5.23M-document corpus, Redis caches search responses, and the React dashboard runs against `beir/hotpotqa/dev` queries/qrels.

## 1. System Overview

```text
HotpotQA full corpus + beir/hotpotqa/dev queries
  -> staging JSONL shards
  -> Elasticsearch BM25 index + TurboVec dense index
  -> retrieval methods / support overlay
  -> benchmark metrics / FastAPI API
  -> React dashboard
```

| Layer | Component | Role |
|---|---|---|
| Dataset / ETL | `scripts/stage_hotpotqa.py`, `src/data/staging.py` | Load HotpotQA from `ir_datasets`, normalize documents, write staging JSONL |
| Ingest | `scripts/es_hotpotqa.py` | Create index, encode embeddings, bulk ingest, validate count, search CLI |
| Retrieval | `src/retrieval/elasticsearch_retriever.py`, `src/retrieval/turbovec_retriever.py` | BM25, TurboVec dense, TurboVec hybrid RRF, filtered TurboVec hybrid |
| Evaluation | `src/evaluation/benchmark_es.py`, `src/evaluation/metrics.py` | Run benchmarks, write TREC runs, compute metrics |
| API | `src/api/main.py` | FastAPI endpoints for health, stats, queries, benchmark, history, search |
| Cache | Redis | Cache repeated `/search` responses by query/method/top-k/index |
| History | SQLite | Store search history and top returned documents |
| Frontend | `frontend/` | React/Vite dashboard calling the FastAPI API |
| Embedding service | `scripts/embedding_server.py` | Local `/embed` HTTP service so the API container does not need PyTorch |

## 2. Repository Layout

```text
src/
  api/                  FastAPI app and history store
  core/                 Runtime settings from environment variables
  data/                 HotpotQA loading, staging, ingest EDA helpers
  evaluation/           Benchmark runner, metrics, paraphrase comparison
  retrieval/            Elasticsearch retriever and retrieval primitives

scripts/
  stage_hotpotqa.py     Stage HotpotQA docs from ir_datasets
  es_hotpotqa.py        Create/index/ingest/validate/search Elasticsearch
  embedding_server.py   Local embedding HTTP service
  paraphrase_queries.py Query paraphrase stress-test generator

frontend/               React/Vite dashboard
docs/baseline/          Baseline reports and reproduce commands
docs/data/vimqa/        VimQA JSON files, not yet integrated natively
evaluation/results/     Benchmark JSON outputs and query TSVs
evaluation/runs/        TREC run files
artifacts/*/staging     JSONL staging shards
artifacts/*/progress    Ingest done markers
```

## 3. Data Pipeline

HotpotQA documents are loaded from the full `beir/hotpotqa` corpus. API query examples and gold support labels default to `beir/hotpotqa/dev`; Docker uses `evaluation/results/hotpotqa_full_dev_queries.tsv` as the fallback query/qrels file because the API image intentionally does not install `ir_datasets`.

`src/data/staging.py` normalizes every document into this staging shape:

```json
{
  "doc_id": "...",
  "title": "...",
  "text": "...",
  "url": "...",
  "content": "title + text",
  "embedding_text": "title + text"
}
```

`content` is used for lexical retrieval in Elasticsearch. `embedding_text` is only used during ingest to encode vectors; it is not stored in the Elasticsearch source document.

Staging writes JSONL shards such as:

```text
artifacts/hotpotqa_full/staging/docs-00000.jsonl
artifacts/hotpotqa_full/staging/manifest.json
```

## 4. Elasticsearch Indexing

`scripts/es_hotpotqa.py` is the main index lifecycle CLI. It supports `create-index`, `ingest`, `validate`, and `search`.

The current index schema is built by `build_index_body()`:

| Field | Type | Role |
|---|---|---|
| `doc_id` | `keyword` | Stable document id, also used as ES `_id` |
| `title` | `text` | Search/display title |
| `text` | `text` | Search/display body |
| `url` | `keyword` | Metadata |
| `content` | `text` | Lexical search field |
| `embedding` | `dense_vector` | Dense vector field with cosine similarity |

Default vector dimension is `384`, matching `BAAI/bge-small-en-v1.5`.

Ingest flow:

```text
staging JSONL
  -> read batch
  -> encode row["embedding_text"] with SentenceTransformer
  -> helpers.bulk() into Elasticsearch
  -> write progress marker docs-xxxxx.done
  -> refresh index after ingest completes
```

Progress markers under `artifacts/.../progress` allow interrupted ingest jobs to resume.

## 5. Retrieval Layer

Retrieval logic lives in `src/retrieval/elasticsearch_retriever.py` and `src/retrieval/turbovec_retriever.py`.

| Method | Internal name | Behavior |
|---|---|---|
| `es_bm25` | `bm25` | Elasticsearch `multi_match` over `title^2` and `content` |
| `tv_dense` | `tv_dense` | Encode query through the host embedding service and search the mounted TurboVec index |
| `tv_hybrid` | `tv_hybrid` | Retrieve BM25 and TurboVec dense candidates, then fuse by RRF |
| `tv_filtered_hybrid` | `tv_filtered_hybrid` | Use BM25 candidates as an allowlist for TurboVec dense search, then fuse results |

In Docker, query embeddings are produced by the host HTTP embedding endpoint configured with `EMBEDDING_SERVICE_URL`. The API container does not install PyTorch or SentenceTransformers.

## 6. Benchmark Layer

`src/evaluation/benchmark_es.py` is the main benchmark runner. It currently loads an `ir_datasets` dataset first, then loads queries/qrels from either the dataset or optional TSV files.

Important CLI inputs:

```text
--dataset          ir_datasets id, default beir/hotpotqa/dev
--index            Elasticsearch index or alias
--methods          comma-separated method names
--top-k
--candidate-k
--num-candidates
--rrf-k
--first-hop-k
--second-hop-k
--context-chars
--query-file       optional TSV for paraphrase/custom queries
--qrels-file       optional TSV for custom qrels
```

Outputs are written to `evaluation/results/*.json` and `evaluation/runs/**/*.trec`.

Metrics are computed in `src/evaluation/metrics.py`: `precision@k`, `recall@k`, `mrr@k`, `ndcg@k`, `full_support_recall@k`, latency p50/p95/p99, and QPS. The dashboard surfaces the current 200-query full-corpus dev benchmark as project progress and keeps legacy nano benchmarks below it; paper-comparable claims should use the full `beir/hotpotqa/test` split.

`full_support_recall@k` is important for HotpotQA because many queries need all supporting documents, not just one relevant hit.

## 7. API Layer

The FastAPI app is in `src/api/main.py`.

| Endpoint | Method | Role |
|---|---|---|
| `/health` | GET | Health check |
| `/stats` | GET | Runtime config: backend, index, dataset, model, cache, history path |
| `/queries` | GET | Query examples and support docs from `ir_datasets` or TSV fallback |
| `/benchmark` | GET | Benchmark dashboard payload with current full-corpus project-progress results plus legacy nano history |
| `/search` | POST | Run BM25/TurboVec retrieval and return support coverage metadata |
| `/history` | GET | List search history |
| `/history/{id}` | GET | Return one search history entry |
| `/history` | DELETE | Clear search history |

Search request shape:

```json
{
  "query_id": "...",
  "query": "...",
  "method": "tv_hybrid",
  "top_k": 10
}
```

When `REDIS_URL` is set, `/search` responses are cached by `index + query_id + query + method + top_k`. If Redis is unavailable, the API falls back to direct retrieval. `/search` responses include a `support` summary and per-result `is_support` flag when qrels are available.

`src/api/history.py` stores search history in SQLite. The default path is `data/query_history.sqlite3`; in Docker Compose it is backed by the `history_data` volume.

## 8. Frontend Layer

The frontend is a React/Vite app in `frontend/`.

| View | Component | Role |
|---|---|---|
| Status | `StatusView` | Show backend/runtime configuration |
| Search | `SearchView` | Run a query by method/top-k |
| Queries | `QueriesView` | Show query examples and support docs |
| Benchmark | `BenchmarkView` | Show benchmark metrics |
| History | `HistoryView` | Review search history and run a query again |

The API client is `frontend/src/lib/api.ts`. The default API base URL is `/api`, matching the Docker/Vite proxy setup.

## 9. Docker Development Stack

`docker-compose.yml` defines four services:

| Service | Host port | Role |
|---|---:|---|
| `elasticsearch` | `9200` | Elasticsearch 8.15.1, single node, security disabled |
| `redis` | internal | Search response cache |
| `api` | `8001 -> 8000` | FastAPI retrieval API |
| `frontend` | `3001` | Vite React dashboard |

The embedding model does not run inside the API container by default. The API calls a host service at `http://host.docker.internal:8010/embed`, started with:

```bash
python scripts/embedding_server.py --host 0.0.0.0 --port 8010
```

## 10. Configuration

Runtime settings live in `src/core/config.py`.

| Env var | Default | Role |
|---|---|---|
| `DATASET_ID` | `beir/hotpotqa/dev` | Full HotpotQA split used by API query examples and support labels |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch endpoint |
| `ELASTICSEARCH_INDEX` | `hotpotqa_docs_current` locally, `hotpotqa_full_bm25_current` in Docker | Search index or alias |
| `ELASTICSEARCH_NUM_CANDIDATES` | `1000` | Default dense kNN candidate count |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | SentenceTransformer model |
| `EMBEDDING_SERVICE_URL` | empty locally, `http://host.docker.internal:8010/embed` in Docker | Remote embedding endpoint, when configured |
| `REDIS_URL` | empty | Redis cache URL |
| `SEARCH_CACHE_TTL_SECONDS` | `300` | Search cache TTL |
| `HISTORY_DB_PATH` | `data/query_history.sqlite3` | SQLite history path |
| `TURBOVEC_INDEX_PATH` | `artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim` | Mounted TurboVec dense index |
| `DEFAULT_SEARCH_METHOD` | `tv_hybrid` | Default dashboard/API search method |

## 11. Dataset Boundaries

### HotpotQA

HotpotQA is the officially integrated dataset in the current code path. Documents come from the full `beir/hotpotqa` corpus; API examples and support labels use `beir/hotpotqa/dev`. Benchmark qrels come from `ir_datasets` unless `--qrels-file` is provided. API `/queries` prefers query/qrels data from `ir_datasets` and falls back to `evaluation/results/hotpotqa_full_dev_queries.tsv` in Docker.

### VimQA

VimQA currently lives at:

```text
docs/data/vimqa/train_vimqa.json
docs/data/vimqa/test_vimqa.json
```

Observed schema:

```json
{
  "question": "...",
  "context": "...",
  "answer": "..."
}
```

Current status:

- No native `VimQADataset` adapter exists yet.
- No native VimQA staging script exists yet.
- The benchmark runner does not accept `--dataset-type vimqa` yet.
- VimQA can be tested manually by converting `context` into docs, `question` into queries, and generating qrels TSV, but that is not yet first-class architecture.

VimQA is currently a single-context QA dataset, not a BEIR-style retrieval dataset with separate corpus/query/qrels files. Running retrieval evaluation on VimQA requires defining a retrieval proxy explicitly.

## 12. Known Limitations

1. The dataset layer is still hard-coded around HotpotQA and `ir_datasets`.
2. The benchmark runner still depends on `ir_datasets` for standard HotpotQA runs.
3. VimQA is not isolated as a first-class dataset yet.
4. API labels and dashboard copy are still HotpotQA-oriented.
5. The default embedding model is English BGE small, not optimized for Vietnamese.
6. First TurboVec load after API reload can be slower than warm searches because the full `.tvim` artifact is opened on demand.

## 13. Recommended Direction For Dataset Isolation

To isolate HotpotQA and VimQA, add a dataset adapter layer:

```text
RetrievalDataset interface
  -> HotpotQADataset: ir_datasets source
  -> VimQADataset: local JSON source
```

Each adapter should expose the same contract: `docs_iter()`, `queries(max_queries)`, `qrels(query_ids)`, `slug()`, and `metadata()`.

Artifacts should also be separated by dataset:

```text
artifacts/hotpotqa_full/...
artifacts/vimqa/test/...
evaluation/results/hotpotqa/...
evaluation/results/vimqa/...
evaluation/runs/hotpotqa/...
evaluation/runs/vimqa/...
```

Elasticsearch indexes and aliases should be separate too:

```text
hotpotqa_full_bm25_v1   -> hotpotqa_full_bm25_current
vimqa_test_v1           -> vimqa_test_current
```

This preserves the existing retrieval methods while removing the need to use HotpotQA as a dummy dataset when benchmarking VimQA.
