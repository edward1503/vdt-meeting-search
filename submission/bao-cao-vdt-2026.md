# Không gian truy xuất bằng chứng full-corpus cho QA đa bước và tìm kiếm metadata ngữ nghĩa

[Họ và tên sinh viên], [Họ và tên mentor]1

1 [Đơn vị mentor hướng dẫn] - [email mentor hướng dẫn]

## 1. GIỚI THIỆU CHUNG

Trong các hệ thống hỏi đáp và tìm kiếm trên kho tài liệu lớn, bước truy xuất bằng chứng quyết định chất lượng của toàn bộ pipeline phía sau. Với bài toán HotpotQA, một câu hỏi thường cần nhiều tài liệu hỗ trợ; nếu hệ thống chỉ tìm được một tài liệu đúng nhưng thiếu tài liệu còn lại, câu trả lời cuối cùng vẫn có thể sai. Vì vậy đề tài không chỉ tối ưu việc tìm một tài liệu liên quan, mà xây dựng một không gian truy xuất bằng chứng có khả năng tìm đủ bộ tài liệu hỗ trợ trong top-k.

Mục tiêu của đề tài là xây dựng một hệ thống retrieval chạy được trên HotpotQA full corpus gồm 5,233,329 tài liệu, đánh giá bằng metric phù hợp với truy vấn đa bước, và mở rộng runtime sang demo dataset-first cho HotpotQA/VimQA. Phần cốt lõi gồm: ingest corpus full-scale, xây Elasticsearch BM25 index, sinh embedding bằng BGE-small, xây dense index nén bằng TurboVec, tích hợp hybrid retrieval, thiết kế bridge-aware retrieval để tìm tài liệu hỗ trợ thứ hai, benchmark/ablation, và triển khai API/UI để quan sát kết quả.

Hai phương pháp chính được chọn để báo cáo kết quả là `tv_hybrid` và `tv_bridge_title_entities_rrf`. `tv_hybrid` là baseline thực dụng: kết hợp BM25 của Elasticsearch với dense retrieval của TurboVec bằng Reciprocal Rank Fusion (RRF). `tv_bridge_title_entities_rrf` là phương pháp quality-first: bắt đầu từ kết quả first-hop của `tv_hybrid`, sinh truy vấn bridge từ title/entity của tài liệu đầu tiên, rồi truy xuất second-hop để giảm lỗi thiếu support document thứ hai.

Ý nghĩa thực tiễn của đề tài là tạo một nền tảng demo cho meeting/document search: người dùng cần kết quả liên quan, nhưng cũng cần biết kết quả nào là bằng chứng, tài liệu hỗ trợ nào còn thiếu, vì sao một phương pháp tốt hơn phương pháp khác, và có thể điều khiển không gian tìm kiếm bằng metadata như tác giả hoặc thời gian.

## 2. NỘI DUNG VÀ PHƯƠNG PHÁP

Hệ thống được tách thành hai pipeline: offline ingest và online retrieval. Pipeline offline biến corpus thô thành artifact ổn định: load BEIR HotpotQA, chuẩn hóa tài liệu, gán `numeric_id`, ghi JSONL staging shards, xây Elasticsearch BM25 index, sinh embedding shards bằng `BAAI/bge-small-en-v1.5`, xây TurboVec index 4-bit `.tvim`, và validate số lượng tài liệu. Pipeline online chạy khi người dùng nhập truy vấn: parser metadata tùy chọn, BM25 retrieval, TurboVec dense retrieval, hydrate kết quả dense qua Elasticsearch bằng `numeric_id`, gộp hạng bằng RRF, tùy chọn chạy bridge-aware second-hop retrieval, rồi trả kết quả lên dashboard kèm support overlay, highlighting, benchmark metadata và search history.

Kiến trúc tổng thể có thể tóm tắt như sau:

