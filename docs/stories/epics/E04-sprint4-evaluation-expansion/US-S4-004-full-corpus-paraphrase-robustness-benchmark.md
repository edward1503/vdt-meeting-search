# US-S4-004 Full-Corpus Paraphrase Robustness Benchmark

## Status

implemented

## Lane

normal

## Product Contract

The benchmark runner can compare original HotpotQA queries with accepted natural paraphrase variants on the full-corpus retrieval stack, reporting quality and latency deltas for BM25, TurboVec dense, and TurboVec hybrid retrieval.

## Relevant Product Docs

- `docs/sprint4/plan.md`
- `docs/sprint4/paraphrase-robustness-report.md`
- `docs/architecture/current-architecture.md`
- `docs/sprint3/sprint3-report.md`

## Acceptance Criteria

- Original 200-query benchmark is run with the same source query ids used for paraphrase export.
- `natural_mild` and `natural_strong` variants are benchmarked separately.
- Primary methods are `es_bm25`, `tv_dense`, and `tv_hybrid`.
- `tv_filtered_hybrid` is optional and only included if time and runtime budget allow.
- Report includes `recall@10`, `ndcg@10`, `mrr@10`, `full_support_recall@10`, and p95 latency.
- Report includes absolute deltas from original query performance.
- Report states rejected paraphrase counts and why they were rejected.
- Report clearly says this is a 200-query project-progress pilot, not a paper-comparable BEIR claim.

## Design Notes

- Commands: reuse `python -m src.evaluation.benchmark_es` with query/qrels files after validation.
- Queries: variant query ids must map to source qrels.
- API: no API changes required.
- Tables: no database schema changes.
- Domain rules: do not compare synthetic paraphrase results as if they were a new BEIR split.
- UI surfaces: benchmark dashboard update is optional; markdown report is required.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-004 --unit 0 --integration 1 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Covered by export/validator stories. |
| Integration | Benchmark JSON and TREC outputs for original, mild, and strong query sets. |
| E2E | Not required unless dashboard benchmark display changes. |
| Platform | Full-corpus benchmark commands complete or the blocker is documented with partial artifacts. |
| Release | Report reviewed before any external claim. |

## Harness Delta

No Harness policy change is planned.

## Evidence

- Final 200-query benchmark completed on 2026-06-20 using `artifacts/hotpotqa_full/paraphrase/validated/original_200.tsv`, `mild_200.tsv`, `strong_200.tsv`, and `lexical_strong_200.tsv`.
- Methods run: `es_bm25`, `tv_dense`, `tv_hybrid`, and `tv_filtered_hybrid`.
- Output summary: `evaluation/results/hotpotqa_full/paraphrase_final/summary.json`.
- Benchmark JSON outputs: `original_200.json`, `mild_200.json`, `strong_200.json`, and `lexical_strong_200.json` under `evaluation/results/hotpotqa_full/paraphrase_final/`.
- Original 200 full_support_recall@10: `es_bm25=0.365`, `tv_dense=0.515`, `tv_hybrid=0.535`, `tv_filtered_hybrid=0.430`.
- Mild 200 full_support_recall@10 deltas vs original: `es_bm25=+0.000`, `tv_dense=+0.000`, `tv_hybrid=-0.020`, `tv_filtered_hybrid=+0.005`.
- Strong 200 full_support_recall@10 deltas vs original: `es_bm25=+0.010`, `tv_dense=+0.000`, `tv_hybrid=-0.020`, `tv_filtered_hybrid=+0.010`.
- Lexical-strong 200 full_support_recall@10 deltas vs original: `es_bm25=-0.025`, `tv_dense=-0.020`, `tv_hybrid=-0.055`, `tv_filtered_hybrid=-0.035`.
- Follow-up lexical diversity audit completed after review: `natural_mild` median content-change is `0.0976` and 44.5% add no new content terms; `natural_strong` median content-change is `0.2727` and 11.5% add no new content terms; `lexical_strong` median content-change is `0.5000` with 0 rows adding no new content terms. Report now scopes mild/strong as syntax/reordering paraphrase and `lexical_strong_200` as the lexical-substitution stress test.
- Report now includes full-support decay and relative-decay charts under `docs/sprint4/assets/`.
- This is a 200-query project-progress pilot on `beir/hotpotqa/dev`; it is not a paper-comparable BEIR/HotpotQA leaderboard claim.

- Report written: `docs/sprint4/paraphrase-robustness-report.md`.
