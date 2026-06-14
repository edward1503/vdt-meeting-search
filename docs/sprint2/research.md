# Nghiên cứu Sprint 2: Truy hồi 5M tài liệu và tìm kiếm multi-hop

Ngày: 2026-06-11

## Tóm tắt quyết định

Không nên bắt đầu bằng cách embed và index toàn bộ 5M tài liệu dưới dạng dense vectors trong Elasticsearch trên laptop hiện tại. Máy đủ tốt để phát triển và benchmark theo từng nấc, nhưng không thoải mái cho một hệ vector search local ở quy mô đầy đủ.

Hướng Sprint 2 nên đi:

1. Dùng Elasticsearch chủ yếu cho BM25, filter, metadata và hybrid retrieval.
2. Chỉ thêm dense embeddings sau khi đã có baseline BM25, và benchmark theo từng nấc: 100k, 500k, 1M, rồi mới tới 5M.
3. Ưu tiên embedding nhỏ, ví dụ 384 hoặc 512 chiều, kèm vector indexing đã quantize nếu version/license hỗ trợ.
4. Xây tầng multi-hop retrieval ở phía trên Elasticsearch bằng graph expansion, query decomposition, beam retrieval và reranking.
5. Đánh giá bằng support-evidence recall, không chỉ final answer accuracy.

## Giới hạn của máy hiện tại

Spec máy đọc được:

| Thành phần | Giá trị |
|---|---|
| Model | MSI GF63 Thin 10SCXR |
| CPU | Intel Core i5-10300H |
| CPU cores | 4 cores / 8 threads |
| RAM | Khoảng 16 GB |
| GPU | NVIDIA GTX 1650 Max-Q |
| VRAM | Khoảng 4 GB |
| Ổ còn trống lớn nhất | E: khoảng 366 GB free |

Máy này đủ để dev, chạy benchmark nhỏ, và có thể thử nghiệm tới khoảng 1M vectors nếu cấu hình cẩn thận. Nó không phù hợp để coi như môi trường production cho 5M+ vectors, đặc biệt nếu tài liệu nguồn còn bị chunk thành nhiều đoạn.

## Có nên embed 5M documents vào Elasticsearch không?

Câu trả lời ngắn: chỉ nên làm như một thí nghiệm theo từng nấc, không nên là bước triển khai đầu tiên.

Điểm mơ hồ quan trọng là `5M documents` nghĩa là 5M vectors cuối cùng, hay là 5M tài liệu nguồn rồi sau đó còn chunk. Nếu mỗi document thành 3-10 chunks, số vector thật sẽ là 15M-50M. Mức đó là quá nặng cho laptop này.

Ước lượng dung lượng vector float32 thô cho 5M vectors:

| Số chiều embedding | Dung lượng raw vector cho 5M vectors |
|---:|---:|
| 384 | Khoảng 7.2 GiB |
| 768 | Khoảng 14.3 GiB |
| 1024 | Khoảng 19.1 GiB |
| 1536 | Khoảng 28.6 GiB |

Các con số trên chưa tính HNSW graph overhead, Lucene segment overhead, stored fields, metadata, text gốc, doc values, JVM heap và OS page cache. Trong thực tế, một Elasticsearch vector index chạy tốt thường cần đủ RAM cho graph/vector data nóng ở ngoài JVM heap.

Elasticsearch hỗ trợ `dense_vector`, approximate kNN, HNSW indexing, và các lựa chọn vector quantization như `int8_hnsw`, `int4_hnsw`, cùng các biến thể BBQ tùy version/license. Disk-backed BBQ có tồn tại, nhưng biến thể thiên về disk gắn với tính năng thương mại của Elastic.

Tài liệu chính thức:

- Elasticsearch `dense_vector`: <https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/dense-vector>
- Elasticsearch kNN search: <https://www.elastic.co/docs/solutions/search/vector/knn>
- Elasticsearch BBQ: <https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/bbq>
- Elastic vector hardware discussion: <https://www.elastic.co/search-labs/blog/elasticsearch-vector-profile-gcp>

