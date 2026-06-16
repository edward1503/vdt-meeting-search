# US-S3-014 Docker TurboVec Runtime

## Status

planned

## Lane

normal

## Product Contract

The existing Docker API container should run the TurboVec dense retrieval methods (`tv_dense`, `tv_hybrid`, and `tv_filtered_hybrid`) by loading a mounted `.tvim` artifact directly inside the container. Elasticsearch remains the BM25 and document hydration backend. The embedding model stays outside the API image through the existing `EMBEDDING_SERVICE_URL` path, so the migration does not pull PyTorch or SentenceTransformers into the API Docker image.

## Relevant Product Docs

- `README.md`
- `docs/architecture/current-architecture.md`
- `docs/sprint3/sprint3-report.md`

## Acceptance Criteria

- `requirements-api.txt` installs the minimum dependencies needed for TurboVec search in the API container: `numpy` and `turbovec`.
- `TurboVecHybridRetriever.from_paths()` uses `EMBEDDING_SERVICE_URL` when configured and does not import `sentence_transformers` in that path.
- Docker Compose exposes `TURBOVEC_INDEX_PATH` to the API container and continues mounting `./artifacts:/app/artifacts`.
- A full demo can run with `ELASTICSEARCH_INDEX=hotpotqa_full_bm25_current` and `TURBOVEC_INDEX_PATH=/app/artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim`.
- `/stats` shows enough runtime information to confirm the active Elasticsearch index, TurboVec artifact path, and embedding service URL.
- Frontend behavior remains unchanged: it calls `/api/search`, and `tv_*` methods route through the backend.

## Design Notes

- Commands: no new user command is required; existing Docker Compose commands keep working with env overrides.
- Queries: `tv_dense`, `tv_hybrid`, and `tv_filtered_hybrid` are the migration target; `es_dense` remains legacy and optional.
- API: no search request or response shape change is required.
- Tables: no SQLite or Elasticsearch schema migration.
- Domain rules: do not mix ES nano with TurboVec full for serious demos; use matching runtime profiles.
- UI surfaces: no required frontend change in the minimal migration.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S3-014 --unit 1 --integration 1 --e2e 0 --platform 0`.

| Layer | Expected proof |
| --- | --- |
| Unit | `python -m pytest tests/test_turbovec_retriever.py tests/test_api_es_config.py -q` |
| Integration | Docker build of the API image plus API `/stats` and `/search` smoke checks. |
| E2E | Frontend dashboard search using `tv_hybrid` against the Docker API. |
| Platform | `docker compose build api` and `docker compose up -d elasticsearch redis api frontend` with full env overrides. |
| Release | Not required unless publishing a benchmark or demo artifact. |

## Harness Delta

No Harness policy change is planned.

## Evidence

Planned. Add validation commands and output after implementation.
