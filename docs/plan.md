# Implementation Plan — Semantic Search for Meeting Minutes

## Problem Statement

Xây dựng hệ thống Semantic Search real-time cho meeting minutes, cho phép truy vấn bằng ngôn ngữ tự nhiên, kết hợp hybrid search (semantic + keyword + metadata filtering), triển khai Docker.

MVP dùng public meeting datasets tiếng Anh (QMSum và AMI) để có ground truth và demo ổn định. Hỗ trợ tiếng Việt là hướng mở rộng (thay embedding model bằng multilingual khi có dữ liệu đánh giá phù hợp).

## Requirements

### Functional

| # | Yêu cầu |
|---|---------|
| F1 | Semantic search — hiểu ngữ nghĩa câu hỏi |
| F2 | Prompt-based search — truy vấn bằng ngôn ngữ tự nhiên |
| F3 | Hybrid retrieval — semantic + keyword + metadata filtering |
| F4 | Tìm kiếm trên nội dung biên bản |
| F5 | Lọc theo metadata (người tham gia, nguồn, thời gian) |
| F6 | Ranking kết quả theo độ liên quan |
| F7 | Near real-time indexing |
| F8 | Highlight đoạn nội dung liên quan |
| F9 | REST API |
| F10 | Giao diện demo |

### Non-Functional

| # | Yêu cầu | Ghi chú |
|---|---------|---------|
| NF1 | Latency < 500ms | Benchmark trên máy demo |
| NF2 | Kết quả meeting-level kèm evidence passages | Aggregation/dedup |
| NF3 | Đánh giá Precision/Recall/MRR/NDCG | Cần ground-truth |
| NF4 | Triển khai Docker | Docker Compose |

### Deliverables

1. Hệ thống Semantic Search end-to-end (data → index → search)
2. REST API
3. Near real-time indexing
4. Hybrid search (semantic + keyword + metadata)
5. Demo UI
6. Báo cáo đánh giá (metrics)

## Tech Stack

- **Backend:** FastAPI (Python 3.11+)
- **Embedding:** sentence-transformers `all-MiniLM-L6-v2` (384-dim, chạy tốt trên CPU)
- **Search Engine:** Elasticsearch 8.x (BM25 + kNN + RRF + metadata filters + highlight + near real-time)
- **Frontend:** HTML/JS demo
- **Deployment:** Docker Compose
- **Evaluation:** Custom Python scripts

## Task Breakdown

### Task 1: Infrastructure ✅
- Docker Compose: ES 8.15.1 + FastAPI
- FastAPI skeleton với `/health`
- Pinned `requirements.txt`

### Task 2: Data & Preprocessing ✅
- Parse QMSum và AMI → unified meeting schema
- Speaker-turn chunking (Method B): target 384 / max 512 / overlap 100 tokens
- Output: `meetings.jsonl`, `chunks.jsonl`, `qmsum_queries.jsonl`, `qrels.jsonl`
- Validation checks (`validate_processed.py`)

### Task 3: Indexing & Embedding ✅
- ES mapping: `content_text` (BM25), `metadata_text` (BM25), `content_embedding` (dense_vector 384-dim, HNSW, cosine), structured metadata (keyword/float)
- Batch embedding + bulk indexing (`bulk_index.py`)
- `content_embedding = embed(content_text)`

### Task 4: Hybrid Search API ✅
- `POST /search` với query, top_k, mode (bm25/semantic/hybrid), filters
- BM25 + kNN + metadata filter + RRF (k=60)
- Meeting-level aggregation: meeting score = max passage score + small multi-evidence boost
- Mỗi kết quả kèm top evidence passages, highlights, speakers, timestamps

### Task 5: Prompt Filter Extraction
- Rule-based: speaker dictionary, source/dataset, date parsing
- Confidence thấp → giữ full query cho semantic/BM25, không áp hard filter

### Task 6: Near Real-time Ingest API
- `POST /meetings` — ingest → chunk → embed → index
- `PUT /meetings/{id}`, `DELETE /meetings/{id}`
- Stable document IDs; ES near real-time refresh (~1s)

### Task 7: Demo Frontend
- Search bar, results list, highlights, filter sidebar
- Serve qua Docker

### Task 8: Evaluation
- Meeting-level: QMSum query → source meeting relevant
- Metrics: Recall@10, MRR, NDCG@10
- Latency p50/p95
- So sánh: BM25-only vs semantic-only vs hybrid

### Task 9: Tests & Documentation
- Unit tests cho preprocessing/chunking/search; integration test cho API
- README, API docs, Docker deployment guide

## Phase Plan

| Phase | Goal | Tasks | Output |
|-------|------|-------|--------|
| 1 | Infrastructure | Task 1 | Docker Compose, FastAPI health, ES reachable |
| 2 | Data & indexing | Tasks 2-3 | Processed chunks, ES index |
| 3 | Search core | Task 4 | BM25, kNN, RRF, meeting-level aggregation |
| 4 | Prompt filters | Task 5 | Prompt → semantic query + filters |
| 5 | Real-time ingest | Task 6 | Add/update/delete meetings |
| 6 | Demo | Task 7 | UI với filters, highlights, evidence |
| 7 | Evaluation | Task 8 | Metrics + latency report |
| 8 | Tests & docs | Task 9 | Tests, deployment docs |

## Current Status

- ✅ Tasks 1-4: infrastructure, preprocessing, indexing, hybrid search (code complete)
- Data generated: 403 meetings (232 QMSum + 171 AMI), 8,304 chunks, 1,810 queries + qrels
- ⬜ Tasks 5-9: prompt filters, real-time ingest, demo UI, evaluation run, tests

## Research Basis

- BM25 lexical baseline cho exact terms và names: Robertson et al., Okapi at TREC-3, 1994.
- Reciprocal Rank Fusion để kết hợp các hệ retrieval: Cormack, Clarke, Buettcher, SIGIR 2009.
- Sentence-BERT cho bi-encoder embeddings: Reimers và Gurevych, EMNLP-IJCNLP 2019.
- Dense Passage Retrieval cho semantic matching: Karpukhin et al., EMNLP 2020.
- QMSum cho meeting-level retrieval evaluation: Zhong et al., NAACL 2021.
