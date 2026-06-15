# HotpotQA Full Ingest EDA

## Dataset

| Field | Value |
|---|---|
| Dataset | beir/hotpotqa |
| Docs count | 5,233,329 |
| Queries count | 97,852 |
| Qrels count |  |
| Docs iterated for EDA |  |

## Document Profile

Docs scan skipped: --skip-docs was used; document length/source profile was not scanned

| Metric | Value |
|---|---|
| content_tokens.p50 |  |
| content_tokens.p95 |  |
| content_tokens.p99 |  |
| content_tokens.max |  |
| content_tokens.avg |  |
| source_bytes.avg |  |

## Ingest Plan Estimate

| Field | Value |
|---|---|

## Query/Qrel Splits

| Dataset | Queries | Qrels |
|---|---|---|
| beir/hotpotqa/train | 85,000 | 170,000 |
| beir/hotpotqa/dev | 5,447 | 10,894 |
| beir/hotpotqa/test | 7,405 | 14,810 |

## Ingest Implications

- Use one Elasticsearch index with text fields and one dense_vector field.
- Build staging JSONL shards before embedding so workers can resume by shard.
- Use doc_id as Elasticsearch _id to make reruns idempotent.
- Disable refresh and replicas during initial bulk ingest, then restore after final count validation.
