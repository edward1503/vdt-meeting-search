# E04 Sprint 4 Evaluation Expansion

## Status

active

## Source Plan

- `docs/sprint4/plan.md`

## Goal

Complete four Sprint 4 workstreams by Sunday, 2026-06-21: paraphrase robustness testing, iterative retrieval improvement, lightweight synthetic author/date metadata search, and a minimal VimQA retrieval pipeline.

## Harness Classification

- Type: new initiative
- Lane: high-risk at initiative level
- Story lane default: normal
- Intake: #32
- Reason: benchmark validity, external Kaggle artifacts, qrels preservation, metadata schema, retrieval filter behavior, and future dataset protocol.

## Story Order

1. `US-S4-001-initiative-setup.md`
2. `US-S4-002-hotpotqa-paraphrase-export-protocol.md`
3. `US-S4-003-kaggle-paraphrase-roundtrip-validator.md`
4. `US-S4-004-full-corpus-paraphrase-robustness-benchmark.md`
5. `US-S4-010-lexical-strong-paraphrase-profile.md`
6. `US-S4-009-iterative-retrieval-improvement.md`
7. `US-S4-005-synthetic-asr-meeting-metadata-generator.md`
8. `US-S4-006-metadata-aware-retrieval-path.md`
9. `US-S4-007-metadata-demo-benchmark-report.md`
10. `US-S4-008-vimqa-benchmark-pipeline-research.md`
11. `US-S4-011-dataset-first-api-ui-refactor.md`

## Current Execution Decision

VimQA data and retrieval activation (`US-S4-008`) must land before the
dataset-first API/UI refactor (`US-S4-011`). This keeps the refactor grounded
in real VimQA staging, indexes, benchmark artifacts, and readiness state rather
than designing API profiles around hypothetical data.

## Evidence Policy

Benchmark and metadata claims must point to concrete artifacts, commands, and report paths. Paraphrase benchmark outputs must keep original qrels traceable through `source_query_id`; rejected paraphrases must be counted and explained. Retrieval-improvement claims must compare against current `tv_hybrid` evidence and include latency. Metadata-demo evidence must be reported separately from BEIR/HotpotQA benchmark claims. VimQA results are pipeline-readiness evidence, not paper-comparable benchmark claims.

## Completion Evidence

- Sprint 4 initiative setup is finalized in `docs/sprint4/plan.md` with four
  workstreams, MVP outputs, priority order, deadline schedule, exit criteria,
  and explicit non-goals.
- Story skeletons exist for `US-S4-001` through `US-S4-009`; implementation
  starts with `US-S4-009` after setup closeout.
- Redis retrieval cache hardening is intentionally excluded from Sprint 4.