| Thành phần | Vai trò |
| --- | --- |
| Staging pipeline | Chuẩn hóa HotpotQA, giữ `doc_id`, sinh `numeric_id`, ghi 105 shards cho 5,233,329 tài liệu. |
| Elasticsearch | BM25 lexical retrieval, structured filter, document store và hydrate kết quả từ `numeric_id`. |
| Embedding service | Chạy BGE-small trên host GPU để tạo query embedding 384 chiều cho HotpotQA. |
| TurboVec | Dense vector search trên full corpus bằng index nén 4-bit, artifact khoảng 1.07 GB. |
| FastAPI | Cung cấp dataset profiles, search endpoints, benchmark/status/history APIs. |
| React dashboard | Hiển thị Search, Queries, Benchmarks, Indexes, Metadata, History và Status. |
| Redis/SQLite | Cache kết quả search lặp lại và lưu search history cục bộ. |

TurboVec không thay Elasticsearch. Elasticsearch vẫn là thành phần phù hợp nhất cho BM25, filter, lưu document, exact lookup và hydrate kết quả. TurboVec được dùng vì dense retrieval full-corpus bằng Elasticsearch `dense_vector`/HNSW trên 5.23M documents có rủi ro RAM và index overhead cao trong môi trường laptop mục tiêu. Với TurboVec, hệ thống giữ dense index nén 4-bit riêng, trả về `numeric_id`, rồi dùng Elasticsearch để lấy lại title/text/url và metadata. Như vậy lợi thế của TurboVec nằm ở dense vector search full-corpus cục bộ, còn Elasticsearch vẫn là xương sống lexical và document store.

Lợi ích chất lượng của TurboVec được thể hiện qua benchmark hybrid. Trên pilot 200 truy vấn, BM25 đơn thuần đạt `full_support@10=36.50%`, trong khi `tv_hybrid` kết hợp BM25 + TurboVec đạt `54.50%`. Nói cách khác, TurboVec đóng góp phần semantic retrieval cho hybrid system; hệ thống tốt lên không phải vì bỏ Elasticsearch, mà vì dùng đúng vai trò của cả hai thành phần.

Phương pháp `tv_hybrid` chạy song song hai đường retrieval. Đường BM25 dùng Elasticsearch `multi_match` trên `title^2` và `content` để bắt tín hiệu lexical/entity. Đường dense encode query bằng BGE-small, tìm nearest neighbors trong TurboVec, rồi hydrate các `numeric_id` qua Elasticsearch. Hai ranking được fuse bằng RRF để tránh phải calibrate score giữa BM25 và vector distance. Đây là phương pháp cân bằng nhất cho runtime: chất lượng cao hơn BM25, đơn giản hơn bridge, và phù hợp làm default interactive demo.

Phương pháp `tv_bridge_title_entities_rrf` nhắm trực tiếp vào lỗi đặc thù của HotpotQA: hệ thống thường tìm được một support document nhưng thiếu support document còn lại. Method này chạy first-hop `tv_hybrid`, lấy các ứng viên đầu, trích title/entity/lead terms để tạo bridge query, chạy second-hop retrieval, rank evidence chains rồi flatten thành top-10 documents. Cấu hình full test dùng `beam_size=1`, `max_bridge_terms=6`, đây là điểm đã tune từ pilot dev vì giữ được chất lượng nhưng giảm độ trễ so với beam rộng hơn.

Các phương pháp khác được dùng làm ablation: `es_bm25` là lexical baseline; `tv_dense` đo riêng dense retrieval; `tv_filtered_hybrid` dùng BM25/filter làm allowlist cho dense retrieval; `es_bm25_title` thử tăng title/entity lexical signal; `tv_hybrid_rerank` thử cross-encoder reranking; `tv_two_hop_bridge_rrf` là bridge baseline trước khi có title/entity bridge. Chúng không phải headline method, nhưng giúp giải thích vì sao kết luận cuối cùng chọn hybrid và bridge-aware retrieval.

