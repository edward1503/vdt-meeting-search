# US-S5-008 Reranker RRF Ablation

## Status

planned

## Lane

normal

## Product Contract

The project can run a benchmark-only ablation comparing the current `tv_hybrid` RRF baseline with a configurable reranker method, while reporting candidate-depth diagnostics and avoiding runtime default changes.

## Relevant Product Docs

- `docs/sprint5/plan.md`
- `docs/sprint5/ranking-diagnostics-report.md`
- `docs/superpowers/specs/2026-06-28-reranker-rrf-ablation-design.md`

## Acceptance Criteria

- Benchmark runner accepts `tv_hybrid_rerank` without changing API/dashboard defaults.
- Benchmark config records `reranker_model`.
- Candidate diagnostics run on a top-100 `tv_hybrid` TREC artifact.
- Ablation report compares `tv_hybrid` and `tv_hybrid_rerank` on 200 queries and labels the result as a pilot, not a paper-comparable claim.
- If runtime or reranker model loading fails, the blocker is recorded without claiming ablation success.

## Design Notes

- Commands: `src.evaluation.benchmark_es`, `scripts/ranking_diagnostics.py`, and `scripts/reranker_rrf_ablation_report.py`.
- Queries: 5-query smoke first, then 200-query pilot.
- API: no API or dashboard default change.
- Tables: no database change.
- Domain rules: 200 queries can detect large effects but does not prove small reranker gains reliably.
- UI surfaces: none.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id <id> --unit 1 --integration 1 --e2e 0 --platform 0`.

| Layer | Expected proof |
| --- | --- |
| Unit | Reranker utility, benchmark dispatch, and report tests pass. |
| Integration | 5-query smoke writes benchmark JSON/TREC and report if runtime is available. |
| E2E | Not required because the dashboard default does not change. |
| Platform | 200-query pilot may run only when API, Elasticsearch, embedding service, and reranker model are available. |
| Release | Report states 200-query statistical caveat and artifact paths. |

## Harness Delta

No Harness policy changes expected.

## Evidence

- 2026-06-28: Implemented benchmark-only `tv_hybrid_rerank`,
  configurable `--reranker-model`, top-100 candidate diagnostics, and
  ablation report generation. Unit proof: `python -m pytest
  tests/test_reranker.py tests/test_benchmark_es.py
  tests/test_reranker_rrf_ablation_report.py tests/test_turbovec_retriever.py
  -q` -> 34 passed.
- 2026-06-28: Runtime preflight passed for API health, Elasticsearch,
  embedding service, and Docker services. Five-query smoke wrote artifacts
  under `evaluation/results/hotpotqa_full/reranker_ablation/` and
  `evaluation/runs/hotpotqa_full/reranker_ablation/`.
- 2026-06-28: 200-query pilot completed with candidate budget 100 and
  reranker model `cross-encoder/ms-marco-MiniLM-L-6-v2`. RRF `tv_hybrid`
  top-10: full_support@10=0.545, recall@10=0.750, MRR@10=0.8691,
  nDCG@10=0.7291, p50=631.8788ms, p95=2061.4370ms. Reranker:
  full_support@10=0.545, recall@10=0.755, MRR@10=0.9268, nDCG@10=0.7464,
  p50=963.9905ms, p95=1304.2816ms. Paired full-support movement:
  RRF-only=14, reranker-only=14, net=0. Candidate diagnostics at depth 100:
  candidate_recall=0.8325, missing_candidate=3, partial_candidate_support=61,
  candidate_ranked_low=27, success=109. Report:
  `docs/sprint5/reranker-rrf-ablation-report.md`.
