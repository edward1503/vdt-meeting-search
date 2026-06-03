# Sprint Plan - VDT Meeting Search

**Timeline**: 01/06/2026 → 30/06/2026 (4 tuần)
**Deadline nộp**: Đầu tháng 7/2026
**Docs sync**: 03/06/2026 — trạng thái dưới đây đã được đối chiếu với codebase hiện tại.

> Lưu ý: checklist này phản ánh implementation trong repo, không thay thế kết quả benchmark cuối cùng. Những mục phụ thuộc Elasticsearch/data sống cần chạy lại trước khi nộp/demo.

---

## Sprint 1: Data & Infrastructure (01/06 - 08/06)

### Mục tiêu
Có data pipeline hoàn chỉnh + Elasticsearch chạy được + index data thành công.

### Tasks
- [x] Verify preprocessed data (meetings.jsonl, chunks.jsonl) đúng format bằng preprocessing + validation code
- [x] Docker Compose: Elasticsearch 8.15 chạy qua `docker/docker-compose.yml`
- [x] Implement self-host embedding pipeline (`intfloat/e5-base-v2`, 768-dim) for content + metadata chunks
- [x] Implement bulk indexing (dense_vector + text fields)
- [x] Index toàn bộ processed chunks vào ES qua `make index` / `src.indexing.bulk_index`
- [ ] Verify lại bằng ES sống trước demo: `curl localhost:9201/meeting_chunks/_count`

### Deliverables
1. Elasticsearch running với data đã index
2. Script `make preprocess && make index` chạy end-to-end không lỗi
3. Verify bằng `curl localhost:9201/meeting_chunks/_count` → số docs khớp `data/processed/chunks.jsonl` hiện tại

### Success Metrics
| Metric | Target |
|--------|--------|
| Chunks indexed | ≥ 2500 |
| Index time (full) | < 10 phút |
| ES health | green/yellow |
| Zero data loss | meetings_count match giữa JSONL và ES |

---

## Sprint 2: Search Engine (09/06 - 15/06)

### Mục tiêu
Hybrid search hoạt động: BM25 + kNN + RRF fusion + meeting-level aggregation.

### Tasks
- [x] BM25 search endpoint (full-text trên `content_text`, `metadata_text`, `title`)
- [x] kNN search endpoint (vector similarity trên `content_embedding` hoặc `metadata_embedding`)
- [x] RRF fusion (application-layer, k=60)
- [x] Meeting-level aggregation (best chunk score + small evidence boost)
- [x] Query understanding rule-based: source, speaker, date range theo năm
- [x] Metadata filters: source, speaker, date range; tự tách prompt dùng lọc mềm khi caller chưa truyền filter tường minh
- [x] Unit tests cho fusion/chunking/query understanding/API

### Deliverables
1. `search_meetings()` function trả về ranked meetings + highlighted chunks
2. 3 modes hoạt động: `bm25`, `semantic`, `hybrid`
3. Tests pass: `make test`

### Success Metrics
| Metric | Target |
|--------|--------|
| BM25 search works | ✓ returns results |
| kNN search works | ✓ returns results |
| Hybrid returns better results than either alone | Spot-check 5 queries |
| Latency (hybrid, single query) | < 500ms |
| Unit tests | All pass |

---

## Sprint 3: API + Evaluation (16/06 - 22/06)

### Mục tiêu
FastAPI hoàn chỉnh + evaluation benchmark chạy được + đạt target metrics.

### Tasks
- [x] FastAPI endpoints: `POST /search`, `POST /meetings`, `PUT /meetings/{id}`, `DELETE /meetings/{id}`
- [x] API key authentication cho write endpoints qua `X-API-Key` / `INGEST_API_KEY`
- [x] Evaluation script: MRR@K, Precision@K, Recall@K, nDCG@K
- [ ] Run lại benchmark trên QMSum queries (`qrels.jsonl`) trước khi chốt báo cáo
- [x] So sánh modes bằng `--matrix`: BM25 vs Semantic vs Hybrid, content vs metadata channel
- [ ] Tune nếu benchmark mới chưa đạt: chunk_size, RRF k, aggregation weights, `num_candidates`
- [x] Latency benchmark: P50, P95 trong `evaluation/run_eval.py`

### Deliverables
1. API chạy: `uvicorn src.api.main:app`
2. Evaluation report (bảng so sánh 3 modes)
3. Đạt target metrics

