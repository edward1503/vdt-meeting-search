# Script thuyết trình VDT 2026

File slide: `submission/VDT2026-NguyenDonDuc-Search(Slide).pdf`

Chủ đề: **Hệ thống truy xuất evidence trên HotpotQA cho multi-hop reasoning**

## Cách dùng script

- Nếu thời gian ngắn, nói theo các slide 2-20 và bỏ qua phụ lục 21-23.
- Slide 21-23 chỉ dùng khi có thời gian hoặc khi mentor hỏi thêm.
- Khi nói về benchmark, luôn nhấn mạnh `full-support@10` là metric chính cho HotpotQA multi-hop retrieval.

## Thông điệp chính cần giữ

Đề tài không chỉ tìm một document liên quan, mà tập trung vào việc **tìm đủ evidence** cho câu hỏi multi-hop trên full corpus. Hybrid search là baseline nhanh và thực dụng; bridge-aware retrieval cải thiện khả năng tìm đủ supporting documents, đổi lại latency cao hơn.

---

## Slide 1 - Cover

**Mục tiêu:** Mở đầu, chuẩn bị vào bài.

**Script nói:**

Em xin chào các anh chị. Em là Nguyễn Đôn Đức. Hôm nay em xin trình bày đề tài trong chương trình Viettel Digital Talent 2026.

Nội dung của em tập trung vào bài toán truy xuất bằng chứng, hay evidence retrieval, trên tập dữ liệu HotpotQA cho multi-hop reasoning.

**Chuyển ý:** Sau đây em xin giới thiệu ngắn gọn tên đề tài và mục tiêu chính.

---

## Slide 2 - Title

**Mục tiêu:** Nói rõ bài toán và ngữ cảnh.

**Script nói:**

Tên đề tài của em là **Hệ thống truy xuất evidence trên HotpotQA cho multi-hop reasoning**.

Trong đề tài này, em xây dựng một hệ thống retrieval có khả năng tìm kiếm trên corpus lớn, kết hợp lexical search, semantic search và các hướng cải tiến cho truy vấn đa bước.

Điểm em muốn nhấn mạnh là với multi-hop reasoning, hệ thống không chỉ cần tìm một tài liệu đúng, mà cần tìm đủ các tài liệu hỗ trợ để có thể trả lời câu hỏi.

**Chuyển ý:** Em sẽ đi theo bốn phần chính của bài trình bày.

---

## Slide 3 - Mục lục

**Mục tiêu:** Báo trước cấu trúc bài nói.

**Script nói:**

Bài trình bày của em gồm bốn phần.

Phần thứ nhất là tổng quan đề tài và vì sao bài toán này quan trọng. Phần thứ hai là pipeline ingest và retrieval. Phần thứ ba là kết quả benchmark. Cuối cùng là kết luận và demo.

**Chuyển ý:** Đầu tiên, em xin bắt đầu từ bài toán thực tế mà đề tài hướng tới.

---

## Slide 4 - Tổng quan: semantic search cho kho tài liệu lớn

**Mục tiêu:** Đặt vấn đề từ góc nhìn sản phẩm/thực tế.

**Script nói:**

Trong các hệ thống tìm kiếm trên kho tài liệu lớn, cách truy xuất bằng chứng quyết định rất lớn đến chất lượng của cả pipeline phía sau.

Ví dụ với dữ liệu biên bản họp hoặc tài liệu nghiệp vụ, người dùng có thể hỏi: "Tìm cuộc họp liên quan đến nghị định X", "Ai đã nhắc đến vấn đề deployment?", hoặc "Các cuộc họp Nguyễn An tham gia trong tháng 1".

Những câu hỏi này không phải lúc nào cũng match trực tiếp với keyword trong tài liệu. Vì vậy tìm kiếm bằng keyword thường không đủ. Hệ thống cần kết hợp lexical search, semantic search, metadata filtering và ranking để trả về tài liệu phù hợp hơn trên corpus lớn.

