# US-S5-014 HotpotQA Full Test Benchmark

## Status

implemented

## Lane

normal

## Product Contract

The project has a durable record for the full `beir/hotpotqa/test` retrieval benchmark, and presentation/report material uses the full-test numbers instead of treating the 200-query dev pilot as the final HotpotQA result.

## Relevant Product Docs

- `docs/sprint5/hotpotqa-test-benchmark-paper-comparison.md`
- `REPORT.md`
- `PRESENTATION.md`
- `submission/bao-cao-vdt-2026.md`

## Acceptance Criteria

- Harness matrix includes a story for the full 7,405-query HotpotQA test benchmark.
- Report/presentation wording says the benchmark is retrieval evidence coverage, not answer EM/F1 or supporting-fact F1.
- Submission report uses full-test `tv_hybrid` and `tv_bridge_title_entities_rrf` results as the main HotpotQA result.
- Word submission files are regenerated from the updated Markdown source.

## Design Notes

- Full-test source artifacts:
  - `evaluation/results/hotpotqa_full/test_full/tv_hybrid_test_full.json`
  - `evaluation/results/hotpotqa_full/test_full/tv_bridge_title_entities_rrf_beam1_terms6_test_full.json`
- Main presentation claim: bridge-aware retrieval improves `full_support@10` from `0.5175` to `0.6008` on 7,405 test queries.
- Runtime caveat: `tv_hybrid` remains the better interactive default because p95 is lower and MRR is higher.

## Validation

| Layer | Expected proof |
| --- | --- |
| Unit | Artifact metrics readback from the two full-test JSON files. |
| Integration | Updated report files mention `0.6008`, `0.5175`, and `7,405`. |
| E2E | Regenerated Word report contains the updated full-test table. |
| Platform | Not required. |
| Release | Not required. |

## Harness Delta

Added this story because the Harness matrix previously had dev pilot/tuning evidence but no explicit full-test benchmark row.

## Evidence

- `tv_hybrid_test_full.json`: 7,405 queries, `full_support_recall@10=0.5175`, `recall@10=0.7305`, `mrr@10=0.8413`, `ndcg@10=0.7001`, `p95=760.9212 ms`.
- `tv_bridge_title_entities_rrf_beam1_terms6_test_full.json`: 7,405 queries, `full_support_recall@10=0.6008`, `recall@10=0.7585`, `mrr@10=0.8251`, `ndcg@10=0.7120`, `p95=1598.3422 ms`.
- `docs/sprint5/hotpotqa-test-benchmark-paper-comparison.md` documents safe external-comparison wording.
