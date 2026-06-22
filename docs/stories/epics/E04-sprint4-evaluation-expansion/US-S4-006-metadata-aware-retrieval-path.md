# US-S4-006 Metadata-Aware Retrieval Path

## Status

implemented

## Lane

normal

## Product Contract

Search can filter and display lightweight synthetic meeting metadata through the Elasticsearch-backed retrieval path while leaving dense embeddings content-only in v1. Sprint 4 metadata filters are limited to `author`, `created_at`, and `modified_at`.

## Relevant Product Docs

- `docs/sprint4/plan.md`
- `docs/architecture/current-architecture.md`

## Acceptance Criteria

- Elasticsearch mapping indexes `author` as a keyword field and `created_at`/`modified_at` as date fields.
- Search supports filters for `author`, `created_at` range, and `modified_at` range.
- Metadata filters apply to `es_bm25` and the BM25 side of hybrid retrieval.
- Result payloads expose `author`, `created_at`, and `modified_at` for display/debugging.
- Dense `embedding_text` remains based on HotpotQA content, not synthetic metadata.
- Tests cover filter query construction and at least one API-level filtered search path.
- Dashboard controls for author/date metadata filters are included only if Sprint 4 scope is confirmed during review.

## Design Notes

- Commands: Elasticsearch index creation/ingest may need lightweight metadata-aware variants or flags.
- Queries: filters narrow candidate sets; qrels are unchanged.
- API: likely add optional filter fields to `/search` request.
- Tables: search history may need to record filters if API request shape changes.
- Domain rules: author/date metadata filter behavior is a demo/product feature, not a BEIR metric change.
- UI surfaces: optional filter controls and result metadata display.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-006 --unit 1 --integration 1 --e2e 1 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Author/date metadata mapping and filter query construction tests. |
| Integration | Elasticsearch filtered search smoke with synthetic metadata index. |
| E2E | Required only if dashboard controls are implemented. |
| Platform | Full or representative metadata index can be searched with filters. |
| Release | Not required. |

## Harness Delta

If v1 formally decides "metadata is filter/display only, not dense embedding input", consider recording a decision under `docs/decisions/`.

## Evidence

- 2026-06-21: Implemented metadata-aware retrieval path for synthetic `author`, `created_at`, and `modified_at` fields. Elasticsearch BM25 indexes optional metadata mappings and applies filters in filter context; BM25 ingest copies metadata when present; search hit payloads include metadata fields. TurboVec hybrid accepts metadata filters through the BM25 candidate path; `tv_hybrid` with metadata filters routes to `tv_filtered_hybrid`; `tv_dense` with metadata filters returns HTTP 400. Dashboard controls were intentionally not implemented in this MVP, so E2E remains 0.
- Unit/API proof: `python -m pytest tests/test_elasticsearch_retriever.py tests/test_es_hotpotqa_cli.py tests/test_turbovec_retriever.py tests/test_api_es_config.py -q` -> 55 passed, 3 warnings.
- Adjacent regression proof: `python -m pytest tests/test_api_cache.py tests/test_search_history.py -q` -> 2 passed, 3 warnings.
- Platform/integration smoke: created `hotpotqa_full_metadata_smoke_v1` with `--metadata`, ingested one metadata smoke shard with 50,000 docs, validated alias `hotpotqa_full_metadata_current` count 50,000, then searched `Anarchism` with author filter `Nguyen An`. Result included `doc_id=12`, `author=Nguyen An`, `created_at=2024-01-01`, `modified_at=2024-01-02`.
