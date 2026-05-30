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

**Decision (ground theo README): embedding cho CẢ nội dung VÀ metadata.** README ghi rõ "xây dựng vector embeddings cho cả nội dung văn bản và metadata", nên hệ thống tạo **hai embedding**: `content_embedding` (nghĩa của nội dung) và `metadata_embedding` (nghĩa của metadata_text). Đồng thời vẫn giữ structured fields cho **exact filtering** — embedding bổ sung khả năng *semantic matching trên metadata*, không thay thế filter.

Lý do:
1. **Đúng yêu cầu đề bài.** Đề yêu cầu vector cho cả hai nguồn; đây là điểm phải bám sát, không chỉ dùng BM25 cho metadata.
2. **Semantic matching trên metadata.** Cho phép prompt kiểu "discussion led by the project manager" khớp với role/title dù không trùng từ khóa — điều BM25 thuần không làm tốt.
3. **Tách kênh để đánh giá riêng (NF3).** Có `content_embedding` và `metadata_embedding` tách biệt giúp **đánh giá riêng đóng góp của nội dung và metadata** đúng như README yêu cầu.

Lưu ý trung thực (assumption): metadata dạng ID thuần (vd "MEO069") gần như không mang nghĩa nên embedding ít lợi; phần có lợi là **title, topic, role, speaker name**. Vì vậy `metadata_text` được xây từ các trường có ngữ nghĩa, và đóng góp thực tế của `metadata_embedding` phải được **đo bằng đánh giá theo-nguồn** (mục 8), không giả định trước.

Biểu diễn:
- `content_text`: text passage sạch cho BM25 + highlighting
- `content_embedding`: dense vector của `content_text`
- `metadata_text`: dạng text của title, speakers, role, date, source, topic — cho BM25 **và** metadata embedding
- `metadata_embedding`: dense vector của `metadata_text`
- structured fields: exact filters cho speaker, time range, meeting_id, source

## 4. Hybrid Search Architecture (Elasticsearch 8.x)

Trước retrieval, một bước query-understanding (rule-based) tách prompt thành `semantic_query` + `filters` với **ba loại điều kiện theo README: chủ đề (topic), người tham gia (speaker), thời gian (date/range)**. Dùng deterministic components: speaker dictionary, date parser (mốc và khoảng), source/meeting-id matching; topic giữ trong `semantic_query`. Filter confidence thấp **không** áp như hard filter — giữ full prompt cho BM25 và dense retrieval. Điều này giữ prompt search thực dụng mà không cần LLM, và lỗi filter có thể debug tách biệt khỏi ranking.

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

Đánh giá phải khớp behavior sản phẩm **và bám các tiêu chí README** (Precision/Recall/MRR, đánh giá riêng từng nguồn, truy vấn phức tạp, độ trễ, ảnh hưởng cấu hình).

### Ground Truth

| Level | Unit | Source | Metrics |
|-------|------|--------|---------|
| Meeting-level | meeting_id | QMSum query-meeting pairs | Precision@K, Recall@K, MRR, NDCG@K |
| Complex-query (đa điều kiện) | meeting_id | `metadata_queries.jsonl` (chủ đề + người + thời gian) | Filter accuracy, Recall@K, MRR |
| Latency | request | Benchmark script | p50, p95 |

### Đánh giá riêng theo nguồn (NF3 — README yêu cầu)
Đo riêng đóng góp của từng nguồn để biết nội dung và metadata mỗi cái giúp được bao nhiêu:
- **Content-only:** chỉ `content_text` BM25 + `content_embedding`.
- **Metadata-only:** chỉ `metadata_text` BM25 + `metadata_embedding`.
- **Hybrid:** kết hợp cả hai qua RRF + structured filters.

### Configurations so sánh
- BM25-only / Semantic-only (dense) / Hybrid (RRF).
- Content-only / Metadata-only / Hybrid (theo nguồn, ở trên).

### Config-influence study (NF5 — README yêu cầu)
- **Kích thước embedding:** vd 384 (MiniLM) so với 768 (model lớn hơn) — ảnh hưởng chất lượng vs độ trễ/bộ nhớ.
- **Index strategy:** tham số HNSW (`num_candidates`/ef) và kích thước ứng viên kNN — ảnh hưởng recall vs latency.

### Complex queries (F6 — README yêu cầu)
Bộ truy vấn nhiều điều kiện gồm **chủ đề + người tham gia + thời gian** để kiểm tra NLU tách filter và metadata matching.

### Success Criteria
- Default config p95 latency < 500ms trên máy demo (benchmark, không giả định).
- Hybrid cải thiện meeting-level Recall@10 hoặc MRR so với cả BM25-only và semantic-only.
- Thêm metadata embedding phải cải thiện (hoặc ít nhất không hại) đánh giá theo-nguồn so với metadata BM25 thuần.

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
2. **Embedding cho cả nội dung và metadata** (`content_embedding` + `metadata_embedding`) theo README, kèm structured fields cho exact filtering.
3. Rule-based query understanding đa điều kiện (chủ đề + người + thời gian) trước retrieval.
4. Trả meeting-level results kèm evidence passages cho explainability.
5. Đánh giá đa tầng: meeting-level (Precision/Recall/MRR/NDCG), **riêng theo nguồn nội dung vs metadata**, truy vấn phức tạp, latency, và **ảnh hưởng cấu hình (embedding size, index strategy)**.
