# US-S5-002 Ranking Diagnostics Before Reranker

## Status

implemented

## Lane

normal

## Product Contract

Before adding a reranker, the project should separate retrieval failures caused
by missing candidates from failures where relevant documents are present but not
ranked high enough.

## Relevant Product Docs

- `docs/sprint5/plan.md`
- `docs/sprint5/ranking-diagnostics-report.md`

## Acceptance Criteria

- A reusable diagnostics script can read HotpotQA support qrels and TREC run
  files.
- The diagnostics classify each method/query into interpretable buckets.
- The first-pass report compares existing `es_bm25`, `tv_dense`, `tv_hybrid`,
  and `tv_filtered_hybrid` runs.
- The report states whether the current evidence is enough to justify a
  reranker.

## Design Notes

- Commands: `scripts/ranking_diagnostics.py` reads existing artifacts only.
- Queries: no retrieval query execution in this slice.
- API: no API change.
- Tables: no database change.
- Domain rules: top-10 run artifacts cannot prove top-50/top-100 reranker
  readiness.
- UI surfaces: no UI change in this slice.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id <id> --unit 1 --integration 1 --e2e 0 --platform 0`.

| Layer | Expected proof |
| --- | --- |
| Unit | Toy qrels/TREC tests for bucket classification and CLI output. |
| Integration | Report generated from existing HotpotQA full-corpus TREC artifacts. |
| E2E | Not required for this diagnostics slice. |
| Platform | Not required for this diagnostics slice. |
| Release | Deeper top-50/top-100 runs are required before final reranker decision. |

## Harness Delta

No Harness policy changes. The story adds a reusable diagnostics command for
future reranker-readiness checks.

## Evidence

- 2026-06-22: Added `scripts/ranking_diagnostics.py` and tests in
  `tests/test_ranking_diagnostics.py`. Red proof: `python -m pytest
  tests/test_ranking_diagnostics.py -q` failed before the script existed, then
  failed again when the `partial_candidate_support` bucket was missing. Green
  proof: `python -m pytest tests/test_ranking_diagnostics.py -q` -> 2 passed.
- 2026-06-22: Generated `docs/sprint5/ranking-diagnostics-report.md` and
  `evaluation/results/hotpotqa_full/ranking_diagnostics/top10_diagnostics.json`
  from existing top-10 full-corpus HotpotQA runs. First-pass result: `tv_hybrid`
  remains best on full support@10 at 0.545, with 109/200 successes, 82 partial
  candidate-support cases, and 9 missing-candidate cases. Because the available
  TREC artifacts are only top-10, this does not yet justify adding a reranker;
  a deeper top-50/top-100 candidate run is the next required proof.