### Success Metrics
| Metric | Target | Stretch |
|--------|--------|---------|
| MRR@10 | ≥ 0.50 | ≥ 0.60 |
| Recall@10 | ≥ 0.60 | ≥ 0.70 |
| Precision@10 | ≥ 0.12 | ≥ 0.15 |
| nDCG@10 | ≥ 0.45 | ≥ 0.55 |
| Latency P50 | < 200ms | < 100ms |
| Latency P95 | < 500ms | < 300ms |
| Hybrid > BM25 (MRR) | ≥ +10% | ≥ +20% |

---

## Sprint 4: Frontend + Polish + Documentation (23/06 - 30/06)

### Mục tiêu
Demo UI hoạt động, documentation hoàn chỉnh, sẵn sàng nộp.

### Tasks
- [x] Frontend ghép vào backend API (search box + results list + highlights) qua `frontend/index.html` và FastAPI static mount
- [x] Near real-time indexing API: create/update/delete meeting, refresh ES sau ghi
- [x] Startup script `start.sh` hỗ trợ chạy ES, index data nếu cần, rồi chạy API trên host
- [x] README có architecture, setup, commands, evaluation summary
- [ ] Slides/báo cáo: problem statement, approach, results, demo
- [x] Edge cases cơ bản trong UI/API: empty query, HTTP error, escaped highlight HTML, bounded `top_k`
- [x] CI: GitHub Actions workflow tồn tại trong `.github/workflows/ci.yml`

### Deliverables
1. Demo chạy end-to-end: `docker compose up` → mở browser → search
2. Báo cáo/slides hoàn chỉnh
3. Video demo (nếu cần)
4. Code clean, documented, tests pass

### Success Metrics
| Metric | Target |
|--------|--------|
| Full stack starts with 1 command | ✓ |
| Search UI returns results | ✓ |
| New meeting indexable via API | < 5s to searchable |
| All tests pass | ✓ |
| Documentation complete | README + docs/ |
| Demo scenario works | 3 query types: keyword, semantic, mixed |

---

## Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Metrics không đạt target | Cao | Tune sớm ở Sprint 3, có 1 tuần buffer |
| ES performance issues | Trung bình | Giảm num_candidates, tăng RAM |
| Embedding chậm | Trung bình | Batch processing, pre-compute offline, chạy API/indexing trên host để dùng CUDA nếu có |
| Frontend integration issues | Thấp | Frontend đã mock sẵn, chỉ ghép API |

---

## Weekly Checkpoints

| Tuần | Checkpoint | Pass/Fail criteria |
|------|-----------|-------------------|
| W1 (08/06) | Data indexed, ES running | Implementation done; re-run ES `_count` before demo |
| W2 (15/06) | Search works end-to-end | Implementation done; verify 3 modes against live ES |
| W3 (22/06) | Metrics đạt target | Eval script done; benchmark numbers need fresh run |
| W4 (30/06) | Demo ready | UI + startup script done; still need final report/slides |

---

## Current Codebase Status (03/06/2026)

| Area | Status | Evidence |
|------|--------|----------|
| Data preprocessing | ✅ Implemented | `src/preprocessing/*`, `make preprocess` |
| Embedding/indexing | ✅ Implemented | `src/embedding/model.py`, `src/indexing/bulk_index.py`, `make index` |
| Search API | ✅ Implemented | `src/api/main.py`, `src/search/hybrid.py` |
| Prompt NLU | ✅ Basic implementation | `src/search/query_understanding.py`; source/speaker/year filters |
| Ingest/update/delete | ✅ Implemented | `POST /meetings`, `PUT /meetings/{id}`, `DELETE /meetings/{id}` |
| Demo UI | ✅ Implemented | `frontend/index.html`, FastAPI static mount |
| Evaluation | ✅ Script implemented | `evaluation/run_eval.py`, `--matrix`, p50/p95 |
| Tests | ✅ Implemented | `tests/test_api.py`, `tests/test_chunking.py`, `tests/test_hybrid_fusion.py`, `tests/test_query_understanding.py` |
| Final benchmark/report | ⚠️ Pending verification | Need live ES + processed/indexed data run |

---

## Lưu ý

- Sprint 1-2 là **critical path** - nếu trễ sẽ ảnh hưởng toàn bộ
- Sprint 3 có buffer để tune metrics
- Sprint 4 chủ yếu polish, nếu Sprint 1-3 xong sớm thì dư thời gian
- Mỗi sprint kết thúc bằng 1 deliverable có thể demo được
