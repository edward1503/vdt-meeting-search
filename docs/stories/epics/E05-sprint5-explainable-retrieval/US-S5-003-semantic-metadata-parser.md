# US-S5-003 Semantic Metadata Parser

## Status

implemented

## Lane

normal

## Product Contract

Semantic metadata search should parse explicit natural-language document-search
queries into a content query plus filters over the existing synthetic HotpotQA
metadata fields: `author`, `created_at`, and `modified_at`.

## Relevant Product Docs

- `docs/sprint5/plan.md`
- `docs/sprint5/semantic-metadata-implementation-plan.md`

## Acceptance Criteria

- The parser recognizes explicit `documents about` or `documents related to`
  query frames.
- Known synthetic authors become `author` filters.
- Created/modified before/after phrases become ISO date range filters.
- Original HotpotQA questions such as `written by ... what nationality?` are
  not parsed as metadata search queries.
- Unknown authors are warned about and are not applied as hard filters.

## Design Notes

- Commands: no runtime command changes.
- Queries: parser is deterministic and rule-based.
- API: parser output feeds the later API execution-plan slice.
- Tables: no database changes.
- Domain rules: no metadata field is added and metadata text is not embedded.
- UI surfaces: parser chips are displayed by `US-S5-004`.

## Validation

| Layer | Expected proof |
| --- | --- |
| Unit | Parser tests for author/date extraction, HotpotQA false-positive protection, and unknown-author warnings. |
| Integration | Covered by API execution-plan tests in `US-S5-004`. |
| E2E | Not required for parser-only slice. |
| Platform | Not required. |
| Release | Included in Sprint 5 combined validation. |

## Harness Delta

No Harness policy changes.

## Evidence

- 2026-06-23: Red proof: `python -m pytest tests/test_metadata_query_parser.py -q` failed before `src.retrieval.metadata_query_parser` existed. Green proof: `python -m pytest tests/test_metadata_query_parser.py -q` -> 4 passed.
