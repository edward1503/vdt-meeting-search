# TurboVec Trong Sprint 3: Cách Hoạt Động, Lý Do Tiết Kiệm, Và Trade-off

## 1. Bối cảnh

Sprint 3 đưa hệ thống retrieval từ bộ `nano-beir/hotpotqa` nhỏ lên full HotpotQA với `5,233,329` documents. Ở quy mô này, cách làm cũ là lưu dense vector trực tiếp trong Elasticsearch trở nên nặng với máy local khoảng 16 GB RAM.

Vì vậy Sprint 3 tách retrieval thành hai phần:

```text
Elasticsearch -> BM25 lexical search + document store
TurboVec      -> dense vector search nén 4-bit
Application   -> RRF fusion giữa BM25 và dense
```

Nói đơn giản: Elasticsearch vẫn giữ văn bản và tìm kiếm từ khóa rất tốt. TurboVec chỉ chịu trách nhiệm tìm kiếm theo vector embedding, tức tìm những document gần nghĩa với query trong không gian vector.

## 2. Dense retrieval là gì?

Dense retrieval biến query và document thành vector số. Trong Sprint 3, model `BAAI/bge-small-en-v1.5` tạo vector 384 chiều.

Ví dụ tưởng tượng:

```text
Query: "Who was the father-in-law of Queen Hyojeong?"
-> vector query: [0.12, -0.04, 0.88, ...] 384 số

Document A
-> vector doc A: [0.10, -0.03, 0.80, ...]

Document B
-> vector doc B: [-0.40, 0.11, 0.05, ...]
```

Nếu vector của query gần vector của document A hơn document B, dense retriever xếp document A cao hơn.

Điểm mạnh của dense retrieval là nó không cần khớp từ y hệt. Nó có thể bắt được quan hệ ngữ nghĩa, thực thể liên quan, hoặc cách diễn đạt khác nhau. Đây là lý do `tv_dense` và `tv_hybrid` trong Sprint 3 cải thiện rõ so với BM25 trên HotpotQA.

## 3. TurboVec nằm ở đâu trong pipeline?

Pipeline Sprint 3 có 5 bước chính.

### Bước 1: Staging full corpus

Mỗi document HotpotQA được normalize thành JSONL row. Sprint 3 thêm `numeric_id` ổn định:

```json
{
  "numeric_id": 123,
  "doc_id": "46979246",
  "title": "Donald Trump 2016 presidential campaign",
  "text": "...",
  "content": "title + text",
  "embedding_text": "title + text"
}
```

`doc_id` gốc là string, còn TurboVec làm việc tốt hơn với id số kiểu `uint64`. Vì vậy `numeric_id` là cầu nối giữa TurboVec và Elasticsearch.

### Bước 2: Tạo embedding shards

Script embedding đọc từng staging shard, encode `embedding_text`, rồi ghi ra:

```text
docs-00000.float16.npy  -> vector embedding
docs-00000.ids.npy      -> numeric_id tương ứng
docs-00000.meta.json    -> metadata của shard
```

Sprint 3 có 105 shard embedding cho `5,233,329` docs.

### Bước 3: Build TurboVec index

TurboVec đọc các embedding shard, build `IdMapIndex`, và lưu ra:

```text
artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim
```

Index này chứa vector đã được nén và mapping từ vector về `numeric_id`.

### Bước 4: Search bằng TurboVec

Khi user gửi query:

```text
query text
-> SentenceTransformer encode thành vector query
-> TurboVec search top-k numeric_id gần nhất
```

Kết quả TurboVec trả về chưa phải document đầy đủ, mà là danh sách id:

```text
[28793979, 513194, 60598, ...]
```

### Bước 5: Hydrate document từ Elasticsearch

API lấy `numeric_id` từ TurboVec, gọi Elasticsearch để lấy lại `doc_id`, `title`, `text`, `url`.

```text
TurboVec result ids
-> Elasticsearch terms query by numeric_id
-> hydrated documents for UI/API
```

Đây là lý do Elasticsearch vẫn quan trọng: TurboVec không thay thế document store.

## 4. Vì sao TurboVec tiết kiệm hơn Elasticsearch dense vector?

