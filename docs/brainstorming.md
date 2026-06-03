# Brainstorming Log - VDT Meeting Search

> Historical note (docs sync 03/06/2026): file này là nhật ký brainstorm/ý tưởng ban đầu, không phải trạng thái implementation hiện tại. Source of truth hiện tại là `README.md`, `docs/plan.md`, `docs/research.md`, và `docs/sprint_plan.md`. Codebase hiện dùng self-host `intfloat/e5-base-v2` 768-dim, content + metadata embeddings tách riêng, FastAPI ingest/search API, demo UI, evaluation matrix, và tests.

## Thông tin đề bài
- Xây dựng hệ thống Semantic Search real-time cho meeting minutes
- Cho phép truy vấn bằng prompt tự nhiên
- Trả về danh sách biên bản phù hợp + highlight đoạn liên quan
- Dataset: AMI Meeting Corpus (tiếng Anh)

---

## Vòng 1: Phân rã vấn đề

### Q1: Scope - Retrieval vs QA?
- **Trả lời**: Retrieval + snippet highlighting. QA nằm ngoài scope.
- **Lý do**: Đề bài yêu cầu "trả về danh sách biên bản" (retrieval) và "highlight đoạn nội dung liên quan" (snippet), không yêu cầu sinh câu trả lời.

### Q2: "Real-time" nghĩa là gì?
- **Trả lời**: Post-upload indexing nhanh (vài giây), không phải live streaming.
- **Lý do**: "Meeting minutes" là sản phẩm sau cuộc họp. Đề bài không nhắc ASR/speech-to-text. "Near real-time" = biên bản mới upload → searchable trong vài giây.

### Q3: Đối tượng tìm kiếm?
- **Trả lời**: Không giới hạn - nội dung, metadata, người tham gia, thời gian, chủ đề.
- **Vấn đề thiết kế**: Cần strategy kết hợp content search + metadata filtering.

### Q4: Giá trị thực của semantic search so với keyword?
- **Trả lời**: Giải quyết vocabulary mismatch.
- **Ví dụ**: "tăng lương" match cả "điều chỉnh thu nhập"; "vấn đề bảo mật" match cả "rò rỉ thông tin".
- **Bổ sung**: Đề bài yêu cầu "prompt-based search" → keyword search không đủ. Nhưng hybrid (BM25 + semantic) luôn tốt hơn pure semantic vì exact match vẫn quan trọng cho tên người, mã số, ngày tháng.

---

## Vòng 2: Thiết kế chi tiết

### Q5: Metadata strategy - Filter riêng hay embed cùng content?
- **Trả lời**: Chưa rõ, cần phân tích thêm.
- **Kết luận**: Dùng CẢ HAI:
  - Structured metadata (meeting_id, date, participants, topics) → dùng để filter
  - Enriched text (gộp metadata vào text trước khi embed) → để vector "hiểu" context
  - Lý do: Filter chính xác cho query cụ thể, semantic search cho query mơ hồ

### Q6: Chunking strategy?
- **Trả lời**: Nghiêng về chunk theo topic segment.
- **Phân tích các phương pháp**: Xem bên dưới.

### Q7: Kết quả trả về ở level nào?
- **Trả lời**: Meeting-level result + highlight nội dung liên quan.
- **Implication**: Cần bước aggregation - nhiều chunks cùng 1 meeting → gộp score → trả về meeting → highlight chunks có score cao nhất.

---

## Phân tích: Chunking Strategy

### Phương pháp A: Embed cả meeting thành 1 vector

| Ưu | Nhược |
|----|-------|
| Đơn giản, không cần aggregation | Embedding model có giới hạn token (512-8192) |
| 1 meeting = 1 vector = dễ quản lý | Meeting dài → thông tin bị nén, mất chi tiết |
| | Không thể highlight đoạn cụ thể |

**Kết luận**: Không phù hợp. Meeting 30 phút = 5000-10000 tokens, vượt giới hạn model. Và không highlight được.

### Phương pháp B: Chunk theo topic segment

| Ưu | Nhược |
|----|-------|
| Mỗi chunk có ngữ nghĩa trọn vẹn (1 chủ đề) | Cần topic segmentation (AMI có sẵn annotation) |
| Phù hợp để highlight | Kích thước chunk không đều |
| Giữ được context tự nhiên | Nếu dataset khác không có annotation → cần model segment |

