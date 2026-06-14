# Current Architecture

Last updated: 2026-06-13

This document describes the current architecture of `vdt-meeting-search`. The active system is an Elasticsearch-only retrieval baseline for HotpotQA multi-hop retrieval. VimQA data exists in the repository, but it is not yet integrated as a first-class benchmark dataset.

## 1. System Overview

```text
HotpotQA via ir_datasets
  -> staging JSONL shards
  -> SentenceTransformer embeddings
  -> Elasticsearch index
  -> retrieval methods
  -> benchmark metrics / FastAPI API
  -> React dashboard
```

| Layer | Component | Role |
|---|---|---|
| Dataset / ETL | `scripts/stage_hotpotqa.py`, `src/data/staging.py` | Load HotpotQA from `ir_datasets`, normalize documents, write staging JSONL |
| Ingest | `scripts/es_hotpotqa.py` | Create index, encode embeddings, bulk ingest, validate count, search CLI |
| Retrieval | `src/retrieval/elasticsearch_retriever.py` | BM25, dense kNN, hybrid RRF, iterative hybrid |
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

HotpotQA is loaded directly from `ir_datasets`. The default configured dataset is `nano-beir/hotpotqa`.

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
artifacts/nano/staging/docs-00000.jsonl
artifacts/nano/staging/manifest.json
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

Retrieval logic lives in `src/retrieval/elasticsearch_retriever.py`.

| Method | Internal name | Behavior |
|---|---|---|
| `es_bm25` | `bm25` | Elasticsearch `multi_match` over `title^2` and `content` |
| `es_dense` | `dense` | Encode query and run ES kNN over `embedding` |
| `es_hybrid` | `hybrid` | Retrieve BM25 and dense candidates, then fuse by RRF |
| `es_iterative_hybrid` | `iterative_hybrid` | Hop 1 hybrid, expand query from first-hop evidence, hop 2 hybrid, RRF fuse all hops |

Dense query embedding can run in-process with `SentenceTransformer`, or through a remote HTTP embedding endpoint when `EMBEDDING_SERVICE_URL` is configured.

Iterative hybrid currently uses this flow:

```text
Hop 1: run hybrid(query), take first_hop_k docs.
Hop 2: for each hop-1 doc, run hybrid(query + title + text prefix), take second_hop_k docs.
Fusion: RRF-fuse hop-1 and hop-2 rankings.
```

The benchmark CLI also has internal iterative variants: `es_iterative_title`, `es_iterative_sentence`, and `es_iterative_fast`.

## 6. Benchmark Layer

`src/evaluation/benchmark_es.py` is the main benchmark runner. It currently loads an `ir_datasets` dataset first, then loads queries/qrels from either the dataset or optional TSV files.

Important CLI inputs:

```text
--dataset          ir_datasets id, default nano-beir/hotpotqa
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

Metrics are computed in `src/evaluation/metrics.py`: `precision@k`, `recall@k`, `mrr@k`, `ndcg@k`, `full_support_recall@k`, latency p50/p95/p99, and QPS.

`full_support_recall@k` is important for HotpotQA because many queries need all supporting documents, not just one relevant hit.

## 7. API Layer

The FastAPI app is in `src/api/main.py`.

| Endpoint | Method | Role |
|---|---|---|
| `/health` | GET | Health check |
| `/stats` | GET | Runtime config: backend, index, dataset, model, cache, history path |
| `/queries` | GET | Query examples and support docs from `ir_datasets` or TSV fallback |
| `/benchmark` | GET | Benchmark JSON artifact |
| `/search` | POST | Run a retrieval method through `ElasticsearchRetriever` |
| `/history` | GET | List search history |
| `/history/{id}` | GET | Return one search history entry |
| `/history` | DELETE | Clear search history |

Search request shape:

```json
{
  "query": "...",
  "method": "es_hybrid",
  "top_k": 10
}
```

When `REDIS_URL` is set, `/search` responses are cached by `index + query + method + top_k`. If Redis is unavailable, the API falls back to direct Elasticsearch search.

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
| `DATASET_ID` | `nano-beir/hotpotqa` | Dataset used by API query examples |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch endpoint |
| `ELASTICSEARCH_INDEX` | `hotpotqa_docs_current` | Search index or alias |
| `ELASTICSEARCH_NUM_CANDIDATES` | `1000` | Default dense kNN candidate count |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | SentenceTransformer model |
| `EMBEDDING_SERVICE_URL` | empty | Remote embedding endpoint, when configured |
| `REDIS_URL` | empty | Redis cache URL |
| `SEARCH_CACHE_TTL_SECONDS` | `300` | Search cache TTL |
| `HISTORY_DB_PATH` | `data/query_history.sqlite3` | SQLite history path |
| `MULTIHOP_FIRST_HOP` | `5` | Iterative retrieval hop-1 size |
| `MULTIHOP_SECOND_HOP` | `10` | Iterative retrieval hop-2 size |
| `MULTIHOP_CONTEXT_CHARS` | `256` | Text prefix used for query expansion |

## 11. Dataset Boundaries

### HotpotQA

HotpotQA is the officially integrated dataset in the current code path. The code assumes the dataset exposes `docs_iter()`, `queries_iter()`, and `qrels_iter()` through `ir_datasets`. Benchmark qrels come from `ir_datasets` unless `--qrels-file` is provided. API `/queries` also prefers query/qrels data from `ir_datasets`.

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
2. The benchmark runner always loads `ir_datasets` before running, even when `--query-file` and `--qrels-file` are provided.
3. VimQA is not isolated as a first-class dataset yet.
4. API labels and dashboard copy are still HotpotQA-oriented.
5. The default embedding model is English BGE small, not optimized for Vietnamese.
6. `es_iterative_hybrid` is heuristic, has high latency, and does not currently beat `es_hybrid` on the nano benchmark.
7. The full HotpotQA corpus of 5.23M docs has not been ingested/indexed in the active baseline.

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
artifacts/hotpotqa/nano/...
artifacts/vimqa/test/...
evaluation/results/hotpotqa/...
evaluation/results/vimqa/...
evaluation/runs/hotpotqa/...
evaluation/runs/vimqa/...
```

Elasticsearch indexes and aliases should be separate too:

```text
hotpotqa_nano_v1        -> hotpotqa_nano_current
vimqa_test_v1           -> vimqa_test_current
```

This preserves the existing retrieval methods while removing the need to use HotpotQA as a dummy dataset when benchmarking VimQA.