Elasticsearch mạnh ở text search, filtering, distributed indexing, và document storage. Nhưng dense vector search ở quy mô 5M documents có chi phí đáng kể, đặc biệt khi dùng HNSW index.

### 4.1. Vector float gốc rất lớn

Mỗi document có vector 384 chiều. Nếu dùng `float32`:

```text
384 chiều * 4 bytes = 1,536 bytes / document
5,233,329 docs * 1,536 bytes ~= 8.0 GB vector thô
```

Đây mới chỉ là vector raw, chưa tính metadata, index graph, segment overhead, JVM heap/off-heap, filesystem cache, Elasticsearch internals.

Nếu dùng `float16`:

```text
384 chiều * 2 bytes = 768 bytes / document
5,233,329 docs * 768 bytes ~= 4.0 GB vector thô
```

Vẫn khá lớn với máy 16 GB nếu còn phải chạy Elasticsearch, Python API, embedding model, Docker, OS.

### 4.2. HNSW có overhead lớn

Elasticsearch dense vector thường dựa trên approximate nearest neighbor index như HNSW. HNSW tăng tốc search bằng cách xây một graph hàng xóm giữa vector.

Graph này giúp truy vấn nhanh, nhưng nó cần thêm bộ nhớ để lưu cạnh, level, metadata, segment structure. Trên full corpus, overhead này có thể làm tổng chi phí RAM/disk cao hơn nhiều so với vector raw.

### 4.3. TurboVec dùng nén 4-bit

Sprint 3 dùng TurboVec `bit_width=4`. Về trực giác, thay vì lưu mỗi chiều vector bằng float 32-bit, TurboVec lượng tử hóa vector thành biểu diễn ít bit hơn.

So sánh ý tưởng:

```text
float32: 32 bit / giá trị
float16: 16 bit / giá trị
4-bit:    4 bit / giá trị
```

Nếu chỉ nhìn số bit trên mỗi chiều, 4-bit rẻ hơn float32 khoảng 8 lần. Thực tế index còn có metadata và cấu trúc phụ, nên không thể lấy đúng 8 lần cho toàn file. Nhưng kết quả Sprint 3 cho thấy full TurboVec index chỉ khoảng:

```text
1,067,602,206 bytes ~= 1.07 GB
```

Với full `5,233,329` docs, đây là mức phù hợp hơn nhiều cho laptop 16 GB so với việc cố đưa dense vector full vào Elasticsearch.

## 5. Vì sao không bỏ Elasticsearch luôn?

TurboVec giải quyết dense vector search, nhưng không làm hết việc Elasticsearch đang làm.

Elasticsearch vẫn cần cho:

- BM25 lexical retrieval.
- Lưu document text/title/url để trả về API/UI.
- Hydrate kết quả TurboVec từ `numeric_id` sang document đầy đủ.
- Debug và fallback khi dense path lỗi hoặc quá chậm.
- Các query cần keyword exact match, tên riêng, ngày tháng, cụm từ hiếm.

BM25 vẫn rất hữu ích. Với HotpotQA, nhiều query chứa entity rõ ràng. Ví dụ một tên chiến dịch, một nhân vật, một địa danh. BM25 thường tìm các match này nhanh và ổn định.

Vì vậy kiến trúc tốt nhất trong Sprint 3 không phải là "TurboVec thay Elasticsearch", mà là:

```text
BM25 tìm lexical signal
TurboVec tìm semantic signal
RRF hợp nhất hai ranking
Elasticsearch hydrate document cuối cùng
```

## 6. Các mode retrieval hiện tại

### `es_bm25`

Chỉ dùng Elasticsearch BM25.

Nên dùng khi:

- Cần latency thấp.
- Query có nhiều entity/từ khóa rõ.
- Máy yếu hoặc chưa load được TurboVec.
- Cần fallback ổn định.

Sprint 3 benchmark:

```text
full_support_recall@10 = 0.365
p95 latency = 359.6319 ms
```

### `tv_dense`

Chỉ dùng TurboVec dense retrieval.

Nên dùng khi:

- Query có paraphrase hoặc semantic relation.
- Muốn kiểm tra sức mạnh riêng của embedding.
- Không cần lexical exact match quá nhiều.

Sprint 3 benchmark:

```text
full_support_recall@10 = 0.515
p95 latency = 868.0033 ms
```

### `tv_hybrid`

Chạy BM25 và TurboVec dense, sau đó fuse bằng Reciprocal Rank Fusion.

Nên dùng khi:

- Muốn chất lượng retrieval tốt nhất trong Sprint 3.
- Chấp nhận latency cao hơn BM25.
- Cần vừa entity match vừa semantic match.

Sprint 3 benchmark:

```text
full_support_recall@10 = 0.545
p95 latency = 3089.2229 ms với k=100
```

Config laptop được khuyến nghị trong report:

```text
candidate_k=50, num_candidates=50, rrf_k=30
full_support_recall@10 = 0.535
p95 latency = 2053.6018 ms
```

Tức là giảm khoảng 1 giây p95 so với k=100, đổi lại mất 0.010 absolute full-support recall.

### `tv_filtered_hybrid`

`tv_filtered_hybrid` dùng BM25 làm bước lọc candidate trước. Thay vì để TurboVec search toàn bộ 5.23M vector, hệ thống lấy `numeric_id` từ các BM25 hits, truyền danh sách đó vào TurboVec `allowlist`, rồi dense search chỉ trong tập candidate này. Kết quả cuối vẫn được fuse với BM25 bằng RRF.

Nên dùng khi:

- Muốn giảm search space của dense retrieval.
- Query có lexical signal đủ tốt để BM25 tạo candidate set đáng tin.
- Muốn thử trade-off latency/quality so với broad `tv_hybrid`.

Trade-off:

- Nếu BM25 không đưa support doc vào candidate set, filtered dense search cũng không thể tìm lại document đó.
- Nếu Elasticsearch hit thiếu `numeric_id` hoặc index không khớp TurboVec artifact, mode này phải fallback sang dense search rộng hoặc trả kết quả kém.
- Cần benchmark riêng trước khi dùng làm default.

## 7. RRF fusion hoạt động như nào?

RRF là Reciprocal Rank Fusion. Nó không cần score BM25 và dense cùng thang đo. Nó chỉ dùng thứ hạng.

Công thức đơn giản:

```text
RRF_score(doc) = sum(1 / (rrf_k + rank_i(doc)))
```

Nếu một document đứng cao trong cả BM25 và dense, nó nhận điểm cao hơn. Nếu document chỉ xuất hiện trong một bên nhưng đứng rất cao, nó vẫn có cơ hội vào top kết quả.

Ví dụ:

```text
BM25 ranking:  A, B, C
Dense ranking: B, D, A
```

Document B đứng rank 2 ở BM25 và rank 1 ở dense, nên khả năng được đẩy lên cao. Document A rank 1 ở BM25 và rank 3 ở dense cũng mạnh. Document D chỉ xuất hiện ở dense, vẫn có điểm nhưng yếu hơn nếu không xuất hiện ở BM25.

RRF hợp với hybrid search vì BM25 score và dense score không cùng bản chất. BM25 là lexical score, dense là vector similarity. Cộng raw score trực tiếp thường không ổn nếu chưa calibration.

## 8. Trade-off chính của TurboVec

### 8.1. Tiết kiệm tài nguyên nhưng là approximate retrieval

TurboVec nén vector nên tiết kiệm RAM/disk, nhưng nén đồng nghĩa có mất thông tin. Search trả về nearest neighbors theo biểu diễn nén, không phải vector float32 đầy đủ.

Hệ quả:

- Có thể miss một số document gần đúng nếu quantization làm sai thứ tự nhỏ.
- 4-bit tiết kiệm hơn nhưng có thể giảm recall so với 8-bit hoặc float.
- Cần benchmark thực tế, không nên chỉ tin lý thuyết.

Trong Sprint 3, 4-bit vẫn đủ tốt: `tv_dense` và `tv_hybrid` đều vượt BM25 rõ ràng trên 200 query.

### 8.2. Dense tốt về nghĩa, yếu hơn với exact token

Dense retriever có thể hiểu paraphrase, nhưng đôi khi lại bỏ qua chi tiết nhỏ:

- số năm;
- tên riêng rất hiếm;
- ký hiệu;
- cụm từ cần match chính xác;
- document có entity trùng y hệt query.

