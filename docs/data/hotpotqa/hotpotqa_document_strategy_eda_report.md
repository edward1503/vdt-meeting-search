# HotpotQA Document EDA and Ingest Strategy Report

## Executive Summary

Recommendation: keep HotpotQA retrieval document-level for the next quality experiment, but rebuild the indexed representation as a stronger title-aware document index. Do not make broad passage-level chunking the first ingest change.

The new EDA sampled 525,000 documents from the existing full HotpotQA staging artifact: 5,000 rows from each of the 105 staging shards. The sample shows that full HotpotQA documents are already short: median content length is 39 tokens, p95 is 111 tokens, and p99 is 160 tokens. A full passage index would therefore mostly reproduce the current document index, while adding grouping complexity and only modestly increasing the number of retrieval units.

The current retrieval failure pattern also points away from chunking as the first fix. On the 200-query full-corpus pilot, `tv_hybrid` already has any-support@10 of 0.955 but full-support@10 of 0.545. The main failure bucket is partial support: one gold document appears, but the second support document does not. This is a bridge/candidate-generation issue more than a document-length issue.

## Evidence Used

| Artifact | Purpose |
| --- | --- |
| `artifacts/hotpotqa_full/staging/manifest.json` | Confirms full staged corpus size: 5,233,329 docs in 105 JSONL shards. |
| `evaluation/results/hotpotqa_full/document_strategy_eda.json` | New sampled EDA over 525,000 staged documents. |
| `evaluation/results/hotpotqa_full/tv_full_200.json` | Current full-corpus BM25, dense, and hybrid metrics. |
| `docs/sprint5/ranking-diagnostics-report.md` | Failure bucket analysis for existing top-10 runs. |
| `docs/data/hotpotqa/hotpotqa_eda.md` | Prior HotpotQA data and multi-hop notes. |

## Dataset Shape

The full staged corpus has:

| Item | Value |
| --- | ---: |
| Documents | 5,233,329 |
| Staging shards | 105 |
| Default docs per shard | 50,000 |
| Train queries | 85,000 |
| Dev queries | 5,447 |
| Test queries | 7,405 |
| Qrels per query | 2.0 |

The qrels shape matters: HotpotQA success requires retrieving both support documents. A method that reliably retrieves one support document can still score poorly on `full_support_recall@10`.

## Document Length Profile

Sample design: 5,000 documents per staging shard, across all 105 shards.

| Metric | p50 | p75 | p90 | p95 | p99 | Max | Avg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Title tokens | 3 | 4 | 5 | 6 | 9 | 27 | 3.021 |
| Text tokens | 36 | 59 | 87 | 108 | 157 | 633 | 44.582 |
| Content tokens | 39 | 62 | 90 | 111 | 160 | 636 | 47.603 |
| Content chars | 238 | 372 | 545 | 671 | 969 | 3,706 | 289.097 |
| Sentence count/doc | 2 | 3 | 5 | 6 | 8 | 36 | 2.478 |
| Sentence tokens | 16 | 23 | 30 | 36 | 49 | 394 | 17.996 |

Implication: most HotpotQA full-corpus documents are already closer to passages than long articles. A broad passage index is unlikely to unlock a large length-normalization gain.

## Passage Index Estimate

If every document is converted into overlapping token windows:

| Strategy | Avg windows/doc | Estimated full retrieval units | Increase vs doc-level |
| --- | ---: | ---: | ---: |
| 80 tokens, stride 40 | 1.188 | 6,217,195 | +18.8% |
| 120 tokens, stride 60 | 1.043 | 5,458,362 | +4.3% |
| 160 tokens, stride 80 | 1.011 | 5,290,896 | +1.1% |

This is the key EDA result. The 120-token and 160-token strategies barely change the corpus shape because most docs fit into one window. The 80-token strategy changes more, but it can split already-short documents and requires careful parent aggregation to preserve document-level qrels.

## Current Retrieval Failure Pattern

Existing 200-query full-corpus metrics:

| Method | Recall@10 | nDCG@10 | Full-support@10 |
| --- | ---: | ---: | ---: |
| `es_bm25` | 0.6025 | 0.5727 | 0.365 |
| `tv_dense` | 0.7225 | 0.7082 | 0.515 |
| `tv_hybrid` | 0.7500 | 0.7286 | 0.545 |
| `tv_filtered_hybrid` | 0.6800 | 0.6735 | 0.455 |

Top-10 failure buckets from the diagnostics report:

| Method | Any support@10 | Missing candidate | Partial support | Success |
| --- | ---: | ---: | ---: | ---: |
| `es_bm25` | 0.840 | 32 | 95 | 73 |
| `tv_dense` | 0.930 | 14 | 83 | 103 |
| `tv_hybrid` | 0.955 | 9 | 82 | 109 |
| `tv_filtered_hybrid` | 0.905 | 19 | 90 | 91 |

For `tv_hybrid`, only 9/200 queries miss all support in top 10, but 82/200 retrieve only partial support. That pattern says the stack can find an entry point for most questions but often fails to bring in the second support document.

## Strategy Comparison

### Option A: Broad Passage-Level Index

Description: split every document into overlapping windows, retrieve passages, then group back to parent docs.

Pros:

- Can improve matching for long documents.
- Gives a more precise evidence surface for result display.
- Compatible with future sentence-level explainability.

Cons:

- EDA shows most docs are already short.
- Adds parent aggregation complexity before there is strong evidence it will improve full-support recall.
- Can split title/entity context away from evidence if the construction is careless.
- Qrels are document-level, so evaluation still needs parent-level grouping.

Verdict: useful later as a controlled experiment, not the first ingest change.

### Option B: Title-Aware Document-Level Reindex

Description: keep one indexed unit per HotpotQA document, but strengthen fields and query representation:

- `title` as exact keyword and boosted text field.
- `content` as title plus text.
- `title_repeat_content` or equivalent BM25 field where title is repeated to preserve entity signal.
- Dense embedding text formatted as `Title: <title>\nText: <text>`.
- Optional `lead_sentence` field for the first sentence.

Pros:

- Matches EDA: documents are short enough to remain the retrieval unit.
- Preserves document-level qrels without grouping complexity.
- Directly strengthens the most important HotpotQA signal: page title/entity.
- Lower implementation risk than entity linking or passage aggregation.

Cons:

- May not solve all bridge failures by itself.
- Needs a fresh BM25/TurboVec benchmark to prove improvement.
- Title repetition/boosting must be tuned to avoid overfitting to entity overlap.

Verdict: best next ingest/index strategy.

### Option C: Entity/Bridge-Aware Index

Description: enrich ingest with entity-like fields from titles and mentions, then use them for bridge retrieval or hop-conditioned expansion.

Pros:

- Directly targets HotpotQA bridge behavior.
- Better aligned with the partial-support failure pattern.
- Can help find the missing second support document.

Cons:

- Entity extraction/linking adds many new variables.
- Without official hyperlinks in the current staging rows, this can become heuristic-heavy.
- Harder to explain and benchmark cleanly as the next incremental step.

Verdict: promising research direction after a title-aware reindex baseline.

## Recommendation

Choose Option B first: title-aware document-level reindex.

This is the most defensible next step because the EDA contradicts the assumption that broad passage chunking is necessary. The full HotpotQA corpus is already made of short Wikipedia snippets. The retrieval problem is not primarily that evidence is buried inside long documents; it is that multi-hop queries need both support documents, and the second support is often missing from top 10.

Implementation shape:

```text
doc_id
numeric_id
title
title_exact
text
content = title + "\n" + text
title_repeat_content = title + "\n" + title + "\n" + text
lead_sentence
embedding_text = "Title: <title>\nText: <text>"
```

BM25 candidate generation should test:

```text
title^3
title_repeat_content^1.5
content
lead_sentence
```

Dense/TurboVec should test embeddings generated from the formatted title-aware text instead of the current plain content string.

## Secondary Experiment

After title-aware reindexing, run a small passage experiment only for the long tail:

- Keep documents with `content_tokens <= 160` as one unit.
- Split only documents over 160 tokens into 120-token windows with stride 60.
- Store `parent_doc_id`, `passage_id`, `passage_start_token`, and `passage_token_count`.
- Evaluate by grouping passage hits back to parent doc ids.

This should keep the retrieval-unit increase close to the p99 tail rather than changing the entire corpus.

## Success Criteria

The next index strategy should be considered useful only if it improves at least one of these without unacceptable latency regression:

| Metric | Baseline to beat |
| --- | ---: |
| `tv_hybrid` full-support@10 | 0.545 |
| `tv_hybrid` recall@10 | 0.750 |
| `tv_hybrid` nDCG@10 | 0.7286 |
| `tv_hybrid` partial-support failures | 82/200 |

The most important target is reducing partial-support failures, because that bucket dominates current top-10 errors.

## Presentation Claim

Use this wording:

> The original ingest pipeline made full-corpus retrieval reliable. The EDA showed that HotpotQA documents are already short, so broad passage chunking is not the best first quality upgrade. The next evidence-based indexing strategy is a title-aware document-level reindex that strengthens entity/page-title signals while preserving document-level qrels. Passage indexing should be limited to the long tail or tested as a separate ablation.
