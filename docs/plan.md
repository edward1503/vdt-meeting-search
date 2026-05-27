# Implementation Plan — Semantic Search for Meeting Minutes

## Problem Statement

Xây dựng hệ thống Semantic Search real-time cho meeting minutes, cho phép truy vấn bằng ngôn ngữ tự nhiên (tiếng Anh), kết hợp hybrid search (semantic + keyword + metadata filtering), triển khai Docker, hoàn thành trong 3-4 tuần.

## Requirements

### Functional Requirements

| # | Yêu cầu | Phân loại |
|---|---------|-----------|
| F1 | Semantic search — hiểu ngữ nghĩa câu hỏi, không chỉ keyword matching | Core |
| F2 | Prompt-based search — nhập truy vấn bằng ngôn ngữ tự nhiên | Core |
| F3 | Hybrid retrieval — kết hợp semantic + metadata filtering | Core |
| F4 | Tìm kiếm trên nội dung văn bản biên bản | Core |
| F5 | Tìm kiếm/lọc theo metadata (người tham gia, thời gian, chủ đề) | Core |
| F6 | Ranking kết quả theo độ liên quan | Core |
| F7 | Near real-time indexing — cập nhật dữ liệu mới nhanh | Important |
| F8 | Highlight đoạn nội dung liên quan trong biên bản | Demo |
| F9 | API cho phép gửi truy vấn và nhận kết quả | Deliverable |
| F10 | Giao diện demo nhập prompt và hiển thị kết quả | Deliverable |

### Non-Functional Requirements

| # | Yêu cầu | Ghi chú |
|---|---------|---------|
| NF1 | Thời gian truy vấn thấp (low latency <500ms) | Cần benchmark |
| NF2 | Xử lý truy vấn phức tạp nhiều điều kiện | Chủ đề + người + thời gian cùng lúc |
| NF3 | Đánh giá bằng metrics: Precision, Recall, MRR | Cần ground-truth dataset |
| NF4 | So sánh ảnh hưởng cấu hình (embedding size, index strategy) | Experiment tracking |
| NF5 | Triển khai Docker/Server | Docker Compose |

### Deliverables

1. Hệ thống Semantic Search hoàn chỉnh — end-to-end pipeline
2. REST API — endpoint tìm kiếm
3. Hệ thống indexing — near real-time
4. Hybrid search — semantic + metadata
5. Demo UI — giao diện web
6. Báo cáo đánh giá — metrics, so sánh cấu hình

## Background Research

### 1. Semantic Search & Dense Retrieval

**Sparse Retrieval (BM25):** Tìm kiếm dựa trên term frequency — tốt cho exact match, tên riêng, mã số.

**Dense Retrieval (Bi-encoder):** Encode query và document thành vectors, tìm nearest neighbors — tốt cho semantic similarity, paraphrase, intent matching.

**Hybrid:** Kết hợp cả hai qua Reciprocal Rank Fusion (RRF) — cho recall cao hơn 15-30% so với dùng riêng lẻ.

**Retrieve & Re-rank Pipeline (2-stage):**

```
Stage 1: Retrieval (fast, broad)
  - BM25 → top 100 keyword matches
  - kNN → top 100 semantic matches
  - RRF fusion → top 50 combined

Stage 2: Re-ranking (slow, precise)
  - Cross-encoder scores (query, doc) pairs
  - Re-sort top 50 → final top 10
```

### 2. Embedding Models

| Model | Type | Dim | Speed | Accuracy | Use case |
|-------|------|-----|-------|----------|----------|
| **all-MiniLM-L6-v2** | Bi-encoder (sentence) | 384 | ~5ms/text CPU | Good | Production, low resource |
| all-mpnet-base-v2 | Bi-encoder (sentence) | 768 | ~12ms/text | Better | Higher accuracy needs |
| intfloat/e5-large-v2 | Bi-encoder (asymmetric) | 1024 | ~25ms/text | Best | SOTA retrieval |
| ColBERT | Late interaction (contextual) | 128/token | Slower index | Excellent | Fine-grained matching |

