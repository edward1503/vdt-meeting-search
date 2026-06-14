# VimQA EDA and Retrieval Strategy Report

Ngày cập nhật: 2026-06-13

Tài liệu này phân tích tập `docs/data/vimqa/`, so sánh cấu trúc với HotpotQA đang dùng trong codebase, và đề xuất chiến lược xử lý retrieval cho dữ liệu tiếng Việt.

## 1. Executive Summary

VimQA trong repository hiện là dataset hỏi đáp tiếng Việt dạng `question/context/answer`, không phải retrieval benchmark chuẩn kiểu BEIR/HotpotQA có sẵn `corpus/queries/qrels`. Tuy nhiên, cấu trúc nội dung của nhiều context khá gần với multi-hop QA: một context thường gồm 1-2 câu/fact nối với nhau, ví dụ một fact về entity chính và một fact về entity liên quan.

Vì vậy, cách phù hợp nhất là xử lý VimQA như một **Vietnamese context retrieval benchmark derived from QA examples**:

```text
question -> query
unique context -> document
question-context mapping -> qrel
answer -> metadata for QA/verifier later
```

Retrieval stack Elasticsearch hiện tại vẫn dùng lại được: BM25, dense, hybrid RRF, iterative hybrid. Nhưng metric và cách diễn giải phải khác HotpotQA: trên VimQA, gold evidence hiện chỉ là một context, không phải 2 supporting documents rời như HotpotQA.

Khuyến nghị chính:

1. Isolate VimQA thành dataset adapter riêng, index riêng, artifacts riêng.
2. Dùng corpus là union unique contexts từ train + test; split query theo train/test.
3. Benchmark chính: `recall@1`, `recall@5`, `recall@10`, `mrr@10`, `ndcg@10`, latency.
4. Đổi embedding model sang multilingual hoặc Vietnamese model; không nên dùng mặc định English BGE small để kết luận chất lượng dense retrieval tiếng Việt.
5. Chạy `es_iterative_hybrid` như diagnostic multi-hop, nhưng không kỳ vọng giống HotpotQA vì qrel VimQA hiện chỉ trỏ tới một context đã ghép sẵn.

## 2. Dataset Files and Schema

Files hiện có:

```text
docs/data/vimqa/train_vimqa.json
docs/data/vimqa/test_vimqa.json
```

Mỗi record có schema:

```json
{
  "question": "...",
  "context": "...",
  "answer": "..."
}
```

Ví dụ nội dung có dạng:

```text
question: Film điện ảnh mà Margalit Ruth "Maggie" Gyllenhaal nhận được vai phụ độc lập vào năm 2001 có kinh phí là 4,5 triệu USD phải không?
context: Cô khởi đầu sự nghiệp điện ảnh ... Donnie Darko (2001) ... Kinh phí làm phim này là 4,5 triệu USD ...
answer: đúng
```

Record đã chứa context chứa evidence. Vì vậy muốn benchmark retrieval thì cần tự tạo corpus và qrels từ context.

## 3. EDA Summary

### 3.1 Size and Duplicates

| Split | Rows | Unique questions | Duplicate question rows | Unique contexts | Duplicate context rows | Unique answers |
|---|---:|---:|---:|---:|---:|---:|
| Train | 8,041 | 7,935 | 106 | 3,198 | 4,843 | 2,130 |
| Test | 1,003 | 989 | 14 | 900 | 103 | 599 |

Nhận xét:

- Train có mức reuse context rất cao: 8,041 QA rows nhưng chỉ 3,198 unique contexts.
- Test có 1,003 QA rows và 900 unique contexts, ít duplicate hơn train.
- Một context có thể sinh nhiều question, nên khi convert sang retrieval benchmark cần dedupe context theo hash.

### 3.2 Length Distribution

| Split | Question p50 | Question p95 | Context p50 | Context p95 | Context max | Context sentences p50 |
|---|---:|---:|---:|---:|---:|---:|
| Train | 16 tokens | 27 tokens | 62 tokens | 106 tokens | 201 tokens | 2 |
| Test | 13 tokens | 24 tokens | 54 tokens | 102 tokens | 150 tokens | 2 |