**Kết luận**: Phù hợp nhất cho AMI (đã có topic annotation). Mỗi segment là 1 unit tìm kiếm, dễ highlight.

### Phương pháp C: Fixed-size chunking (ví dụ 512 tokens)

| Ưu | Nhược |
|----|-------|
| Đơn giản, không cần annotation | Có thể cắt giữa câu/ý |
| Kích thước đều → embedding quality ổn định | Mất ngữ cảnh nếu 1 ý trải qua 2 chunks |
| Dễ implement | Cần overlap để giảm mất thông tin |

**Kết luận**: Backup plan nếu không có topic annotation. Cần overlap 10-20%.

### Phương pháp D: Hybrid - Topic segment + fallback fixed-size

- Nếu segment quá dài (>1024 tokens) → chia nhỏ thêm bằng fixed-size
- Nếu segment quá ngắn (<50 tokens) → gộp với segment liền kề

**Kết luận**: Đây là phương pháp robust nhất trong thực tế.

---

## Quyết định tạm thời

| Thành phần | Quyết định |
|------------|-----------|
| Scope | Retrieval + highlight, không QA |
| Real-time | Near real-time indexing (post-upload) |
| Search type | Hybrid (BM25 + semantic) |
| Metadata | Structured filter + enriched embedding |
| Chunking | Topic segment (AMI có sẵn) + fallback fixed-size |
| Result level | Meeting-level + highlight relevant chunks |
| Language | Tiếng Anh |
| Dataset | AMI Meeting Corpus |

---

### Q8: Aggregation strategy - gộp chunk scores thành meeting score?
- **Trả lời**: Weighted - max score + bonus cho nhiều chunks match.
- **Lý do**: Max đơn thuần bỏ qua tín hiệu "nhiều đoạn liên quan" (meeting có 5 chunks match đáng tin hơn meeting chỉ có 1 chunk match). Sum/Mean bị bias bởi meeting dài (nhiều chunks hơn). Weighted cân bằng cả hai.
- **Công thức gợi ý**: `score = max_chunk_score + α * log(num_matching_chunks)` (α cần tune)

### Q9: Metadata filter - Pre-filter, Post-filter, hay Hybrid?
- **Trả lời**: Xem phân tích bên dưới.

---

## Phân tích: Metadata Filtering Strategy

### Bối cảnh
User nhập prompt tự nhiên, ví dụ: "meetings with the project manager about budget last week". Hệ thống cần xử lý cả semantic meaning lẫn metadata constraints.

### Phương pháp 1: Pre-filter (lọc trước, search sau)

```
Query → Parse intent (extract metadata) → Filter documents → Semantic search trên tập đã lọc
```

| Ưu | Nhược |
|----|-------|
| Nhanh - search space nhỏ hơn | Cần query parser/NLU để extract metadata |
| Kết quả chính xác về metadata | Parser sai → mất kết quả (false negative) |
| Elasticsearch hỗ trợ tốt (bool query + knn) | Phức tạp implementation |

**Khi nào dùng**: Query có metadata rõ ràng ("meetings in March", "meetings with John").

### Phương pháp 2: Post-filter (search trước, lọc sau)

```
Query → Semantic search toàn bộ → Lọc kết quả theo metadata → Return
```

| Ưu | Nhược |
|----|-------|
| Đơn giản, không cần parser | Lãng phí compute (search rồi bỏ) |
| Không bị mất kết quả do parse sai | Top-K sau filter có thể ít hơn mong muốn |
| | Không scale nếu dataset lớn |

**Khi nào dùng**: Dataset nhỏ, hoặc metadata filter không critical.

### Phương pháp 3: Embed metadata cùng content (no explicit filter)

```
Query → Semantic search trên enriched text (content + metadata đã gộp) → Return
```

| Ưu | Nhược |
|----|-------|
| Đơn giản nhất - không cần parser | Metadata bị "chìm" trong content dài |
| Semantic model tự "hiểu" metadata | Không chính xác cho exact match (tên, ngày) |
| Một pipeline duy nhất | Khó debug khi kết quả sai |

**Khi nào dùng**: Metadata ít, query chủ yếu về content.

### Phương pháp 4: Hybrid - Semantic search + metadata boost (RECOMMENDED)