Metric chính của HotpotQA là `full_support_recall@10`: một truy vấn chỉ được tính thành công khi toàn bộ gold support documents xuất hiện trong top-10. Các metric khác như `recall@10`, `MRR@10`, `nDCG@10`, p95 latency và QPS vẫn được báo cáo, nhưng nếu chỉ nhìn recall hoặc nDCG thì chưa đủ phản ánh yêu cầu multi-hop.

## 3. KẾT QUẢ THỰC HIỆN

Hệ thống đã hoàn thiện một workspace có thể chạy trên HotpotQA và VimQA trong cùng API/UI. Với HotpotQA, hệ thống stage và index toàn bộ 5,233,329 tài liệu, xây alias `hotpotqa_full_bm25_current`, tạo artifact TurboVec `hotpotqa_bge_small_4bit.tvim`, hỗ trợ BM25, dense, hybrid, filtered hybrid và bridge-aware benchmark. Với VimQA, hệ thống stage 3,623 tài liệu và 9,044 truy vấn/qrels, xây BM25/dense index và benchmark toàn bộ tập truy vấn.

Kết quả full test 7,405 truy vấn trên `beir/hotpotqa/test` cho hai phương pháp chính:

| Phương pháp | Full-support@10 | Recall@10 | MRR@10 | nDCG@10 | p95 latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 51.75% | 73.05% | 84.13% | 70.01% | 0.76 s |
| `tv_bridge_title_entities_rrf` | 60.08% | 75.85% | 82.51% | 71.20% | 1.60 s |
| Chênh lệch tuyệt đối | +8.33 điểm % | +2.80 điểm % | -1.62 điểm % | +1.19 điểm % | +0.84 s |
| Chênh lệch tương đối | +16.1% | +3.8% | -1.9% | +1.7% | +110.1% |

Kết quả này cho thấy bridge-aware retrieval tăng mạnh metric quan trọng nhất: complete evidence coverage. `full_support@10` tăng từ 51.75% lên 60.08%, tức thêm 8.33 điểm phần trăm, tương đương tăng tương đối khoảng 16.1%. Đổi lại, p95 latency tăng từ 0.76 giây lên 1.60 giây. Vì vậy `tv_hybrid` phù hợp hơn cho interactive default, còn `tv_bridge_title_entities_rrf` là quality-first benchmark method khi mục tiêu chính là tìm đủ bằng chứng.

Ablation 200 truy vấn ban đầu trên HotpotQA dev/qrels cho thấy vai trò của từng lớp retrieval.

| Nhóm | Phương pháp | Full-support@10 | Recall@10 | nDCG@10 | p95 latency | Kết luận |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Lexical | `es_bm25` | 36.50% | 60.25% | 57.27% | 359.63 ms | Nhanh, nhưng thiếu semantic support. |
| Dense | `tv_dense` | 51.50% | 72.25% | 70.82% | 868.00 ms | Dense retrieval cải thiện mạnh so với BM25. |
| Filtered hybrid | `tv_filtered_hybrid` | 45.50% | 68.00% | 67.35% | 1953.61 ms | Hữu ích khi có filter/metadata, không phải default chất lượng. |
| Hybrid | `tv_hybrid` | 54.50% | 75.00% | 72.86% | 3089.22 ms | Baseline hybrid mạnh nhất trong nhóm một lượt. |

Title-aware BM25 thử tăng trọng số title/entity bằng các field `title_exact`, `lead_sentence`, `title_repeat_content`. Kết quả cải thiện nhẹ metric lexical nhưng không cải thiện `full_support@10`.

| Phương pháp | Full-support@10 | Recall@10 | MRR@10 | nDCG@10 | p95 latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| `es_bm25` | 36.50% | 60.25% | 71.08% | 57.27% | 359.63 ms |
| `es_bm25_title` | 36.50% | 60.50% | 71.59% | 57.86% | 316.95 ms |

