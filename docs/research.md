# Research — Semantic Search for Meeting Minutes

## 1. Retrieval Approach

**Sparse (BM25):** term-frequency matching — tốt cho exact match, tên riêng, mã số.

**Dense (Bi-encoder):** encode query và document thành vectors, tìm nearest neighbors — tốt cho semantic similarity, paraphrase, intent.

**Hybrid (chosen):** kết hợp cả hai qua Reciprocal Rank Fusion (RRF). Lexical signal mạnh cho names/IDs/dates; dense signal mạnh cho paraphrase và ngữ nghĩa. RRF gộp hai ranking mà không cần chuẩn hóa score.

**RRF Formula:** `score = Σ 1/(k + rank_i)`, k=60.

## 2. Embedding Model

**Chosen: `all-MiniLM-L6-v2`** (bi-encoder, 384-dim).
- Chạy tốt trên CPU (~5ms/text), 384-dim tiết kiệm storage.
- Encode full chunk text thành 1 vector — nhanh, scalable, đủ cho meeting retrieval.
- Vector được normalize → dot product = cosine similarity.

## 3. Embedding Input & Metadata Representation

**Decision: embed raw chunk content only.** Metadata được xử lý qua kênh riêng, không trộn vào dense vector.

Lý do:
1. **Separation of concerns.** ES structured fields lo filtering (speaker, date, source); BM25 lo keyword matching; dense vector chỉ lo semantic similarity trên *nội dung*. Không trộn trách nhiệm vào một vector 384-dim.
2. **Embedding capacity.** Token metadata như speaker ID ("MEO069") không mang ngữ nghĩa — làm loãng tín hiệu nội dung.
3. **RRF là điểm tích hợp.** RRF gộp BM25 (bắt metadata/keyword) và kNN (semantic content) mà không cần kênh nào biết kênh kia.

Biểu diễn:
- `content_text`: text passage sạch cho BM25 + highlighting
- `content_embedding`: dense vector của `content_text`
- `metadata_text`: dạng text của title, speakers, date, source, topic — cho BM25
- structured fields: exact filters cho speaker, time range, meeting_id, source

## 4. Hybrid Search Architecture (Elasticsearch 8.x)

Trước retrieval, một bước query-understanding nhẹ (rule-based) tách prompt thành `semantic_query` + `filters`. Dùng deterministic components: speaker dictionary, date parsing, source/meeting-id matching. Filter confidence thấp **không** áp như hard filter — giữ full prompt cho BM25 và dense retrieval. Điều này giữ prompt search thực dụng mà không cần LLM, và lỗi filter có thể debug tách biệt khỏi ranking.

```
User Query (prompt)
   │
   ▼
Embedding (all-MiniLM-L6-v2) → query vector 384-dim
   │
   ▼
Elasticsearch 8.x
   ┌──────────────┐  ┌──────────────┐  ┌───────────────┐
   │  BM25 Search │  │  kNN Search  │  │Metadata Filter│
   │ (inverted    │  │ (HNSW        │  │ (structured   │
   │  index)      │  │  dense_vec)  │  │  fields)      │
   └──────┬───────┘  └──────┬───────┘  └──────┬────────┘
          └─────────┬───────┴─────────────────┘
                    ▼
              RRF (k=60)
                    │ top candidates
                    ▼
   Meeting-level aggregation (group by meeting_id)
                    │ top-K meetings + highlights
                    ▼
       Response (ranked meetings + evidence passages)
```

## 5. Data & Chunking Strategy

**Datasets:**
- **QMSum** (232 meetings, ~1,808 query-summary pairs): dùng làm evaluation backbone vì có query-focused meeting relevance labels.
- **AMI** (171 meetings, speaker turns + timestamps): dùng cho transcript chunking và speaker/time metadata.

Public datasets thiếu metadata title/date/topic đáng tin cậy. Topic labels suy ra từ summaries/keyphrases phải được đánh dấu là derived metadata.

**Chunking: Speaker-turn grouping + sliding-window fallback (Method B).**

Meeting transcripts là dialogue — speaker change thường tương quan với topic shift. Fixed-size chunking cắt ngang ranh giới này, tạo chunk lẫn speaker và câu bị cắt → giảm precision và phá highlight/speaker attribution. Method B giữ đơn vị hội thoại tự nhiên.