```
Query → Parallel:
  ├── Semantic search trên enriched chunks → scores
  ├── BM25 keyword search → scores  
  └── Metadata match (soft filter, boost score) → bonus
→ Fusion (RRF hoặc weighted sum) → Final ranking
```

| Ưu | Nhược |
|----|-------|
| Không cần perfect parser - metadata match chỉ boost, không loại | Phức tạp hơn |
| Robust: nếu parser sai, semantic vẫn cứu | Cần tune weights |
| Tận dụng tất cả signals | |
| Elasticsearch native support (bool + knn + function_score) | |

**Chi tiết**: Thay vì hard filter (loại bỏ), dùng soft filter (boost score):
- Query mention "project manager" → documents có participant=PM được +0.2 score
- Query mention "last week" → documents trong tuần trước được +0.2 score
- Nếu parser không extract được gì → chỉ dùng semantic, không mất gì

---

## Quyết định tạm thời (cập nhật)

| Thành phần | Quyết định |
|------------|-----------|
| Scope | Retrieval + highlight, không QA |
| Real-time | Near real-time indexing (post-upload) |
| Search type | Hybrid (BM25 + semantic + metadata boost) |
| Metadata | Structured filter + enriched embedding |
| Chunking | Topic segment (AMI có sẵn) + fallback fixed-size |
| Result level | Meeting-level + highlight relevant chunks |
| Aggregation | Weighted: max_score + α*log(num_matching_chunks) |
| Metadata filter | Hybrid soft boost (không hard filter) |
| Language | Tiếng Anh |
| Dataset | AMI Meeting Corpus |

---

---

## Phân tích: Query Parser

### Phương pháp 1: Rule-based (regex/pattern matching)

```
"meetings with John" → participant = "John"
"in March 2024" → date_range = [2024-03-01, 2024-03-31]
"about budget" → topic_hint = "budget"
```

| Ưu | Nhược |
|----|-------|
| Cực nhanh (<1ms) | Brittle - chỉ match pattern đã define |
| Không cần model/API | Không hiểu paraphrase ("involving John" vs "with John") |
| Deterministic, dễ debug | Cần maintain regex cho mỗi pattern mới |
| Zero latency overhead | Không handle ambiguity |

**Phù hợp khi**: Query patterns ít và predictable, cần latency thấp nhất.

### Phương pháp 2: NER model (spaCy / lightweight transformer)

```
"meetings with John about budget last week"
→ PERSON: "John", TOPIC: "budget", DATE: "last week"
```

| Ưu | Nhược |
|----|-------|
| Hiểu nhiều biến thể ngôn ngữ hơn | Latency ~10-50ms |
| Có sẵn pre-trained (spaCy en_core_web_sm) | NER standard không có label "TOPIC" |
| Không cần external API | Cần fine-tune hoặc custom pipeline cho domain |
| Chạy local, offline | Accuracy phụ thuộc training data |

**Phù hợp khi**: Cần balance giữa accuracy và latency, chạy offline.

### Phương pháp 3: LLM-based (GPT/local LLM parse intent)

```
Prompt: "Extract structured filters from this query: ..."
→ {"participant": "John", "topic": "budget", "time": "last week"}
```

| Ưu | Nhược |
|----|-------|
| Hiểu mọi biến thể, rất flexible | Latency cao (500ms-2s nếu API, 100-500ms nếu local) |
| Không cần training data | Cost nếu dùng API |
| Handle ambiguity tốt nhất | Overkill cho query đơn giản |
| Zero-shot, không cần fine-tune | Non-deterministic |

**Phù hợp khi**: Query phức tạp, latency không critical, có budget cho API.

### So sánh tổng hợp

| Tiêu chí | Rule-based | NER | LLM |
|----------|-----------|-----|-----|
| Latency | <1ms ✅ | 10-50ms | 100-2000ms ❌ |
| Accuracy | Thấp (chỉ exact pattern) | Trung bình | Cao ✅ |
| Flexibility | Thấp ❌ | Trung bình | Cao ✅ |
| Complexity | Thấp ✅ | Trung bình | Cao |
| Offline | ✅ | ✅ | ❌ (trừ local LLM) |

### Recommendation: NER + Rule-based fallback