Không nên xem GTX 1650 Max-Q local là accelerator thực tế cho Elasticsearch vector indexing. GPU vector indexing của Elastic hướng tới GPU NVIDIA mới hơn, kèm version/license cụ thể, nên không phải giả định phù hợp cho laptop này.

## Kế hoạch Elasticsearch khuyến nghị

Vẫn nên dùng Elasticsearch, nhưng dùng đúng vai trò:

1. BM25 và filter phải là nền tảng chính. Index metadata của meeting, title, speaker, timestamp, project, topic và normalized entities.
2. Lưu text theo chunk, không lưu nguyên document dài làm đơn vị truy hồi chính. Chunk size nên tune theo evidence, khả năng hợp lý là 200-500 tokens cho meeting transcript search.
3. Chỉ thêm embeddings sau khi đã có baseline BM25.
4. Bắt đầu bằng embedding model nhỏ, khoảng 384d hoặc 512d. Tránh 1024d hoặc 1536d cho tới khi có bằng chứng recall tăng đủ đáng để trả chi phí.
5. Đặt Elasticsearch data ở ổ `E:` vì còn nhiều dung lượng nhất.
6. Index theo từng nấc: 100k -> 500k -> 1M -> 5M vectors.
7. Bulk indexing, tắt replicas khi ingest, và dùng refresh interval dài hơn hoặc tắt refresh tạm thời.
8. Giữ JVM heap khoảng 4-6 GB trên máy 16 GB RAM, để lại RAM cho OS cache.
9. Nếu được, giữ raw documents đầy đủ ở storage khác. Elasticsearch chỉ nên giữ chunks có thể search, IDs, snippets và metadata.
10. Thêm reranking trên candidate set nhỏ, ví dụ top 50-200 kết quả.

Milestone hợp lý của Sprint 2 là benchmark 1M vectors đủ chắc, không phải nhảy thẳng lên full 5M.

## Multi-hop retrieval ngoài naive iterative search

Vấn đề chính của naive iterative retrieval là nó commit quá sớm vào một đường suy luận. Nếu hop 1 bỏ lỡ bridge entity hoặc lấy nhầm distractor, các hop sau thường hỏng theo. Các hướng dưới đây cố gắng mở rộng, cấu trúc hóa hoặc kiểm chứng quá trình tìm kiếm.

### 1. Graph-based retrieval

Xây hoặc suy ra graph giữa chunks, entities, meetings, topics, speakers, dates và documents. Từ query, retrieve seed nodes trước, expand qua graph edges, rồi rerank candidate evidence.

Paper liên quan:

- Asai et al., `Learning to Retrieve Reasoning Paths over Wikipedia Graph for Question Answering`, ICLR 2020: <https://arxiv.org/abs/1911.10470>
- `Multi-Hop Paragraph Retrieval for Open-Domain Question Answering`, ACL 2019: <https://aclanthology.org/P19-1222/>
- `Document Graph Network for Multi-hop Reading Comprehension`, EMNLP-IJCNLP 2019: <https://aclanthology.org/D19-5306/>
- `DEHG: A Dynamic Heterogeneous Graph Reasoning Framework for Open-Domain Question Answering`, Findings NAACL 2022: <https://aclanthology.org/2022.findings-naacl.12/>

Độ phù hợp với meeting search: rất mạnh. Meeting tự nhiên đã có entities, speakers, decisions, agenda items và follow-up links.

### 2. Multi-hop dense retrieval

Train hoặc dùng dense retrievers được thiết kế riêng để model multi-hop evidence, thay vì chỉ bắn nhiều semantic search độc lập.

Paper liên quan:

- Xiong et al., `Answering Complex Open-Domain Questions with Multi-Hop Dense Retrieval`, ICLR 2021: <https://openreview.net/forum?id=EMHoBG0avc1>
- `ReSCORE: Label-free Iterative Retriever Training for Multi-hop QA Requiring Multiple Pieces of Evidence`, ACL 2025: <https://aclanthology.org/2025.acl-long.16/>

Độ phù hợp với meeting search: hứa hẹn, nhưng có thể tốn kém nếu chưa có labeled hoặc synthetic training set. Nên để sau khi đã có evaluation data.

### 3. Beam retrieval

