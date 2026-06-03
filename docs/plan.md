# Implementation Plan — Semantic Search for Meeting Minutes

> Plan này được **ground trực tiếp theo README** (Mô tả dự án / Nhiệm vụ / Phương pháp đánh giá / Sản phẩm). Mỗi task ánh xạ tới một yêu cầu cụ thể trong README (xem ma trận truy vết ở mục cuối).

## Problem Statement

Xây dựng hệ thống **Semantic Search real-time** cho meeting minutes, dùng **prompt-based search** trên **cả nội dung lẫn metadata (thông tin ngữ cảnh)**. Người dùng gõ prompt tự nhiên (vd: "các cuộc họp có sự tham gia của một cá nhân", "cuộc họp liên quan đến một nghị định cụ thể"); hệ thống hiểu ngữ nghĩa, kết hợp semantic + metadata filtering, trả về danh sách biên bản kèm độ liên quan và đoạn highlight.

MVP dùng public datasets tiếng Anh (QMSum + AMI) để có ground truth và demo ổn định. Tiếng Việt là hướng mở rộng (đổi sang embedding đa ngôn ngữ khi có dữ liệu đánh giá).

## Requirements

### Functional (bám README — mục "Thuật toán", "Sản phẩm", "Demo")

| # | Yêu cầu | Nguồn README |
|---|---------|--------------|
| F1 | Semantic search hiểu ngữ nghĩa câu hỏi | Thuật toán |
| F2 | Prompt-based search bằng NLU (tách prompt → semantic query + điều kiện metadata) | Thuật toán |
| F3 | Embedding cho **cả nội dung VÀ metadata** | Thuật toán / Mô tả |
| F4 | Lưu embedding trong vector store để truy vấn nhanh | Thuật toán |
| F5 | Hybrid retrieval: semantic + metadata filtering | Thuật toán / Sản phẩm |
| F6 | Xử lý truy vấn phức tạp **nhiều điều kiện: chủ đề + người tham gia + thời gian** | Phương pháp đánh giá |
| F7 | Ranking kết quả theo độ liên quan | Thuật toán |
| F8 | Near real-time indexing (cập nhật dữ liệu) | Sản phẩm |
| F9 | Highlight đoạn nội dung liên quan | Demo |
| F10 | REST API gửi truy vấn / nhận kết quả | Sản phẩm |
| F11 | Demo UI: nhập prompt, hiển thị tiêu đề/thời gian/người tham gia | Demo |

### Non-Functional (bám README — mục "Huấn luyện và tối ưu", "Phương pháp đánh giá")

| # | Yêu cầu | Nguồn README |
|---|---------|--------------|
| NF1 | Đo Precision, Recall, MRR | Đánh giá |
| NF2 | Đánh giá độ liên quan ngữ nghĩa (thủ công/benchmark) | Đánh giá |
| NF3 | **Đánh giá riêng từng nguồn: nội dung biên bản và metadata** | Đánh giá |
| NF4 | Đo thời gian truy vấn và độ trễ hệ thống | Huấn luyện & tối ưu |
| NF5 | **So sánh ảnh hưởng cấu hình: kích thước embedding, index strategy** | Huấn luyện & tối ưu |
| NF6 | Kết quả mức cuộc họp kèm evidence passages | Demo / Sản phẩm |
| NF7 | Triển khai Docker | Sản phẩm (hệ thống hoàn chỉnh) |

### Deliverables (README — "Sản phẩm hệ thống" + "Chương trình demo")

1. Hệ thống Semantic Search end-to-end (data → index → search)
2. REST API
3. Near real-time indexing
4. Hybrid search (semantic + metadata filtering)
5. Demo UI (prompt + danh sách biên bản + highlight)
6. Báo cáo đánh giá (metrics, đánh giá riêng nội dung/metadata, ảnh hưởng cấu hình)

## Tech Stack (bám README — "Dữ liệu & công cụ")

- **Backend:** FastAPI (Python 3.11+)
- **Embedding:** self-host `intfloat/e5-base-v2` qua `sentence-transformers` (768-dim), encode **content_text** và **metadata_text**; chạy CUDA nếu có, fallback CPU
- **Search Engine / Vector store:** Elasticsearch 8.x (BM25 + kNN + RRF + metadata filters + highlight + near real-time). README liệt kê FAISS/ES/Milvus — chọn ES vì gộp đủ tính năng trong một hệ thống
- **Frontend:** HTML/JS demo
- **Deployment:** Docker Compose
- **Evaluation:** Custom scripts; cân nhắc `ranx` cho metric IR chuẩn + significance test

