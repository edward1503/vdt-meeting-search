# Elasticsearch Processing Pipeline

Pipeline active hiện tại là Elasticsearch-only.

## 1. Load dữ liệu

`ir_datasets` cung cấp corpus, queries và qrels cho `nano-beir/hotpotqa` hoặc các split full của `beir/hotpotqa`.

## 2. Normalize document

Mỗi document được normalize thành:

```json
{
  "doc_id": "...",
  "title": "...",
  "text": "...",
  "url": "...",
  "content": "title + text",
  "embedding_text": "title + text"
}
```

Không chunk document ở baseline hiện tại. Một HotpotQA document map thành một Elasticsearch document và một embedding vector.

## 3. Staging

Documents được ghi thành JSONL shards để ingest có thể resume. Default `docs_per_file=50000`; nano reproduce dùng `docs_per_file=2000`.

## 4. Elasticsearch index

Mapping chính:

| Field | Type |
|---|---|
| `doc_id` | `keyword` |
| `title` | `text` |
| `text` | `text` |
| `url` | `keyword` |
| `content` | `text` |
| `embedding` | `dense_vector`, dims 384, cosine |

Index settings baseline: `number_of_shards=1`, `number_of_replicas=0`, `refresh_interval=-1` trong lúc ingest.

## 5. Embedding ingest

Model active: `BAAI/bge-small-en-v1.5`.

Ingest encode `embedding_text` với `normalize_embeddings=True`, sau đó bulk insert vào Elasticsearch. `embedding_text` không được lưu vào ES source; ES source lưu `content` và `embedding`.

## 6. Search methods

### `es_bm25`

Elasticsearch `multi_match` query trên:

```text
title^2, content
```

### `es_dense`

Encode query bằng cùng BGE model, normalize embedding, rồi chạy ES kNN trên field `embedding`.

### `es_hybrid`

Chạy `es_bm25` và `es_dense`, lấy `candidate_k` candidates mỗi nhánh, rồi fuse bằng Reciprocal Rank Fusion:

```text
score(doc) = sum(1 / (rrf_k + rank_i))
```

### `es_iterative_hybrid`

```text
Hop 1:
  query -> es_hybrid -> first_hop_k docs

Hop 2:
  expanded_query = query + hop1_title + first context_chars của hop1_text
  expanded_query -> es_hybrid -> second_hop_k docs

Fusion:
  RRF fuse hop 1 và toàn bộ hop 2 rankings.
```

## 7. Metrics

Metrics đang dùng:

| Metric | Ý nghĩa |
|---|---|
| `precision@k` | Tỷ lệ top-k documents là relevant |
| `recall@k` | Tỷ lệ relevant documents được retrieve |
| `mrr@k` | Reciprocal rank của relevant document đầu tiên |
| `ndcg@k` | Ranking quality có xét thứ tự |
| `full_support_recall@k` | Top-k có chứa đầy đủ tất cả supporting documents hay không |
| latency p50/p95/p99 | Real-time latency |
| QPS | Query throughput tuần tự trong benchmark |

`full_support_recall@k` là metric quan trọng nhất cho HotpotQA multi-hop vì retrieve thiếu một support doc vẫn chưa đủ evidence để answer.