**Chuyển ý:** Để đánh giá bài toán này một cách có hệ thống, em sử dụng HotpotQA.

---

## Slide 5 - HotpotQA và bài toán multi-hop

**Mục tiêu:** Giải thích vì sao HotpotQA phù hợp.

**Script nói:**

HotpotQA là benchmark hỏi đáp trên Wikipedia với hơn 5 triệu documents. Điểm khó của HotpotQA là nhiều câu hỏi không thể trả lời bằng một tài liệu duy nhất.

Ví dụ câu hỏi: "What occupations do both Ian Hunter and Rob Thomas have?". Hệ thống cần tìm document về Ian Hunter, document về Rob Thomas, rồi so sánh occupations.

Do đó, nếu hệ thống chỉ tìm được một document đúng thì vẫn chưa đủ. Metric quan trọng ở đây là `full-support recall@10`: top-10 kết quả có chứa đủ toàn bộ supporting documents hay không.

**Chuyển ý:** Với multi-hop retrieval, trên thế giới có một số hướng xử lý phổ biến.

---

## Slide 6 - Các phương pháp tiếp cận multi-hop retrieval

**Mục tiêu:** Đặt bridge-aware vào bối cảnh related work.

**Script nói:**

Với multi-hop retrieval, các hướng tiếp cận phổ biến có thể chia thành bốn nhóm.

Một là one-shot hybrid retrieval, tức là retrieve một lần bằng BM25 và dense. Hai là iterative retrieval, dùng kết quả hop 1 để tìm tiếp hop 2. Ba là entity hoặc graph-based retrieval, dùng entity, title, hyperlink làm cầu nối. Bốn là reasoning-guided retrieval, dùng reasoning step hoặc LLM để dẫn hướng truy hồi tiếp theo.

Phương pháp bridge-aware retrieval của em nằm trong nhóm iterative retrieval nhẹ. Hệ thống lấy title và entity-like terms từ document hop 1, tạo bridge query, retrieve hop 2, sau đó rank evidence chain.

**Chuyển ý:** Trước khi vào pipeline, em xin nói ngắn gọn các metric đánh giá.

---

## Slide 7 - Evaluation metrics cơ bản

**Mục tiêu:** Nói nhanh, không sa vào công thức.

**Script nói:**

Trong retrieval, các metric cơ bản gồm Precision@k, Recall@k, MRR@k và nDCG@k.

Precision đo tỷ lệ tài liệu đúng trong top-k. Recall đo tỷ lệ tài liệu đúng đã được retrieve. MRR quan tâm vị trí của relevant document đầu tiên. nDCG đánh giá chất lượng ranking có xét thứ tự kết quả.

Nhưng với HotpotQA, các metric này chưa phản ánh hết yêu cầu multi-hop, vì một câu hỏi có thể cần nhiều supporting documents.

**Chuyển ý:** Vì vậy em dùng thêm metric quan trọng nhất là full-support recall.

---

## Slide 8 - Full-support recall và latency

**Mục tiêu:** Đóng khung metric chính.

**Script nói:**

Metric quan trọng nhất trong bài này là `full-support recall@k`.

Với mỗi query, nếu top-k chứa đủ toàn bộ supporting documents thì query đó được tính là thành công. Nếu thiếu ít nhất một supporting document thì query đó vẫn bị tính là chưa thành công.

Ví dụ gold support gồm A và B. Nếu top-10 có cả A và B thì `full-support@10 = 1`. Nếu top-10 chỉ có A mà thiếu B thì `full-support@10 = 0`.

Ngoài chất lượng, em cũng báo cáo p95 latency, tức là độ trễ mà 95% queries chạy nhanh hơn hoặc bằng giá trị đó.

**Chuyển ý:** Sau đây là pipeline ingest và retrieval của hệ thống.

---

## Slide 9 - Section transition: Pipeline Ingest / Retrieval

**Mục tiêu:** Chuyển sang phần kỹ thuật.

**Script nói:**

Phần tiếp theo em xin trình bày cách hệ thống xử lý dữ liệu offline và cách các method retrieval được xây dựng trên các artifact đó.

