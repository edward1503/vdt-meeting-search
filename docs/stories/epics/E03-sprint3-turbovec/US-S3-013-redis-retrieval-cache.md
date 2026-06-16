# US-S3-013 Redis Retrieval Cache Hardening

## Status

planned

## Lane

normal

## Product Contract

Repeated search requests should return consistent results faster without serving stale results after retrieval tuning, index, model, or TurboVec artifact changes. Redis remains an optional optimization: if Redis is unavailable, search must still execute directly through Elasticsearch, TurboVec, and the embedding path.

This story does not change ranking semantics. It only improves cache safety and reuse for the existing `/search` path.

## Relevant Product Docs

- `docs/architecture/current-architecture.md`
- `docs/sprint3/sprint3-report.md`
- `README.md`

## Acceptance Criteria

- Final `/search` response cache keys include normalized query text, index, method, top-k, and retrieval parameters that affect ranking.
- Query embedding results can be cached by normalized query, embedding model, and embedding dimension for both Elasticsearch dense paths and TurboVec dense paths.
- `tv_filtered_hybrid` can cache BM25 candidate hits used to build the TurboVec allowlist.
- Redis failures never fail a search request; they produce cache misses or skipped writes.
- Tests prove cache key invalidation across tuning parameters and cache fallback behavior.
- API responses continue to include `latency_breakdown_ms` for TurboVec methods.

## Design Notes

- Commands: no new user command is added.
- Queries: `/search` remains the only user-facing search entrypoint affected by this story.
- API: request and response shapes remain compatible; optional cache fields may be added only if frontend tolerates absence.
- Tables: no database schema changes.
- Domain rules: cache correctness is scoped by retrieval signature, not only query text.
- UI surfaces: no required frontend change; future UI may display cache status or timing breakdown.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S3-013 --unit 1 --integration 1 --e2e 0 --platform 0`.

| Layer | Expected proof |
| --- | --- |
| Unit | `python -m pytest tests/test_api_cache.py tests/test_turbovec_retriever.py tests/test_elasticsearch_retriever.py -q` |
| Integration | `python -m pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q` |
| E2E | Manual dashboard search with repeated `tv_hybrid` and `tv_filtered_hybrid` queries after Docker stack is running. |
| Platform | Optional Docker smoke: `./scripts/docker-dev.ps1`, then `GET /api/stats` and repeated `POST /api/search`. |
| Release | Benchmark comparison before and after cache work only if claiming performance numbers. |

## Harness Delta

No Harness policy change is planned. The stale split between `docs/ARCHITECTURE.md` and `docs/architecture/current-architecture.md` remains known friction from the preceding analysis.

## Evidence

Planned. Add test commands and timing evidence after implementation.