Nhận xét:

- Context khá ngắn, thường chỉ 1-2 câu.
- Không cần chunking ở baseline đầu tiên; `one context = one document = one vector` là hợp lý.
- Sentence-level retrieval có thể thử sau, nhưng chưa nên là baseline chính vì không có gold supporting sentence labels.

### 3.3 Answer Distribution

| Split | Boolean answers | Boolean pct | Span answers | Span exact-in-context |
|---|---:|---:|---:|---:|
| Train | 3,932 | 48.90% | 4,109 | 99.54% |
| Test | 302 | 30.11% | 701 | 92.87% |

Top answers cho thấy có nhiều câu đúng/sai:

| Split | Frequent answers |
|---|---|
| Train | `đúng`, `không`, `new york`, `thái bình dương`, `mỹ`, `washington, d.c.` |
| Test | `đúng`, `không`, `4`, `2`, `châu âu`, `1` |

Nhận xét:

- VimQA không chỉ là extractive span QA; có tỷ lệ lớn câu yes/no.
- Với span answers, phần lớn answer xuất hiện trực tiếp trong context, nên có thể dùng answer làm metadata hoặc downstream QA validation.
- Retrieval benchmark không nên chấm bằng answer string ở bước đầu; nên chấm bằng context retrieval.

### 3.4 Train/Test Overlap

| Metric | Value |
|---|---:|
| Exact context overlap train-test | 475 contexts |
| Test contexts appearing in train | 52.78% |
| Exact question overlap train-test | 69 questions |
| Exact question-context pair overlap | 5 pairs |

Nhận xét:

- Có overlap context đáng kể giữa train và test.
- Vì mục tiêu retrieval là search trong một corpus, nên corpus nên là union unique contexts từ train + test, còn split eval nên nằm ở query level.
- Nếu chỉ index train contexts rồi eval test, gần một nửa test contexts sẽ không có trong corpus, làm metric sai.
- Nếu chỉ index test contexts, task quá nhỏ và dễ hơn thực tế.

### 3.5 Retrieval Proxy Size

Nếu convert `unique context` thành document:

| Split | Corpus docs if unique contexts | Queries | Qrels | Avg queries/doc | Max queries/doc |
|---|---:|---:|---:|---:|---:|
| Train | 3,198 | 8,041 | 8,041 | 2.514 | 19 |
| Test | 900 | 1,003 | 1,003 | 1.114 | 4 |

Union train + test unique contexts có khoảng 3,623 docs.

### 3.6 Lexical Overlap

| Split | Median question-context token overlap | Average overlap |
|---|---:|---:|
| Train | 0.72 | 0.70 |
| Test | 0.70 | 0.65 |

Nhận xét:

- Question-context lexical overlap cao.
- BM25 có khả năng rất mạnh, đặc biệt với câu hỏi chứa entity/từ khóa giống context.
- Dense-only với embedding model không phù hợp tiếng Việt có thể thua BM25.
- Hybrid vẫn đáng dùng vì dense có thể bổ sung semantic signal cho các câu hỏi diễn đạt khác context.

## 4. Comparison With HotpotQA

### 4.1 Structural Comparison

| Aspect | HotpotQA in current codebase | VimQA local dataset |
|---|---|---|
| Source | `ir_datasets` / BEIR-style | Local JSON files |
| Native retrieval corpus | Có | Chưa có sẵn, phải tạo từ `context` |
| Queries | Có sẵn | Lấy từ `question` |
| Qrels | Có sẵn | Tự sinh: question maps to context doc |
| Evidence granularity | Supporting documents | Single provided context |
| Typical relevant docs/query | Thường 2 support docs | 1 gold context nếu convert trực tiếp |
| Language | English | Vietnamese |
| Multi-hop nature | Native multi-hop retrieval | Multi-hop-like QA context, but evidence already merged |
| Current code support | First-class | Not first-class yet |

### 4.2 Similarities

VimQA giống HotpotQA ở các điểm:

1. Câu hỏi thường yêu cầu nối thông tin giữa entity chính và entity liên quan.
2. Context nhiều khi là tổ hợp 2 fact/wiki snippets, tương tự bridge/comparison reasoning.
3. Entity overlap cao, nên BM25 là baseline quan trọng.
4. Hybrid sparse+dense là hướng hợp lý vì cần cân bằng exact match và semantic match.
5. Có thể đo retrieval bằng qrels và các metric IR như Recall/MRR/nDCG sau khi convert.

### 4.3 Differences

VimQA khác HotpotQA ở các điểm quan trọng:

1. HotpotQA retrieval benchmark có corpus lớn và qrels document-level tách sẵn; VimQA chỉ có context đi kèm từng QA row.
2. HotpotQA cần retrieve đủ nhiều supporting documents; VimQA context hiện đã ghép evidence thành một đoạn.
3. `full_support_recall@k` trên HotpotQA có nghĩa là retrieve đủ toàn bộ support docs; trên VimQA direct-conversion nó chỉ có nghĩa là retrieve đúng một gold context.
4. HotpotQA hiện là English; VimQA là Vietnamese, cần xử lý embedding/tokenization/language-specific normalization khác.
5. HotpotQA full corpus có hàng triệu docs; VimQA proxy corpus hiện chỉ khoảng vài nghìn contexts, nhỏ hơn nhiều.

## 5. Vietnamese-Specific Processing Strategy

### 5.1 Text Normalization

Nên chuẩn hóa nhẹ, không phá tiếng Việt:

- Normalize Unicode về NFC.
- Collapse whitespace.
- Giữ dấu tiếng Việt; không strip accents ở baseline chính.
- Lowercase cho hashing/dedupe, nhưng lưu text gốc để display và embedding.
- Chuẩn hóa quote/dash nếu cần, nhưng tránh heuristic quá mạnh.

Không nên:

- Bỏ dấu tiếng Việt đại trà, vì nhiều từ khác nghĩa sẽ bị nhập nhằng.
- Dịch sang tiếng Anh để dùng model English, vì mất entity/local phrase và thêm noise.
- Tokenize bằng regex tiếng Anh rồi xem như final solution; chỉ dùng cho EDA/simple overlap.

### 5.2 BM25 on Vietnamese

Elasticsearch standard analyzer vẫn có thể chạy baseline BM25 vì tiếng Việt dùng khoảng trắng giữa âm tiết. Tuy nhiên, tiếng Việt có vấn đề: một từ có thể gồm nhiều âm tiết cách nhau bằng space, ví dụ `thành phố`, `bóng đá`, `Thái Bình Dương`.

Baseline hiện tại có thể dùng standard analyzer để chạy nhanh. Nhưng nếu muốn cải thiện lexical retrieval tiếng Việt, có thể thử:

1. Keep standard analyzer as baseline.
2. Add Vietnamese analyzer/tokenizer later, ví dụ plugin hoặc preprocessing word segmentation.
3. Add field phụ `content_unaccented` hoặc normalized aliases nếu thấy nhiều mismatch dấu/không dấu.

Không nên đưa Vietnamese analyzer vào ngay nếu mục tiêu là benchmark retrieval methods trước, vì nó làm thay đổi quá nhiều biến cùng lúc.

### 5.3 Dense Embedding for Vietnamese

Embedding model hiện tại trong codebase là:

```text
BAAI/bge-small-en-v1.5
```

Model này là English-oriented. Không nên dùng nó làm kết luận cuối cho VimQA dense retrieval.

Khuyến nghị model theo mức độ thực dụng:

| Option | Model | Pros | Cons | Recommendation |
|---|---|---|---|---|
| Fast compatible | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Multilingual, 384 dims, dễ thay vào index hiện tại | Không phải model retrieval mạnh nhất | Best first replacement |
| Stronger multilingual retrieval | `BAAI/bge-m3` | Multilingual, retrieval-oriented, hỗ trợ nhiều ngôn ngữ | 1024 dims, index dims phải đổi, nặng hơn | Good second experiment |
| Vietnamese-focused | Vietnamese SBERT/PhoBERT embedding model | Có thể hợp tiếng Việt hơn | Cần kiểm chứng model availability, dims, pooling, speed | Use after baseline |