Algorithm:
1. Gộp consecutive utterances cùng speaker thành block.
2. Tích lũy turns đến target ~384 tokens.
3. Block > 512 tokens → sliding window (512, overlap 100).
4. Mỗi chunk lưu: `meeting_id`, `speakers[]`, `time_start`, `time_end`, `content_text`, `metadata_text`.

**Indexing: single-level + meeting grouping.** Index chunks (passage-level) với meeting metadata là field trên mỗi chunk; group theo `meeting_id` trong response. Passage-level cần cho highlighting.

## 6. Meeting-level Ranking & Evidence Aggregation

Engine retrieve chunks nhưng sản phẩm trả về meeting minutes, nên ranking phải gộp evidence passage-level thành meeting-level.

1. Retrieve top-N chunks (sau RRF).
2. Group theo `meeting_id`.
3. Meeting score = best chunk score + small boost từ extra relevant chunks.
4. Trả top meetings, mỗi cái kèm 2-3 evidence passages, speakers, timestamps, highlights.

Vì sao:
- Best chunk score tránh meeting dài thắng chỉ vì nhiều chunk.
- Small boost thưởng meeting có nhiều đoạn liên quan.
- Trả passages giữ kết quả explainable.

## 7. Vector Database: Elasticsearch 8.x

ES kết hợp BM25 mature, vector kNN, structured filters, RRF-style fusion, highlighting, và near-real-time indexing trong một search engine. Khớp trực tiếp yêu cầu demo: prompt search trên nội dung, metadata filters, meeting-level results, evidence passages, text highlights — không cần ghép nhiều service.

## 8. Evaluation Framework

Đánh giá phải khớp behavior sản phẩm: prompt tự nhiên → ranked meeting minutes kèm evidence.

### Ground Truth

| Level | Unit | Source | Metrics |
|-------|------|--------|---------|
| Meeting-level | meeting_id | QMSum query-meeting pairs | Recall@K, MRR, NDCG@K |
| Latency | request | Benchmark script | p50, p95 |

### Configurations so sánh
- BM25-only
- Semantic-only (dense)
- Hybrid BM25 + dense (RRF)

### Success Criteria
- Default config p95 latency < 500ms trên máy demo (benchmark, không giả định).
- Hybrid cải thiện meeting-level Recall@10 hoặc MRR so với cả BM25-only và semantic-only.

## 9. Citations

| Topic | Citation | Why |
|-------|----------|-----|
| BM25 | Robertson et al., Okapi at TREC-3, 1994; Robertson & Zaragoza, FnTIR 2009 | Sparse baseline cho terms, people, IDs, dates |
| RRF | Cormack, Clarke, Buettcher, SIGIR 2009 | Fusion BM25 + dense |
| Sentence embeddings | Reimers & Gurevych, EMNLP-IJCNLP 2019 | Bi-encoder chunk embeddings |
| Dense retrieval | Karpukhin et al., EMNLP 2020 | Dense passage retrieval |
| ANN/HNSW | Malkov & Yashunin, IEEE TPAMI 2020 | Scalable approximate kNN |
| Meeting benchmark | Zhong et al., NAACL 2021 | QMSum query-focused meeting data |

Reference URLs:
- RRF: https://doi.org/10.1145/1571941.1572114
- Sentence-BERT: https://aclanthology.org/D19-1410/
- DPR: https://aclanthology.org/2020.emnlp-main.550/
- QMSum: https://aclanthology.org/2021.naacl-main.472/
- HNSW: https://doi.org/10.1109/TPAMI.2018.2889473

## 10. Final Decisions

1. Elasticsearch làm backend — BM25 + vector kNN + metadata filters + RRF + highlighting + near real-time trong một system.
2. Content-only MiniLM embeddings làm dense representation; metadata qua structured fields + BM25.
3. Rule-based query understanding trước retrieval để prompt kích hoạt filters cho people/dates/source.
4. Trả meeting-level results kèm evidence passages cho explainability.
5. Đánh giá ở meeting-level + latency để chứng minh hệ thống giải quyết bài toán sản phẩm.
