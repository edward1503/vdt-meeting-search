# HotpotQA Full Ingest EDA

## Dataset

| Field | Value |
|---|---|
| Dataset | nano-beir/hotpotqa |
| Docs count | 5,090 |
| Queries count | 50 |
| Qrels count | 100 |
| Docs iterated for EDA | 5,090 |

## Document Profile

| Metric | Value |
|---|---|
| missing.title | 5,090 |
| missing.text | 0 |
| missing.url | 5,090 |
| missing.content | 0 |
| duplicates.doc_id_duplicate_count | 0 |
| duplicates.content_hash_duplicate_count | 0 |
| content_tokens.p50 | 50 |
| content_tokens.p95 | 136 |
| content_tokens.p99 | 194 |
| content_tokens.max | 352 |
| content_tokens.avg | 58.399 |
| source_bytes.avg | 778.956 |

## Ingest Plan Estimate

| Field | Value |
|---|---|
| recommended_primary_shards | 1 |
| recommended_bulk_docs | 2,150 |
| staging_file_count | 1 |
| embedding_float32_gb | 0.007 |
| embedding_float16_gb | 0.004 |
| estimated_source_gb | 0.004 |
| estimated_index_gb | 0.015 |

## Query/Qrel Splits

| Dataset | Queries | Qrels |
|---|---|---|
| beir/hotpotqa/train | 85,000 | 170,000 |
| beir/hotpotqa/dev | 5,447 | 10,894 |
| beir/hotpotqa/test | 7,405 | 14,810 |
| nano-beir/hotpotqa | 50 | 100 |

## Ingest Implications

- Use one Elasticsearch index with text fields and one dense_vector field.
- Build staging JSONL shards before embedding so workers can resume by shard.
- Use doc_id as Elasticsearch _id to make reruns idempotent.
- Disable refresh and replicas during initial bulk ingest, then restore after final count validation.