Strategy tốt nhất:

1. Chạy baseline với `BAAI/bge-small-en-v1.5` để so sánh với HotpotQA stack hiện tại.
2. Chạy lại VimQA với `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` vì cùng 384 dims, ít đổi code/index.
3. Nếu có thời gian, thử `BAAI/bge-m3` với index dims 1024 để đo upper bound multilingual retrieval.

Cấu hình khuyến nghị cho baseline chính VimQA:

```text
Embedding model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
Vector dims: 384
Normalize embeddings: true
ES similarity: cosine
Granularity: one context = one vector
```

## 6. Retrieval Strategy For VimQA

### 6.1 Corpus Construction

Tạo corpus từ union unique contexts của train + test:

```text
corpus = unique(normalized context from train + test)
doc_id = vimqa_ctx_<hash(normalized_context)>
title = ""
text = original context
content = original context
embedding_text = original context
```

Tạo queries theo split:

```text
train query_id = vimqa_train_000000 ...
test query_id = vimqa_test_000000 ...
query text = question
```

Tạo qrels:

```text
query_id -> doc_id(context) relevance=1
```

Answer nên được giữ trong metadata hoặc file sidecar để dùng cho QA/verifier sau này, không cần đưa vào ES source baseline.

### 6.2 Index Isolation

Không dùng chung HotpotQA index. Đặt riêng:

```text
vimqa_all_v1 -> vimqa_all_current
```

Artifacts riêng:

```text
artifacts/vimqa/all/staging/
artifacts/vimqa/all/progress/
evaluation/results/vimqa/
evaluation/runs/vimqa/
```

### 6.3 Benchmark Protocol

Dùng train queries để tune:

```text
vimqa train queries -> tune candidate_k, rrf_k, model choice
```

Dùng test queries để report:

```text
vimqa test queries -> final comparison
```

Metrics chính:

```text
recall@1
recall@5
recall@10
mrr@10
ndcg@10
latency_p50_ms
latency_p95_ms
```

Có thể vẫn log `full_support_recall@10` để dùng chung code, nhưng report phải ghi rõ metric này trên VimQA là single-context success, không phải multi-support success như HotpotQA.

### 6.4 Methods To Run

Chạy tối thiểu:

```text
es_bm25
es_dense
es_hybrid
es_iterative_hybrid
```

Chạy theo hai embedding settings:

```text
BGE English baseline: BAAI/bge-small-en-v1.5
Multilingual baseline: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Nếu có thời gian:

```text
BAAI/bge-m3
```

Expected behavior từ EDA:

- BM25 sẽ mạnh vì median lexical overlap khoảng 0.70.
- Dense English có thể kém hoặc không ổn định trên tiếng Việt.
- Dense multilingual nên cải thiện semantic retrieval.
- Hybrid có khả năng là best trade-off.
- Iterative hybrid có thể không vượt hybrid vì gold qrel chỉ là một context đã chứa evidence ghép.

## 7. Multi-hop Retrieval On VimQA

### 7.1 Multi-hop Meaning In HotpotQA

Trong HotpotQA, multi-hop retrieval nghĩa là:

```text
query -> retrieve support doc A and support doc B from a larger corpus
```

Một query thường cần đủ 2 support docs. Vì vậy `full_support_recall@k` có ý nghĩa rất rõ: top-k có chứa đủ tất cả evidence documents không?

### 7.2 Multi-hop Meaning In VimQA

Trong VimQA hiện tại, evidence đã nằm trong một `context`. Nhiều context có vẻ được ghép từ 2 facts, nhưng dataset không cho nhãn support doc/sentence riêng.

Vì vậy direct retrieval task là:

```text
query -> retrieve the provided context
```

Đây là **single-context retrieval**, dù nội dung context có thể cần multi-hop reasoning để answer.

### 7.3 How To Run Iterative Retrieval Anyway

Có thể chạy `es_iterative_hybrid` trên VimQA như một diagnostic:

```text
Hop 1: retrieve likely contexts
Hop 2: expand query using top context text/title
Fusion: return final contexts
```

Nhưng khác HotpotQA:

- Hop 2 không có qrel riêng để biết evidence thứ hai đúng hay sai.
- Nếu hop 1 đã retrieve đúng context, hop 2 có thể chỉ thêm noise.
- Nếu context đã ghép đủ 2 facts, iterative retrieval không có lợi thế rõ như HotpotQA.

Do đó, trên VimQA, iterative hybrid nên được report như:

```text
multi-hop-style retrieval heuristic over context documents
```

không nên gọi là native multi-hop retrieval benchmark.

### 7.4 Possible Advanced Multi-hop Setup

Nếu muốn làm VimQA giống HotpotQA hơn, có thể tạo pseudo-hop corpus:

1. Split mỗi context thành sentences.
2. Mỗi sentence là một pseudo-document.
3. Gán qrel sentence nếu sentence chứa answer hoặc có overlap cao với question/entity.
4. Retrieve multiple sentences per query.

Nhưng đây là weak supervision, dễ nhiễu, và không nên là baseline chính. Nên làm sau khi context-level benchmark ổn.

## 8. Recommended Implementation Plan

### Phase 1: Dataset Adapter and Context Retrieval

Tạo adapter VimQA:

```text
src/data/datasets/base.py
src/data/datasets/hotpotqa.py
src/data/datasets/vimqa.py
src/data/datasets/registry.py
```

VimQA adapter responsibilities:

```text
load train/test JSON
normalize and hash contexts
emit unique docs from corpus split all
emit queries from train/test split
emit qrels query -> context doc
emit metadata: rows, unique contexts, answer stats
```

### Phase 2: Generic Staging and Benchmark

Thêm hoặc refactor:

```text
scripts/stage_dataset.py
src/evaluation/benchmark_es.py --dataset-type hotpotqa|vimqa
```

Không dùng `nano-beir/hotpotqa` làm dummy dataset khi benchmark VimQA.

### Phase 3: VimQA Baselines

Run baseline set:

```text
BM25 standard analyzer
Dense BGE English
Hybrid BGE English
Dense multilingual MiniLM
Hybrid multilingual MiniLM
Iterative hybrid multilingual MiniLM
```

Report riêng trong:

```text
evaluation/results/vimqa/
docs/data/vimqa/
```

### Phase 4: Vietnamese Optimization

Sau khi baseline có số:

1. Thử Vietnamese analyzer/tokenizer hoặc segmentation.
2. Thử `BAAI/bge-m3` hoặc Vietnamese embedding model.
3. Thử reranker multilingual nếu cần top-k quality cao hơn.
4. Thử pseudo-sentence/pseudo-hop retrieval nếu mục tiêu là multi-hop analysis.

## 9. Final Recommendation

VimQA nên được đưa vào hệ thống như một dataset riêng, không trộn với HotpotQA.

Tên task nên dùng trong report:

```text
VimQA Context Retrieval
```

Không nên gọi trực tiếp là HotpotQA-style multi-hop retrieval, vì qrels hiện chỉ map query tới một context. Cách diễn giải đúng hơn:

```text
VimQA tests Vietnamese retrieval over QA-derived evidence contexts.
HotpotQA tests native multi-hop document retrieval over a corpus with support-document qrels.
```

Retrieval strategy phù hợp nhất:

```text
Corpus: train + test unique contexts
Eval split: train/test queries
Granularity: one context = one ES document = one vector
Primary methods: BM25, dense multilingual, hybrid multilingual
Diagnostic method: iterative hybrid
Primary model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
Second model to try: BAAI/bge-m3
Primary metrics: recall@1/5/10, mrr@10, ndcg@10, latency
```

Điểm giống HotpotQA: câu hỏi entity-heavy, có tính bridge/reasoning, BM25/hybrid rất đáng dùng.

Điểm khác HotpotQA: evidence đã nằm trong context ghép sẵn, không có qrels nhiều support docs, tiếng Việt cần embedding/tokenization phù hợp, corpus nhỏ hơn nhiều.