- Dùng spaCy NER cho PERSON, DATE, ORG
- Rule-based bổ sung cho patterns đơn giản (topic keywords)
- Không dùng LLM vì: latency cao, đề bài yêu cầu real-time, và metadata boost là soft (sai cũng không sao)
- Nếu parser không extract được gì → chỉ dùng semantic search, vẫn OK

---

## Phân tích: Embedding Model

### Yêu cầu cho bài toán này:
- Tiếng Anh
- Conversational text (meeting transcript, không phải formal document)
- Asymmetric search (query ngắn 5-20 tokens, chunk dài 100-500 tokens)
- Chạy local (không API dependency)
- Latency hợp lý cho real-time

### Phương pháp 1: all-MiniLM-L6-v2 (sentence-transformers)

| Thuộc tính | Chi tiết |
|-----------|----------|
| Dimensions | 384 |
| Max tokens | 256 |
| Size | 80MB |
| Speed | Rất nhanh (~5ms/query on CPU) |
| Quality | Trung bình |

| Ưu | Nhược |
|----|-------|
| Nhẹ, nhanh, dễ deploy | Chất lượng thấp hơn models lớn |
| Phổ biến, nhiều tài liệu | Max 256 tokens - chunks dài bị cắt |
| Chạy tốt trên CPU | Không tối ưu cho asymmetric search |

### Phương pháp 2: all-mpnet-base-v2 (sentence-transformers)

| Thuộc tính | Chi tiết |
|-----------|----------|
| Dimensions | 768 |
| Max tokens | 384 |
| Size | 420MB |
| Speed | Trung bình (~15ms/query on CPU) |
| Quality | Tốt |

| Ưu | Nhược |
|----|-------|
| Chất lượng tốt hơn MiniLM đáng kể | Chậm hơn 3x |
| Vẫn chạy được trên CPU | Max 384 tokens vẫn có thể không đủ |
| Balanced size/quality | Symmetric - không tối ưu cho search |

### Phương pháp 3: intfloat/e5-base-v2 hoặc e5-large-v2

| Thuộc tính | e5-base | e5-large |
|-----------|---------|----------|
| Dimensions | 768 | 1024 |
| Max tokens | 512 | 512 |
| Size | 420MB | 1.3GB |
| Speed | ~15ms | ~40ms |
| Quality | Tốt | Rất tốt |

| Ưu | Nhược |
|----|-------|
| Thiết kế cho retrieval/search ✅ | Cần prefix "query:" và "passage:" |
| Asymmetric search native ✅ | e5-large cần GPU để real-time |
| 512 tokens - đủ cho hầu hết chunks | |
| MTEB benchmark top-tier | |

### Phương pháp 4: BAAI/bge-base-en-v1.5 hoặc bge-large-en-v1.5

| Thuộc tính | bge-base | bge-large |
|-----------|----------|-----------|
| Dimensions | 768 | 1024 |
| Max tokens | 512 | 512 |
| Size | 420MB | 1.3GB |
| Speed | ~15ms | ~40ms |
| Quality | Tốt | Rất tốt |

| Ưu | Nhược |
|----|-------|
| MTEB #1 khi release ✅ | Cần prefix "Represent this sentence:" |
| Retrieval-optimized ✅ | bge-large cần GPU |
| 512 tokens | Newer models đã vượt qua |
| Hỗ trợ instruction-based query | |

### Phương pháp 5: intfloat/e5-mistral-7b-instruct hoặc large embedding models

| Thuộc tính | Chi tiết |
|-----------|----------|
| Dimensions | 4096 |
| Max tokens | 4096+ |
| Size | 14GB |
| Speed | Cần GPU mạnh |
| Quality | State-of-the-art |

| Ưu | Nhược |
|----|-------|
| Chất lượng cao nhất | Cần GPU 16GB+ ❌ |
| Handle long context | Latency cao cho real-time ❌ |
| Instruction-following | Overkill cho bài toán này |

### So sánh tổng hợp

| Model | Quality | Speed | Max tokens | Asymmetric | Phù hợp? |
|-------|---------|-------|-----------|------------|-----------|
| all-MiniLM-L6-v2 | ⭐⭐ | ⭐⭐⭐⭐⭐ | 256 | ❌ | Prototype |
| all-mpnet-base-v2 | ⭐⭐⭐ | ⭐⭐⭐⭐ | 384 | ❌ | OK |
| e5-base-v2 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 512 | ✅ | ✅ Recommended |
| bge-base-en-v1.5 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 512 | ✅ | ✅ Good |
| e5-large-v2 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 512 | ✅ | Nếu có GPU |
| e5-mistral-7b | ⭐⭐⭐⭐⭐ | ⭐ | 4096 | ✅ | Overkill ❌ |

