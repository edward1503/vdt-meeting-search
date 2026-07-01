# Không gian truy xuất bằng chứng cho QA đa bước và tìm kiếm metadata ngữ nghĩa

[Họ và tên sinh viên], [Họ và tên mentor]1

1 [Đơn vị mentor hướng dẫn] - [email mentor hướng dẫn]

## 1. GIỚI THIỆU CHUNG

Trong các hệ thống hỏi đáp và tìm kiếm trên kho tài liệu lớn, bước quan trọng đầu tiên không phải là sinh câu trả lời, mà là truy xuất đúng các tài liệu làm bằng chứng cho bước suy luận phía sau. Với bài toán HotpotQA, một câu hỏi thường cần nhiều tài liệu hỗ trợ; nếu hệ thống chỉ tìm được một tài liệu đúng nhưng thiếu tài liệu còn lại, câu trả lời cuối cùng vẫn có thể sai. Vì vậy đề tài tập trung vào xây dựng một không gian truy xuất bằng chứng có khả năng chạy trên toàn bộ corpus, đánh giá đúng bài toán đa bước và mở rộng sang tìm kiếm theo metadata ngữ nghĩa.

Mục tiêu của đề tài gồm: (1) xây dựng pipeline ingest và truy xuất cho HotpotQA full corpus 5,233,329 tài liệu; (2) so sánh BM25, dense retrieval, hybrid RRF, filtered hybrid, reranker và bridge-aware retrieval bằng các metric phù hợp; (3) hỗ trợ runtime dataset-first cho HotpotQA và VimQA; (4) triển khai semantic metadata search để người dùng có thể nhập truy vấn tự nhiên chứa cả ý định nội dung và điều kiện metadata. Phần trực tiếp thực hiện bao gồm thiết kế pipeline dữ liệu, xây dựng index và artifact, tích hợp retrieval methods, benchmark/ablation, API/UI dataset-first, semantic metadata parser và báo cáo kết quả.

Ý nghĩa thực tiễn của đề tài là tạo một nền tảng demo cho meeting/document search: người dùng không chỉ cần kết quả liên quan theo từ khóa, mà còn cần biết kết quả nào là bằng chứng, vì sao được chọn, lỗi nằm ở sinh ứng viên hay xếp hạng, và có thể lọc theo thông tin như tác giả hoặc thời gian.

## 2. NỘI DUNG VÀ PHƯƠNG PHÁP

Kiến trúc được tách thành hai pipeline rõ ràng. Pipeline ingest/xử lý offline biến raw corpus thành artifact ổn định: chuẩn hóa tài liệu, gán `numeric_id`, tạo metadata tổng hợp, chia JSONL shards, xây Elasticsearch BM25 index, sinh embedding shards, xây TurboVec dense index 4-bit và validate số lượng tài liệu. Pipeline retrieval online chạy tại thời điểm người dùng nhập truy vấn: parser metadata tùy chọn, BM25 retrieval, TurboVec dense retrieval, hydrate kết quả qua Elasticsearch, gộp hạng bằng RRF hoặc bridge-aware strategy, sau đó trả kết quả lên dashboard kèm support overlay và highlighting.

Các phương pháp chính:

| Phương pháp | Vai trò |
| --- | --- |
| `es_bm25` | Mốc so sánh lexical nhanh trên Elasticsearch, dùng `title^2` và `content`. |
| `tv_dense` | Truy xuất ngữ nghĩa bằng TurboVec với BGE-small 384 chiều, nén 4-bit. |
| `tv_hybrid` | Gộp BM25 và dense candidates bằng Reciprocal Rank Fusion. |
| `tv_filtered_hybrid` | Dùng BM25/filter làm allowlist cho TurboVec; phù hợp ràng buộc metadata. |
| `tv_hybrid_rerank` | Ablation chỉ dùng trong benchmark; rerank top-100 candidates bằng cross-encoder. |
| `tv_bridge_title_entities_rrf` | Sinh truy vấn bước hai từ title/entity để tìm tài liệu hỗ trợ còn thiếu. |

Điểm mới của cách tiếp cận là không chỉ tối ưu top-k ranking chung, mà tập trung vào lỗi đặc thù của multi-hop retrieval: thiếu tài liệu hỗ trợ thứ hai. Vì vậy đề tài dùng `full_support_recall@10` làm metric chính cho HotpotQA. Reranker chỉ có thể cải thiện khi tài liệu đúng đã có trong tập ứng viên; bridge-aware retrieval được thiết kế để mở rộng tập ứng viên theo bằng chứng bước đầu.