**Chuyển ý:** Đầu tiên là ingestion pipeline.

---

## Slide 10 - Ingestion pipeline

**Mục tiêu:** Giải thích offline data processing.

**Script nói:**

Pipeline offline bắt đầu từ HotpotQA/BEIR dataset, gồm corpus documents, queries và qrels.

Với corpus documents, hệ thống normalize các trường `title`, `text`, `url`, gán `doc_id` và `numeric_id` ổn định. Sau đó tạo hai field dẫn xuất: `content` và `embedding_text`, đều dựa trên `title + text`.

Dữ liệu được ghi thành JSONL staging shards. Tổng cộng có 5,233,329 documents, chia thành 105 shards, mỗi shard khoảng 50,000 documents.

Từ staging này, hệ thống tách thành hai nhánh build index.

Nhánh thứ nhất là Elasticsearch BM25 index. Index này phục vụ lexical retrieval và đồng thời là document store để hydrate kết quả bằng `numeric_id`.

Nhánh thứ hai là embedding/vector build. Hệ thống encode `embedding_text` bằng model `BAAI/bge-small-en-v1.5`, dimension 384, sau đó build TurboVec 4-bit vector retrieval artifacts.

Kết quả cuối là hai retrieval stores sẵn sàng cho search: BM25 store và vector retrieval artifacts.

**Chuyển ý:** Trên các artifact đó, baseline đầu tiên là hybrid search.

---

## Slide 11 - Baseline method: Hybrid Search

**Mục tiêu:** Giải thích BM25 + dense + RRF.

**Script nói:**

Baseline chính của em là hybrid search, kết hợp BM25 và dense retrieval.

Khi người dùng nhập query, hệ thống tiền xử lý query, sau đó chạy song song hai nhánh.

Nhánh thứ nhất là lexical retrieval bằng Elasticsearch BM25. Nhánh này bắt tốt keyword, entity và các cụm từ xuất hiện trực tiếp trong tài liệu.

Nhánh thứ hai là dense search. Query được encode thành vector, sau đó tìm nearest neighbors trong dense vector index.

Hai danh sách kết quả này được gộp bằng Reciprocal Rank Fusion, hay RRF. Ưu điểm của RRF là không cần calibrate score giữa BM25 và vector similarity, mà chỉ dựa vào thứ hạng của document trong từng hệ thống.

Sau khi fuse, hệ thống trả về top-k kết quả và hydrate document đầy đủ từ Elasticsearch bằng `numeric_id`.

**Chuyển ý:** Tuy nhiên với HotpotQA, one-shot hybrid vẫn có thể chỉ tìm được một support document. Vì vậy em thêm bridge-aware retrieval.

---

## Slide 12 - Proposed method: Bridge-aware retrieval

**Mục tiêu:** Giải thích phương pháp đề xuất.

**Lưu ý sửa slide:** Nếu còn sửa được, đổi `PHRASE` thành `PHASE`.

**Script nói:**

Phương pháp đề xuất của em là bridge-aware retrieval.

Phase 1 là find bridge documents. Hệ thống chạy first-hop hybrid retrieval bằng query gốc để lấy các document ứng viên ban đầu. Các document top đầu này được xem như bridge documents.

Phase 2 là build bridge query. Từ bridge document, hệ thống trích các tín hiệu như title, entity-like terms và lead terms. Ví dụ với câu hỏi về đạo diễn của Inception, hop 1 có thể tìm được document Inception hoặc Christopher Nolan. Từ đó hệ thống lấy các bridge terms như `Christopher Nolan` để mở rộng query.

Phase 3 là retrieve and rank evidence. Hệ thống chạy second-hop hybrid retrieval bằng bridge query, tạo các evidence chains gồm hop 1 document và hop 2 document, sau đó rank chain bằng RRF và flatten thành final top-k documents.

Mục tiêu của phương pháp này là giảm lỗi rất phổ biến trong HotpotQA: hệ thống tìm được một support document nhưng thiếu support document thứ hai.