Reranker ablation dùng cross-encoder `cross-encoder/ms-marco-MiniLM-L-6-v2` để rerank top-100 candidates. Reranker cải thiện MRR/nDCG nhẹ nhưng không tạo net win ở full-support.

| Phương pháp | Full-support@10 | Recall@10 | MRR@10 | nDCG@10 | p95 latency | Paired full-support |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `tv_hybrid` | 54.50% | 75.00% | 86.91% | 72.91% | 2061.44 ms | 14 RRF-only wins |
| `tv_hybrid_rerank` | 54.50% | 75.50% | 92.68% | 74.64% | 1304.28 ms | 14 reranker-only wins |

Kết luận từ reranker là bottleneck không nằm chủ yếu ở xếp hạng lại nếu tài liệu đúng đã có trong candidates. Diagnostics cho thấy cần cải thiện candidate generation, đặc biệt là tìm support document thứ hai, trước khi đầu tư thêm vào reranking.

Bridge ablation 200 truy vấn cho thấy phương pháp title/entity bridge là bước đầu tiên tăng rõ metric chính.

| Phương pháp | Full-support@10 | Recall@10 | nDCG@10 | p95 latency | Success / 200 | Partial support |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 54.50% | 75.00% | 72.91% | 1146.58 ms | 109 | 82 |
| `tv_two_hop_bridge_rrf` | 56.00% | 74.50% | 69.99% | 2773.59 ms | 112 | 74 |
| `tv_bridge_title_entities_rrf` | 62.00% | 78.50% | 73.98% | 2670.36 ms | 124 | 66 |

So với `tv_hybrid`, `tv_bridge_title_entities_rrf` chuyển thêm 15/200 truy vấn thành full-support success và giảm 16 partial-support failures. Đây là bằng chứng đúng với giả thuyết: lỗi quan trọng nhất là thiếu tài liệu hỗ trợ thứ hai, không chỉ là rank tài liệu đầu tiên.

Bridge tuning tiếp tục giảm độ trễ. Cấu hình `beam1_terms6` giữ `full_support@10=62.00%` như beam rộng, nhưng p95 giảm mạnh.

| Cấu hình | Beam | Terms | Full-support@10 | Recall@10 | nDCG@10 | p95 latency | QPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `beam1_terms6` | 1 | 6 | 62.00% | 77.75% | 73.82% | 1224.99 ms | 1.1034 |
| `beam2_terms4` | 2 | 4 | 61.00% | 78.25% | 74.30% | 1758.89 ms | 0.7452 |
| `beam2_terms6` | 2 | 6 | 62.00% | 78.50% | 74.23% | 2593.46 ms | 0.6062 |
| `beam2_terms8` | 2 | 8 | 62.00% | 78.50% | 73.99% | 1827.80 ms | 0.6896 |
| `beam3_terms8` | 3 | 8 | 62.00% | 78.50% | 73.98% | 2670.36 ms | 0.5206 |

Các ablation bổ sung cũng cho thấy phạm vi ứng dụng của hệ thống. Paraphrase lexical-strong làm BM25 giảm mạnh hơn dense/hybrid, xác nhận dense retrieval bền hơn khi query đổi từ vựng. Metadata search có thể thu hẹp không gian ứng viên rất mạnh: kịch bản tác giả + ngày tạo giảm từ 5,233,329 tài liệu xuống 1,793 tài liệu, tương đương 99.9657%. Với VimQA, BM25 là phương pháp tốt nhất về cân bằng chất lượng và độ trễ: `recall@10=96.27%`, `MRR@10=86.06%`, `nDCG@10=88.59%`, p95 khoảng 84.42 ms; điều này cho thấy lựa chọn retrieval method phụ thuộc vào đặc tính dataset.

## 4. ĐÁNH GIÁ HIỆU QUẢ

Hiệu quả của giải pháp được đánh giá theo bốn nhóm: chất lượng truy xuất, độ trễ, khả năng giải thích, và vị trí so với các benchmark/paper liên quan.

