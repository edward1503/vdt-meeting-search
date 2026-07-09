# Semantic Metadata Search Report

## Scope

This Sprint 5 artifact evaluates natural-language metadata search over existing synthetic HotpotQA metadata fields only: `author`, `created_at`, and `modified_at`.
It does not add metadata fields, does not embed metadata text, and does not claim production meeting metadata coverage.

## Query Design

- Query artifact: `evaluation/results/hotpotqa_full/semantic_metadata/semantic_queries_smoke.json`
- Smoke query count: 2
- Semantic form: `find documents about <title> by <author> before <created_at>`
- Ground truth: the source document used to synthesize each query.

## Comparison Settings

- `content_only_original`: search the full natural-language query without metadata filters.
- `manual_filter`: search the content query with explicit metadata filters.
- `parsed_metadata`: parse the natural-language query, then search with effective query plus parsed filters.

## Smoke Summary

| Setting | Recall |
| --- | --- |
| `content_only_original` | 0.0000 |
| `manual_filter` | 1.0000 |
| `parsed_metadata` | 1.0000 |

## Next Evaluation Step

Run the same three settings against a larger metadata-enriched HotpotQA shard with the live retrieval API to replace the placeholder smoke runs.
