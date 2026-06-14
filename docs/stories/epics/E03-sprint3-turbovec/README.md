# E03 Sprint 3 TurboVec Full-Scale Retrieval

## Status

planned

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
