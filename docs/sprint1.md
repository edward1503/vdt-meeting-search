# Sprint 1 - Báo cáo những việc đã làm

## 1. Mục tiêu sprint

Sprint 1 tập trung xây dựng MVP end-to-end cho hệ thống semantic search trên meeting minutes. Mục tiêu chính là có một pipeline chạy được từ dữ liệu đầu vào, tiền xử lý transcript, tạo embedding, lập chỉ mục vector, truy vấn qua API và demo kết quả trên giao diện web.

Pipeline tổng thể của Sprint 1:

```text
Raw meeting data
-> Parse và chuẩn hóa dữ liệu
-> Chunk transcript
-> Tạo embedding
-> Build FAISS index
-> Search bằng query tự nhiên
-> Trả kết quả qua API
-> Hiển thị trên frontend demo
-> Chạy evaluation MVP
```

Kết quả cuối Sprint 1 là một semantic search MVP có thể nhận prompt tự nhiên, tìm các đoạn transcript gần nghĩa nhất, gom kết quả theo meeting, trả về snippets liên quan và hiển thị trên UI.

## 2. Pipeline xử lý dữ liệu chi tiết

### 2.1. Input đầu vào

Hệ thống hiện hỗ trợ hai nguồn dữ liệu đầu vào. Nguồn chính là AMI Meeting Corpus, gồm `corpusResources/meetings.xml`, `words/*.words.xml` và `segments/*.segments.xml`. Nguồn phụ là JSON/JSONL local để smoke test nhanh khi chưa có full AMI dataset.

Với JSON/JSONL, schema tối thiểu gồm các field: `meeting_id`, `source`, `title`, `date`, `participants`, `turns`. Mỗi item trong `turns` cần có `speaker`, `speaker_role`, `time_start`, `time_end`, `text`.

### 2.2. Parse và chuẩn hóa meeting

File triển khai chính: `src/preprocessing/parse_ami.py`.

Mục tiêu của bước này là chuyển dữ liệu raw từ AMI hoặc JSON thành một format meeting thống nhất. Sau bước này, các bước chunking, embedding và search không cần biết dữ liệu đến từ AMI hay JSON mẫu.

Các field meeting cần có sau chuẩn hóa:

| Field | Nguồn/Cách xử lý | Mục đích |
|-------|------------------|----------|
| `meeting_id` | AMI `observation` thêm prefix `ami_`, hoặc JSON `meeting_id` | ID chính dùng xuyên suốt hệ thống |
| `raw_meeting_id` | AMI `observation`, hoặc JSON `raw_meeting_id`/`meeting_id` | Trace về dữ liệu gốc |
| `source` | `ami`, `json`, hoặc `sample` | Phân biệt nguồn dữ liệu |
| `title` | Sinh từ AMI id hoặc lấy từ JSON | Hiển thị kết quả |
| `date` | AMI `dateOnly` hoặc JSON `date` | Hiển thị/lọc theo ngày |
| `participants` | Speaker `global_name` hoặc JSON `participants` | Hiển thị người tham gia, hỗ trợ filter sau này |
| `turns` | Danh sách lượt nói đã ghép token | Nội dung chính để search |
| `metadata` | `meeting_type`, `visibility`, `split` hoặc JSON metadata | Phục vụ phân tích/filter |

Các field trong từng `turn`:

| Field | Nguồn/Cách xử lý | Mục đích |
|-------|------------------|----------|
| `speaker` | Map AMI `nxt_agent` sang `global_name`; nếu thiếu dùng agent id | Hiển thị người nói, thêm ngữ cảnh vào chunk |
| `speaker_agent` | Agent trong tên file AMI | Trace về file AMI raw |
| `speaker_role` | Role trong metadata speaker | Hỗ trợ search/filter theo vai trò |
| `text` | Ghép các word token thuộc segment | Nội dung chính để semantic search |
| `time_start` | `transcriber_start` hoặc min start time của token | Vị trí bắt đầu đoạn nói |
| `time_end` | `transcriber_end` hoặc max end time của token | Vị trí kết thúc đoạn nói |

Logic xử lý AMI:

1. Tìm thư mục AMI bằng cách kiểm tra `corpusResources/meetings.xml`.
2. Parse `meetings.xml` để lấy metadata meeting và danh sách speaker.
3. Parse `words/*.words.xml` để lấy word id, text, start time, end time và punctuation flag.
4. Parse `segments/*.segments.xml`; mỗi segment có `href` trỏ tới một range word id.
5. Dựa vào range word id để lấy token tương ứng, rồi ghép token thành câu/đoạn nói.
6. Sắp xếp các lượt nói theo `time_start` để giữ thứ tự hội thoại.
7. Chuẩn hóa output thành list meeting thống nhất.

Nếu không tìm thấy AMI, parser fallback sang JSON/JSONL trong `data/raw`. Nếu JSON record không có `turns`, hệ thống lấy `transcript`, `text` hoặc `summary` để tạo một turn mặc định.

### 2.3. Chunk transcript

File triển khai chính: `src/preprocessing/chunking.py`.

Mục tiêu là chia transcript dài thành các đoạn nhỏ hơn để embedding và retrieval hiệu quả. Nếu embed nguyên cả meeting, vector dễ bị loãng ngữ nghĩa; nếu chunk quá nhỏ, mất ngữ cảnh hội thoại.

Cấu hình Sprint 1:

```text
chunk_size_words: 260
overlap_words: 60
step: 200
```

Cách xử lý: duyệt `turns` theo thứ tự thời gian, làm sạch whitespace, prefix mỗi lượt nói bằng speaker, gom transcript thành danh sách word, rồi cắt sliding window 260 words với overlap 60 words.

Field output của mỗi chunk:

| Field | Ý nghĩa |
|-------|---------|
| `chunk_id` | ID duy nhất của chunk, dạng `meeting_id::chunk_0000` |
| `meeting_id` | Meeting chứa chunk |
| `title` | Tiêu đề meeting để hiển thị |
| `date` | Ngày meeting nếu có |
| `participants` | Danh sách người tham gia meeting |
| `speakers` | Danh sách speaker xuất hiện trong transcript đã gom |
| `time_start` | Thời gian bắt đầu gần đúng |
| `time_end` | Thời gian kết thúc gần đúng |
| `text` | Nội dung chunk đã có speaker prefix |
| `source` | Nguồn dữ liệu, ví dụ `ami`, `sample` |
| `metadata` | Metadata gốc của meeting |

Ghi chú hạn chế: `time_start` và `time_end` hiện đang lấy gần đúng theo transcript đã gom, chưa phải timestamp chính xác của từng sliding window chunk. Sprint sau nên tính timestamp theo token range thực sự của từng chunk.

### 2.4. Embedding, index và output artifacts

File triển khai chính: `src/embedding/model.py` và `src/indexing/build_faiss.py`.

Input của bước embedding là danh sách `chunk[text]`. Model mặc định là `sentence-transformers/all-MiniLM-L6-v2`, sinh vector 384 chiều và normalize embedding. Vì vector đã normalize, FAISS dùng `IndexFlatIP`; inner product lúc này tương đương cosine similarity.

Build index chạy các bước: load meeting đã parse, chunk transcript, encode embedding cho từng chunk, lưu artifacts vào `data/index`, sau đó tạo FAISS index nếu môi trường có FAISS.

Output artifacts trong `data/index`:

| File | Nội dung | Dùng để làm gì |
|------|----------|----------------|
| `embeddings.npy` | Matrix vector của toàn bộ chunks | Fallback search bằng numpy và kiểm tra vector |
| `chunks.jsonl` | Metadata + text của từng chunk | Mapping FAISS result về nội dung/snippet |
| `meetings.json` | Meeting đã parse đầy đủ | API `GET /meetings/{meeting_id}` |
| `manifest.json` | Tên model và số chiều embedding | Load đúng embedding model lúc search |
| `chunks.faiss` | FAISS index của chunk vectors | Search vector nhanh |

### 2.5. Search, ranking và API output

File triển khai chính: `src/search/searcher.py` và `src/api/main.py`.

