# US-S4-008 VimQA Retrieval Pipeline

## Status

implemented

## Lane

normal

## Product Contract

Sprint 4 produces a minimal runnable VimQA retrieval pipeline plus a design/report explaining how a QA dataset is converted into a retrieval proxy and what risks remain. The pipeline is MVP evidence for dataset readiness, not a production or paper-comparable benchmark claim.

## Relevant Product Docs

- `docs/sprint4/plan.md`
- `docs/sprint4/vimqa-benchmark-design.md`
- `docs/architecture/current-architecture.md`
- `docs/data/vimqa/train_vimqa.json`
- `docs/data/vimqa/test_vimqa.json`

## Acceptance Criteria

- Pipeline loads local `train_vimqa.json` and `test_vimqa.json` inputs.
- Pipeline defines `corpus = union unique contexts train+test`.
- Pipeline defines `query = question`.
- Pipeline defines `qrel = question -> context_doc_id`.
- Pipeline writes corpus, query, qrels, run, and result artifacts under `artifacts/vimqa/all/`, `evaluation/results/vimqa/`, and `evaluation/runs/vimqa/`.
- Design uses BM25 as the paper-backed baseline because the VIMQA paper uses BM25 for distractor retrieval.
- Design proposes `bkai-foundation-models/vietnamese-bi-encoder` as the primary dense model, with 768-dim Elasticsearch `dense_vector` storage.
- Design records `AITeamVN/Vietnamese_Embedding` as a fallback only if BKAI runtime blocks progress.
- Design metrics are `recall@1/5/10`, `mrr@10`, `ndcg@10`, and latency.
- Design proposes index aliases `vimqa_all_bm25_current` and `vimqa_all_dense_bkai_current`.
- Design explicitly discusses leakage risk and the fact that VimQA is not native BEIR.
- Elasticsearch BM25 and BKAI dense indexes are created, ingested, validated, and benchmarked on the full 9,044-query set.

## Design Notes

- Commands: `scripts/stage_vimqa.py` converts local VimQA files into staging JSONL, query TSV, and qrels TSV.
- Queries: expose question rows as retrieval queries.
- API: no API changes in Sprint 4.
- Tables: no database changes.
- Domain rules: pipeline-readiness evidence only; no paper-comparable claim.
- UI surfaces: no UI changes.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-008 --unit 1 --integration 1 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Loader/dedup/qrels tests for sample VimQA rows. |
| Integration | Pipeline smoke writes result artifacts and metrics. |
| E2E | Not required. |
| Platform | Design and pipeline report exist with commands/artifacts. |
| Release | Not required. |

## Harness Delta

No Harness policy change is planned.

## Evidence

- Loader and staging tests: `python -m pytest tests/test_stage_vimqa.py tests/test_vimqa_dataset.py -q` -> 3 passed.
- Elasticsearch metadata/staging regression tests: `python -m pytest tests/test_elasticsearch_retriever.py tests/test_stage_vimqa.py -q` -> 19 passed.
- Benchmark TSV compatibility tests: `python -m pytest tests/test_benchmark_es.py -q` -> 11 passed.
- Staging command: `python scripts/stage_vimqa.py --docs-per-file 5000` wrote 3,623 documents, 9,044 queries, and 9,044 qrels.
- BM25 index validation: `python scripts/es_hotpotqa.py validate --index vimqa_all_bm25_current --expected-count 3623` passed.
- BKAI dense index validation: `python scripts/es_hotpotqa.py validate --index vimqa_all_dense_bkai_current --expected-count 3623` passed.
- BM25 pilot result: `evaluation/results/vimqa/bm25_vimqa_1000.json` reports recall@10 0.987, mrr@10 0.9113, ndcg@10 0.9300, p95 63.2800 ms, qps 18.7042.
- BKAI pilot result: `evaluation/results/vimqa/dense_bkai_vimqa_1000.json` reports `es_dense` recall@10 0.891 and `es_hybrid` recall@10 0.983.
- BM25 full result: `evaluation/results/vimqa/bm25_vimqa_full.json` reports 9,044 queries, recall@10 0.9627, mrr@10 0.8606, ndcg@10 0.8859, p95 84.4191 ms, qps 16.3922.
- BKAI full result: `evaluation/results/vimqa/dense_bkai_vimqa_full.json` reports 9,044 queries, `es_dense` recall@10 0.8716, mrr@10 0.7272, ndcg@10 0.7625, p95 115.0396 ms, qps 10.5955; `es_hybrid` recall@10 0.9644, mrr@10 0.8277, ndcg@10 0.8609, p95 206.3031 ms, qps 1.2394.
- Full runs completed, but the local runner still needs progress logging or batching for repeated long benchmark tuning.
