# VimQA Benchmark Design

## Dataset Contract

VimQA is converted from local QA rows into a context retrieval proxy:

```text
question -> query
unique normalized context -> document
question-context relation -> qrel
```

The source files are:

```text
docs/data/vimqa/train_vimqa.json
docs/data/vimqa/test_vimqa.json
```

Each input row has `question`, `context`, and `answer`. The retrieval pipeline does not answer the question; it measures whether retrieval finds the context paired with that question.

## Corpus Shape

The corpus is the union of unique normalized contexts from train and test. The current conversion emits:

| Item | Count |
| --- | ---: |
| Unique context documents | 3,623 |
| Queries | 9,044 |
| Qrels | 9,044 |

Generated artifacts:

```text
artifacts/vimqa/all/staging/docs-00000.jsonl
artifacts/vimqa/all/staging/manifest.json
evaluation/results/vimqa/vimqa_queries.tsv
evaluation/results/vimqa/vimqa_qrels.tsv
```

## Retrieval Semantics

Each query has one gold context document. `recall@k` means the top-k results include that one context. This is not the same as HotpotQA full-support retrieval, where a query can require retrieving multiple support documents.

VimQA results are pipeline-readiness evidence for Vietnamese context retrieval. They are not BEIR-native or paper-comparable leaderboard claims.

## Index Strategy

Use Elasticsearch first:

| Index alias | Purpose |
| --- | --- |
| `vimqa_all_bm25_current` | BM25 baseline over context text |
| `vimqa_all_dense_bkai_current` | Dense vector and hybrid retrieval with BKAI embeddings |

TurboVec is out of scope for the VimQA MVP. The corpus is small enough for Elasticsearch `dense_vector`, and future synthetic metadata filters fit Elasticsearch more naturally than a separate dense vector artifact.

## Model Strategy

The paper-backed retrieval baseline is BM25. The VIMQA paper uses BM25 for distractor retrieval rather than a dense embedding retriever.

For dense retrieval, use one primary model to avoid spending Sprint time on embedding sweeps:

```text
bkai-foundation-models/vietnamese-bi-encoder
dims = 768
backend = Elasticsearch dense_vector
similarity = cosine
```

Fallback only if BKAI runtime blocks progress:

```text
AITeamVN/Vietnamese_Embedding
dims = 1024
```

## Metrics

Report:

```text
recall@1/5/10
mrr@10
ndcg@10
latency_p50_ms
latency_p95_ms
qps
```

The benchmark runner still emits `full_support_recall@k` for compatibility, but for VimQA it is equivalent to single-context recall because each query has one relevant context.
