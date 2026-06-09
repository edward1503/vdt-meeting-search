# Yêu cầu đề bài - HotpotQA Multihop Retrieval

## 1. Bài toán được chọn

Project tập trung vào bài toán **HotpotQA Multihop Retrieval** trong nhóm **Hybrid Information Retrieval**.

Mục tiêu của hệ thống là nhận một câu hỏi tự nhiên phức tạp và trả về danh sách top-k documents liên quan nhất từ corpus HotpotQA.

Phát biểu bài toán:

```text
Input:
  - Một corpus documents từ HotpotQA
  - Một câu truy vấn/câu hỏi tự nhiên

Output:
  - Top-k documents liên quan tới câu hỏi
  - Điểm ranking/relevance cho từng document
```

Điểm quan trọng của HotpotQA là nhiều câu hỏi không thể trả lời chỉ bằng một document. Hệ thống cần retrieve đủ nhiều documents/supporting evidence để phục vụ reasoning nhiều bước.

## 2. Đặc thù multihop retrieval

HotpotQA thuộc bối cảnh **multiple-hop scenario**.

Trong multiple-hop retrieval, thông tin cần tìm thường nằm rải rác ở nhiều documents. Một query có thể cần:

1. Tìm document/evidence thứ nhất.
2. Dựa trên thông tin từ document thứ nhất để tìm document/evidence tiếp theo.
3. Kết hợp nhiều documents để có đủ thông tin trả lời câu hỏi.

Ví dụ dạng truy vấn:

```text
What occupations do both Ian Hunter and Rob Thomas have?
```

Để trả lời câu hỏi này, hệ thống cần tìm thông tin về cả Ian Hunter và Rob Thomas, sau đó xác định nghề nghiệp chung của hai người.

Vì vậy, evaluation không chỉ đo hệ thống có tìm được một document liên quan hay không, mà còn cần đo hệ thống có tìm đủ toàn bộ supporting documents hay không.

## 3. Dataset sử dụng

Dataset chính của project là:

```text
HotpotQA
```

Dataset được sử dụng trực tiếp thông qua thư viện Python:

```python
ir_datasets
```

Theo yêu cầu đề bài, HotpotQA trong multiple-hop scenario có quy mô lớn:

| Thành phần | Mô tả |
|------------|-------|
| Documents | hơn 5 triệu documents, tùy version |
| Queries | khoảng hơn 100k queries, tùy version |
| Loại truy vấn | phức tạp, nhiều bước, multihop |
| Nguồn load | `ir_datasets` |

Trong baseline phase 1, có thể dùng subset nhỏ để đảm bảo hệ thống chạy được end-to-end:

```text
nano-beir/hotpotqa
```

Sau khi baseline ổn định, có thể mở rộng lên split lớn hơn:

```text
beir/hotpotqa
beir/hotpotqa/dev
```

## 4. Yêu cầu hệ thống

Project nên phát triển theo hướng **system**, không chỉ là một script benchmark offline.

Hệ thống tối thiểu nên có các thành phần:

- data loader cho HotpotQA;
- preprocessing và normalization documents/queries/qrels;
- sparse index;
- dense/vector index;
- retrieval service;
- API backend;
- frontend demo;
- evaluation pipeline;
- logging hoặc thống kê latency/QPS.

Ngoài baseline ban đầu, hệ thống nên có định hướng bổ sung:

- database hoặc persistent document store;
- persistent index storage;
- caching query results;
- caching query embeddings;
- caching intermediate hop results cho multihop retrieval;
- monitoring latency và throughput.

Mục tiêu là hướng tới một retrieval system có thể mở rộng, không chỉ chạy thử nghiệm nhỏ.

## 5. Hướng retrieval cần xây dựng

Solution nên đi theo hướng **dense-sparse hybrid retrieval** cho HotpotQA.

Các nhóm phương pháp cần có trong baseline hoặc roadmap:

## 5.1. Sparse retrieval

Ví dụ:

```text
BM25
```

Vai trò:

- bắt lexical overlap;
- mạnh với entity, tên riêng, ngày tháng, cụm từ xuất hiện trực tiếp;
- là baseline quan trọng cho HotpotQA vì nhiều câu hỏi chứa entity hoặc title clue.

## 5.2. Dense retrieval

Ví dụ:

```text
SentenceTransformer / DPR-style encoder + FAISS
```

Vai trò:

- tìm kiếm theo ngữ nghĩa;
- hỗ trợ paraphrase;
- giảm phụ thuộc vào exact keyword matching.

## 5.3. Hybrid dense-sparse retrieval

Ví dụ:

```text
BM25 + dense vector retrieval + rank fusion
```

Có thể dùng:

- Reciprocal Rank Fusion;
- weighted score fusion;
- reranking;
- dense-sparse hybrid vector retrieval.

