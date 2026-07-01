# US-S5-011 Bridge-Aware Second-Support Retrieval

## Status

implemented

## Lane

normal

## Product Contract

The project can benchmark a HotpotQA retrieval ablation that targets missing second support documents without changing the default retrieval method.

## Relevant Product Docs

- `docs/sprint5/title-aware-bm25-ablation-report.md`
- `docs/sprint5/multihop-retrieval-methods.md`
- `docs/sprint5/bridge-aware-second-support-report.md`

## Acceptance Criteria

- Add a benchmark-only method named `tv_bridge_title_entities_rrf`.
- The method uses first-hop `tv_hybrid` candidates and builds second-hop bridge queries from title, entity-like spans, and lead-sentence terms.
- The benchmark runner dispatches `tv_bridge_title_entities_rrf` without changing existing defaults.
- A 200-query `beir/hotpotqa/dev` pilot compares the method against `tv_hybrid` and existing `tv_two_hop_bridge_rrf`.
- The report states whether the method improves `full_support_recall@10`, recall@10, nDCG@10, and latency.

## Design Notes

- This story improves candidate generation, not ingestion.
- The method should stay benchmark-only unless the pilot materially improves `full_support_recall@10`.
- Query expansion must be deterministic and cheap: no LLM, no parser service, no new persistent index.
- Default API/UI behavior is unchanged.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S5-011 --unit 1 --integration 1 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Focused pytest for bridge query extraction, retriever dispatch, and benchmark dispatch. |
| Integration | 200-query HotpotQA benchmark artifact generated. |
| E2E | Not required; no UI/API default path changes. |
| Platform | Benchmark report and run artifacts generated from local runtime. |
| Release | Not required. |

## Harness Delta

No Harness policy changes expected.

## Evidence

- 2026-06-29: Added benchmark-only method `tv_bridge_title_entities_rrf`.
- Red/green proof: `python -m pytest tests/test_turbovec_retriever.py -q` failed before `_build_title_entity_bridge_query` and `search_bridge_title_entities_rrf` existed; final run -> 14 passed.
- Red/green proof: `python -m pytest tests/test_benchmark_es.py -q` failed before benchmark dispatch supported `tv_bridge_title_entities_rrf`; final run -> 16 passed.
- Focused proof: `python -m pytest tests/test_turbovec_retriever.py tests/test_benchmark_es.py -q` -> 30 passed, with the existing `pytest_asyncio` deprecation warning.
- Benchmark artifact: `evaluation/results/hotpotqa_full/bridge_title_entities/bridge_title_entities_200.json`.
- Run files: `evaluation/runs/hotpotqa_full/bridge_title_entities/*.trec`.
- Diagnostics: `evaluation/results/hotpotqa_full/bridge_title_entities/second_support_diagnostics.json`.
- Result: `tv_bridge_title_entities_rrf` reached `full_support_recall@10=0.620`, improving over `tv_hybrid=0.545` and `tv_two_hop_bridge_rrf=0.560` on the same 200-query pilot.
