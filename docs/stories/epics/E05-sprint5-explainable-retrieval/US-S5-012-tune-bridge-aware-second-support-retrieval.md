# US-S5-012 Tune Bridge-Aware Second-Support Retrieval

## Status

implemented

## Lane

normal

## Product Contract

The project can tune HotpotQA bridge-aware retrieval using benchmark evidence without changing ingestion, API defaults, or UI behavior.

## Relevant Product Docs

- `docs/sprint5/bridge-aware-second-support-report.md`
- `docs/sprint5/bridge-aware-tuning-report.md`

## Acceptance Criteria

- Run at least three 200-query `beir/hotpotqa/dev` tuning pilots for `tv_bridge_title_entities_rrf`.
- Compare quality against the `beam_size=3`, `max_bridge_terms=8` baseline from `US-S5-011`.
- Report `full_support_recall@10`, recall@10, nDCG@10, p95 latency, and QPS for each configuration.
- Recommend one operating point for the next HotpotQA experiment.
- Do not change default retrieval behavior.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S5-012 --unit 0 --integration 1 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Not required; no code changes expected. |
| Integration | Benchmark JSON artifacts generated for tuning configs. |
| E2E | Not required; no UI/API default path changes. |
| Platform | Report and run artifacts generated from local runtime. |
| Release | Not required. |

## Evidence

- 2026-06-29: Ran four 200-query `beir/hotpotqa/dev` tuning pilots for `tv_bridge_title_entities_rrf`.
- Artifacts: `evaluation/results/hotpotqa_full/bridge_title_entities_tuning/*.json`.
- TREC runs: `evaluation/runs/hotpotqa_full/bridge_title_entities_tuning/*/*.trec`.
- Summary: `evaluation/results/hotpotqa_full/bridge_title_entities_tuning/summary.json`.
- Diagnostics: `evaluation/results/hotpotqa_full/bridge_title_entities_tuning/tuning_diagnostics.json`.
- Recommended config: `beam_size=1`, `max_bridge_terms=6`.
- Result: `beam1_terms6` kept `full_support_recall@10=0.6200` while reducing p95 latency to `1224.9911 ms`, compared with `2670.3591 ms` for the `beam3_terms8` quality-first baseline.
