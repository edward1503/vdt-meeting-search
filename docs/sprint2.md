# Sprint 2 - Benchmark 3 retrieval backends

## 1. Mục tiêu

Sprint 2 tập trung đánh giá riêng tầng retrieval/indexing, không thay đổi pipeline xử lý dữ liệu của Sprint 1. Ba hệ thống được đưa vào cùng một benchmark là FAISS, Elasticsearch và TurboVec.

Nguyên tắc thực nghiệm là giữ cố định parser, data processing, chunking, embedding model, qrels và `top_k`, sau đó chỉ thay backend vector search. Cách này giúp kết quả phản ánh khác biệt của hệ retrieval thay vì khác biệt do dữ liệu hoặc embedding.

Pipeline chung:

```text
AMI/JSON raw data
-> Sprint 1 parser
-> normalized meetings
-> Sprint 1 chunking
-> shared embedding matrix
-> FAISS index
-> Elasticsearch dense_vector index
-> TurboVec index
-> shared qrels evaluation
```

## 2. Cấu hình chung

| Thành phần | Giá trị |
|------------|---------|
| Dataset | AMI parsed data trong `data/raw` |
| Meetings | 171 |
| Chunks | 5347 |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Embedding dimension | 384 |
| Chunk size | 260 words |
| Chunk overlap | 60 words |
| Top K | 5 |
| Qrels | `data/eval/ami_qrels.json` |
| Queries | 10 |

Shared artifacts vẫn nằm trong `data/index`: `embeddings.npy`, `chunks.jsonl`, `meetings.json`, `manifest.json`. Các backend index riêng nằm dưới `data/index/faiss/`, `data/index/turbovec/`, và Elasticsearch index `vdt-meeting-chunks`.

## 3. Parser và processing dùng lại

Sprint 2 không thay parser. Parser AMI trong `src/preprocessing/parse_ami.py` vẫn đọc `corpusResources/meetings.xml`, `words/*.words.xml` và `segments/*.segments.xml`. Parser lấy metadata meeting, speaker, token, timestamp, segment range, rồi ghép token thành từng lượt nói.

Dữ liệu sau parse vẫn được chuẩn hóa thành meeting object gồm `meeting_id`, `raw_meeting_id`, `source`, `title`, `date`, `participants`, `turns`, `metadata`. Mỗi `turn` giữ speaker, role, text, `time_start`, `time_end`. Các turn được sort theo thời gian để giữ đúng thứ tự hội thoại. JSON/JSONL sample vẫn là fallback cho smoke test.

## 4. Chunking và embedding dùng lại

Chunking vẫn dùng sliding window với `chunk_size_words = 260`, `chunk_overlap_words = 60`, `step = 200`. Mỗi turn được prefix speaker trước khi gom transcript để chunk vẫn giữ ngữ cảnh hội thoại.

Mỗi chunk lưu `chunk_id`, `meeting_id`, `title`, `date`, `participants`, `speakers`, `time_start`, `time_end`, `text`, `source`, `metadata`.

Embedding được sinh một lần duy nhất từ `chunk[text]`, sau đó cả ba backend cùng dùng chung matrix vector. Model chính là `sentence-transformers/all-MiniLM-L6-v2`, vector đã normalize, nên inner product của FAISS có thể xem như cosine similarity.

## 5. Ba retrieval backends

### FAISS cổ điển

FAISS là baseline local exact vector search. Backend dùng `IndexFlatIP` trên vector float32 đầy đủ. FAISS không cần service ngoài, dễ dùng làm baseline chất lượng, nhưng storage lớn hơn TurboVec vì lưu float32 đầy đủ.

File chính: `src/retrieval/faiss_backend.py`.

### Elasticsearch

Elasticsearch backend index mỗi chunk thành một document có metadata và `dense_vector` field. Document chứa `chunk_index`, `chunk_id`, `meeting_id`, `title`, `date`, `participants`, `speakers`, `time_start`, `time_end`, `text`, `embedding`.

Mapping vector dùng `dense_vector`, `dims=384`, `index=true`, `similarity=cosine`. Backend search dùng kNN trên field `embedding`. Elasticsearch phù hợp để đánh giá hướng production-style vì có service riêng, metadata document, filter và khả năng kết hợp lexical/vector search sau này.

File chính: `src/retrieval/elasticsearch_backend.py`.

Ghi chú thực nghiệm: trong môi trường local hiện tại, Elasticsearch server tại `http://localhost:9200` chưa chạy, nên benchmark ghi backend này là `skipped`. Code backend đã được implement để chạy khi service available.