### Recommendation: intfloat/e5-base-v2

- **Lý do chính**: Thiết kế cho retrieval, asymmetric search native, 512 tokens đủ cho topic segments, chạy được trên CPU với latency chấp nhận được.
- **Backup**: Nếu cần chất lượng cao hơn và có GPU → e5-large-v2.
- **Prototype nhanh**: all-MiniLM-L6-v2 để test pipeline trước, swap model sau.

---

## Phân tích: Reranker

### Bối cảnh
Sau retrieval (bi-encoder) lấy top-50 candidates, reranker (cross-encoder) re-score chính xác hơn.

**Tại sao cần?** Bi-encoder encode query và document RIÊNG RẼ → so sánh bằng cosine similarity. Cross-encoder encode query+document CÙNG LÚC → attention giữa query và document → chính xác hơn nhưng chậm hơn nhiều.

### Phương pháp 1: Không dùng reranker

| Ưu | Nhược |
|----|-------|
| Đơn giản, nhanh | Bi-encoder miss subtle relevance |
| Latency thấp nhất | Ranking quality thấp hơn |
| Ít component = ít bug | |

**Khi nào OK**: Dataset nhỏ, query đơn giản, hoặc bi-encoder đã đủ tốt.

### Phương pháp 2: Cross-encoder reranker

Các model phổ biến:

| Model | Size | Latency (50 docs) | Quality |
|-------|------|-------------------|---------|
| cross-encoder/ms-marco-MiniLM-L-6-v2 | 80MB | ~100ms (CPU) | Tốt |
| cross-encoder/ms-marco-MiniLM-L-12-v2 | 120MB | ~200ms (CPU) | Tốt hơn |
| BAAI/bge-reranker-base | 420MB | ~300ms (CPU) | Rất tốt |
| BAAI/bge-reranker-large | 1.3GB | ~500ms (GPU) | Excellent |

| Ưu | Nhược |
|----|-------|
| Cải thiện ranking đáng kể (+5-15% MRR) | Thêm 100-500ms latency |
| Catch subtle relevance bi-encoder miss | Thêm complexity |
| Chỉ chạy trên top-K (không full corpus) | Cần manage thêm 1 model |

### Phương pháp 3: ColBERT (late interaction)

| Ưu | Nhược |
|----|-------|
| Nhanh hơn cross-encoder | Phức tạp hơn để deploy |
| Chất lượng gần cross-encoder | Index size lớn hơn (token-level vectors) |
| Có thể pre-compute document embeddings | Ít tooling support |

### Recommendation: Dùng cross-encoder/ms-marco-MiniLM-L-6-v2

- **Lý do**: +100ms latency chấp nhận được cho real-time (tổng <500ms). Cải thiện ranking rõ rệt. Nhẹ, chạy CPU.
- **Strategy**: Retrieve top-50 bằng bi-encoder → rerank → return top-10.
- **Nếu latency quá cao**: Giảm candidate set xuống top-20, hoặc bỏ reranker.

---

## Phân tích: Vector Database

### Phương pháp 1: FAISS (Facebook AI Similarity Search)

| Ưu | Nhược |
|----|-------|
| Cực nhanh (in-memory) | Không persistent mặc định (cần save/load) |
| Mature, well-tested | Không có built-in BM25/full-text search |
| Nhiều index types (Flat, IVF, HNSW) | Không có metadata filtering native |
| Free, no infra | Không scale horizontally |
| Python native | Cần tự build API layer |

**Phù hợp khi**: Dataset nhỏ (<100K vectors), prototype, hoặc kết hợp với Elasticsearch riêng cho BM25.

### Phương pháp 2: Elasticsearch (với knn search)

| Ưu | Nhược |
|----|-------|
| BM25 + vector search trong 1 hệ thống ✅ | Nặng hơn FAISS (cần JVM, cluster) |
| Metadata filtering native ✅ | Vector search chậm hơn FAISS thuần |
| Hybrid search built-in (RRF) ✅ | Config phức tạp |
| Persistent, scalable | Cần RAM nhiều |
| REST API sẵn | Learning curve |
| Mature ecosystem, monitoring | |