**Chosen: `all-MiniLM-L6-v2`** — chạy tốt trên CPU, 384-dim tiết kiệm storage, đủ tốt cho benchmark.

**Sentence Embedding vs Contextual Embedding:**

- **Sentence embedding (Bi-encoder):** Encode toàn bộ text thành 1 vector duy nhất. Nhanh, scalable, nhưng mất fine-grained token interactions.
- **Contextual embedding (ColBERT/Late interaction):** Giữ 1 vector per token, tính relevance qua MaxSim. Chính xác hơn nhưng storage lớn hơn 100x.
- **Decision:** Dùng sentence embedding (bi-encoder) cho retrieval + cross-encoder cho reranking = balance tốt nhất.

### 3. Hybrid Search Architecture (Elasticsearch 8.x)

```
┌─────────────────────────────────────────────────────────┐
│                    User Query (prompt)                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Embedding Service (FastAPI)                  │
│         sentence-transformers: all-MiniLM-L6-v2          │
└─────────────────────┬───────────────────────────────────┘
                      │ query vector (384-dim)
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Elasticsearch 8.x                            │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  BM25 Search │  │  kNN Search  │  │Metadata Filter│  │
│  │  (inverted   │  │  (HNSW index │  │  (structured  │  │
│  │   index)     │  │   dense_vec) │  │   fields)     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │          │
│         └──────────┬───────┘──────────────────┘          │
│                    │                                     │
│         ┌──────────▼──────────┐                          │
│         │   RRF (k=60)        │                          │
│         │   Rank Fusion       │                          │
│         └──────────┬──────────┘                          │
│                    │                                     │
└────────────────────┼────────────────────────────────────┘
                     │ top-50 candidates
                     ▼
┌─────────────────────────────────────────────────────────┐
│           Cross-Encoder Re-ranker                        │
│     cross-encoder/ms-marco-MiniLM-L6-v2                  │
│     Score each (query, passage) pair                     │
└─────────────────────┬───────────────────────────────────┘
                      │ top-10 ranked results
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Response (ranked meetings + highlights)      │
└─────────────────────────────────────────────────────────┘
```

**RRF Formula:** `score = Σ 1/(k + rank_i)` where k=60 (standard).

### 4. Data & Chunking Strategy

**Datasets:**
- AMI (`edinburghcstr/ami`, config `ihm`): 137 meetings, ~109K utterances, fields: `meeting_id`, `text`, `speaker_id`, `begin_time`, `end_time`
- ICSI (`StDestiny/icsi_cleaned`): 59 meetings, fields: `src` (dialogue), `tgt` (summary)
- QMSum (`pszemraj/qmsum-cleaned`): 232 meetings, 1,808 query-summary pairs, fields: `input` (query + dialogue), `output` (summary)

**Chunking Strategy: Speaker-turn grouping with sliding window fallback (Method B)**

We evaluated two approaches:

| Criteria | A: Fixed sliding window | B: Speaker-turn + fallback |
|----------|------------------------|---------------------------|
| Semantic coherence | ❌ Cuts mid-sentence/speaker | ✅ Preserves speaker boundaries |
| Speaker attribution | ❌ Mixed speakers per chunk | ✅ Clear speaker metadata |
| Supports "who said X" queries | ❌ No | ✅ Yes |
| Chunk size consistency | ✅ Uniform 512 tokens | ⚠️ Variable, needs min/max bounds |
| Implementation complexity | ✅ Simple | ⚠️ Moderate |
| Embedding quality | ⚠️ Random boundaries dilute signal | ✅ Natural semantic units |