### TurboVec

TurboVec backend dùng `IdMapIndex` với `bit_width=4`. Numeric id trong TurboVec chính là vị trí chunk trong `chunks.jsonl`, giúp mapping kết quả về meeting/snippet ổn định.

TurboVec là local vector index có nén vector. Điểm cần đánh giá là storage, latency và độ giữ chất lượng so với FAISS exact baseline.

File chính: `src/retrieval/turbovec_backend.py`.

## 6. Benchmark runner

Benchmark được thêm tại `evaluation/benchmark_retrieval.py`.

Runner làm các bước: build hoặc reuse shared Sprint 1 artifacts, load chunks/vectors/qrels, encode toàn bộ query một lần, build từng backend từ cùng matrix vector, search cùng query vectors, gom chunk results theo `meeting_id`, rồi tính Precision@K, Recall@K, MRR@K, build time, latency avg/p50/p95 và storage size.

Lệnh chạy benchmark chính:

```bash
python -m evaluation.benchmark_retrieval --qrels data/eval/ami_qrels.json --top-k 5 --output evaluation/results/retrieval_benchmark_ami.json
```

Smoke test nhẹ bằng hashing embedding:

```bash
python -m evaluation.benchmark_retrieval --model hashing --rebuild-shared --qrels data/eval/sample_qrels.json --top-k 5
```

## 7. Kết quả benchmark AMI

Kết quả được lưu tại `evaluation/results/retrieval_benchmark_ami.json`.

Kết quả chạy ngày 2026-06-05 trên local machine:

| Backend | Status | Precision@5 | Recall@5 | MRR@5 | Build time | Avg latency | P50 latency | P95 latency | Storage |
|---------|--------|-------------|----------|-------|------------|-------------|-------------|-------------|---------|
| FAISS | ok | 0.6000 | 1.0000 | 1.0000 | 0.2211s | 7.9021ms | 1.4919ms | 60.6207ms | 7.8326 MB |
| Elasticsearch | skipped | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| TurboVec | ok | 0.6000 | 1.0000 | 1.0000 | 0.7188s | 4.3292ms | 0.6878ms | 36.8005ms | 1.0432 MB |

Elasticsearch skip reason: `Elasticsearch is not reachable at http://localhost:9200`.

## 8. Nhận xét ban đầu

FAISS và TurboVec đạt cùng chất lượng trên qrels nhỏ hiện tại: `Precision@5 = 0.60`, `Recall@5 = 1.00`, `MRR@5 = 1.00`. Điều này cho thấy với `bit_width=4`, TurboVec vẫn giữ được các meeting relevant trong top 5 của judged set hiện tại.

TurboVec có storage nhỏ hơn FAISS rõ rệt: FAISS là `7.8326 MB`, TurboVec là `1.0432 MB`. Tức TurboVec index nhỏ hơn khoảng 7.5 lần trong benchmark này.

Latency của TurboVec trong lần chạy này cũng thấp hơn FAISS ở avg, p50 và p95. Tuy nhiên dataset chỉ có 5347 chunks và 10 queries, nên latency cần được đo lại với nhiều query hơn, warm-up rõ ràng hơn và nhiều lần lặp để giảm nhiễu.

Elasticsearch chưa có số liệu thực tế vì service local chưa chạy. Khi bật Elasticsearch, benchmark hiện có thể index và đo cùng metrics để hoàn thiện bảng so sánh 3 backend.

## 9. Hạn chế

- Qrels còn nhỏ, mới 10 query AMI.
- Metrics chất lượng đang đánh giá theo meeting-level relevance, không đánh giá chunk-level relevance.
- Latency hiện đo retrieval-only sau khi query đã được encode, chưa bao gồm thời gian embedding query.
- Chưa đo memory usage runtime.
- Elasticsearch backend chưa được đo do thiếu server local.
- Chưa benchmark nhiều cấu hình TurboVec bit width như 2, 3, 4.

## 10. Kết luận

Sprint 2 đã tách retrieval layer thành backend interface chung và implement ba backend: FAISS, Elasticsearch và TurboVec. Pipeline parser, processing data, chunking và embedding của Sprint 1 được giữ nguyên để đảm bảo benchmark công bằng.

Kết quả local hiện tại cho thấy FAISS là baseline exact ổn định, TurboVec đạt cùng quality trên qrels nhỏ nhưng dùng storage thấp hơn nhiều, còn Elasticsearch đã có backend code nhưng cần bật service để hoàn tất thực nghiệm production-style.