Về chất lượng, kết quả quan trọng nhất là bridge-aware retrieval tăng `full_support@10` trên full test từ 51.75% lên 60.08%. Vì HotpotQA cần đủ evidence chain, mức tăng +8.33 điểm phần trăm này có ý nghĩa hơn việc tăng nhẹ một metric document-level thông thường. Bridge method cũng tăng `recall@10` và `nDCG@10`, nhưng giảm nhẹ `MRR@10`, phản ánh trade-off hợp lý: hệ thống ưu tiên lấy đủ cặp support hơn là chỉ đẩy support đầu tiên lên thật cao.

Về độ trễ, `tv_hybrid` vẫn tốt hơn cho demo tương tác vì p95 khoảng 0.76 giây trên full test, trong khi `tv_bridge_title_entities_rrf` khoảng 1.60 giây. Bridge method chậm hơn vì phải chạy second-hop retrieval và xử lý evidence chains. Kết quả tuning cho thấy có thể giảm đáng kể latency bằng `beam1_terms6`, nhưng để đưa bridge thành default runtime cần tiếp tục tối ưu caching, embedding call, hydration và song song hóa.

Về khả năng giải thích, hệ thống không chỉ trả danh sách document. Dashboard có query browser, support overlay, highlight query terms, benchmark surface, parsed metadata chips và search history. Các artifact diagnostics phân tách success, partial support, missing candidate và candidate-ranked-low. Điều này giúp giải thích vì sao reranker không thắng, vì sao title-aware BM25 chưa đủ, và vì sao bridge-aware candidate generation mới tạo gain chính.

So sánh với benchmark/paper cần phân biệt rõ loại metric. Với BEIR/Pyserini, có thể so sánh tương đối bằng `nDCG@10` trên HotpotQA retrieval. Bảng Pyserini BEIR công bố các baseline như BM25, SPLADE++, Contriever và BGE-base. Trong bối cảnh đó, `tv_bridge_title_entities_rrf` đạt `nDCG@10=71.20%`, cao hơn các baseline Pyserini được ghi nhận như BM25 multifield khoảng 60.3%, Contriever khoảng 63.8% và SPLADE++ khoảng 68.7%, đồng thời gần BGE-base khoảng 72.6%. Tuy nhiên đây không phải leaderboard claim tuyệt đối vì khác biệt về index construction, model size, quantization, latency environment và implementation details.

Với HotpotQA original paper, MDR, Beam Retrieval và IRCoT, so sánh an toàn nhất là so sánh về mục tiêu và thiết kế, không so sánh trực tiếp metric. HotpotQA paper báo cáo answer EM/F1, supporting-fact EM/F1 và joint EM/F1 cho hệ QA end-to-end; báo cáo này chỉ đánh giá retrieval evidence coverage trước reader/answer stage. MDR là learned multi-hop dense retriever, có metric chain/path riêng trên setup của họ. Beam Retrieval đánh giá trong môi trường candidate passage/reading-comprehension nhỏ hơn full-corpus retrieval. IRCoT interleave chain-of-thought với retrieval bằng LLM, trong khi hệ thống này dùng bridge heuristic không cần LLM. Vì vậy `full_support@10` không được so trực tiếp với answer F1 hoặc supporting-fact F1; nó là điều kiện tiền đề để reader phía sau có đủ bằng chứng.

Tổng hợp lại, điểm mạnh của đề tài là chạy được full corpus thay vì subset nhỏ, kết hợp lexical và dense retrieval đúng vai trò, dùng metric phù hợp với multi-hop QA, và có ablation chứng minh candidate generation quan trọng hơn reranking trong bối cảnh hiện tại. Giới hạn chính là bridge retrieval còn chậm, metadata hiện là synthetic/demo metadata, và hệ thống chưa có reader/answer stage để so sánh với QA papers theo EM/F1.

