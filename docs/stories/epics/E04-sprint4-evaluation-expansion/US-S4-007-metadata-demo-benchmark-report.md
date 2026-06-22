# US-S4-007 Metadata Demo Benchmark Report

## Status

implemented

## Lane

normal

## Product Contract

Metadata-aware retrieval has a separate demo report that shows how lightweight synthetic author/date filters narrow search results without presenting the experiment as a BEIR or HotpotQA benchmark claim.

## Relevant Product Docs

- `docs/sprint4/plan.md`
- `docs/sprint4/metadata-demo-report.md`

## Acceptance Criteria

- Report includes `content-only`, `metadata-filtered`, and `metadata + content hybrid` scenarios.
- Report measures candidate/result narrowing before and after filters.
- Report includes latency observations for filtered and unfiltered paths.
- Report includes at least a few author/date-filtered search scenarios.
- Report states that metadata is synthetic and should not be treated as true HotpotQA metadata.
- Report separates metadata-demo findings from paraphrase robustness metrics.

## Design Notes

- Commands: likely benchmark/report script over curated filter scenarios.
- Queries: scenarios should exercise author/date filters, not BEIR leaderboard evaluation.
- API: uses metadata filter support from `US-S4-006`.
- Tables: no database schema changes unless search history stores filter payloads.
- Domain rules: narrowing is useful only if it is explicit and inspectable.
- UI surfaces: screenshots or dashboard examples optional if controls exist.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-007 --unit 0 --integration 1 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Covered by metadata retrieval story. |
| Integration | Scenario run artifacts or report tables. |
| E2E | Optional dashboard smoke if UI controls exist. |
| Platform | Report path and scenario artifacts exist. |
| Release | Not required. |

## Harness Delta

No Harness policy change is planned.

## Evidence

- 2026-06-21: Added metadata demo scenario artifact generation with `scripts/metadata_demo_scenarios.py` and focused tests in `tests/test_metadata_demo_scenarios.py`. Red/green proof: the focused test first failed because `scripts.metadata_demo_scenarios` did not exist, then passed after implementation: `python -m pytest tests/test_metadata_demo_scenarios.py -q` -> 2 passed.
- 2026-06-21: Generated full-corpus metadata scenario evidence at `evaluation/results/hotpotqa_full/metadata/scenario_summary.json` from `artifacts/hotpotqa_full/metadata`. The artifact counted 5,233,329 docs across 5 scenarios. Key narrowing results: author `Nguyen An` -> 40,886 docs / 99.2187% narrowing; created January 2024 -> 222,239 docs / 95.7534% narrowing; modified 2024-01-10..2024-01-20 -> 60,589 docs / 98.8422% narrowing; metadata + content hybrid prefilter `author=Nguyen An` and January 2024 -> 1,793 docs / 99.9657% narrowing.
- 2026-06-21: Wrote `docs/sprint4/metadata-demo-report.md` with content-only, metadata-filtered, and metadata + content hybrid scenarios, offline latency/count observations, sample result metadata, synthetic-data caveats, and separation from BEIR/HotpotQA benchmark claims.
