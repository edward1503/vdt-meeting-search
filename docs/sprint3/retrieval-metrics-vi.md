# Metrics Đánh Giá Retrieval Trong Sprint 3

## 1. Vì sao cần nhiều metric?

Retrieval không chỉ hỏi "có trả về document đúng không?". Ta còn cần biết:

- Document đúng có nằm trong top đầu không?
- Có lấy đủ tất cả evidence cần cho multi-hop không?
- Ranking có tốt không hay đúng doc bị đẩy xuống cuối?
- Hệ thống nhanh hay chậm?
- Có trade-off nào giữa chất lượng và latency?

Sprint 3 dùng các metric chính:

```text
precision@k
recall@k
mrr@k
ndcg@k
full_support_recall@k
latency_p50_ms / latency_p95_ms / latency_p99_ms
qps
```

Với HotpotQA, metric quan trọng nhất không phải lúc nào cũng là `precision@10`. Vì mỗi query thường chỉ có 2 support documents, top 10 dù hoàn hảo cũng chỉ có 2 relevant docs. Do đó `precision@10` có trần thấp. Metric cần nhìn kỹ hơn là `recall@10`, `nDCG@10`, và đặc biệt `full_support_recall@10`.

## 2. Ký hiệu chung

Với một query:

- `k`: số kết quả đầu tiên được xét, ví dụ `k=10`.
- `returned@k`: danh sách top-k document hệ thống trả về.
- `relevant`: tập document đúng theo qrels.
- `hit`: một document trong top-k cũng nằm trong `relevant`.

Ví dụ HotpotQA:

```text
relevant = {doc_A, doc_B}
returned@10 = [doc_X, doc_A, doc_Y, doc_Z, doc_B, doc_M, doc_N, doc_P, doc_Q, doc_R]
```

Ở đây có 2 hit: `doc_A` và `doc_B`.

## 3. Precision@k

### Công thức

```text
precision@k = số relevant docs trong top-k / k
```

Với ví dụ trên:

```text
precision@10 = 2 / 10 = 0.2
```

### Ý nghĩa

Precision đo độ "sạch" của top-k. Nếu precision cao, nhiều kết quả trong top-k là relevant.

### Use case

Precision hữu ích khi:

- User chỉ đọc một số ít kết quả.
- Cần giảm nhiễu trong UI.
- Corpus có nhiều relevant documents cho mỗi query.
- Search use case giống web/product search, nơi nhiều result có thể đúng.

### Với HotpotQA, cần đọc cẩn thận

HotpotQA/BEIR thường có 2 support docs cho mỗi query. Nếu đánh giá `precision@10`, trần lý thuyết thường là:

```text
max precision@10 = 2 / 10 = 0.2
```

Vì vậy `precision@10 = 0.1500` của `tv_hybrid` không có nghĩa là hệ thống chỉ đúng 15% theo nghĩa thông thường. Nó nghĩa là trung bình top 10 chứa 1.5 support docs:

```text
0.1500 * 10 = 1.5 relevant docs / query
```

So với trần 2 relevant docs:

```text
1.5 / 2 = 75% support docs được lấy trong top 10
```

### Tốt hay xấu?

Với HotpotQA top-10:

- `0.20`: gần như hoàn hảo nếu mỗi query có đúng 2 relevant docs.
- `0.15`: khá tốt, tương ứng trung bình 1.5/2 support docs.
- `0.10`: trung bình 1/2 support docs, thường thiếu một hop.
- `<0.05`: yếu, đa số query miss evidence.

Nhưng không nên dùng precision một mình để kết luận.

## 4. Recall@k

### Công thức

```text
recall@k = số relevant docs trong top-k / tổng số relevant docs
```

Với ví dụ:

```text
relevant = {doc_A, doc_B}
returned@10 chứa cả doc_A và doc_B
recall@10 = 2 / 2 = 1.0
```

Nếu chỉ lấy được `doc_A`:

```text
recall@10 = 1 / 2 = 0.5
```

### Ý nghĩa

Recall đo khả năng không bỏ sót document đúng. Với retrieval làm đầu vào cho QA, recall rất quan trọng: reader không thể trả lời đúng nếu evidence không được retrieve.

### Use case

Recall hữu ích khi:

- Retrieval là bước trước reader/reranker.
- Muốn đảm bảo không mất evidence.
- Có thể chấp nhận top-k hơi nhiễu miễn là document đúng có mặt.

### Tốt hay xấu?

Trong Sprint 3:

```text
es_bm25 recall@10   = 0.6025
tv_dense recall@10  = 0.7225
tv_hybrid recall@10 = 0.7500
```

Diễn giải:

- BM25 lấy được khoảng 60.25% support docs trong top 10.
- Dense lấy được khoảng 72.25%.
- Hybrid lấy được khoảng 75%.

Với HotpotQA, `recall@10 = 0.75` là tín hiệu tốt cho baseline full-corpus, nhưng vẫn còn thiếu nhiều support docs thứ hai cho multi-hop QA.

## 5. Full Support Recall@k

### Công thức

Với mỗi query:

```text
full_support@k = 1 nếu tất cả relevant docs đều nằm trong top-k
full_support@k = 0 nếu thiếu ít nhất một relevant doc
```

Sau đó lấy trung bình trên toàn bộ queries:

```text
full_support_recall@k = trung bình(full_support@k)
```

Ví dụ:

```text
Query 1: top-10 có cả doc_A và doc_B -> 1
Query 2: top-10 chỉ có doc_A          -> 0
Query 3: top-10 có cả doc_C và doc_D -> 1

full_support_recall@10 = (1 + 0 + 1) / 3 = 0.6667
```

### Ý nghĩa

Đây là metric rất quan trọng cho HotpotQA. Multi-hop QA thường cần đủ cả hai support docs. Lấy được một doc đúng nhưng thiếu doc còn lại vẫn có thể không đủ để trả lời.

`recall@10` có thể cao nhưng `full_support_recall@10` vẫn thấp nếu hệ thống thường chỉ lấy được một trong hai hop.

### Use case

Full support recall hữu ích khi:

- Dataset cần nhiều evidence documents.
- Bài toán là multi-hop QA.
- Muốn đo khả năng cung cấp đủ context cho reader.
- Cần phân tích lỗi "retrieve đúng một nửa".

### Tốt hay xấu?

Sprint 3:

```text
es_bm25 full_support_recall@10   = 0.365
tv_dense full_support_recall@10  = 0.515
tv_hybrid full_support_recall@10 = 0.545
```

Diễn giải:

- BM25 lấy đủ cả hai support docs cho 36.5% query.
- Dense lấy đủ cho 51.5% query.
- Hybrid lấy đủ cho 54.5% query.

Đây là cải thiện rõ, nhưng cũng chỉ ra bài toán còn khó: gần một nửa query vẫn thiếu ít nhất một support doc trong top 10.

Muốn cải thiện metric này, hướng tốt nhất thường là multi-hop retrieval hoặc reranker, không chỉ tăng `top_k` một cách mù quáng.

## 6. MRR@k

### Công thức

MRR là Mean Reciprocal Rank. Với mỗi query:

```text
RR = 1 / rank của relevant doc đầu tiên
```

Nếu document đúng đầu tiên nằm rank 1:

```text
RR = 1 / 1 = 1.0
```

Nếu document đúng đầu tiên nằm rank 4:

```text
RR = 1 / 4 = 0.25
```

Nếu không có document đúng trong top-k:

```text
RR = 0
```

MRR@k là trung bình RR trên tất cả queries.

### Ý nghĩa

MRR đo document đúng đầu tiên xuất hiện sớm đến đâu. Nó thưởng rất mạnh cho việc đưa relevant doc lên rank 1.

### Use case

MRR hữu ích khi:

- User thường chỉ xem kết quả đầu tiên.
- Cần ít nhất một evidence doc xuất hiện rất sớm.
- Bài toán chỉ cần một câu trả lời/document đúng.

### Hạn chế với HotpotQA

HotpotQA cần nhiều support docs. MRR chỉ quan tâm relevant doc đầu tiên. Nếu rank 1 đúng nhưng support doc thứ hai mất hút, MRR vẫn cao.

Ví dụ:

```text
Query cần {doc_A, doc_B}
returned@10 = [doc_A, doc_X, doc_Y, ...]
MRR = 1.0
full_support = 0
```

Vì vậy MRR cao không đảm bảo multi-hop evidence đầy đủ.

Sprint 3:

```text
tv_hybrid mrr@10 = 0.8681
```

Điều này nói rằng `tv_hybrid` thường đưa ít nhất một support doc lên rất cao. Nhưng metric quyết định cho multi-hop vẫn là `full_support_recall@10`.

## 7. nDCG@k

### Công thức

nDCG là Normalized Discounted Cumulative Gain.

Trước hết tính DCG:

```text
DCG@k = sum(gain_i / log2(i + 1)) với i là rank bắt đầu từ 1
```

Trong benchmark này, qrels relevance thường là `1` cho support doc và `0` cho doc khác. Document đúng ở rank cao được thưởng nhiều hơn document đúng ở rank thấp.

Sau đó normalize bằng ranking lý tưởng:

```text
nDCG@k = DCG@k / IDCG@k
```

`IDCG@k` là DCG tốt nhất có thể nếu tất cả relevant docs được xếp lên đầu.

### Ví dụ trực giác

Hai ranking đều có 2 support docs trong top 10:

```text
Ranking A: [doc_A, doc_B, x, x, x, ...]
Ranking B: [x, x, x, x, doc_A, x, x, x, doc_B, x]
```

Recall@10 của cả hai đều là `1.0`, nhưng nDCG@10 của Ranking A cao hơn vì docs đúng nằm sớm hơn.

### Use case

nDCG hữu ích khi:

- Cần đánh giá chất lượng ranking, không chỉ có/không.
- User xem từ trên xuống.
- Relevant documents ở rank 1-3 quan trọng hơn rank 8-10.
- Muốn so sánh retriever tổng quát theo chuẩn IR.

### Tốt hay xấu?

Sprint 3:

```text
es_bm25 ndcg@10   = 0.5727
tv_dense ndcg@10  = 0.7082
tv_hybrid ndcg@10 = 0.7286
```

`tv_hybrid` không chỉ lấy được nhiều support docs hơn BM25, mà còn xếp chúng cao hơn. Đây là dấu hiệu ranking tốt hơn.

## 8. Latency percentiles: p50, p95, p99

### Công thức

Latency là thời gian xử lý một query, thường tính bằng milliseconds.

Percentile mô tả phân phối latency:

```text
p50 = 50% query nhanh hơn hoặc bằng mức này
p95 = 95% query nhanh hơn hoặc bằng mức này
p99 = 99% query nhanh hơn hoặc bằng mức này
```

Ví dụ:

```text
p95 = 2000 ms
```

Nghĩa là 95% query chạy trong 2 giây hoặc ít hơn, còn 5% chậm hơn 2 giây.

### Vì sao không chỉ nhìn average?

Average dễ bị che bởi outlier. Với user-facing API, tail latency quan trọng hơn. Một hệ thống trung bình nhanh nhưng thỉnh thoảng đứng 8 giây vẫn cho trải nghiệm xấu.

### Sprint 3 latency

Primary benchmark:

```text
es_bm25 p95   = 359.6319 ms
tv_dense p95  = 868.0033 ms
tv_hybrid p95 = 3089.2229 ms
```

Tuning `tv_hybrid k=50`:

```text
p95 = 2053.6018 ms
full_support_recall@10 = 0.535
```

Primary `tv_hybrid k=100`:

```text
p95 = 3089.2229 ms
full_support_recall@10 = 0.545
```

Giảm candidate từ 100 xuống 50 giúp p95 giảm khoảng 1 giây, trong khi full support recall chỉ giảm 0.010 absolute. Vì vậy report khuyến nghị `k=50` cho demo laptop.

## 9. QPS

### Công thức

```text
qps = số queries / tổng thời gian xử lý tính bằng giây
```

QPS là queries per second.

### Ý nghĩa

QPS đo throughput. Latency hỏi "một query mất bao lâu", còn QPS hỏi "mỗi giây xử lý được bao nhiêu query".

### Use case

QPS hữu ích khi:

- Chạy benchmark batch.
- Dự tính capacity server.
- So sánh config candidate size.
- Cần biết hệ thống chịu được bao nhiêu traffic.

### Sprint 3

```text
es_bm25 qps   = 5.9315
tv_dense qps  = 1.2499
tv_hybrid qps = 0.7935
```

BM25 throughput cao hơn vì chỉ chạy Elasticsearch lexical search. Hybrid thấp hơn vì phải encode query, chạy BM25, chạy TurboVec, fuse, rồi hydrate.

## 10. Đọc các metric cùng nhau

Không nên nhìn một metric đơn lẻ. Bảng Sprint 3 chính:

| Method | precision@10 | recall@10 | mrr@10 | ndcg@10 | full_support_recall@10 | p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `es_bm25` | 0.1205 | 0.6025 | 0.7108 | 0.5727 | 0.365 | 359.6319 |
| `tv_dense` | 0.1445 | 0.7225 | 0.8472 | 0.7082 | 0.515 | 868.0033 |
| `tv_hybrid` | 0.1500 | 0.7500 | 0.8681 | 0.7286 | 0.545 | 3089.2229 |

Diễn giải đúng:

- `es_bm25` nhanh nhất, nhưng thiếu nhiều evidence multi-hop.
- `tv_dense` tăng mạnh quality so với BM25, latency vẫn thấp hơn hybrid.
- `tv_hybrid` quality tốt nhất, nhưng latency p95 cao nhất.
- `precision@10` nhìn thấp vì HotpotQA qrels sparse, thường chỉ có 2 relevant docs/query.
- `full_support_recall@10` là metric nói rõ nhất hệ thống đã đủ evidence cho multi-hop chưa.