## 5. KẾT LUẬN

Đề tài đã xây dựng được hệ thống truy xuất bằng chứng full-corpus cho HotpotQA và mở rộng runtime sang VimQA. Hệ thống tách rõ pipeline offline và online, dùng Elasticsearch cho BM25/filter/document store, dùng TurboVec cho dense retrieval full-corpus cục bộ, và dùng FastAPI/React để tạo workspace quan sát kết quả. Hai phương pháp chính là `tv_hybrid` và `tv_bridge_title_entities_rrf`.

Kết quả full test cho thấy `tv_bridge_title_entities_rrf` đạt `full_support@10=60.08%`, cao hơn `tv_hybrid=51.75%`, tương đương +8.33 điểm phần trăm và +16.1% tương đối. Các ablation 200 truy vấn giải thích đường đi đến kết quả này: BM25 nhanh nhưng thiếu semantic support; dense và hybrid cải thiện rõ; title-aware BM25 không tăng full-support; reranker không tạo net win; bridge-aware title/entity retrieval mới xử lý trực tiếp lỗi thiếu support thứ hai.

Tính mới của đề tài nằm ở cách coi retrieval là bài toán tìm đủ bằng chứng thay vì chỉ tìm tài liệu liên quan đơn lẻ. Tính sáng tạo nằm ở bridge-aware retrieval cho support thứ hai, semantic metadata parser opt-in, và runtime dataset-first cho HotpotQA/VimQA. Tính hiệu quả được thể hiện bằng benchmark full test, ablation 200-query, latency trade-off và khả năng demo trực tiếp qua API/UI.

Hướng phát triển tiếp theo gồm: tối ưu latency cho bridge retrieval; cache và song song hóa second-hop; thêm diagnostics full test sâu hơn; dùng metadata thật cho meeting search; mở rộng semantic metadata evaluation; và thêm reader/LLM answer stage nếu muốn so sánh với HotpotQA QA papers bằng answer EM/F1, supporting-fact F1 và joint metrics.

## 6. TÀI LIỆU THAM KHẢO

[1] Yang et al., HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering, EMNLP 2018, https://aclanthology.org/D18-1259/.

[2] Thakur et al., BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models, 2021, https://arxiv.org/abs/2104.08663.

[3] Pyserini BEIR regression table and HotpotQA retrieval baselines, https://castorini.github.io/pyserini/2cr/beir.html.

[4] Cormack, Clarke, and Buettcher, Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods, SIGIR 2009.

[5] BAAI, `bge-small-en-v1.5` embedding model, https://huggingface.co/BAAI/bge-small-en-v1.5.

[6] Elasticsearch documentation, BM25 retrieval, index management, and dense vector search, https://www.elastic.co/guide/.

[7] TurboVec dense retrieval backend and project artifact `hotpotqa_bge_small_4bit.tvim`; design decision `docs/decisions/0006-sprint3-dense-backend.md`.

[8] Xiong et al., Answering Complex Open-Domain Questions with Multi-Hop Dense Retrieval, https://arxiv.org/abs/2009.12756.

[9] Facebook Research, Multi-Hop Dense Retrieval repository, https://github.com/facebookresearch/multihop_dense_retrieval.

[10] Zhang et al., End-to-End Beam Retrieval for Multi-Hop Question Answering, https://arxiv.org/html/2308.08973v2.

[11] Trivedi et al., Interleaving Retrieval with Chain-of-Thought Reasoning for Knowledge-Intensive Multi-Step Questions, ACL 2023, https://aclanthology.org/2023.acl-long.557/.

[12] Project reports and artifacts: Sprint 3 full-corpus retrieval report; Sprint 4 paraphrase, metadata and VimQA reports; Sprint 5 reranker, title-aware BM25, bridge-aware retrieval, bridge tuning, HotpotQA full-test benchmark, and `evaluation/results/hotpotqa_full`.