**Phù hợp khi**: Cần hybrid search, production-ready, có metadata filtering.

### Phương pháp 3: Milvus

| Ưu | Nhược |
|----|-------|
| Thiết kế cho vector search | Overkill cho dataset nhỏ |
| Scale tốt (billions of vectors) | Thêm infra component |
| Metadata filtering | Không có BM25 native (cần kết hợp ES) |
| Cloud-managed option (Zilliz) | Ít mature hơn ES |

**Phù hợp khi**: Dataset rất lớn, cần scale, pure vector search.

### Phương pháp 4: Qdrant / Weaviate / Pinecone

| Ưu | Nhược |
|----|-------|
| Modern, developer-friendly | Thêm dependency |
| Metadata filtering tốt | Không có BM25 (trừ Weaviate) |
| Managed options | Lock-in (Pinecone) |

### So sánh tổng hợp

| Tiêu chí | FAISS | Elasticsearch | Milvus | Qdrant |
|----------|-------|--------------|--------|--------|
| Hybrid search (BM25+vector) | ❌ | ✅ Native | ❌ | ❌ |
| Metadata filter | ❌ | ✅ | ✅ | ✅ |
| Latency (vector) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Scalability | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| All-in-one | ❌ | ✅ | ❌ | ❌ |
| Complexity | Thấp | Trung bình | Cao | Trung bình |

### Recommendation: Elasticsearch

- **Lý do chính**: Hybrid search (BM25 + knn + metadata filter) trong 1 hệ thống duy nhất. Đề bài yêu cầu hybrid search → ES là lựa chọn tự nhiên nhất.
- **Cụ thể**: ES 8.x hỗ trợ `knn` search + `RRF` (Reciprocal Rank Fusion) để combine BM25 và vector scores.
- **Tradeoff**: Chậm hơn FAISS cho pure vector search, nhưng bù lại không cần maintain 2 hệ thống riêng.

---

## Quyết định tạm thời (cập nhật)

| Thành phần | Quyết định | Lý do |
|------------|-----------|-------|
| Scope | Retrieval + highlight | Đề bài |
| Real-time | Near real-time indexing | Post-upload |
| Search type | Hybrid (BM25 + semantic + metadata boost) | Robust |
| Metadata | Structured filter + enriched embedding | Cả hai |
| Chunking | Topic segment + fallback fixed-size | AMI có annotation |
| Result level | Meeting-level + highlight chunks | Đề bài |
| Aggregation | Weighted: max + α*log(n_chunks) | Balance |
| Metadata filter | Soft boost (NER + rule-based) | Real-time friendly |
| Embedding | intfloat/e5-base-v2 | Retrieval-optimized, 512 tokens |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | +100ms, đáng trade |
| Vector DB | Elasticsearch 8.x | Hybrid native, all-in-one |
| Language | Tiếng Anh | |
| Dataset | AMI Meeting Corpus | |

---

## Phân tích: Evaluation Strategy

### Vấn đề: AMI Corpus không có search relevance labels

AMI có summaries, topic annotations, dialogue acts - nhưng KHÔNG có bộ "query → relevant meetings" sẵn. Bạn phải tự tạo.

### Bước 1: Tạo Ground Truth Dataset

**Cách 1: Manual annotation (recommended cho project này)**

- Viết 50-100 queries đa dạng:
  - Content-based: "discussions about remote control button design"
  - Person-based: "meetings where the project manager presented"
  - Time/topic: "meetings about budget in the early phase"
  - Complex: "meetings where industrial designer disagreed with marketing"
- Với mỗi query, label 3-5 meetings là relevant (binary: relevant/not relevant)
- Effort: ~4-8 giờ cho 50 queries

**Cách 2: Synthetic từ summaries**

- AMI có extractive/abstractive summaries cho mỗi meeting
- Dùng summary làm "query" → meeting đó là relevant
- Ưu: Tự động, nhiều data. Nhược: Không realistic (user không query bằng summary)

**Cách 3: Hybrid**

- 30 queries synthetic (từ summaries, paraphrase lại)
- 20 queries manual (realistic, phức tạp)
- Đây là cách balanced nhất

### Bước 2: Metrics - Cái nào đo gì?