**Chuyển ý:** Sau đây là kết quả benchmark để kiểm tra giả thuyết này.

---

## Slide 13 - Section transition: Kết quả benchmark

**Mục tiêu:** Mở phần kết quả.

**Script nói:**

Phần tiếp theo là kết quả benchmark. Em sẽ tập trung vào hai phần: error analysis theo evidence coverage và bảng benchmark chính giữa hybrid search với bridge-aware retrieval.

**Chuyển ý:** Đầu tiên là evidence coverage breakdown.

---

## Slide 14 - Evidence coverage breakdown

**Mục tiêu:** Giải thích vì sao bridge-aware có ích.

**Lưu ý sửa slide:** Title chart đang hơi sát mép phải. Nên giảm font hoặc kéo chart xuống/trái.

**Script nói:**

Biểu đồ này phân tích 7,405 queries trên HotpotQA test thành ba nhóm.

Màu xanh là các query tìm đủ support documents. Màu cam là partial support, tức là chỉ tìm được một phần support. Màu xám là missing support.

Với baseline hybrid search, hệ thống tìm đủ support cho 3,832 queries. Với bridge-aware retrieval, con số này tăng lên 4,449 queries, tức thêm 617 queries thành công.

Điểm đáng chú ý là partial support giảm mạnh, từ 3,155 xuống 2,335, giảm 820 cases. Điều này đúng với mục tiêu của bridge-aware: biến các case chỉ tìm được một phần support thành tìm đủ support.

Missing support có tăng từ 418 lên 621. Đây là trade-off của query expansion heuristic: khi bridge terms đúng, hop 2 giúp tìm support thứ hai; khi bridge terms nhiễu hoặc lệch, hop 2 có thể kéo retrieval sang hướng khác.

Tổng thể, gain ở full-support lớn hơn trade-off missing-support, và quan trọng là cải thiện đúng metric chính của multi-hop retrieval.

**Chuyển ý:** Tiếp theo là bảng benchmark tổng hợp.

---

## Slide 15 - One-shot hybrid vs bridge-aware retrieval

**Mục tiêu:** Chốt kết quả định lượng chính.

**Lưu ý sửa slide:** Đổi câu "benchmark tốt hơn" thành "tăng Full-support@10 từ 51.75% lên 60.08%".

**Script nói:**

Trên benchmark chính với 7,405 queries của `beir/hotpotqa/test`, hybrid search đạt `full-support@10` là 51.75%.

Bridge-aware retrieval đạt 60.08%, tăng 8.33 điểm phần trăm. Nếu tính tương đối, đây là mức tăng khoảng 16.1% so với baseline hybrid.

Recall@10 cũng tăng từ 73.05% lên 75.85%, và nDCG@10 tăng từ 70.01% lên 71.20%.

MRR@10 giảm nhẹ từ 84.13% xuống 82.51%. Điều này có thể hiểu là bridge-aware không tối ưu riêng việc đẩy relevant document đầu tiên lên cao nhất, mà ưu tiên tìm đủ cặp supporting documents.

Trade-off lớn nhất là latency. p95 latency tăng từ 0.76 giây lên 1.60 giây vì bridge-aware phải chạy thêm second-hop retrieval.

Vì vậy, kết luận của em là hybrid search phù hợp làm baseline realtime, còn bridge-aware retrieval phù hợp khi ưu tiên chất lượng evidence coverage.

**Chuyển ý:** Em cũng đối chiếu nDCG với một số baseline retrieval công khai.

---

## Slide 16 - So sánh với các method trên leaderboard

**Mục tiêu:** Đặt kết quả vào bối cảnh benchmark ngoài.

**Script nói:**

Slide này so sánh theo metric nDCG@10 với một số baseline trên BEIR/Pyserini.

Baseline hybrid của em đạt 70.01%, bridge-aware đạt 71.20%. Kết quả này cao hơn một số baseline như BM25 multifield, BM25 flat, Contriever và SPLADE++ trong bảng tham chiếu, và gần với BGE-base.

