# US-S5-005 Semantic Metadata Evaluation

## Status

implemented

## Lane

normal

## Product Contract

Semantic metadata search should have a repeatable evaluation design that
compares content-only natural-language queries, manual metadata filters, and
parsed metadata search against known document-level ground truth.

## Relevant Product Docs

- `docs/sprint5/plan.md`
- `docs/sprint5/semantic-metadata-search-report.md`

## Acceptance Criteria

- A helper can build semantic metadata queries from metadata-enriched document
  rows.
- Each generated query stores the content query, metadata filters, and relevant
  document ids.
- A comparison helper reports recall for `content_only_original`,
  `manual_filter`, and `parsed_metadata` runs.
- A Sprint 5 report states the scope and limitation of the smoke artifact.

## Design Notes

- Commands: `scripts/semantic_metadata_eval.py` writes smoke artifacts and a
  report.
- Queries: smoke queries use `find documents about <title> by <author> before
  <created_at>`.
- API: no API call is required for the smoke helper.
- Tables: no database change.
- Domain rules: smoke evidence is protocol proof, not a live full-corpus
  benchmark claim.
- UI surfaces: no UI change in this slice.

## Validation

| Layer | Expected proof |
| --- | --- |
| Unit | Toy-row tests for query generation and recall comparison. |
| Integration | Smoke artifacts under `evaluation/results/hotpotqa_full/semantic_metadata/`. |
| E2E | Not required. |
| Platform | Not required. |
| Release | Included in Sprint 5 combined validation. |

## Harness Delta

No Harness policy changes.

## Evidence

- 2026-06-23: Red proof: `python -m pytest tests/test_semantic_metadata_eval.py -q` failed before `scripts.semantic_metadata_eval` existed. Green proof: `python -m pytest tests/test_semantic_metadata_eval.py -q` -> 2 passed.
- 2026-06-23: Ran `python scripts/semantic_metadata_eval.py --limit 2 --top-k 1`, generating `evaluation/results/hotpotqa_full/semantic_metadata/semantic_queries_smoke.json`, `evaluation/results/hotpotqa_full/semantic_metadata/summary_smoke.json`, and `docs/sprint5/semantic-metadata-search-report.md`.