## Data (bám README — "Dữ liệu")

- **QMSum:** evaluation backbone (query-focused → qrels query→meeting).
- **AMI:** metadata-rich backbone (speaker turns, roles, timestamps) → phục vụ điều kiện người/thời gian.
- **ICSI:** README liệt kê như nguồn ví dụ; **optional**, chỉ thêm khi QMSum+AMI đã ổn định.

## Task Breakdown

### Task 1: Infrastructure ✅
- Docker Compose: ES 8.15.1 + FastAPI; `/health`; pinned `requirements.txt`.

### Task 2: Data & Preprocessing ✅
- Parse QMSum + AMI → unified schema; speaker-turn chunking (target 384 / max 512 / overlap 100).
- Output: `meetings.jsonl`, `chunks.jsonl`, `qmsum_queries.jsonl`, `qrels.jsonl`; validation.

### Task 3: Indexing & Embedding — content + metadata (F3, F4) ✅
- ES mapping: `content_text` (BM25), `metadata_text` (BM25), `content_embedding` (dense 768-dim), `metadata_embedding` (dense 768-dim), structured metadata (keyword/date/float). ✅ đã có.
- `index_chunk_docs()` embed cả nội dung và metadata bằng cùng model `intfloat/e5-base-v2`; e5 prefix được xử lý trong `src/embedding/model.py`.

### Task 4: Hybrid Search API (F5, F7, NF6) ✅
- `POST /search`: BM25 + kNN + metadata filter + RRF (k=60); gom mức cuộc họp (max passage score + small boost); evidence + highlight.

### Task 5: Prompt-based NLU — đa điều kiện (F2, F6) ⚠️ partial
- Tách prompt tự nhiên → `{semantic_query, filters}` với **3 loại điều kiện: chủ đề (topic), người tham gia (speaker), thời gian (date/range)**.
- Code hiện có rule-based parser cho source/dataset, speaker ID/tên cơ bản, và date range theo năm; cần mở rộng date parser và dictionary để phủ nhiều prompt demo hơn.
- **Lọc mềm:** confidence thấp → không áp hard filter, giữ full prompt cho BM25 + dense.

### Task 6: Near Real-time Ingest API (F8) ✅
- `POST /meetings` (ingest → chunk → embed nội dung + metadata → index), `PUT /meetings/{id}`, `DELETE /meetings/{id}`; ID ổn định; ES refresh sau ghi.
- Endpoint ghi/xóa được bảo vệ bằng header `X-API-Key`, cấu hình qua `INGEST_API_KEY`.

### Task 7: Demo Frontend (F9, F11) ✅
- `frontend/index.html` đã có demo UI static: ô nhập prompt, chọn mode `bm25|semantic|hybrid`, sidebar filter source/speaker/year, hiển thị danh sách biên bản kèm title/date/participants/score và evidence highlights.
- FastAPI mount frontend qua `StaticFiles` nếu thư mục `frontend/` tồn tại, nên có thể mở UI từ API host.

### Task 8: Evaluation — đa tầng + theo nguồn + cấu hình (NF1–NF5) ✅ implementation / ⚠️ results chưa verify trong turn này
- `evaluation/run_eval.py` đã có meeting-level metrics: Precision@K, Recall@K, MRR, nDCG@K, latency p50/p95 trên QMSum qrels.
- `--matrix` so sánh `bm25|semantic|hybrid` trên cả `content` và `metadata` channel, phục vụ đánh giá riêng nội dung vs metadata.
- `--num-candidates` cho phép khảo sát ảnh hưởng index strategy/kNN candidate size.
- Chưa thấy code tạo `metadata_queries.jsonl` trong lượt rà này; complex-query evaluation vẫn là phần cần bổ sung nếu muốn đo riêng prompt đa điều kiện.
- Các bảng kết quả benchmark trong README/docs cần được xem là kết quả mục tiêu hoặc kết quả đã ghi nhận trước đó, chưa được chạy lại trong lượt đồng bộ này.

### Task 9: Tests & Documentation ✅ implementation / ⚠️ docs vừa đồng bộ tiếp
- Tests hiện có: `tests/test_api.py`, `tests/test_chunking.py`, `tests/test_hybrid_fusion.py`, `tests/test_query_understanding.py`.
- Documentation hiện có: README, plan/research/processing/decision explanation/sprint plan, architecture diagrams trong `docs/architecture/`, proposal docs trong `docs/mentor-duty/`.
- `docs/changelog.md` được thêm để follow lịch sử theo commit log và working tree.