Khi nhận query, hệ thống load manifest, chunks, meetings, embeddings và FAISS index; encode query bằng cùng embedding model đã dùng khi build index; search FAISS để lấy candidate chunk gần nhất; nếu không load được FAISS thì fallback sang numpy dot product.

Sau đó hệ thống lọc theo speaker nếu request có tham số `speaker`, gom chunk hits theo `meeting_id`, lấy score meeting bằng score cao nhất trong các chunk thuộc meeting đó, trả tối đa 3 snippets cho mỗi meeting, rồi sắp xếp meeting theo score giảm dần.

API search nhận `query`, `top_k`, optional `speaker`. API output gồm `query`, `top_k`, `results` và `latency_ms`. Mỗi result có `meeting_id`, `title`, `date`, `participants`, `score` và danh sách `snippets`.

Output cuối cùng của pipeline dùng để phục vụ demo semantic search: người dùng nhập prompt, backend tìm meeting liên quan, frontend hiển thị meeting và snippets để người dùng mở/xem tiếp.

## 3. Phạm vi đã hoàn thành

### 3.1. Khởi tạo cấu trúc dự án

- Tạo cấu trúc repo theo các module chính: `src/api`, `src/core`, `src/embedding`, `src/indexing`, `src/preprocessing`, `src/search`, `evaluation`, `frontend`, `data`.
- Bổ sung `requirements.txt`, `Makefile`, `.gitignore` và `README.md` để hỗ trợ cài đặt, chạy indexing, chạy API và evaluation.
- Thiết lập cấu hình tập trung trong `src/core/config.py`, bao gồm đường dẫn dữ liệu, thư mục index, model embedding, kích thước chunk và overlap.

### 3.2. Chuẩn bị dữ liệu và preprocessing

- Xây dựng parser cho AMI Meeting Corpus trong `src/preprocessing/parse_ami.py`.
- Parser hỗ trợ đọc cấu trúc AMI gồm `corpusResources/meetings.xml`, `words/` và `segments/`.
- Trích xuất metadata cuộc họp gồm meeting id, tiêu đề, ngày, danh sách người tham gia, loại meeting, visibility và split.
- Ghép token từ AMI words/segments thành lượt nói theo speaker, kèm thời gian bắt đầu/kết thúc nếu có.
- Bổ sung fallback đọc dữ liệu local dạng JSON/JSONL để smoke test khi chưa có full AMI dataset.
- Thêm file mẫu `data/raw/sample_meetings.json` để kiểm thử pipeline nhanh.

### 3.3. Chunking transcript

- Xây dựng logic chunking trong `src/preprocessing/chunking.py`.
- Mỗi transcript được gom thành các chunk có speaker prefix để giữ ngữ cảnh hội thoại.
- Cấu hình mặc định hiện tại:
  - `CHUNK_SIZE_WORDS = 260`
  - `CHUNK_OVERLAP_WORDS = 60`
- Mỗi chunk lưu các thông tin cần thiết cho retrieval và hiển thị: `chunk_id`, `meeting_id`, `title`, `date`, `participants`, `speakers`, `time_start`, `time_end`, `text`, `source`, `metadata`.

### 3.4. Embedding model

- Xây dựng wrapper embedding trong `src/embedding/model.py`.
- Model mặc định là `sentence-transformers/all-MiniLM-L6-v2`, sinh vector đã normalize để phù hợp tìm kiếm inner product/cosine similarity.
- Bổ sung chế độ `hashing` embedding để chạy smoke test nhẹ, không cần tải transformer model.

### 3.5. Xây dựng FAISS index

- Xây dựng script indexing trong `src/indexing/build_faiss.py`.
- Pipeline indexing gồm:
  1. Load dữ liệu raw từ AMI hoặc JSON mẫu.
  2. Chunk transcript.
  3. Encode embedding cho từng chunk.
  4. Lưu `embeddings.npy`, `chunks.jsonl`, `meetings.json`, `manifest.json`.
  5. Tạo FAISS `IndexFlatIP` và lưu `chunks.faiss` nếu môi trường có FAISS.