**Why Method B:** Meeting transcripts are dialogue — speaker changes often correlate with topic shifts. Fixed-size chunking blindly cuts across these boundaries, producing chunks with mixed speakers and split sentences. This hurts both retrieval precision (diluted semantic signal) and the highlight feature (can't attribute text to speakers). Method B preserves natural conversation units while maintaining chunk sizes suitable for embedding models.

**Algorithm:**
1. Merge consecutive utterances from same speaker into one block
2. If merged block < 200 tokens → merge with next speaker block (retain both speaker IDs)
3. If merged block > 512 tokens → apply sliding window (512 tokens, 100 token overlap)
4. Each chunk stores: `meeting_id`, `speakers[]`, `time_start`, `time_end`, `text`

**Indexing: Single-level with meeting grouping**
- Index chunks (passage-level) with meeting metadata as fields on each chunk
- Group results by `meeting_id` in response to show per-meeting results
- Simpler than two-level, and passage-level is needed for highlighting anyway

### 5. Evaluation Strategy

**Tạo evaluation dataset:**
- Dùng LLM generate ~100 synthetic queries từ meeting summaries
- Mỗi query có ground-truth relevant meeting IDs
- Query types: topic-based, person-based, time-based, complex multi-condition

**Metrics:**

| Metric | Formula | Ý nghĩa |
|--------|---------|---------|
| Precision@K | relevant_in_K / K | Tỷ lệ đúng trong top-K |
| Recall@K | relevant_in_K / total_relevant | Tỷ lệ tìm được |
| MRR | 1/rank_first_relevant | Vị trí kết quả đúng đầu tiên |
| NDCG@K | DCG/IDCG | Chất lượng ranking có trọng số |
| Latency | ms/query | Tốc độ phản hồi |

**Experiments:**
1. BM25-only vs Semantic-only vs Hybrid
2. Embedding dim: 384 (MiniLM) vs 768 (mpnet)
3. With/without cross-encoder reranking
4. Chunk size: 256 vs 512 tokens
5. Content search vs Metadata search vs Combined

## Tech Stack

- **Backend:** FastAPI (Python 3.11+)
- **Embedding:** sentence-transformers (`all-MiniLM-L6-v2`)
- **Reranker:** cross-encoder (`ms-marco-MiniLM-L6-v2`)
- **Search Engine:** Elasticsearch 8.x (hybrid: BM25 + kNN + metadata filter + RRF)
- **Frontend:** Simple React/HTML demo
- **Deployment:** Docker Compose (ES + FastAPI + Frontend)
- **Evaluation:** Custom Python scripts with precision/recall/MRR/NDCG

## Task Breakdown

### Task 1: Project Setup & Docker Infrastructure

- **Objective:** Thiết lập project structure, Docker Compose với Elasticsearch 8.x và FastAPI skeleton
- **Implementation:**
  - Docker Compose: Elasticsearch 8.x (single node), FastAPI service
  - FastAPI skeleton với health check endpoint
  - `requirements.txt` với pinned versions
- **Test:** Docker compose up thành công, ES health = green, FastAPI `/health` returns 200

### Task 2: Data Collection & Preprocessing Pipeline

- **Objective:** Download AMI corpus, xử lý và chuẩn hóa thành structured format
- **Implementation:**
  - Script download AMI corpus từ HuggingFace
  - Preprocessing: clean text, merge utterances theo speaker turns
  - Chunking: sliding window 512 tokens, 20% overlap
  - Output: JSON files với structure `{meeting_id, chunks, metadata}`
- **Test:** Verify output format, chunk sizes, metadata completeness

### Task 3: Elasticsearch Index Design & Embedding Generation

- **Objective:** Thiết kế ES index mapping cho hybrid search, generate embeddings
- **Implementation:**
  - ES index mapping: `dense_vector` (384-dim, HNSW), `text` (BM25), structured metadata
  - Embedding service: batch encode all chunks
  - 2 indices: `meetings` (document-level) và `meeting_chunks` (passage-level)
  - Bulk indexing script
- **Test:** Indices created, all documents indexed, kNN query returns results

### Task 4: Hybrid Search API Implementation

- **Objective:** Implement core search endpoint với BM25 + kNN + metadata filter + RRF
- **Implementation:**
  - `POST /search` accepting `{query, filters, top_k}`
  - ES query: `sub_searches` + `rank: {rrf: {window_size: 100, rank_constant: 60}}`
  - Response: ranked results with meeting info and relevant passages
- **Test:** Semantic, keyword, and combined queries return correct results

### Task 5: Cross-Encoder Reranking Layer

- **Objective:** Thêm stage-2 reranking để cải thiện precision
- **Implementation:**
  - Load `cross-encoder/ms-marco-MiniLM-L6-v2`
  - Score top-50 candidates, re-sort → final top-K
  - Configurable on/off for A/B comparison
- **Test:** Reranked results show higher relevance

### Task 6: Passage Highlighting

- **Objective:** Highlight relevant text spans trong biên bản
- **Implementation:**
  - ES highlight API cho BM25 matches
  - Return top-scoring chunk text as relevant passage for semantic matches
- **Test:** Highlights contain query-relevant terms/passages

### Task 7: Near Real-time Indexing API

- **Objective:** API cho phép thêm/cập nhật meeting minutes
- **Implementation:**
  - `POST /meetings` — ingest, preprocess, chunk, embed, index
  - `PUT /meetings/{id}`, `DELETE /meetings/{id}`
  - ES refresh interval = 1s
- **Test:** New meeting searchable within 2 seconds

### Task 8: Evaluation Framework & Benchmark

- **Objective:** Xây dựng evaluation dataset và framework đo metrics
- **Implementation:**
  - Generate 100 synthetic evaluation queries
  - Ground-truth relevant meeting IDs per query
  - Compute Precision@5, Precision@10, Recall@10, MRR, NDCG@10
  - Compare: BM25-only, semantic-only, hybrid, hybrid+reranker
- **Test:** Evaluation produces reproducible metrics table

### Task 9: Experiment Comparison & Optimization

- **Objective:** Chạy experiments so sánh các cấu hình, bao gồm đánh giá TurboVec (TurboQuant, ICLR 2026) như một alternative vector search backend
- **Implementation:**
  - Embedding model comparison (MiniLM vs mpnet)
  - Chunk size (256 vs 512)
  - With/without reranker
  - RRF k parameter tuning
  - Latency benchmarking (p50, p95, p99)
  - **TurboVec experimental comparison:**
    - Install `turbovec` as vector index backend
    - Build TurboVec index (IdMapIndex, dim=384, bit_width=4 and bit_width=2)
    - Compare retrieval backends on same query set:
      - ES kNN (HNSW, exact at this scale)
      - TurboVec 4-bit quantization
      - TurboVec 2-bit quantization
      - Brute-force exact search (baseline)
    - Measure: Recall@K vs exact, query latency, memory usage, index build time
    - Evaluate TurboVec filtered search (allowlist from BM25 candidates) as hybrid approach
    - Analyze TurboQuant behavior at low-dim (d=384) vs paper's high-dim results
- **Test:** All experiments produce valid metrics and charts
- **Report section:** "Evaluation of TurboQuant for low-dimensional meeting embeddings" — contributes empirical data at d=384 where few benchmarks exist

### Task 10: Demo Frontend UI

- **Objective:** Giao diện web cho phép nhập query và hiển thị kết quả
- **Implementation:**
  - Search bar, results list, expandable highlights, filter sidebar
  - Serve via Docker
- **Test:** UI renders, search works, filters apply, highlights visible

### Task 11: Documentation & Final Report

- **Objective:** Documentation và báo cáo kết quả
- **Implementation:**
  - README: setup, architecture, API docs
  - Report: methodology, experiments, results, conclusions
  - Docker deployment guide
- **Test:** Fresh clone → docker compose up → working system
