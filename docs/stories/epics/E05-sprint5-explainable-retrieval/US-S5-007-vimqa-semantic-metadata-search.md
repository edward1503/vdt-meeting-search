# US-S5-007 VimQA Semantic Metadata Search

## Status

implemented

## Lane

normal

## Product Contract

VimQA semantic metadata search should use the same opt-in contract as HotpotQA:
when `semantic_metadata=true`, the API parses explicit natural-language
metadata queries into an effective content query plus filters over `author`,
`created_at`, and `modified_at`.

The feature reuses the existing metadata-aware Elasticsearch retrieval path and
does not embed metadata text into vectors.

## Relevant Product Docs

- `docs/sprint5/plan.md`
- `docs/sprint5/semantic-metadata-implementation-plan.md`
- `docs/sprint5/vimqa-semantic-metadata-search-report.md`
- `docs/stories/epics/E05-sprint5-explainable-retrieval/US-S5-006-vimqa-synthetic-metadata.md`

## Acceptance Criteria

- The parser recognizes Vietnamese semantic metadata frames such as
  `tài liệu về <topic>` and `văn bản về <topic>`.
- Vietnamese author cues `của` and `bởi` map known synthetic authors to the
  `author` filter.
- Vietnamese date cues `trước`, `sau`, `chỉnh sửa trước`, and `chỉnh sửa sau`
  map to created/modified date range filters.
- Slash dates such as `31/01/2024` normalize to ISO `2024-01-31`.
- VimQA dataset-scoped search accepts parsed metadata filters through the same
  `semantic_metadata=true` API contract used by HotpotQA.
- The report describes the algorithm, data flow, validation, and limitations.

## Design Notes

- Commands: no new runtime command.
- Queries: parser remains deterministic and opt-in.
- API: VimQA profile now advertises metadata filter support.
- Tables: no database schema changes.
- Domain rules: metadata remains structured filter data; `embedding_text` stays
  content-only.
- UI surfaces: existing Semantic Metadata mode and parsed chips are reused.

## Validation

| Layer | Expected proof |
| --- | --- |
| Unit | Parser tests for Vietnamese semantic metadata query forms. |
| Integration | Dataset-scoped VimQA API test proving effective query and metadata filters. |
| E2E | Not required for this slice. |
| Platform | Metadata-enriched VimQA artifact exists from `US-S5-006`; live index smoke remains a next step. |
| Release | Included in Sprint 5 focused validation. |

## Harness Delta

Added a distinct story so VimQA runtime semantic metadata behavior is tracked
separately from the offline metadata artifact generation.

## Evidence

- 2026-06-24: Red proof: `python -m pytest tests/test_metadata_query_parser.py tests/test_semantic_metadata_api.py -q` failed with three expected failures before Vietnamese parsing and VimQA execution-plan support existed.
- 2026-06-24: Green proof: `python -m pytest tests/test_metadata_query_parser.py tests/test_semantic_metadata_api.py -q` => 10 passed, 3 warnings.