- Có fallback lưu vector numpy khi FAISS không khả dụng.
- Đã có lệnh chạy nhanh qua Makefile:
  - `make index`
  - `make index-smoke`

### 3.6. Search service

- Xây dựng lớp tìm kiếm trong `src/search/searcher.py`.
- Hỗ trợ load manifest, chunks, meetings, embeddings và FAISS index đã build.
- Hỗ trợ semantic search theo query tự nhiên.
- Gom kết quả theo `meeting_id`, lấy điểm cao nhất của các chunk thuộc cùng meeting.
- Trả về tối đa 3 snippets liên quan cho mỗi meeting.
- Có fallback search bằng numpy dot product nếu không load được FAISS index.
- Bổ sung lọc đơn giản theo speaker thông qua tham số `speaker`.
- Kết quả trả về có latency theo millisecond để theo dõi hiệu năng truy vấn.

### 3.7. FastAPI backend

- Xây dựng API trong `src/api/main.py`.
- Các endpoint hiện có:
  - `GET /health`: kiểm tra trạng thái service.
  - `POST /search`: nhận query tự nhiên, `top_k` và optional `speaker`, trả về danh sách meeting phù hợp.
  - `GET /meetings/{meeting_id}`: lấy chi tiết một meeting.
- Bật CORS để frontend local có thể gọi backend.
- Searcher được cache bằng `lru_cache` để tránh reload index nhiều lần.

### 3.8. Frontend demo

- Tạo frontend Vite/React trong thư mục `frontend/`.
- UI gồm các view/chức năng chính:
  - Dashboard tổng quan.
  - Search view để nhập prompt tự nhiên và xem kết quả.
  - Meeting detail view để xem chi tiết meeting/snippet.
  - Analytics view cho phần phân tích/demo chỉ số.
  - Sidebar và Header phục vụ điều hướng.
- Frontend gọi backend FastAPI mặc định tại `http://127.0.0.1:8000`.
- Có `.env.example` và hướng dẫn chạy bằng `npm install`, `npm run dev`.

### 3.9. Evaluation

- Xây dựng script đánh giá trong `evaluation/run_eval.py`.
- Hỗ trợ tính các metrics cơ bản:
  - Precision@K
  - Recall@K
  - MRR@K
- Bổ sung dữ liệu qrels mẫu:
  - `data/eval/sample_qrels.json` cho smoke test.
  - `data/eval/ami_qrels.json` cho bộ đánh giá AMI ban đầu.
- Có lệnh chạy evaluation qua Makefile:
  - `make eval`
  - `python -m evaluation.run_eval --qrels data/eval/ami_qrels.json --top-k 5`

## 4. Kết quả hiện tại

### 4.1. Thống kê index

Sau khi indexing trên AMI `ami_public_manual_1.6.2`, hệ thống ghi nhận các thống kê ban đầu:

```text
meetings: 171
chunks: 5347
embedding dim: 384
index backend: faiss
```

### 4.2. Kết quả đánh giá metrics Sprint 1

Đánh giá được chạy trên bộ `data/eval/ami_qrels.json`, gồm 10 truy vấn mẫu. Mỗi truy vấn có danh sách meeting liên quan được gán nhãn thủ công ở mức MVP. Lệnh đánh giá:

```bash
python -m evaluation.run_eval --qrels data/eval/ami_qrels.json --top-k 5
```

Kết quả metrics với `top_k = 5`:

| Metric | Giá trị | Ý nghĩa |
|--------|---------|---------|
| Queries | 10 | Số truy vấn được dùng để đánh giá |
| Precision@5 | 0.60 | Trung bình trong 5 kết quả trả về có 60% kết quả đúng theo qrels |
| Recall@5 | 1.00 | Hệ thống tìm được toàn bộ meeting liên quan trong top 5 đối với tập qrels hiện tại |
| MRR@5 | 1.00 | Kết quả đúng đầu tiên luôn xuất hiện ở vị trí đầu trong top 5 đối với tập qrels hiện tại |

Output evaluation:

```text
queries: 10
precision@5: 0.60
recall@5: 1.00
mrr@5: 1.00
```

### 4.3. Vì sao metrics Sprint 1 cao bất thường?