| Metric | Đo gì | Công thức đơn giản | Khi nào quan trọng |
|--------|--------|-------------------|-------------------|
| **Precision@K** | Trong top-K results, bao nhiêu % là relevant? | relevant_in_topK / K | User chỉ xem vài kết quả đầu |
| **Recall@K** | Trong tất cả meetings relevant, bao nhiêu % nằm trong top-K? | relevant_in_topK / total_relevant | Không muốn miss kết quả |
| **MRR** (Mean Reciprocal Rank) | Kết quả relevant đầu tiên ở vị trí nào? | 1/rank_of_first_relevant | User muốn answer ngay top-1 |
| **nDCG@K** | Top-K có đúng thứ tự không? (relevant cao hơn) | Normalized discounted cumulative gain | Ranking order matters |
| **MAP** (Mean Average Precision) | Trung bình precision tại mỗi relevant result | mean of AP across queries | Overall system quality |

### Bước 3: Thế nào là "tốt"?

**Benchmark thực tế cho information retrieval:**

| Metric | Kém | Trung bình | Tốt | Rất tốt |
|--------|-----|-----------|-----|---------|
| MRR@10 | <0.3 | 0.3-0.5 | 0.5-0.7 | >0.7 |
| Precision@5 | <0.2 | 0.2-0.4 | 0.4-0.6 | >0.6 |
| Recall@10 | <0.4 | 0.4-0.6 | 0.6-0.8 | >0.8 |
| nDCG@10 | <0.3 | 0.3-0.5 | 0.5-0.7 | >0.7 |

**Lưu ý**: Số này phụ thuộc vào độ khó của queries và dataset. Với AMI (~170 meetings, domain hẹp), target hợp lý:

| Metric | Target cho project này |
|--------|----------------------|
| MRR@10 | ≥ 0.5 (relevant result trong top-2 trung bình) |
| Precision@5 | ≥ 0.4 (2/5 results là relevant) |
| Recall@10 | ≥ 0.7 (tìm được 70% meetings relevant) |

### Bước 4: So sánh gì với gì?

Để chứng minh giá trị của semantic search, so sánh:

| Experiment | Mô tả |
|-----------|--------|
| Baseline 1 | BM25 only (Elasticsearch full-text) |
| Baseline 2 | Semantic only (e5-base-v2 knn) |
| Experiment 1 | Hybrid (BM25 + semantic, RRF) |
| Experiment 2 | Hybrid + metadata boost |
| Experiment 3 | Hybrid + metadata boost + reranker |

Nếu Experiment 3 > Baseline 1 rõ rệt → chứng minh semantic search có giá trị.

### Bước 5: Latency evaluation

| Metric | Target |
|--------|--------|
| P50 latency | < 200ms |
| P95 latency | < 500ms |
| Indexing time (1 meeting) | < 5s |

---

## Quyết định tạm thời (cập nhật)

| Thành phần | Quyết định | Lý do |
|------------|-----------|-------|
| Scope | Retrieval + highlight | Đề bài |
| Real-time | Near real-time indexing | Post-upload |
| Search type | Hybrid (BM25 + semantic + metadata boost) | Robust |
| Metadata | Structured filter + enriched embedding | Cả hai |
| Chunking | Topic segment + fallback fixed-size | AMI có annotation |
| Result level | Meeting-level + highlight chunks | Đề bài |
| Aggregation | Weighted: max + α*log(n_chunks) | Balance |
| Metadata filter | Soft boost (NER + rule-based) | Real-time friendly |
| Embedding | intfloat/e5-base-v2 | Retrieval-optimized, 512 tokens |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | +100ms, đáng trade |
| Vector DB | Elasticsearch 8.x | Hybrid native, all-in-one |
| Evaluation | Hybrid ground truth (30 synthetic + 20 manual) | Balance effort/quality |
| Target metrics | MRR@10 ≥ 0.5, Recall@10 ≥ 0.7 | Realistic |
| Demo UI | Đã có mock, chỉ cần ghép backend | |
| Language | Tiếng Anh | |
| Dataset | AMI Meeting Corpus | |

---

## Câu hỏi mở (chưa trả lời)

- [ ] Fusion strategy: RRF hay weighted sum? Weights bao nhiêu?
- [ ] Deployment: Docker compose setup?
- [ ] AMI corpus preprocessing: format nào, cần clean gì?
- [ ] API design: endpoints nào cần cho frontend?