Tuy nhiên, em muốn lưu ý đây không phải là leaderboard claim tuyệt đối. Lý do là mỗi setup có thể khác nhau về cách build index, model size, quantization, document fields và môi trường latency.

Điểm chính em muốn rút ra là hệ thống full-corpus của em đạt chất lượng cạnh tranh, trong khi vẫn duy trì kiến trúc thực dụng: Elasticsearch cho BM25/document store và TurboVec compressed index cho dense retrieval.

**Chuyển ý:** Ngoài retrieval theo content, hệ thống còn hỗ trợ metadata search.

---

## Slide 17 - Semantic metadata search

**Mục tiêu:** Nói về khả năng mở rộng sang meeting/document search.

**Script nói:**

Ngoài truy vấn nội dung, hệ thống còn hỗ trợ semantic metadata search.

Ví dụ người dùng nhập: "Tài liệu về điện ảnh của Nguyễn An trước 31/01/2024".

Hệ thống cần tách câu này thành hai phần. Phần content query là "điện ảnh". Phần metadata filter gồm `author = Nguyễn An` và `created_at_to = 2024-01-31`.

Sau khi parse metadata, hệ thống lọc ứng viên theo metadata trước, rồi mới ranking theo method retrieval. Cách này phù hợp với bài toán meeting search, vì người dùng thường hỏi kèm điều kiện về người tham gia, thời gian hoặc loại tài liệu.

**Chuyển ý:** Sau các kết quả trên, em xin chuyển sang kết luận.

---

## Slide 18 - Section transition: Kết luận và Demo

**Mục tiêu:** Chuyển sang phần cuối.

**Script nói:**

Phần cuối cùng là kết luận, hướng phát triển và demo hệ thống.

**Chuyển ý:** Em xin tóm tắt các đóng góp chính.

---

## Slide 19 - Kết luận

**Mục tiêu:** Chốt đóng góp.

**Script nói:**

Tổng kết lại, đề tài đã xây dựng được hệ thống full-corpus hybrid retrieval trên HotpotQA với 5.23 triệu documents.

Hệ thống tích hợp indexing pipeline, Elasticsearch BM25, TurboVec dense search, FastAPI, React dashboard và benchmark.

Hybrid search là baseline realtime, kết hợp BM25, TurboVec và RRF.

Bridge-aware retrieval cải thiện multi-hop retrieval, tăng `full-support@10` từ 51.75% lên 60.08%, tăng 8.33 điểm phần trăm.

Ngoài ra, hệ thống còn mở rộng thêm paraphrase benchmark, metadata filtering và VimQA.

**Chuyển ý:** Cuối cùng là một số hướng phát triển tiếp theo.

---

## Slide 20 - Hướng phát triển

**Mục tiêu:** Nói giới hạn và future work.

**Lưu ý sửa slide:** Navbar nên là "04 - KẾT LUẬN VÀ DEMO", không phải "04 - KẾT QUẢ DEMO".

**Script nói:**

Hướng phát triển đầu tiên là tối ưu latency cho bridge-aware retrieval, vì hiện tại method này cần second-hop retrieval nên chậm hơn hybrid.

Thứ hai là cải thiện bridge query bằng entity extraction hoặc sentence selection tốt hơn, để giảm các trường hợp query expansion bị lệch hướng.

Thứ ba là thay synthetic metadata bằng metadata meeting thật, vì mục tiêu dài hạn của hệ thống là ứng dụng vào meeting/document search.

Thứ tư là thêm reader hoặc LLM answer stage để có thể đánh giá thêm Answer F1 và Supporting-fact F1, thay vì chỉ dùng retrieval metrics.

Cuối cùng là benchmark trên server triển khai và thử nghiệm nhiều embedding models hơn.

**Chuyển ý:** Nếu còn thời gian, em có một số phụ lục về paraphrase, VimQA và reranker ablation.

---

## Slide 21 - Phụ lục 1: Paraphrase robustness