Nói thẳng: metrics cao vì bộ evaluation Sprint 1 chưa độc lập và còn bias. Đây là con số smoke-test/MVP, không phải benchmark cuối cùng.

Các nguyên nhân chính:

1. Số lượng query rất ít, chỉ có 10 query. Với sample nhỏ như vậy, chỉ cần vài query dễ là Recall/MRR đã tăng mạnh.
2. Qrels được gán nhãn thủ công từ việc inspect top snippets ban đầu. Nghĩa là bộ relevant meeting có thể đã chịu ảnh hưởng từ chính hệ thống retrieval hiện tại, gây circular evaluation.
3. Mỗi query hiện có 3 relevant meeting và đánh giá ở top 5. Nếu hệ thống tìm được cả 3 meeting trong 5 kết quả, Recall@5 sẽ là 1.00. Đây là setting khá dễ cho tập nhỏ.
4. Các query đang khá gần với từ/cụm từ xuất hiện trong transcript AMI, ví dụ `battery life`, `remote control`, `LCD display`, `market research`.
5. Chưa có negative queries khó, chưa có query mơ hồ, query nhiều điều kiện, query theo metadata hoặc query paraphrase mạnh.
6. Chưa có quy trình blind labeling để người gán nhãn không nhìn kết quả hệ thống.

Cách diễn giải đúng là: Sprint 1 metrics xác nhận pipeline chạy được và có tín hiệu retrieval tốt trên một bộ qrels nhỏ; không được dùng các số này để khẳng định chất lượng production hoặc benchmark cuối cùng.

Việc cần làm ở Sprint 2 để metrics đáng tin hơn: tạo qrels độc lập, tăng số query lên ít nhất 50-100, thêm query khó, có negative judgments, báo cáo thêm Recall@1/3, nDCG@K, latency p50/p95 và so sánh với baseline keyword/BM25.

## 5. Cách chạy demo hiện tại

### 5.1. Cài dependencies backend

```bash
pip install -r requirements.txt
```

### 5.2. Build index

Với model mặc định:

```bash
python -m src.indexing.build_faiss
```

Smoke test không cần tải transformer model:

```bash
python -m src.indexing.build_faiss --model hashing
```

### 5.3. Chạy API

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 5.4. Chạy frontend

```bash
cd frontend
npm install
npm run dev
```

Mở UI tại:

```text
http://127.0.0.1:5173
```

### 5.5. Chạy evaluation

```bash
python -m evaluation.run_eval --top-k 5
python -m evaluation.run_eval --qrels data/eval/ami_qrels.json --top-k 5
```

## 6. Những điểm còn hạn chế

- Chưa có hybrid retrieval hoàn chỉnh giữa semantic search, keyword search và metadata filtering.
- Metadata filter mới ở mức đơn giản theo speaker, chưa hỗ trợ lọc theo ngày, participant, meeting type hoặc nhiều điều kiện phức hợp.
- Ranking hiện chủ yếu dựa trên cosine/inner-product score của chunk tốt nhất, chưa có reranker riêng.
- Bộ qrels đánh giá còn nhỏ, cần mở rộng để phản ánh nhiều loại truy vấn hơn.
- Chưa có test tự động cho parser, chunking, indexing, API và search behavior.
- Frontend là demo UI, chưa có đầy đủ trạng thái lỗi, loading chi tiết và kiểm thử UI.
- Chưa có cơ chế cập nhật index gần real-time; hiện tại cần build lại index bằng script.

## 7. Định hướng sprint tiếp theo

- Mở rộng qrels và chuẩn hóa quy trình đánh giá.
- Bổ sung metadata filtering theo participant, date, meeting type và source.
- Thử nghiệm hybrid search kết hợp semantic vector score với keyword/BM25 score.
- Bổ sung reranking ở tầng kết quả meeting/snippet.
- Viết test cho preprocessing, indexing, search và API.
- Hoàn thiện frontend để hiển thị filter, snippet highlight và trạng thái lỗi rõ ràng hơn.
- Nghiên cứu cơ chế incremental indexing để phục vụ dữ liệu mới gần real-time.
