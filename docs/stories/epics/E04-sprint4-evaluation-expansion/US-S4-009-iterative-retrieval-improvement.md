# US-S4-009 Iterative Retrieval Improvement

## Status

implemented

## Lane

normal

## Product Contract

Sprint 4 improves HotpotQA retrieval quality by measuring evidence-chain recall and adding a TurboVec-backed two-hop Bridge-RRF retrieval method. The existing one-hop methods remain unchanged, and the new method must report quality and latency tradeoffs before it is considered for any default path.

## Relevant Product Docs

- `docs/sprint4/plan.md`
- `docs/sprint4/retrieval-improvement-report.md`
- `docs/architecture/current-architecture.md`
- `docs/sprint3/sprint3-report.md`

## Acceptance Criteria

- Evaluation reports `full_support_recall@2`, `full_support_recall@5`, and `full_support_recall@10`.
- Chain-aware metrics include `chain_recall@1`, `chain_recall@5`, and `chain_mrr` when chain output exists.
- Existing iterative Elasticsearch methods are benchmarked or explicitly ruled out with a documented blocker.
- A new method `tv_two_hop_bridge_rrf` runs first-hop `tv_hybrid`, builds bridge queries from first-hop titles/terms, runs second-hop `tv_hybrid`, creates candidate chains, reranks them, and returns flattened ranked documents.
- Hyperparameters include `hop1_top_k`, `hop2_top_k`, `beam_size`, `max_bridge_terms`, `candidate_k`, and `rrf_k`.
- The benchmark compares `tv_two_hop_bridge_rrf` against `tv_hybrid` on a smoke set and the Sprint 4 pilot set when runtime allows.
- The report states whether the new method improves `full_support_recall@10` by at least `+0.05` while keeping p95 latency within `2.5x` of `tv_hybrid`.
- The dashboard/default search method is not changed unless benchmark evidence supports it.

## Design Notes

- Commands: extend `python -m src.evaluation.benchmark_es` or add a focused benchmark wrapper for Bridge-RRF runs.
- Queries: use the same HotpotQA dev source query set as Sprint 3/Sprint 4 pilot runs.
- API: optional; benchmark path is required first.
- Tables: no SQLite schema changes.
- Domain rules: HotpotQA qrels/supporting docs are the ground truth; Bridge-RRF improves candidate evidence retrieval, not ground-truth generation.
- UI surfaces: no UI changes required.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-009 --unit 1 --integration 1 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Chain metric tests, bridge query tests, and chain reranking tests. |
| Integration | Benchmark smoke comparing `tv_two_hop_bridge_rrf` against `tv_hybrid`. |
| E2E | Not required unless API/dashboard exposure is added. |
| Platform | Retrieval improvement report with commands, artifacts, quality metrics, and latency. |
| Release | Not required. |

## Harness Delta

Add this story to the durable Harness matrix as the Sprint 4 retrieval-improvement workstream.

## Evidence

Implemented.

Implemented changes:

- Chain metadata support on `SearchHit`.
- `full_support_recall@2`, `full_support_recall@5`, and
  `full_support_recall@10` metric output.
- Chain metrics: `chain_recall@1`, `chain_recall@5`, and `chain_mrr` when
  chain output exists.
- Benchmark-only `tv_two_hop_bridge_rrf` method in `TurboVecHybridRetriever`.
- Benchmark dispatcher support for `tv_two_hop_bridge_rrf`, `beam_size`, and
  `max_bridge_terms`.

Unit proof:

```powershell
python -m pytest tests/test_metrics.py tests/test_turbovec_retriever.py tests/test_benchmark_es.py -q
```

Result: 19 passed.

Report: `docs/sprint4/retrieval-improvement-report.md`.

Runtime preflight:

- Elasticsearch `http://localhost:9200`: ready, cluster green.
- `hotpotqa_full_bm25_current`: 5,233,329 documents.
- Embedding service `http://localhost:8010/embed`: ready, dimension 384.
- TurboVec artifact exists at
  `artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim`.

Integration smoke and pilot proof:

- 50-query smoke artifact:
  `evaluation/results/hotpotqa_full/bridge_rrf/bridge_rrf_smoke_50.json`.
- 200-query pilot artifact:
  `evaluation/results/hotpotqa_full/bridge_rrf/bridge_rrf_pilot_200.json`.
- TREC run files under `evaluation/runs/hotpotqa_full/bridge_rrf/` for
  `tv_hybrid` and `tv_two_hop_bridge_rrf`.

200-query pilot result with `candidate_k=50`, `num_candidates=50`, `rrf_k=30`,
`first_hop_k=3`, `second_hop_k=5`, `beam_size=2`, and `max_bridge_terms=6`:

| Method | full_support@10 | p95 ms | QPS |
| --- | ---: | ---: | ---: |
| `tv_hybrid` | 0.535 | 2080.4528 | 0.8313 |
| `tv_two_hop_bridge_rrf` | 0.520 | 2832.7420 | 0.5281 |

Existing Elasticsearch iterative methods were ruled out for the active full
corpus because `hotpotqa_full_bm25_current` is BM25-only and lacks the
`embedding` dense vector field required by the ES hybrid/dense iterative path.

Decision: do not change the dashboard/default method. `tv_two_hop_bridge_rrf`
did not improve `full_support_recall@10` over `tv_hybrid`; it stayed within the
latency guardrail but failed the quality threshold.