Runtime được thiết kế theo dataset profile. HotpotQA dùng Elasticsearch + TurboVec với default `tv_hybrid`; VimQA dùng Elasticsearch BM25/dense/hybrid với model `bkai-foundation-models/vietnamese-bi-encoder` và default `es_bm25`. Semantic metadata search dùng parser rule-based để tách `effective_query` và `metadata_filters`; parser chỉ chạy khi bật `semantic_metadata=true`, filter nhập tay từ UI có quyền ưu tiên, và metadata không được append vào embedding text để tránh làm nhiễu vector nội dung.

## 3. KẾT QUẢ THỰC HIỆN

Hệ thống đã hoàn thiện một không gian truy xuất có thể chạy trên hai dataset trong cùng API/UI. Với HotpotQA, hệ thống stage và index toàn bộ 5,233,329 tài liệu, xây alias `hotpotqa_full_bm25_current`, xây artifact TurboVec `hotpotqa_bge_small_4bit.tvim`, hỗ trợ các phương pháp `es_bm25`, `tv_dense`, `tv_hybrid`, `tv_filtered_hybrid` và các ablation benchmark. Với VimQA, hệ thống stage 3,623 tài liệu và 9,044 truy vấn/qrels, xây BM25/dense index và benchmark toàn bộ tập truy vấn.

Kết quả HotpotQA trên full test `beir/hotpotqa/test` gồm 7,405 truy vấn:

| Phương pháp | Full-support@10 | Recall@10 | MRR@10 | nDCG@10 | Độ trễ p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.5175 | 0.7305 | 0.8413 | 0.7001 | 760.92 ms |
| `tv_bridge_title_entities_rrf` | 0.6008 | 0.7585 | 0.8251 | 0.7120 | 1598.34 ms |
| Chênh lệch | +0.0833 | +0.0280 | -0.0162 | +0.0119 | +837.42 ms |

Các kết quả ablation chính cho thấy: title-aware BM25 không tăng `full_support@10`; reranker top-100 không tạo net win so với RRF; bridge-aware retrieval xử lý đúng lỗi thiếu tài liệu hỗ trợ thứ hai và tăng `full_support@10` từ 0.5175 lên 0.6008 trên full test; cấu hình `beam1_terms6` là điểm vận hành đã tune từ pilot dev; dense retrieval bền hơn khi query bị paraphrase lexical-strong; filtered hybrid phù hợp metadata constraint nhưng không nên dùng làm default chất lượng cho HotpotQA.

Với VimQA, BM25 là phương pháp tốt nhất về cân bằng chất lượng và độ trễ: `recall@10=0.9627`, `MRR@10=0.8606`, `nDCG@10=0.8859`, p95 khoảng 84.42 ms. Dense/hybrid không thắng BM25 trên dataset này, cho thấy lựa chọn retrieval method phụ thuộc mạnh vào đặc tính dataset.

Semantic metadata search đã hoạt động trên API/UI. Ví dụ truy vấn "tài liệu về lịch sử Việt Nam của Nguyen An trước 31/01/2024" được tách thành `effective_query = lịch sử Việt Nam`, `author = Nguyen An`, `created_at_to = 2024-01-31`. Metadata filter có thể thu hẹp không gian ứng viên rất mạnh: kịch bản tác giả + ngày tạo giảm từ 5,233,329 tài liệu xuống 1,793 tài liệu, tương đương 99.9657%.

Mã nguồn, cấu hình chạy, benchmark artifact, report mentor và bản submission được lưu trong repository `vdt-meeting-search`. Các artifact chính gồm `artifacts/hotpotqa_full/staging`, `artifacts/hotpotqa_full/turbovec`, `evaluation/results/hotpotqa_full`, `evaluation/results/vimqa` và dashboard React/FastAPI.

## 4. ĐÁNH GIÁ HIỆU QUẢ

