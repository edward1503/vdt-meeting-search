# US-S3-014 Docker TurboVec Runtime

## Status

implemented

## Lane

normal

## Product Contract

The existing Docker system should run the TurboVec dense retrieval methods (`tv_dense`, `tv_hybrid`, and `tv_filtered_hybrid`) end to end from the current dashboard. The API container loads a mounted `.tvim` artifact directly inside the container. Elasticsearch remains the BM25 and document hydration backend. The embedding model stays outside the API image through the existing `EMBEDDING_SERVICE_URL` path, so the migration does not pull PyTorch or SentenceTransformers into the API Docker image.

The frontend must reflect the runtime that actually exists. The search method selector should expose TurboVec methods, the default selection should match the backend default, and the status page should stop hard-coding a 5,090-document corpus when the backend is running a full 5.23M document profile.

For the demo profile, Docker should default to the full runtime: `hotpotqa_full_bm25_current` for Elasticsearch BM25 and `/app/artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim` for TurboVec. Nano remains available only through explicit environment overrides.

## Relevant Product Docs

- `README.md`
- `docs/architecture/current-architecture.md`
- `docs/sprint3/sprint3-report.md`

## Acceptance Criteria

- `requirements-api.txt` installs the minimum dependencies needed for TurboVec search in the API container: `numpy` and `turbovec`.
- `TurboVecHybridRetriever.from_paths()` uses `EMBEDDING_SERVICE_URL` when configured and does not import `sentence_transformers` in that path.
- Docker Compose defaults the API container to `ELASTICSEARCH_INDEX=hotpotqa_full_bm25_current` and `TURBOVEC_INDEX_PATH=/app/artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim`, while preserving env override support for nano/100k profiles.
- A full demo runs without manually selecting nano-era defaults.
- `/stats` shows enough runtime information to confirm the active Elasticsearch index, TurboVec artifact path, and embedding service URL.
- The Docker frontend reads `/stats`, defaults the search selector to the backend `default_search_method`, shows only methods reported by the backend when available, and can run `tv_hybrid` through the existing `/api/search` proxy.
- The status view displays backend-provided corpus/runtime details and TurboVec dataflow instead of hard-coded nano corpus or ES-dense language.

## Design Notes

- Commands: no new user command is required for the full demo path; existing Docker Compose commands keep working, and env overrides can still select smaller profiles.
- Queries: `tv_dense`, `tv_hybrid`, and `tv_filtered_hybrid` are the migration target; legacy ES dense/hybrid modes are not exposed by the Docker API or frontend.
- API: no search request or response shape change is required.
- Tables: no SQLite or Elasticsearch schema migration.
- Domain rules: do not mix ES nano with TurboVec full for serious demos; use matching runtime profiles.
- UI surfaces: the search method selector, default method, status parameters, corpus count, and pipeline dataflow must align with `/stats` and the Docker runtime.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S3-014 --unit 1 --integration 1 --e2e 0 --platform 0`.

| Layer | Expected proof |
| --- | --- |
| Unit | `python -m pytest tests/test_turbovec_retriever.py tests/test_api_es_config.py -q`; `npm run lint` in `frontend/` |
| Integration | Docker build of the API image plus API `/stats` and `/search` smoke checks. |
| E2E | Frontend dashboard search using visible `tv_hybrid` against the Docker API. |
| Platform | `docker compose build api` and `docker compose up -d elasticsearch redis api frontend` with full env overrides. |
| Release | Not required unless publishing a benchmark or demo artifact. |

## Harness Delta

No Harness policy change is planned.

## Evidence

- `python -m pytest tests/test_api_es_config.py tests/test_turbovec_retriever.py -q`: 14 passed, 3 warnings.
- `cd frontend; npm run lint`: passed (`tsc --noEmit`).
- `docker compose build api --progress plain`: passed; build context reduced to 13.90kB after excluding mounted data artifacts from the image context; `vdt-meeting-search-api:latest` built with `numpy==2.3.5` and `turbovec==0.8.0`.
- `Invoke-RestMethod http://localhost:9200/hotpotqa_full_bm25_current/_count`: count `5233329`.
- `Invoke-RestMethod http://localhost:8001/stats`: returned `index=hotpotqa_full_bm25_current`, `default_search_method=tv_hybrid`, `runtime_profile=full`, `corpus_doc_count=5233329`, `turbovec_index_path=/app/artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim`, and `embedding_service_url=http://host.docker.internal:8010/embed`.
- Docker API `POST /search` with `method=tv_dense`, `top_k=5`: returned 5 dense results from TurboVec, including `Ian Hunter (actor)` rank 1; no `sentence_transformers` import error.
- Docker API `POST /search` with `method=tv_hybrid`, `top_k=5`: returned fused `bm25+dense` results in about 1415ms after TurboVec load, with latency breakdown including `embed`, `turbovec`, `hydrate`, `bm25`, and `fusion`.
- Playwright CLI against `http://localhost:3001`: Status page displayed `FULL`, `5,233,329 docs`, full TurboVec index path, and TurboVec dataflow; Search page defaulted to `TurboVec Hybrid RRF (Full Dense + BM25)`, exposed `tv_dense`, `tv_filtered_hybrid`, and `tv_hybrid`, and returned 10 ranked frontend results with `Method: bm25+dense`.
- Cleanup: `/stats` now exposes only `es_bm25`, `tv_dense`, `tv_filtered_hybrid`, and `tv_hybrid`; `/search` rejects `es_dense`, `es_hybrid`, and `es_iterative_hybrid` with HTTP 400; frontend controls no longer submit those legacy methods.
- Runtime cleanup smoke: Docker API `/stats` returned only the four supported methods above; `POST /search` with `method=es_hybrid` returned HTTP 400; fresh `tv_hybrid` query `Which author wrote The Trial novel?` returned rank 1 `The Trial` with `source=bm25+dense`, `cache_hit=false`, and latency about 1353ms.