Giữ nhiều candidate reasoning paths ở mỗi hop thay vì chỉ giữ một path duy nhất. Cách này giảm rủi ro hỏng từ hop đầu.

Paper liên quan:

- `End-to-End Beam Retrieval for Multi-Hop Question Answering`, NAACL 2024: <https://aclanthology.org/2024.naacl-long.96/>

Độ phù hợp với meeting search: mạnh. Có thể implement phía trên Elasticsearch bằng cách giữ top-k partial chains và rerank chains thay vì chỉ rerank từng chunk rời rạc.

### 4. Query decomposition với parallel retrieval

Tách câu hỏi phức thành các subqueries nguyên tử, retrieve song song cho từng subquery, sau đó join và rerank evidence. Khác với iterative retrieval ở chỗ các lượt search sau không phụ thuộc cứng vào document đầu tiên retrieve được.

Paper liên quan:

- Hướng `QD-RAG` cho multi-hop RAG: <https://arxiv.org/html/2507.00355v1>
- GoldEn Retriever, EMNLP-IJCNLP 2019: <https://aclanthology.org/D19-1261/>

Độ phù hợp với meeting search: rất mạnh. Ví dụ câu hỏi `Alice đã quyết định gì sau khi Bob nêu vấn đề deployment?` có thể tách thành actor, issue, decision và quan hệ thời gian.

### 5. PageRank hoặc Personalized Graph Expansion

Dùng query để seed graph nodes, sau đó chạy graph propagation như Personalized PageRank để tìm evidence liên quan. Cách này có thể giảm số lần gọi LLM lặp đi lặp lại.

Paper liên quan:

- `HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models`, NeurIPS 2024: <https://arxiv.org/abs/2405.14831>
- `HopRAG`, Findings ACL 2025: <https://arxiv.org/html/2502.12442v1>

Độ phù hợp với meeting search: rất tốt. Có thể làm bản lightweight bằng extracted entities và chunk links trước khi train retriever riêng.

### 6. Hierarchical retrieval

Index summary ở nhiều tầng, ví dụ meeting -> section -> chunk. Retrieve node cấp cao trước, rồi drill down vào evidence cụ thể.

Paper liên quan:

- `RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval`, ICLR 2024: <https://arxiv.org/abs/2401.18059>

Độ phù hợp với meeting search: mạnh với transcript dài và topic lặp lại. Có thể kém chính xác hơn với dạng paragraph-hop nhỏ kiểu HotpotQA, nhưng hữu ích cho meeting thật.

### 7. Hybrid sparse-dense retrieval

Kết hợp BM25 và dense vectors, rồi rerank. Sparse retrieval giữ tốt tên riêng, ngày tháng, issue ID và domain terms; dense retrieval giúp bắt paraphrase.

Paper liên quan:

- `Challenges in Generalization in Open Domain Question Answering`, SustainLP 2021: <https://aclanthology.org/2021.sustainlp-1.7/>

Độ phù hợp với meeting search: nên là baseline bắt buộc. Meeting search thường phụ thuộc vào tên người, project và thuật ngữ chính xác mà dense vectors có thể làm mờ.

### 8. Generate-then-ground / retrieval thiên về kiểm chứng

Cho LLM đề xuất subquestions, bridge entities hoặc tentative answers, rồi buộc hệ thống ground từng claim bằng evidence retrieve được.

Paper liên quan:

- `GenGround`: <https://arxiv.org/html/2406.14891v2>
- `LevelRAG`: <https://arxiv.org/html/2502.18139v1>

Độ phù hợp với meeting search: hữu ích cho chất lượng answer, nhưng cần bị ràng buộc bởi evidence vì meeting có thể chứa thông tin vận hành nhạy cảm hoặc cần độ chính xác cao.

## HotpotQA và hướng đánh giá

HotpotQA vẫn là benchmark hữu ích vì yêu cầu nhiều supporting documents và sentence-level supporting facts. Dù production corpus là meeting transcripts, HotpotQA vẫn gợi ý cách thiết kế evaluation cho retrieval.

Tài liệu tham khảo:

- HotpotQA paper: <https://arxiv.org/abs/1809.09600>
- HotpotQA ACL Anthology entry: <https://aclanthology.org/D18-1259/>
- Hướng counterfactual/memory-robust evaluation: <https://arxiv.org/html/2402.11924v5>

Với project này, nên đánh giá ít nhất:

1. Recall@k cho gold support chunks.
2. Khả năng recover đúng toàn bộ support evidence qua nhiều hop.
3. Answer accuracy kèm citations.
4. Latency mỗi query.
5. Index size và memory pressure.
6. Failure cases: miss bridge entity, sai thứ tự thời gian, nhầm entity trùng tên, và distractors giống về semantic.

## Kiến trúc Sprint 2 đề xuất

Kiến trúc khuyến nghị là hybrid graph-aware retrieval stack:

```text
User question
  -> query analyzer
  -> parallel retrieval branches
       -> BM25 Elasticsearch retrieval
       -> vector Elasticsearch retrieval
       -> entity graph expansion / PPR
       -> optional query decomposition
  -> evidence merger
  -> chain or cluster reranker
  -> answer generator with citations
  -> verifier checks answer against retrieved evidence
```

Các cấu trúc dữ liệu lõi:

1. `chunk`: đoạn text có thể search, kèm meeting ID, timestamp, speaker và section.
2. `entity`: person, project, decision, action item, issue, date, organization, product hoặc technical term.
3. `edge`: chunk-entity, entity-entity, chunk-chunk adjacency, same-meeting, temporal-neighbor, topic-neighbor.
4. `evidence_chain`: nhóm chunks có thứ tự hoặc không thứ tự, cùng nhau trả lời một câu hỏi.

## Thứ tự triển khai khuyến nghị

1. Xây BM25-only baseline trong Elasticsearch.
2. Thêm metadata filters chắc chắn: speaker, date, meeting, topic, project.
3. Thêm embeddings chiều nhỏ cho một slice dữ liệu giới hạn.
4. Tạo một evaluation set multi-hop nhỏ từ meeting data hoặc câu hỏi synthetic kiểu HotpotQA.
5. Implement hybrid candidate merging.
6. Thêm entity extraction và lightweight graph.
7. Thêm graph expansion từ seed chunks/entities.
8. Thêm query decomposition với parallel retrieval.
9. Thêm chain reranking và citation-aware answer generation.
10. Chạy benchmark 100k -> 500k -> 1M index trước khi quyết định 5M.

## Khuyến nghị cuối

Với Sprint 2, không nên đặt milestone chính là `5M dense vectors trong Elasticsearch`. Nên đặt milestone là `measured hybrid multi-hop retrieval`:

- Elasticsearch BM25 + metadata search làm nền tảng ổn định.
- Dense vectors là add-on có benchmark, bắt đầu nhỏ.
- Graph expansion và query decomposition là chiến lược multi-hop chính.
- Evaluation ở mức evidence, lấy cảm hứng từ HotpotQA.

Cách này phù hợp với laptop hiện tại, đồng thời vẫn để lại đường nâng cấp sạch lên server lớn hơn hoặc managed vector infrastructure sau này.

## Paraphrase robustness experiment

Sprint 2 bao gồm benchmark robustness trên 50 HotpotQA queries. Experiment tạo synonym paraphrases ở các mức thay thế eligible-token `20%`, `40%`, và `60%`, giữ named entities và map qrels qua `source_query_id`. Sau đó rerun `es_bm25`, `es_dense`, `es_hybrid`, và `es_iterative_hybrid` để đo metric degradation so với original queries.

Primary metrics:

- `recall@10`
- `full_support_recall@10`
- `ndcg@10`
- `mrr@10`
- `latency_p95_ms`

Kết quả nano benchmark hiện tại cho thấy hybrid ổn định nhất trên paraphrase set: `es_hybrid` giữ `recall@10 = 0.90` và `full_support_recall@10 = 0.80` ở cả ba mức syn020/syn040/syn060, thấp hơn original lần lượt `-0.01` và `-0.02`. BM25 dao động nhẹ quanh `recall@10 = 0.86-0.87`, dense giữ `recall@10 = 0.86`, còn iterative hybrid nhạy hơn ở `full_support_recall@10` với delta khoảng `-0.04`.