Hiệu quả của giải pháp được đánh giá theo ba nhóm tiêu chí: chất lượng truy xuất, độ trễ runtime và khả năng giải thích. Về chất lượng, benchmark full test cho thấy bridge-aware retrieval tăng complete evidence coverage từ `full_support@10=0.5175` của `tv_hybrid` lên `0.6008`, tức +8.33 điểm tuyệt đối. Đây là cải tiến quan trọng nhất vì nó xử lý đúng lỗi multi-hop phổ biến: đã tìm được một support document nhưng thiếu support document còn lại. Reranker không tạo net win trong ablation, nên kết quả chỉ ra rằng vấn đề chính nằm ở candidate generation hơn là chỉ xếp hạng lại.

Về độ trễ, `tv_hybrid` vẫn phù hợp hơn cho interactive default vì p95 full test khoảng 760.92 ms, trong khi bridge-aware retrieval đạt p95 khoảng 1598.34 ms. Bridge method vì vậy nên được trình bày là quality-first benchmark path: tăng coverage bằng chứng hoàn chỉnh, đổi lại latency cao hơn. Các số này là số đo cục bộ trên laptop, không phải SLA production.

Về khả năng ứng dụng, hệ thống đã có dataset-first API/UI, Redis cache, search history, benchmark dashboard, support overlay, query highlighting và parsed metadata chips. Các lớp giải thích này giúp người xem hiểu kết quả nào là gold support hit, tài liệu hỗ trợ nào còn thiếu, và lỗi nằm ở sinh ứng viên hay xếp hạng. Với metadata search, người dùng không cần tách thủ công content query và filter form, phù hợp kỳ vọng của bài toán meeting/document search.

So với phương pháp trước đây chỉ dùng BM25 hoặc hybrid một lượt, giải pháp mới có ba giá trị nổi bật: chạy được trên toàn bộ corpus thay vì subset nhỏ; đánh giá đúng bài toán multi-hop bằng full-support; và bổ sung bridge-aware retrieval cùng semantic metadata search để tăng khả năng tìm đủ bằng chứng và điều khiển không gian tìm kiếm.

## 5. KẾT LUẬN

Đề tài đã xây dựng được một hệ thống truy xuất bằng chứng full-corpus cho HotpotQA và mở rộng runtime sang VimQA. Hệ thống tách rõ pipeline ingest offline và retrieval online, kết hợp Elasticsearch BM25 với TurboVec dense retrieval, hỗ trợ nhiều phương pháp retrieval và có benchmark/ablation để giải thích vì sao chọn từng hướng. Kết quả quan trọng nhất là `tv_bridge_title_entities_rrf` đạt `full_support@10=0.6008` trên 7,405 truy vấn full test, cao hơn `tv_hybrid=0.5175`, đồng thời semantic metadata search chứng minh khả năng thu hẹp không gian ứng viên có kiểm soát.

Tính mới của đề tài nằm ở cách nhìn retrieval như một bài toán tìm đủ bằng chứng thay vì chỉ tìm tài liệu liên quan đơn lẻ. Tính sáng tạo nằm ở bridge-aware retrieval cho support thứ hai, semantic metadata parser opt-in, và runtime dataset-first cho HotpotQA/VimQA. Tính hiệu quả được thể hiện bằng các số benchmark, latency, ablation và khả năng demo trực tiếp qua API/UI.

Giới hạn hiện tại là benchmark này mới đánh giá retrieval evidence coverage, không phải answer EM/F1 hay supporting-fact F1 của hệ QA end-to-end; metadata của HotpotQA/VimQA là metadata tổng hợp, chưa phải metadata meeting thật; và chưa khẳng định chất lượng/độ trễ production. Hướng phát triển tiếp theo là tối ưu latency cho bridge-aware retrieval, định nghĩa metadata schema thật cho meeting search, mở rộng semantic metadata evaluation và thêm reader/answer stage nếu muốn so sánh với HotpotQA QA papers.

## 6. TÀI LIỆU THAM KHẢO

[1] BEIR HotpotQA dataset, `beir/hotpotqa`.

[2] Elasticsearch documentation, BM25 retrieval and index management.

[3] TurboVec project/artifact used for compressed dense retrieval.

[4] BAAI, `bge-small-en-v1.5` embedding model.

[5] BKAI Foundation Models, `vietnamese-bi-encoder`.

[6] Reciprocal Rank Fusion and cross-encoder reranking references used in retrieval ablations.

[7] Project repository reports: Sprint 3 full-corpus retrieval report; Sprint 4 paraphrase, metadata and VimQA reports; Sprint 5 reranker, bridge-aware, title-aware BM25 and tuning reports.