## 11. Metric nào nên ưu tiên theo use case?

### Demo search nhanh trên laptop

Ưu tiên:

```text
p95 latency
full_support_recall@10
ndcg@10
```

Khuyến nghị:

```text
tv_hybrid k=50 rrf=30
```

Vì config này giữ quality gần best config nhưng latency dễ chịu hơn.

### Benchmark retrieval chất lượng

Ưu tiên:

```text
ndcg@10
recall@10
full_support_recall@10
```

Khuyến nghị:

```text
tv_hybrid k=100 rrf=30
```

Vì đây là best quality trong Sprint 3 primary/tuning set.

### Multi-hop QA reader

Ưu tiên:

```text
full_support_recall@k
recall@k
```

Nếu reader cần đủ hai support docs, `full_support_recall@k` quan trọng hơn MRR. Một support doc ở rank 1 chưa đủ nếu doc thứ hai bị miss.

### UI search thông thường

Ưu tiên:

```text
precision@5 hoặc precision@10
ndcg@10
p95 latency
```

Nhưng nếu qrels chỉ có 2 docs/query như HotpotQA, precision@10 không phản ánh hết chất lượng cảm nhận của user.

### Production API

Ưu tiên:

```text
p95 latency
p99 latency
qps
cache hit rate
quality guardrail như recall@10 hoặc ndcg@10
```

Sprint 3 chưa đo cache hit rate trong benchmark, vì benchmark đo retriever trực tiếp hơn là production traffic.

## 12. Những bẫy diễn giải sai

### Bẫy 1: Thấy precision@10 = 0.15 rồi kết luận kém

Sai vì HotpotQA thường chỉ có 2 relevant docs/query. Precision@10 tối đa thường là 0.2. `0.15` tương đương 75% trần lý thuyết trong setting 2 support docs.

### Bẫy 2: MRR cao rồi nghĩ đủ evidence

MRR chỉ cần relevant doc đầu tiên đứng cao. Multi-hop cần đủ support docs. Luôn kiểm tra `full_support_recall@k`.

### Bẫy 3: Recall cao nhưng ranking xấu

Nếu relevant docs nằm rank 9-10, recall@10 vẫn cao nhưng user/reader có thể khó dùng hơn. Kiểm tra thêm `nDCG@10`.

### Bẫy 4: Chỉ tối ưu quality mà quên latency

`tv_hybrid k=100` tốt hơn `k=50` về full-support 0.010 absolute, nhưng p95 chậm hơn khoảng 1 giây trong benchmark Sprint 3. Với demo, trade-off này có thể không đáng.

### Bẫy 5: So trực tiếp với paper QA end-to-end

Sprint 3 là retriever. Nhiều paper HotpotQA báo Answer F1, Support F1, Joint F1 sau khi có reader/reranker/multi-hop training. Không nên so trực tiếp với `precision@10` hay `nDCG@10` nếu metric khác nhau.

## 13. Cách report kết quả nên dùng

Một câu report tốt:

```text
Trên 200 query của beir/hotpotqa/dev, tv_hybrid đạt recall@10=0.7500,
ndcg@10=0.7286, full_support_recall@10=0.545, p95=3089.2229 ms.
So với BM25, full_support_recall@10 tăng từ 0.365 lên 0.545,
nhưng p95 latency tăng từ 359.6319 ms lên 3089.2229 ms.
```

Một câu report dễ gây hiểu nhầm:

```text
Precision chỉ có 15%, hệ thống kém.
```

Vì câu này bỏ qua trần precision của HotpotQA và không nói recall/full-support.

## 14. Kết luận thực dụng

Với Sprint 3, đọc metric như sau:

- `precision@10` cho biết top 10 sạch tới đâu, nhưng bị trần thấp vì qrels sparse.
- `recall@10` cho biết lấy được bao nhiêu support docs.
- `full_support_recall@10` cho biết có đủ evidence multi-hop hay không.
- `mrr@10` cho biết support doc đầu tiên có lên sớm không.
- `nDCG@10` cho biết ranking tổng thể tốt không.
- `p95/p99` cho biết user tail latency có ổn không.
- `qps` cho biết throughput.

Nếu chỉ chọn một quality metric cho HotpotQA multi-hop, hãy nhìn `full_support_recall@10`. Nếu chọn một metric ranking tổng quát, hãy nhìn `nDCG@10`. Nếu chọn một metric vận hành, hãy nhìn `p95 latency`.