Mục tiêu là tận dụng cả lexical matching và semantic matching.

## 5.4. Multihop retrieval

Vì dataset là HotpotQA, hệ thống cần có cơ chế hoặc baseline cho retrieval nhiều bước.

Một baseline multihop có thể là:

```text
Hop 1:
  Retrieve top documents bằng query gốc.

Hop 2:
  Dùng documents/evidence từ hop 1 để mở rộng query.
  Retrieve tiếp documents ở hop 2.

Fusion:
  Kết hợp kết quả từ nhiều hop.
```

Mục tiêu là retrieve đủ supporting documents để phục vụ reasoning nhiều bước.

## 6. Metrics đánh giá độ chính xác

Đề bài yêu cầu đánh giá độ chính xác bằng các ranking metrics.

Các metric chính:

```text
Precision@k
Recall@k
```

Nên bổ sung thêm các metric phù hợp với retrieval ranking:

```text
MRR@k
nDCG@k
Full-support Recall@k
```

Ý nghĩa:

| Metric | Ý nghĩa |
|--------|---------|
| Precision@k | Tỷ lệ documents trong top-k là relevant |
| Recall@k | Tỷ lệ relevant documents được tìm thấy trong top-k |
| MRR@k | Vị trí của relevant document đầu tiên |
| nDCG@k | Chất lượng ranking có xét thứ tự |
| Full-support Recall@k | Top-k có chứa đủ tất cả supporting documents hay không |

`Full-support Recall@k` rất quan trọng trong HotpotQA vì một câu hỏi thường cần nhiều supporting documents. Nếu hệ thống chỉ tìm được một phần evidence thì chưa đủ tốt cho multihop reasoning.

Ví dụ:

```text
gold docs = {A, B}
top-10 chứa A và B -> full_support_recall@10 = 1
top-10 chỉ chứa A  -> full_support_recall@10 = 0
```

## 7. Metrics đánh giá real-time

Đề bài yêu cầu đánh giá tính realtime của hệ thống.

Các metric chính:

```text
Latency p50
Latency p95
Latency p99
QPS
```

Ý nghĩa:

| Metric | Ý nghĩa |
|--------|---------|
| Latency p50 | Độ trễ trung vị |
| Latency p95 | Độ trễ ở phân vị 95 |
| Latency p99 | Độ trễ ở phân vị 99 |
| QPS | Queries per Second |

Với multihop retrieval, latency đặc biệt quan trọng vì một query có thể phải chạy nhiều lượt retrieval. Do đó cần so sánh không chỉ accuracy mà cả chi phí thời gian giữa single-pass retrieval và iterative multihop retrieval.

## 8. Yêu cầu đầu ra

Project cần có các đầu ra sau:

1. Một hệ thống retrieval chạy được trên HotpotQA hoặc subset HotpotQA.
2. Baseline theo hướng dense-sparse retrieval.
3. Có xử lý hoặc baseline cho multihop retrieval.
4. Benchmark với các phương pháp:
   - BM25;
   - Dense retrieval;
   - Hybrid retrieval;
   - Multihop retrieval.
5. Metrics đầy đủ:
   - Precision@k;
   - Recall@k;
   - MRR@k;
   - nDCG@k;
   - Full-support Recall@k;
   - latency p50/p95/p99;
   - QPS.
6. Backend API cho truy vấn realtime.
7. Frontend demo để nhập query và xem top-k documents.
8. Report/slide mô tả:
   - bài toán HotpotQA multihop retrieval;
   - dataset;
   - kiến trúc hệ thống;
   - phương pháp retrieval;
   - metrics;
   - kết quả benchmark;
   - hạn chế và hướng phát triển.

## 9. Baseline phase 1 đề xuất

Baseline phase 1 nên tập trung vào correctness và reproducibility.

Các method nên có:

| Method | Vai trò |
|--------|---------|
| BM25 | Sparse retrieval baseline |
| Dense FAISS | Dense retrieval baseline |
| Hybrid RRF | Dense-sparse hybrid baseline |
| Iterative Hybrid | Multihop retrieval baseline |

Dataset phase 1:

```text
nano-beir/hotpotqa
```

Sau phase 1, mở rộng lên:

```text
beir/hotpotqa/dev
```

## 10. Hướng phát triển sau baseline

Sau khi baseline chạy đúng, nên phát triển tiếp theo hướng system:

- thêm persistent database/document store;
- lưu persistent BM25/FAISS index;
- cache query embedding;
- cache query result;
- cache kết quả hop 1 trong multihop retrieval;
- thêm reranker;
- thử dense model mạnh hơn;
- tune hybrid fusion;
- tune multihop query expansion;
- benchmark trên dataset lớn hơn;
- đo latency/QPS ổn định hơn.
