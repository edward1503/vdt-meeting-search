# US-S5-009 HotpotQA Document Strategy EDA

## Status

implemented

## Lane

normal

## Product Contract

The project has an evidence-backed report for choosing the next HotpotQA ingest/index strategy, focused on document shape and retrieval failure modes rather than general pipeline engineering.

## Relevant Product Docs

- `docs/data/hotpotqa/hotpotqa_document_strategy_eda_report.md`
- `docs/data/hotpotqa/hotpotqa_eda.md`
- `docs/sprint5/ranking-diagnostics-report.md`

## Acceptance Criteria

- The report uses full HotpotQA staging artifacts rather than only nano HotpotQA.
- The report compares broad passage indexing, title-aware document-level indexing, and entity/bridge-aware indexing.
- The recommendation names one next strategy and explains why it follows from EDA evidence.
- The report distinguishes quality-improving index design from engineering-only ingest reliability.

## Design Notes

- Commands: sampled staged JSONL shards with Python, 5,000 docs per shard across all 105 shards.
- Queries: no API query behavior changed.
- API: no API behavior changed.
- Tables: no database schema changed.
- Domain rules: HotpotQA qrels remain document-level with two support docs per query in train/dev/test.
- UI surfaces: no UI behavior changed.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id <id> --unit 1 --integration 1 --e2e 0 --platform 0`.

| Layer | Expected proof |
| --- | --- |
| Unit | Report artifact exists and cites generated EDA JSON. |
| Integration | EDA reads staged full-corpus artifacts across all shard files. |
| E2E | Not required; no runtime behavior changed. |
| Platform | Not required; analysis-only artifact. |
| Release | Not required. |

## Harness Delta

No harness changes were needed.

## Evidence

- Generated `evaluation/results/hotpotqa_full/document_strategy_eda.json`.
- Added `docs/data/hotpotqa/hotpotqa_document_strategy_eda_report.md`.
- EDA sample: 525,000 docs, 105/105 staging shards, 5,000 docs per shard.
- Key finding: content token length p50=39, p95=111, p99=160; broad passage chunking is not the best first quality upgrade.
