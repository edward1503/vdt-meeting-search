# vdt-meeting-search

## Thông tin

| Thông tin | Chi tiết |
|-----------|----------|
| Mã số | 105 |
| Đơn vị | VTS |
| Họ tên | Nguyễn Quốc Sinh |
| Email | sinhnq3@viettel.com.vn |
| SĐT | 0362825192 |

## Mô tả dự án

Xây dựng hệ thống Semantic Search real-time cho meeting minutes sử dụng prompt-based search trên nội dung và thông tin ngữ cảnh.

Trong sản phẩm đang triển khai, với việc quản lý nhiều nội dung phiên họp đồng thời của tổ chức, nếu chỉ tìm kiếm bằng keyword thì rất khó tìm được phiên họp mong muốn. Dự án muốn đẩy mạnh khả năng tìm kiếm theo ngữ nghĩa, cả từ nội dung, metadata của phiên họp nhằm cải thiện trải nghiệm người dùng trên sản phẩm đang có.

Dự án tập trung xây dựng một hệ thống Semantic Search real-time cho bài toán quản lý và khai thác biên bản cuộc họp, cho phép người dùng thực hiện truy vấn dưới dạng prompt tự nhiên. Thay vì tìm kiếm theo từ khóa truyền thống, hệ thống có khả năng hiểu ngữ nghĩa câu hỏi như: tìm các cuộc họp liên quan đến một nghị định cụ thể, hoặc các cuộc họp có sự tham gia của một cá nhân, và trả về danh sách biên bản phù hợp.

Pipeline của hệ thống bao gồm các thành phần chính: tiền xử lý và chuẩn hóa dữ liệu biên bản, xây dựng vector embeddings cho cả nội dung văn bản và metadata, và triển khai cơ chế semantic retrieval để tìm kiếm trên không gian biểu diễn ngữ nghĩa. Hệ thống cần kết hợp hiệu quả giữa tìm kiếm trên nội dung và thông tin ngữ cảnh để đảm bảo kết quả chính xác và đầy đủ.

## Nhiệm vụ

### Dữ liệu
Thu thập và xây dựng tập dữ liệu biên bản cuộc họp, bao gồm cả nội dung văn bản và thông tin ngữ cảnh đi kèm.

### Thuật toán
Thiết kế pipeline Semantic Search cho phép truy vấn bằng ngôn ngữ tự nhiên. Bao gồm:
- Xây dựng embedding cho văn bản và metadata using vector representation models
- Lưu trữ embedding trong vector database để phục vụ truy vấn nhanh
- Thiết kế cơ chế prompt-based search using natural language understanding
- Kết hợp tìm kiếm ngữ nghĩa và lọc theo metadata using hybrid retrieval
- Xây dựng cơ chế ranking để sắp xếp kết quả theo độ liên quan

### Huấn luyện và tối ưu
So sánh kết quả theo các tiêu chí:
- Độ chính xác tìm kiếm using metrics như precision, recall, MRR
- Độ liên quan của kết quả theo đánh giá thực tế
- Thời gian truy vấn và độ trễ hệ thống
- Ảnh hưởng của các cấu hình như kích thước embedding, index strategy

## Phương pháp đánh giá

Mỗi truy vấn đầu vào là một câu prompt tự nhiên, hệ thống trả về danh sách các biên bản cuộc họp phù hợp kèm theo mức độ liên quan. Đánh giá bao gồm:
- Độ chính xác tìm kiếm using metrics như precision, recall, mean reciprocal rank
- Độ liên quan ngữ nghĩa giữa truy vấn và kết quả trả về theo đánh giá thủ công hoặc benchmark
- Khả năng xử lý truy vấn phức tạp có nhiều điều kiện như theo chủ đề, người tham gia và thời gian
- Đánh giá riêng cho từng nguồn thông tin gồm nội dung biên bản và metadata

## Chương trình demo
- Demo giao diện cho phép nhập truy vấn dạng prompt tự nhiên
- Hiển thị danh sách biên bản phù hợp kèm thông tin như tiêu đề, thời gian, người tham gia
- Highlight các đoạn nội dung liên quan trong biên bản

## Sản phẩm hệ thống
- Một hệ thống Semantic Search hoàn chỉnh từ dữ liệu đầu vào đến kết quả truy vấn
- API cho phép gửi truy vấn và nhận kết quả tìm kiếm
- Hệ thống indexing cho phép cập nhật dữ liệu gần real-time
- Hỗ trợ hybrid search kết hợp semantic và metadata filtering

## Dữ liệu & công cụ
- Các bộ dữ liệu về hội thoại và meeting transcripts như AMI Meeting Corpus, ICSI Meeting Corpus
- Dữ liệu văn bản dùng cho semantic search và question answering
- Công cụ xử lý NLP như HuggingFace Transformers, SentenceTransformers
- Vector database phục vụ semantic retrieval như FAISS, Elasticsearch, Milvus

## Tài liệu tham khảo
- Các repository về semantic search và dense retrieval using embedding models
- Ví dụ hệ thống hybrid search kết hợp keyword search và vector search
- Pipeline xây dựng hệ thống retrieval từ embedding đến ranking
- Các hệ thống Retrieval-Augmented Generation tích hợp LLM với search
- Các nghiên cứu về Semantic Search và Dense Retrieval using neural networks
- Tài liệu về embedding models cho văn bản như sentence embedding và contextual embedding
- Các phương pháp hybrid search kết hợp semantic và keyword-based retrieval