**Mục tiêu:** Dùng khi có thời gian hoặc bị hỏi về robustness.

**Script nói:**

Phụ lục này kiểm tra paraphrase robustness. Em tạo các biến thể query ở ba mức: mild, strong và lexical strong.

Mild chỉ viết lại nhẹ. Strong đổi cấu trúc câu rõ hơn. Lexical strong đổi nhiều content words bằng từ đồng nghĩa nhưng vẫn giữ entity chính.

Kết quả cho thấy hybrid retrieval vẫn duy trì hiệu quả khá tốt khi truy vấn bị paraphrase, kể cả ở mức thay đổi từ vựng mạnh. Điều này cho thấy việc kết hợp lexical và dense retrieval giúp hệ thống không phụ thuộc hoàn toàn vào keyword matching.

---

## Slide 22 - Phụ lục 2: Vietnamese dataset - VimQA

**Mục tiêu:** Dùng khi muốn nói về khả năng mở rộng tiếng Việt.

**Script nói:**

Phụ lục này là benchmark trên VimQA, một dataset tiếng Việt.

Với VimQA, BM25 đạt recall@10 rất cao, 96.27%, và p95 chỉ khoảng 84 ms. BKAI dense có recall thấp hơn, còn hybrid đạt recall cao nhất nhưng latency cao hơn.

Kết quả này cho thấy không phải dataset nào hybrid cũng là lựa chọn mặc định tốt nhất. Method retrieval cần phụ thuộc vào đặc tính dữ liệu, ngôn ngữ và mục tiêu latency.

---

## Slide 23 - Phụ lục 3: RRF fusion vs reranker

**Mục tiêu:** Dùng khi bị hỏi vì sao không dùng reranker.

**Script nói:**

Phụ lục này so sánh RRF baseline với cross-encoder reranker.

Reranker lấy top-100 candidates rồi sắp xếp lại bằng cross-encoder `ms-marco-MiniLM-L-6-v2`.

Kết quả là reranker cải thiện MRR và nDCG, nhưng không tăng full-support. Điều này cho thấy bottleneck hiện tại không nằm chủ yếu ở reranking, mà nằm ở candidate generation, tức là cần retrieve đủ support documents trước khi rerank.

Vì vậy em ưu tiên bridge-aware retrieval để cải thiện khả năng tìm support document thứ hai.

---

## Slide 24 - Thanks

**Mục tiêu:** Kết thúc.

**Script nói:**

Em xin kết thúc phần trình bày tại đây.

Em cảm ơn các anh chị đã lắng nghe, và em xin nhận câu hỏi.

---

## Slide 25 - Contact / End page

**Mục tiêu:** Không cần nói, chỉ giữ màn hình nếu cần.

**Script nói nếu cần:**

Đây là slide kết thúc với thông tin đơn vị. Em xin cảm ơn.

---

# Bản rút gọn 10 phút

Nếu bị giới hạn thời gian, dùng flow này:

1. Slide 2-3: Giới thiệu và mục lục - 30 giây.
2. Slide 4-5: Bài toán và HotpotQA - 1.5 phút.
3. Slide 6: Các hướng tiếp cận và bridge-aware - 1 phút.
4. Slide 8: Full-support@10 - 1 phút.
5. Slide 10: Ingestion pipeline - 1.5 phút.
6. Slide 11-12: Hybrid và bridge-aware - 2 phút.
7. Slide 14-15: Kết quả benchmark - 2 phút.
8. Slide 19-20: Kết luận và hướng phát triển - 1 phút.

Bỏ qua slide 7 nếu thời gian rất ngắn, chỉ nói:

> Các metric như Recall, MRR và nDCG là metric retrieval phổ biến, nhưng với HotpotQA em tập trung vào Full-support@10 vì nó đo việc top-10 có tìm đủ toàn bộ supporting documents hay không.

---

# Câu hỏi mentor có thể hỏi

## 1. Vì sao dùng full-support@10 thay vì chỉ recall@10?