## Phase Plan

| Phase | Goal | Tasks |
|-------|------|-------|
| 1 | Infrastructure | Task 1 ✅ |
| 2 | Data & indexing (content + metadata embedding) | Tasks 2 ✅, 3 ✅ |
| 3 | Search core | Task 4 ✅ |
| 4 | Prompt NLU đa điều kiện | Task 5 ⚠️ partial |
| 5 | Real-time ingest | Task 6 ✅ |
| 6 | Demo | Task 7 ✅ |
| 7 | Evaluation (theo nguồn + cấu hình) | Task 8 ✅ implementation / ⚠️ cần chạy lại benchmark |
| 8 | Tests & docs | Task 9 ✅ implementation / ⚠️ docs đang tiếp tục polish |

## Current Status

- ✅ Tasks 1, 2, 3, 4, 6, 7, 8, 9 đã có implementation trong codebase: preprocessing, content + metadata embedding, hybrid search, ingest/update/delete API có API key, demo UI, evaluation script, và unit/API tests.
- Data đã sinh theo docs hiện tại: 403 meetings (232 QMSum + 171 AMI), 8.304 chunks, 1.810 queries + qrels.
- ⚠️ Task 5 đã có parser nền rule-based cho source, AMI speaker ID/tên cơ bản, và date range theo năm; cần mở rộng nếu demo cần nhiều kiểu prompt ngày/tháng/tên người tự nhiên hơn.
- ⚠️ Chưa chạy lại E2E trên Elasticsearch sống và benchmark trong lượt đồng bộ docs này; kết quả metric cần verify lại bằng `make evaluate` hoặc `python -m evaluation.run_eval --matrix`.
- ⚠️ Working tree hiện có thay đổi docs/README/start.sh và di chuyển diagram/proposal chưa commit; xem `docs/changelog.md` để follow.

## Out of Scope (README KHÔNG yêu cầu → không làm)

- Reranking / cross-encoder (README chỉ yêu cầu "ranking", không yêu cầu rerank tầng 2).
- So sánh nhiều embedding model (MiniLM/mpnet/ColBERT) — NF5 chỉ yêu cầu ảnh hưởng **kích thước** embedding/index strategy, default hiện tại là e5-base-v2.
- TurboVec / quantization thử nghiệm.
- LLM-based query parser hoặc bước LLM sinh câu trả lời (đây là **search/retrieval**, không phải RAG).
- Audio/ASR/diarization.

## README → Task Traceability Matrix

| Yêu cầu README | Task | Trạng thái |
|----------------|------|-----------|
| Semantic search nội dung | T3, T4 | ✅ |
| Embedding nội dung **và metadata** | T3 | ✅ |
| Prompt-based search (NLU) | T5 | ⚠️ partial |
| Truy vấn nhiều điều kiện (chủ đề/người/thời gian) | T5, T8 | ⚠️ parser nền / complex-query eval set chưa có |
| Hybrid (semantic + metadata filtering) | T4 | ✅ |
| Ranking theo độ liên quan | T4 | ✅ |
| Near real-time indexing | T6 | ✅ |
| Highlight | T4, T7 | ✅ search + UI |
| REST API | T4, T6 | ✅ search + ingest/update/delete |
| Demo UI (tiêu đề/thời gian/người) | T7 | ✅ |
| Precision/Recall/MRR | T8 | ✅ script / ⚠️ cần chạy lại kết quả |
| Đánh giá riêng nội dung vs metadata | T8 | ✅ `--matrix` channel content/metadata |
| Thời gian truy vấn / độ trễ | T8 | ✅ script p50/p95 / ⚠️ cần chạy lại kết quả |
| Ảnh hưởng cấu hình (embedding size, index strategy) | T8 | ⚠️ `num_candidates` có sẵn; embedding-size comparison chưa tự động |

## Research Basis

- BM25 lexical baseline: Robertson et al., TREC-3, 1994.
- Reciprocal Rank Fusion: Cormack, Clarke, Buettcher, SIGIR 2009.
- Sentence-BERT: Reimers & Gurevych, EMNLP-IJCNLP 2019.
- Dense Passage Retrieval: Karpukhin et al., EMNLP 2020.
- QMSum meeting benchmark: Zhong et al., NAACL 2021.
