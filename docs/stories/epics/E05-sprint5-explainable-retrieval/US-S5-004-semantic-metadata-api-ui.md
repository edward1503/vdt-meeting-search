# US-S5-004 Semantic Metadata API And UI Mode

## Status

implemented

## Lane

normal

## Product Contract

The search API and UI should expose semantic metadata search as an opt-in mode
that preserves the original query while searching with an effective content
query plus metadata filters.

## Relevant Product Docs

- `docs/sprint5/plan.md`
- `docs/sprint5/semantic-metadata-implementation-plan.md`

## Acceptance Criteria

- Standard HotpotQA and VimQA searches do not parse semantic metadata by
  default.
- Requests can opt in with `semantic_metadata=true`.
- The API response includes `query`, `effective_query`, `semantic_metadata`,
  and parsed-query debug data when parsing runs.
- Manual metadata filters override parsed metadata filters.
- `tv_hybrid` with metadata filters still routes to `tv_filtered_hybrid` and
  `tv_dense` still rejects metadata filters.
- The UI exposes Standard and Semantic Metadata modes and displays parsed chips
  when available.
- Result highlighting uses the effective query when semantic metadata mode is
  active.

## Design Notes

- Commands: no new runtime command.
- Queries: retrievers receive the effective query; support lookup and history
  preserve the original query.
- API: `SearchRequest.semantic_metadata` and response fields are added.
- Tables: no database schema changes.
- Domain rules: semantic parsing is opt-in and bounded to existing metadata.
- UI surfaces: `frontend/src/components/SearchView.tsx` search controls and
  result explanation area.

## Validation

| Layer | Expected proof |
| --- | --- |
| Unit | API execution-plan tests for opt-in parse, fallback, and manual override. |
| Integration | Existing metadata API regression suite and SearchView source-level tests. |
| E2E | Not required for this slice. |
| Platform | Frontend lint skipped unless Harness has frontend-lint capability. |
| Release | Included in Sprint 5 combined validation. |

## Harness Delta

The local Harness tool registry still lacks a `frontend-lint` capability, so
frontend lint/typecheck is skipped under the registry lookup rule.

## Evidence

- 2026-06-23: Red proof: `python -m pytest tests/test_semantic_metadata_api.py -q` failed because semantic metadata did not affect effective query or parsed filters. Green proof: `python -m pytest tests/test_semantic_metadata_api.py tests/test_api_es_config.py -q` -> 34 passed.
- 2026-06-23: Red proof: `python -m pytest tests/test_search_ui_metadata.py -q` failed before `semanticMetadata`, parsed chips, and effective-query highlighting existed. Green proof: `python -m pytest tests/test_search_ui_metadata.py tests/test_search_highlighting.py tests/test_frontend_dataset_state.py -q` -> 7 passed.