Vì HotpotQA là multi-hop QA. Một câu hỏi thường cần nhiều supporting documents. Recall@10 có thể tăng ngay cả khi hệ thống chỉ tìm được một support document, nhưng query vẫn chưa đủ bằng chứng để trả lời. Full-support@10 chỉ tính thành công khi top-10 có đủ toàn bộ supporting documents, nên phù hợp hơn với mục tiêu evidence retrieval.

## 2. Bridge-aware retrieval khác hybrid search ở điểm nào?

Hybrid search retrieve một lần bằng BM25 + dense và fuse bằng RRF. Bridge-aware retrieval chạy thêm bước second-hop: từ kết quả hop 1, hệ thống trích title/entity-like terms để tạo bridge query, retrieve hop 2, rồi rank evidence chains. Mục tiêu là tìm support document thứ hai.

## 3. Vì sao missing support tăng trong slide error analysis?

Vì bridge-aware dùng query expansion heuristic. Khi bridge terms đúng, hop 2 giúp tìm document còn thiếu. Khi bridge terms nhiễu hoặc lệch, hop 2 có thể kéo retrieval sang hướng khác, làm missing-support tăng. Tuy nhiên full-support tăng +617 cases và partial-support giảm -820 cases, nên tổng thể method vẫn cải thiện đúng mục tiêu chính.

## 4. Vì sao MRR giảm nhẹ?

MRR đo vị trí của relevant document đầu tiên. Bridge-aware không tối ưu riêng việc đưa một document đúng lên vị trí đầu, mà ưu tiên lấy đủ cặp supporting documents trong top-10. Vì vậy MRR có thể giảm nhẹ trong khi full-support@10 tăng mạnh.

## 5. Vì sao không dùng reranker làm method chính?

Reranker cải thiện MRR và nDCG nhưng không tăng full-support trong ablation. Điều này cho thấy bottleneck hiện tại nằm ở candidate generation: nếu support document thứ hai không có trong candidate set, reranker không thể cứu được. Bridge-aware nhắm trực tiếp vào candidate generation.

## 6. TurboVec có thay thế Elasticsearch không?

Không. Elasticsearch vẫn dùng cho BM25 lexical retrieval, filter, document store và hydrate kết quả bằng `numeric_id`. TurboVec chỉ thay phần dense vector search full-corpus, vì dense vector index trên 5.23M documents có thể tốn RAM/index overhead lớn nếu đưa hết vào Elasticsearch HNSW trong môi trường laptop.

## 7. Bridge terms được trích như thế nào?

Hệ thống lấy title terms trước, sau đó lấy entity-like capitalized spans trong text, và nếu chưa đủ thì lấy lead text terms. Các token trùng query gốc, token trùng nhau, hoặc token quá ngắn sẽ bị bỏ. Cấu hình tốt nhất hiện tại dùng `beam_size=1` và `max_bridge_terms=6`.

## 8. Paraphrase robustness đo bằng gì?

Hệ thống tạo ba mức paraphrase: mild, strong và lexical strong. Độ mạnh của paraphrase được audit bằng lexical diversity, gồm `content_change_ratio`, `content_jaccard` và `no_new_content_terms`. Lexical strong là stress test chính vì thay đổi nhiều content words nhất.

## 9. Có thể so sánh trực tiếp với HotpotQA paper không?

Không nên so sánh trực tiếp. HotpotQA paper và các QA papers thường báo cáo Answer EM/F1, Supporting-fact F1 và Joint F1 cho pipeline QA end-to-end. Đề tài này tập trung vào retrieval evidence coverage trước reader/answer stage, nên metric chính là full-support@10.

## 10. Nếu đưa vào sản phẩm meeting search thật thì cần làm gì tiếp?

Cần thay synthetic metadata bằng metadata meeting thật, thêm parser metadata phù hợp tiếng Việt/nội bộ, tối ưu latency cho dense và bridge retrieval, và nếu cần trả lời tự động thì thêm reader hoặc LLM answer stage trên top evidence.
