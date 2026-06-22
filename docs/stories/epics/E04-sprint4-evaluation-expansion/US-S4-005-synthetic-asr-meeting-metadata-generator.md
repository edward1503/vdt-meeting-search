# US-S4-005 Synthetic Meeting Metadata Generator

## Status

implemented

## Lane

normal

## Product Contract

HotpotQA documents can be enriched with deterministic lightweight synthetic meeting metadata for demo and retrieval-filter experiments without changing the original content or treating the metadata as real HotpotQA truth. The generated document metadata is limited to `author`, `created_at`, and `modified_at`.

## Relevant Product Docs

- `docs/sprint4/plan.md`
- `docs/architecture/current-architecture.md`

## Acceptance Criteria

- Generator keeps existing HotpotQA content fields unchanged.
- Metadata is deterministic from `doc_id` or `numeric_id`.
- Each enriched row includes only `author`, `created_at`, and `modified_at` as generated metadata fields.
- `created_at` and `modified_at` are valid dates, and `modified_at` is not earlier than `created_at`.
- Artifact manifest documents the synthetic nature of the metadata.

## Design Notes

- Commands: likely metadata generation CLI over existing staging shards.
- Queries: no benchmark query changes in this story.
- API: no API changes in this story.
- Tables: no SQLite schema change.
- Domain rules: synthetic metadata is limited to author/date filtering and display experiments only.
- UI surfaces: no UI changes in generator story.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-005 --unit 1 --integration 0 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Determinism, limited-field schema, and date-order tests for metadata generation. |
| Integration | Optional small-shard generation smoke. |
| E2E | Not required. |
| Platform | Metadata artifact and manifest exist. |
| Release | Not required. |

## Harness Delta

No Harness policy change is planned.

## Evidence

- 2026-06-21: Added deterministic synthetic metadata artifact generation for `author`, `created_at`, and `modified_at` using 128 realistic synthetic display authors and a 35 percent modified-date rule. The generator writes separate metadata shards and preserves `content` plus `embedding_text` unchanged. Proof: `python -m pytest tests/test_synthetic_metadata.py -q` -> 7 passed. Smoke artifact: `artifacts/hotpotqa_full/metadata_smoke/manifest.json` with `docs_written=50000`, `files_written=1`, `synthetic=true`, and `author_count=128`. Full artifact: `artifacts/hotpotqa_full/metadata/manifest.json` with `docs_written=5233329`, `files_written=105`, `synthetic=true`, `author_count=128`, `modified_docs=1831684`, and `unchanged_docs=3401645`.