BM25 thường mạnh ở các trường hợp này. Đó là lý do hybrid tốt hơn dense-only.

### 8.3. Latency cao hơn BM25

Với `tv_hybrid`, hệ thống phải làm nhiều việc hơn:

```text
1. encode query thành embedding
2. search BM25
3. search TurboVec
4. fuse ranking
5. hydrate documents từ Elasticsearch
```

BM25 chỉ cần search Elasticsearch. Vì vậy BM25 nhanh hơn.

Sprint 3 primary benchmark:

```text
es_bm25 p95    = 359.6319 ms
tv_dense p95   = 868.0033 ms
tv_hybrid p95  = 3089.2229 ms
```

Đổi lại, quality tăng:

```text
es_bm25 full_support_recall@10   = 0.365
tv_hybrid full_support_recall@10 = 0.545
```

### 8.4. Cần vận hành thêm artifact

Elasticsearch index nằm trong ES data volume. TurboVec index là file `.tvim` riêng. Khi deploy, phải đảm bảo:

- file `.tvim` được mount hoặc copy vào container;
- version `turbovec` tương thích;
- `TURBOVEC_INDEX_PATH` đúng;
- Elasticsearch index và TurboVec index được build từ cùng staging manifest;
- `numeric_id` trong ES khớp với ids trong TurboVec.

Nếu ES index là `hotpotqa_nano_current` nhưng TurboVec index là full corpus, hydrate sẽ sai hoặc mất kết quả. Đây là lỗi config rất dễ gặp khi chạy Docker nếu default vẫn trỏ nano index.

### 8.5. Không tự giải quyết multi-hop reasoning

TurboVec chỉ là dense retriever. Nó không tự biết câu hỏi cần hai hop. Với HotpotQA, câu hỏi thường cần đủ hai support docs. `tv_hybrid` tốt hơn BM25, nhưng vẫn là một lượt retrieval chính.

Muốn tiến gần MDR/Baleen hơn, cần thêm:

- hop 1 tìm bridge entity;
- hop 2 condition theo evidence hop 1;
- reranker cho candidate pairs;
- hoặc learned multi-hop retriever.

## 9. Khi nào kết quả TurboVec được coi là tốt?

Trong Sprint 3, `tv_hybrid` có:

```text
precision@10           = 0.1500
recall@10              = 0.7500
ndcg@10                = 0.7286
full_support_recall@10 = 0.545
```

Với HotpotQA, mỗi query thường có 2 support docs. `precision@10` tối đa lý thuyết thường chỉ là `2/10 = 0.2`, nên `0.1500` không thấp như nhìn ban đầu. Nó nghĩa là trung bình hệ thống lấy được khoảng 1.5 support docs trong top 10.

Điểm cần cải thiện nhất là `full_support_recall@10`: chỉ khoảng 54.5% query có đủ cả hai support docs trong top 10. Đây là vấn đề multi-hop, không phải chỉ vấn đề vector index.

## 10. Kết luận thực dụng

TurboVec trong Sprint 3 là lựa chọn hợp lý vì nó giúp chạy dense retrieval trên full HotpotQA 5.23M docs trong điều kiện máy local hạn chế. Nó không thay thế Elasticsearch, mà bổ sung dense semantic retrieval cho BM25.

Tóm tắt:

| Điểm | TurboVec giúp gì? | Giá phải trả |
| --- | --- | --- |
| RAM/disk | Nén vector 4-bit, index full corpus khoảng 1.07 GB | Mất một phần độ chính xác do quantization |
| Quality | Dense/hybrid tăng recall và nDCG so với BM25 | Chưa đạt mức learned multi-hop retriever |
| Latency | Chấp nhận được cho demo/benchmark local | Chậm hơn BM25, nhất là hybrid |
| Vận hành | File index độc lập, dễ copy/mount | Phải giữ khớp với ES index và `numeric_id` |
| Kiến trúc | Tách lexical store và dense search rõ ràng | Có thêm dependency/runtime cần quản lý |

Nếu mục tiêu là demo nhanh, dùng `tv_hybrid` với `candidate_k=50`. Nếu mục tiêu là chất lượng cao hơn, dùng `candidate_k=100` hoặc nghiên cứu reranker/multi-hop retriever ở Sprint sau.
