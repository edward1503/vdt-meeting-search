# US-S5-001 Highlight Query Terms In Retrieval Results

## Status

implemented

## Lane

normal

## Product Contract

Search result cards should visually highlight query-relevant content terms in
the returned document title and snippet so reviewers can see why a result is
related to the query.

## Relevant Product Docs

- `docs/sprint5/plan.md`

## Acceptance Criteria

- Query terms are derived from the submitted query and ignore common English
  stopwords.
- Result titles and text snippets render matching terms with visible highlight
  styling.
- Highlighting preserves the original result text and does not use raw HTML
  injection.

## Design Notes

- Commands: no runtime command changes.
- Queries: existing dataset-scoped search requests are unchanged.
- API: no API contract change in this slice.
- Tables: no database changes.
- Domain rules: lexical highlighting only; semantic metadata explanation chips
  remain a later Sprint 5 slice.
- UI surfaces: `frontend/src/components/SearchView.tsx` result cards.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id <id> --unit 1 --integration 1 --e2e 0 --platform 0`.

| Layer | Expected proof |
| --- | --- |
| Unit | Highlight helper test for stopword filtering and text segmentation. |
| Integration | SearchView source-level regression tests for rendering highlighted result text. |
| E2E | Not required for this first slice. |
| Platform | Not required for this first slice. |
| Release | Frontend lint should be run when a frontend lint capability is registered. |

## Harness Delta

The local tool registry does not currently expose a `frontend-lint` or `node`
capability, so final `npm run lint` verification is skipped under the Harness
tool lookup rule.

## Evidence

- 2026-06-22: Added `frontend/src/lib/highlight.ts` and wired SearchView result
  titles/snippets through a safe React `<mark>` renderer. Red proof:
  `python -m pytest tests/test_search_highlighting.py -q` failed before the
  helper/UI integration existed. Green proof: `python -m pytest
  tests/test_search_highlighting.py tests/test_search_ui_metadata.py
  tests/test_frontend_dataset_state.py -q` -> 6 passed.
