# Sprint Plan - VDT Meeting Search

**Timeline**: 01/06/2026 → 30/06/2026 (4 tuần)
**Deadline nộp**: Đầu tháng 7/2026

---

## Sprint 1: Data & Infrastructure (01/06 - 08/06)

### Mục tiêu
Có data pipeline hoàn chỉnh + Elasticsearch chạy được + index data thành công.

### Tasks
- [ ] Verify preprocessed data (meetings.jsonl, chunks.jsonl) đúng format
- [ ] Docker Compose: Elasticsearch 8.15 chạy stable
- [ ] Implement embedding pipeline (all-MiniLM-L6-v2 encode chunks)
- [ ] Implement bulk indexing (dense_vector + text fields)
- [ ] Index toàn bộ ~3000 chunks vào ES
- [ ] Verify: query thử bằng curl trực tiếp vào ES

### Deliverables
1. Elasticsearch running với data đã index
2. Script `make preprocess && make index` chạy end-to-end không lỗi
3. Verify bằng `curl localhost:9201/meeting_chunks/_count` → ~3000 docs

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
- [ ] BM25 search endpoint (full-text trên content_text)
- [ ] kNN search endpoint (vector similarity trên embedding field)
- [ ] RRF fusion (application-layer, k=60)
- [ ] Meeting-level aggregation (max_score + α*log(n_chunks))
- [ ] Query understanding (entity extraction: speaker, date)
- [ ] Metadata soft boost (speaker match → +score)
- [ ] Unit tests cho fusion logic

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
- [ ] FastAPI endpoints: GET /search, POST /meetings, DELETE /meetings/{id}
- [ ] API key authentication cho write endpoints
- [ ] Evaluation script: MRR@10, Precision@10, Recall@10, nDCG@10
- [ ] Run benchmark trên QMSum queries (qrels.jsonl)
- [ ] So sánh 3 modes (--matrix): BM25 vs Semantic vs Hybrid
- [ ] Tune nếu cần: chunk_size, RRF k, aggregation weights
- [ ] Latency benchmark: P50, P95

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
- [ ] Frontend ghép vào backend API (search box + results list + highlights)
- [ ] Near real-time indexing demo (upload meeting → searchable trong <5s)
- [ ] Docker Compose: full stack (ES + API + Frontend) 1 lệnh
- [ ] README final: architecture, setup, results
- [ ] Slides/báo cáo: problem statement, approach, results, demo
- [ ] Edge cases: empty results, long queries, special characters
- [ ] CI: GitHub Actions chạy tests

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
| Embedding chậm | Thấp | Batch processing, pre-compute offline |
| Frontend integration issues | Thấp | Frontend đã mock sẵn, chỉ ghép API |

---

## Weekly Checkpoints

| Tuần | Checkpoint | Pass/Fail criteria |
|------|-----------|-------------------|
| W1 (08/06) | Data indexed, ES running | `curl ES/_count` → 2500+ docs |
| W2 (15/06) | Search works end-to-end | 3 modes return ranked results |
| W3 (22/06) | Metrics đạt target | MRR ≥ 0.5, Recall ≥ 0.6 |
| W4 (30/06) | Demo ready | Full stack 1 command, UI works |

---

## Lưu ý

- Sprint 1-2 là **critical path** - nếu trễ sẽ ảnh hưởng toàn bộ
- Sprint 3 có buffer để tune metrics
- Sprint 4 chủ yếu polish, nếu Sprint 1-3 xong sớm thì dư thời gian
- Mỗi sprint kết thúc bằng 1 deliverable có thể demo được
