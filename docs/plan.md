# Implementation Plan — Semantic Search for Meeting Minutes

## Problem Statement

Xây dựng hệ thống Semantic Search real-time cho meeting minutes, cho phép truy vấn bằng ngôn ngữ tự nhiên (tiếng Anh), kết hợp hybrid search (semantic + keyword + metadata filtering), triển khai Docker, hoàn thành trong 3-4 tuần.

## Requirements

### Functional Requirements

| # | Yêu cầu | Phân loại |
|---|---------|-----------|
| F1 | Semantic search — hiểu ngữ nghĩa câu hỏi | Core |
| F2 | Prompt-based search — truy vấn bằng ngôn ngữ tự nhiên | Core |
| F3 | Hybrid retrieval — kết hợp semantic + metadata filtering | Core |
| F4 | Tìm kiếm trên nội dung văn bản biên bản | Core |
| F5 | Tìm kiếm/lọc theo metadata (người tham gia, thời gian, chủ đề) | Core |
| F6 | Ranking kết quả theo độ liên quan | Core |
| F7 | Near real-time indexing | Important |
| F8 | Highlight đoạn nội dung liên quan | Demo |
| F9 | REST API | Deliverable |
| F10 | Giao diện demo | Deliverable |

### Non-Functional Requirements

| # | Yêu cầu | Ghi chú |
|---|---------|---------|
| NF1 | Latency <500ms | Cần benchmark |
| NF2 | Xử lý truy vấn phức tạp nhiều điều kiện | Chủ đề + người + thời gian |
| NF3 | Đánh giá bằng Precision, Recall, MRR, NDCG | Cần ground-truth |
| NF4 | So sánh ảnh hưởng cấu hình | Experiment tracking |
| NF5 | Triển khai Docker | Docker Compose |

### Deliverables

1. Hệ thống Semantic Search hoàn chỉnh (end-to-end pipeline)
2. REST API
3. Near real-time indexing
4. Hybrid search (semantic + metadata)
5. Demo UI
6. Báo cáo đánh giá (metrics, so sánh cấu hình)

## Tech Stack

- **Backend:** FastAPI (Python 3.11+)
- **Embedding:** sentence-transformers (`all-MiniLM-L6-v2`, 384-dim)
- **Reranker:** Configurable (FlashRank / cross-encoder / Jina)
- **Search Engine:** Elasticsearch 8.x (BM25 + kNN + RRF)
- **Frontend:** HTML/JS demo
- **Deployment:** Docker Compose
- **Evaluation:** Custom Python scripts

## Task Breakdown

### Task 1: Project Setup & Docker Infrastructure ✅

- Docker Compose: ES 8.15.1 + FastAPI
- FastAPI skeleton with `/health` endpoint
- Pinned `requirements.txt`

### Task 2: Data Collection & Preprocessing Pipeline

- Download AMI, ICSI, QMSum from HuggingFace
- Preprocessing: clean text, speaker-turn chunking (Method B)
- Output: structured chunks with metadata

### Task 3: Elasticsearch Index Design & Embedding Generation

- ES index mapping: `dense_vector` (384-dim, HNSW) + `text` (BM25) + structured metadata
- Batch embedding generation
- Bulk indexing script

### Task 4: Hybrid Search API

- `POST /search` with query, filters, top_k
- ES hybrid query: BM25 + kNN + metadata filter + RRF
- Response: ranked results with passages

### Task 5: Reranking Layer

- Configurable reranker (none / flash / cross-encoder / jina)
- Score top-50 → return top-K

### Task 6: Passage Highlighting

- ES highlight API for BM25 matches
- Return relevant chunk text for semantic matches

### Task 7: Near Real-time Indexing API

- `POST /meetings` — ingest → preprocess → chunk → embed → index
- `PUT /meetings/{id}`, `DELETE /meetings/{id}`

### Task 8: Evaluation Framework & Benchmark

- Evaluation dataset (QMSum queries + hand-crafted queries)
- Metrics: Precision@5, Recall@10, MRR, NDCG@10
- Compare: BM25-only vs semantic-only vs hybrid vs hybrid+rerank

### Task 9: Experiment Comparison & Optimization

- Embedding model comparison (MiniLM vs mpnet)
- Chunk size (256 vs 512)
- Reranker comparison (none vs flash vs cross-encoder vs jina)
- RRF k parameter tuning
- TurboVec experimental comparison (4-bit, 2-bit vs ES kNN)
- Latency benchmarking (p50, p95, p99)

### Task 10: Demo Frontend UI

- Search bar, results list, highlights, filter sidebar
- Serve via Docker

### Task 11: Documentation & Final Report

- README, API docs, architecture diagram
- Report: methodology, experiments, results, conclusions
- Docker deployment guide
