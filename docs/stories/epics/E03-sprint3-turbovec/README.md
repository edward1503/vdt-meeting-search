# E03 Sprint 3 TurboVec Full-Scale Retrieval

## Status

implemented

## Source Plan

- `docs/sprint3/plan.md`

## Goal

Build and evaluate full-scale HotpotQA retrieval over 5,233,329 documents using Elasticsearch BM25, TurboVec dense search, and application-layer RRF fusion.

## Harness Classification

- Type: new initiative
- Lane: high-risk at initiative level
- Reason: changes retrieval architecture, benchmark validity, API method exposure, large generated artifacts, external Elasticsearch runtime, and dependency/runtime assumptions.

## Story Order

1. `US-S3-001-turbovec-dependency-smoke.md`
2. `US-S3-002-numeric-id-staging.md`
3. `US-S3-003-bm25-only-index-path.md`
4. `US-S3-004-stage-full-hotpotqa.md`
5. `US-S3-005-full-bm25-benchmark.md`
6. `US-S3-006-resumable-embedding-shards.md`
7. `US-S3-007-build-turbovec-index.md`
8. `US-S3-008-turbovec-retriever.md`
9. `US-S3-009-turbovec-benchmark-support.md`
10. `US-S3-010-full-benchmark-tuning.md`
11. `US-S3-011-api-integration.md`
12. `US-S3-012-sprint3-report.md`

## Evidence Policy

Unit and integration tests prove code behavior. Full-corpus staging, embedding, indexing, and benchmarks are platform evidence and must be recorded with concrete artifact paths and command output in the story evidence sections.

## Completion Evidence

- Full staging manifest: `artifacts/hotpotqa_full/staging/manifest.json`, `docs_written=5,233,329`, `files_written=105`, `numeric_id_end=5,233,328`.
- Full BM25 index: `hotpotqa_full_bm25_v1`, validated count `5,233,329`.
- Full embedding shards: 105 `.float16.npy`, 105 `.ids.npy`, and 105 `.meta.json` files under `artifacts/hotpotqa_full/embeddings/`.
- Full TurboVec index: `artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim`, `docs=5,233,329`, `dim=384`, `bit_width=4`.
- Primary benchmark: `evaluation/results/hotpotqa_full/tv_full_200.json` on `beir/hotpotqa/dev`, 200 queries.
- Tuning runs: `evaluation/results/hotpotqa_full/tune_k50_rrf30.json`, `evaluation/results/hotpotqa_full/tune_k200_rrf30.json`, and `evaluation/results/hotpotqa_full/tune_k100_rrf60.json`.
- Final report: `docs/sprint3/sprint3-report.md`.
