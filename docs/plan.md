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
- **Embedding:** sentence-transformers `all-MiniLM-L6-v2` (384-dim) cho **nội dung**; cùng model encode **metadata_text** cho metadata embedding
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

### Task 3: Indexing & Embedding — content + metadata (F3, F4) ⚠️ cần bổ sung
- ES mapping: `content_text` (BM25), `metadata_text` (BM25), `content_embedding` (dense 384-dim), structured metadata (keyword/date/float). ✅ đã có.
- **Bổ sung theo README:** `metadata_embedding = embed(metadata_text)` để có embedding cho **cả nội dung và metadata**. Cho phép semantic matching trên metadata (vd "discussion led by the project manager").

### Task 4: Hybrid Search API (F5, F7, NF6) ✅
- `POST /search`: BM25 + kNN + metadata filter + RRF (k=60); gom mức cuộc họp (max passage score + small boost); evidence + highlight.

### Task 5: Prompt-based NLU — đa điều kiện (F2, F6) ⬜ CỐT LÕI
- Tách prompt tự nhiên → `{semantic_query, filters}` với **3 loại điều kiện: chủ đề (topic), người tham gia (speaker), thời gian (date/range)**.
- Rule-based deterministic: speaker dictionary, source/dataset, **date parser (mốc + khoảng)**; topic giữ trong semantic_query.
- **Lọc mềm:** confidence thấp → không áp hard filter, giữ full prompt cho BM25 + dense.

### Task 6: Near Real-time Ingest API (F8) ⬜
- `POST /meetings` (ingest → chunk → embed nội dung + metadata → index), `PUT/DELETE /meetings/{id}`; ID ổn định; ES refresh ~1s.
- ⚠️ Endpoint ghi/xóa dữ liệu → cần cơ chế xác thực tối thiểu (API key); sẽ flag khi cài.

### Task 7: Demo Frontend (F9, F11) ⬜
- Ô nhập prompt; danh sách biên bản kèm tiêu đề/thời gian/người tham gia; highlight đoạn liên quan; filter sidebar. Serve qua Docker.

### Task 8: Evaluation — đa tầng + theo nguồn + cấu hình (NF1–NF5) ⬜
- **Meeting-level (QMSum):** Precision@k, Recall@10, MRR, NDCG@10, latency p50/p95.
- **Đánh giá riêng theo nguồn (NF3):** content-only vs metadata-only vs hybrid — đo riêng đóng góp của nội dung và metadata.
- **Complex-query set (F6):** bộ `metadata_queries.jsonl` nhỏ, đa điều kiện (topic + người + thời gian) để kiểm tra NLU + filter.
- **Config-influence study (NF5):** ảnh hưởng **kích thước embedding** (vd 384 vs 768) và **index strategy** (vd HNSW params / số ứng viên kNN) lên chất lượng + độ trễ.

### Task 9: Tests & Documentation ⬜
- Unit tests (parser, chunking, RRF); integration test API; README + API docs + Docker guide.

## Phase Plan

| Phase | Goal | Tasks |
|-------|------|-------|
| 1 | Infrastructure | Task 1 ✅ |
| 2 | Data & indexing (content + metadata embedding) | Tasks 2 ✅, 3 ⚠️ |
| 3 | Search core | Task 4 ✅ |
| 4 | Prompt NLU đa điều kiện | Task 5 ⬜ (cốt lõi để đúng "prompt-based") |
| 5 | Real-time ingest | Task 6 ⬜ |
| 6 | Demo | Task 7 ⬜ |
| 7 | Evaluation (theo nguồn + cấu hình) | Task 8 ⬜ |
| 8 | Tests & docs | Task 9 ⬜ |

## Current Status

- ✅ Tasks 1, 2, 4 hoàn tất (code). Task 3 đã có content embedding, **thiếu metadata embedding** (README yêu cầu).
- Data đã sinh: 403 meetings (232 QMSum + 171 AMI), 8.304 chunks, 1.810 queries + qrels.
- ⬜ Task 5 (NLU đa điều kiện), Task 6 (ingest), Task 7 (demo), Task 8 (eval), Task 9 (tests/docs).
- ⚠️ Code lõi **chưa commit**; chưa chạy E2E trên ES sống; CI đang bị comment.

## Out of Scope (README KHÔNG yêu cầu → không làm)

- Reranking / cross-encoder (README chỉ yêu cầu "ranking", không yêu cầu rerank tầng 2).
- So sánh nhiều embedding model (mpnet/e5/ColBERT) — NF5 chỉ yêu cầu ảnh hưởng **kích thước** embedding, không phải model zoo.
- TurboVec / quantization thử nghiệm.
- LLM-based query parser hoặc bước LLM sinh câu trả lời (đây là **search/retrieval**, không phải RAG).
- Audio/ASR/diarization.

## README → Task Traceability Matrix

| Yêu cầu README | Task | Trạng thái |
|----------------|------|-----------|
| Semantic search nội dung | T3, T4 | ✅ |
| Embedding nội dung **và metadata** | T3 | ⚠️ thiếu metadata embedding |
| Prompt-based search (NLU) | T5 | ⬜ |
| Truy vấn nhiều điều kiện (chủ đề/người/thời gian) | T5, T8 | ⬜ |
| Hybrid (semantic + metadata filtering) | T4 | ✅ |
| Ranking theo độ liên quan | T4 | ✅ |
| Near real-time indexing | T6 | ⬜ |
| Highlight | T4, T7 | ✅ search / ⬜ UI |
| REST API | T4, T6 | ✅ search / ⬜ ingest |
| Demo UI (tiêu đề/thời gian/người) | T7 | ⬜ |
| Precision/Recall/MRR | T8 | ⬜ |
| Đánh giá riêng nội dung vs metadata | T8 | ⬜ |
| Thời gian truy vấn / độ trễ | T8 | ⬜ |
| Ảnh hưởng cấu hình (embedding size, index strategy) | T8 | ⬜ |

## Research Basis

- BM25 lexical baseline: Robertson et al., TREC-3, 1994.
- Reciprocal Rank Fusion: Cormack, Clarke, Buettcher, SIGIR 2009.
- Sentence-BERT: Reimers & Gurevych, EMNLP-IJCNLP 2019.
- Dense Passage Retrieval: Karpukhin et al., EMNLP 2020.
- QMSum meeting benchmark: Zhong et al., NAACL 2021.
