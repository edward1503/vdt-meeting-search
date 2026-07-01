# US-S5-010 Title-Aware BM25 Ablation

## Status

implemented

## Lane

normal

## Product Contract

The project can build and benchmark a title-aware BM25 HotpotQA index as a controlled ablation against the existing full-corpus BM25 baseline.

## Relevant Product Docs

- `docs/data/hotpotqa/hotpotqa_document_strategy_eda_report.md`
- `docs/sprint5/title-aware-bm25-ablation-report.md`

## Acceptance Criteria

- Title-aware BM25 indexing adds `title_exact`, `lead_sentence`, and `title_repeat_content` fields without modifying the original staging artifact.
- Benchmark method `es_bm25_title` runs through the existing benchmark runner.
- A 200-query `beir/hotpotqa/dev` pilot compares title-aware BM25 against the existing BM25 baseline.
- The report states whether the ablation improved full-support@10, recall@10, nDCG@10, and latency.

## Design Notes

- Commands: `scripts/es_hotpotqa.py create-bm25-index`, `ingest-bm25`, `validate`, and `python -m src.evaluation.benchmark_es`.
- Queries: title-aware BM25 searches boosted `title`, `title_exact`, `title_repeat_content`, `lead_sentence`, and `content`.
- API: no default API behavior changes.
- Tables: no durable database schema changes.
- Domain rules: HotpotQA qrels remain document-level.
- UI surfaces: no UI changes.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id <id> --unit 1 --integration 1 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Focused pytest for title-aware query/index/action helpers and benchmark dispatch. |
| Integration | Full title-aware BM25 index count validates to 5,233,329 docs. |
| E2E | Not required; no UI/API default path changes. |
| Platform | Benchmark artifact and report generated from local runtime. |
| Release | Not required. |

## Harness Delta

No harness changes expected.

## Evidence

- 2026-06-29: Added title-aware BM25 helpers and benchmark method `es_bm25_title`.
- Unit proof: `python -m pytest tests/test_elasticsearch_retriever.py -q` -> 21 passed; `python -m pytest tests/test_benchmark_es.py -q` -> 15 passed. Both runs emitted the existing `pytest_asyncio` deprecation warning.
- Combined proof: `python -m pytest tests/test_elasticsearch_retriever.py tests/test_benchmark_es.py -q` -> 36 passed, with the existing `pytest_asyncio` deprecation warning.
- Index proof: `python scripts/es_hotpotqa.py validate --index hotpotqa_full_titleaware_bm25_current --expected-count 5233329` -> count matched 5,233,329.
- Benchmark artifact: `evaluation/results/hotpotqa_full/title_aware_bm25_200.json`.
- Run file: `evaluation/runs/hotpotqa_full/title_aware_bm25/es_bm25_title_beir_hotpotqa_dev_top10.trec`.
- Report: `docs/sprint5/title-aware-bm25-ablation-report.md`.
- Result: `es_bm25_title` improved recall@10 from 0.6025 to 0.6050 and nDCG@10 from 0.5727 to 0.5786, but full-support@10 stayed 0.365, so the ablation should not become the default.
