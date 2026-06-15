# Báo cáo tổng hợp Sprint 2

Ngày cập nhật: 2026-06-13

## 1. Mục tiêu Sprint 2

Sprint 2 tập trung mở rộng baseline Elasticsearch đã có từ Sprint 1 theo 4 hướng:

1. Kiểm tra độ bền của retrieval pipeline khi query bị paraphrase.
2. Mở rộng và đánh giá các biến thể iterative multi-hop retrieval trên HotpotQA.
3. Scale benchmark từ nano 5,090 docs lên subset 100,000 docs HotpotQA.
4. Bổ sung và phân tích dataset tiếng Việt VimQA để chuẩn bị benchmark retrieval phục vụ multi-hop reasoning riêng.

Kết quả chung: đã có report và artifacts cho paraphrase benchmark, iterative search, benchmark 100k HotpotQA, và EDA/strategy cho VimQA. Phần VimQA hiện mới ở mức phân tích và thiết kế strategy, chưa implement adapter/index/benchmark chính thức.

## 2. Tổng quan công việc đã hoàn thành

| Công việc | Trạng thái | Kết quả chính | Report / Artifact |
|---|---|---|---|
| Paraphrase query + benchmark | Done | Tạo 150 paraphrase variants cho 50 HotpotQA queries và benchmark 4 retrievers | `docs/sprint1/paraphrase-robustness-report.md`, `evaluation/results/paraphrase_summary.csv` |
| Mở rộng iterative search | Done | Thêm và benchmark `es_iterative_title`, `es_iterative_sentence`, `es_iterative_fast` | `docs/sprint2/100k-multihop-iteration-report.md`, `evaluation/results/es_100k_iterative_compare.json` |
| Benchmark 100k HotpotQA | Done | Index 100,000 docs, benchmark trên 82 validation queries có đủ gold docs | `docs/sprint2/100k-multihop-iteration-report.md`, `evaluation/results/es_100k_baseline.json` |
| Bổ sung dataset tiếng Việt | Report done, implementation pending | EDA VimQA và đề xuất convert thành VimQA Multi-hop Evidence Retrieval | `docs/data/vimqa/vimqa-eda-retrieval-strategy.md` |

## 3. Paraphrase Query + Benchmark

### Mục tiêu

Đo độ bền của các retriever khi query bị thay đổi lexical form nhưng vẫn giữ ý nghĩa gốc. Đây là stress test cho retrieval robustness: nếu câu hỏi được paraphrase bằng synonym substitution, retriever có còn tìm được support documents tương ứng với qrels gốc hay không.

### Thiết kế

- Dataset: `nano-beir/hotpotqa`.
- Số query gốc: 50.
- Mỗi query có 3 biến thể paraphrase:
  - `syn020`: thay khoảng 20% token đủ điều kiện.
  - `syn040`: thay khoảng 40% token đủ điều kiện.
  - `syn060`: thay khoảng 60% token đủ điều kiện.
- Paraphrase deterministic bằng synonym substitution, seed cố định.
- Không thay named entities, số, ngày tháng, hoặc token viết hoa giữa câu.
- Qrels được map từ query gốc sang query paraphrase qua `source_query_id`.

### Phương pháp paraphrase

Paraphrase trong Sprint 2 được tạo bằng **synonym substitution có kiểm soát**, không dùng LLM paraphrase. Mục tiêu là tạo thay đổi lexical vừa đủ để stress-test retriever, nhưng vẫn giữ nguyên ý nghĩa và gold qrels của câu hỏi gốc.

Quy trình cụ thể:

1. Lấy 50 query HotpotQA gốc từ `nano-beir/hotpotqa`.
2. Tokenize query và chọn các token đủ điều kiện để thay thế.
3. Với mỗi token đủ điều kiện, tra synonym trong dictionary nội bộ.
4. Sinh 3 mức biến đổi: `syn020`, `syn040`, `syn060`, tương ứng target thay khoảng 20%, 40%, 60% token đủ điều kiện.
5. Giữ nguyên `source_query_id` để map qrels từ query gốc sang query paraphrase.
6. Benchmark các query paraphrase bằng cùng qrels gốc để đo robustness của retriever.

Các rule bảo toàn ý nghĩa:

- Không thay named entities.
- Không thay số, năm, ngày tháng.
- Không thay token viết hoa giữa câu.
- Không thay nếu synonym dictionary không có candidate phù hợp.
- Generator dùng seed cố định để kết quả deterministic và reproduce được.

Ví dụ ý tưởng:

```text
original: Which film did X star in?
paraphrase: Which movie did X appear in?
```

Đây là lexical paraphrase/synonym substitution, không phải natural paraphrase bằng LLM. Vì vậy kết quả chủ yếu phản ánh độ nhạy của retriever với thay đổi từ vựng, chưa phản ánh đầy đủ paraphrase tự nhiên ở mức câu.

### Methods benchmark

```text
es_bm25
es_dense
es_hybrid
es_iterative_hybrid
```

### Kết quả chính

| Method | Original Recall@10 | Paraphrase Recall@10 | Nhận xét |
|---|---:|---:|---|
| `es_bm25` | 0.88 | 0.86 - 0.87 | Giảm nhẹ, không sụp đổ vì paraphrase vẫn giữ entity/lexical anchors |
| `es_dense` | 0.86 | 0.86 | Ổn định nhất về Recall@10 và full-support |
| `es_hybrid` | 0.91 | 0.90 | Tốt nhất về quality và robustness, chỉ giảm Recall@10 khoảng -0.01 |
| `es_iterative_hybrid` | 0.90 | 0.88 | Giảm full-support nhiều hơn, khoảng -0.04 |

### Kết luận

`es_hybrid` là retriever cân bằng và ổn định nhất trong paraphrase benchmark. Dense retrieval giữ recall ổn định, BM25 giảm nhẹ, còn iterative hybrid nhạy cảm hơn với lexical variation do query expansion ở hop sau có thể bị ảnh hưởng.

Report chi tiết:

```text
docs/sprint1/paraphrase-robustness-report.md
evaluation/results/paraphrase_summary.csv
```

## 4. Mở rộng Iterative Search trên HotpotQA

### Mục tiêu

Baseline iterative ban đầu dùng:

```text
expanded_query = original query + hop1 title + first context_chars of hop1 text
```

Cách này có rủi ro query drift: nếu hop 1 lấy sai document, hop 2 bị kéo sang topic sai. Sprint 2 mở rộng iterative search thành nhiều biến thể để giảm drift và latency.

### Biến thể đã thêm

Các biến thể iterative đều giữ cùng khung 2-hop:

```text
Hop 1: chạy hybrid search bằng query gốc để lấy first_hop_k documents.
Hop 2: với mỗi document ở hop 1, tạo expanded query rồi chạy hybrid search lần nữa.
Fusion: RRF fuse ranking hop 1 và toàn bộ ranking hop 2, sau đó trả top-k cuối.
```

Điểm khác nhau nằm ở cách tạo `expanded_query` và mức fan-out:

| Method | Expansion mode | Expanded query | Mục tiêu | Trade-off |
|---|---|---|---|---|
| `es_iterative_hybrid` | context | `question + hop1.title + first N chars of hop1.text` | Dùng nhiều context nhất từ evidence hop 1 để tìm evidence hop 2 | Có nhiều thông tin nhưng dễ query drift nếu hop 1 sai; latency cao |
| `es_iterative_title` | title | `question + hop1.title` | Giữ expansion gọn, ưu tiên entity/title của hop 1 | Ít drift và nhanh hơn context expansion, nhưng thiếu nội dung chi tiết |
| `es_iterative_sentence` | sentence | `question + hop1.title + selected sentence` | Chọn câu trong hop-1 doc có lexical overlap cao nhất với query để giảm noise | Full-support tốt nhất trong nhóm iterative, nhưng ranking MRR/nDCG vẫn thấp hơn hybrid |
| `es_iterative_fast` | title/low fanout | `question + hop1.title`, đồng thời giảm `candidate_k`, `num_candidates`, `first_hop_k`, `second_hop_k` | Biến thể tối ưu latency để demo trade-off | Nhanh nhất trong nhóm iterative nhưng giảm quality |

Ý nghĩa từng biến thể:

- `es_iterative_hybrid`: baseline iterative đầy đủ nhất, dùng context prefix của top documents để mở rộng query. Phù hợp để debug multi-hop chain, nhưng rủi ro drift cao nhất.
- `es_iterative_title`: chỉ dùng title/entity của hop-1 document. Cách này giả định title là bridge entity quan trọng, giúp giảm noise từ body text.
- `es_iterative_sentence`: chọn một câu đại diện trong hop-1 document dựa trên overlap với query. Mục tiêu là giữ evidence liên quan hơn context prefix thô.
- `es_iterative_fast`: cấu hình low-fanout để giảm số lần ES search và embedding calls. Phù hợp demo latency/quality trade-off, chưa phải best quality.

### Cấu hình benchmark iterative improved

```text
top_k = 10
candidate_k = 50
num_candidates = 300
first_hop_k = 3
second_hop_k = 5
rrf_k = 30
context_chars = 256
```

### Kết quả chính trên 100k docs

| Method | Recall@10 | nDCG@10 | MRR@10 | Full-support Recall@10 | p50 latency | Highlight |
|---|---:|---:|---:|---:|---:|---|
| `es_hybrid` | **0.8963** | **0.8598** | **0.9106** | 0.8171 | **213.80 ms** | Best overall để serve: ranking tốt nhất và latency thấp nhất |
| `es_iterative_hybrid` | 0.8902 | 0.6403 | 0.6507 | 0.8171 | 834.36 ms | Context expansion đầy đủ, nhưng ranking giảm mạnh |
| `es_iterative_title` | 0.8720 | 0.5482 | 0.4507 | 0.7927 | 692.96 ms | Ít noise hơn context, nhưng thiếu evidence chi tiết |
| `es_iterative_sentence` | 0.8902 | 0.6287 | 0.6064 | **0.8293** | 787.05 ms | Best full-support trong nhóm iterative |
| `es_iterative_fast` | 0.8659 | 0.5573 | 0.4731 | 0.7805 | 635.19 ms | Iterative nhanh nhất, nhưng quality thấp hơn |

### Kết luận

- `es_hybrid` vẫn là method tốt nhất để serve vì có ranking tốt nhất và latency thấp hơn iterative variants.
- `es_iterative_sentence` là biến thể multi-hop đáng chú ý nhất vì full-support Recall@10 = 0.8293, cao hơn `es_hybrid` = 0.8171.
- Tuy nhiên, iterative variants có MRR/nDCG thấp hơn, nghĩa là tìm đủ evidence có thể tốt hơn một chút nhưng xếp hạng evidence chưa tốt.
- Iterative search nên giữ ở experimental/debug mode, chưa nên làm default.

Report chi tiết:

```text
docs/sprint2/100k-multihop-iteration-report.md
evaluation/results/es_100k_iterative_compare.json
```

## 5. Benchmark 100k Docs HotpotQA

### Mục tiêu

Scale Elasticsearch baseline từ nano corpus 5,090 docs lên subset 100,000 docs HotpotQA để đánh giá chất lượng và latency khi corpus lớn hơn.

### Data và index

| Thành phần | Giá trị |
|---|---:|
| Corpus source | `BeIR/hotpotqa` Hugging Face corpus split |
| Indexed docs | 100,000 |
| Index | `hotpotqa_100k_v1` |
| Alias | `hotpotqa_100k_current` |
| Embedding model | `BAAI/bge-small-en-v1.5` |
| Filtered validation queries | 82 |
| Filtered qrels | 164 |

Do 100k chỉ là prefix subset, chỉ giữ lại validation queries có toàn bộ gold docs nằm trong 100k index để benchmark công bằng.

### Baseline 100k results

Config baseline:

```text
top_k = 10
candidate_k = 100
num_candidates = 1000
first_hop_k = 5
second_hop_k = 10
context_chars = 256
```

| Method | Recall@10 | nDCG@10 | MRR@10 | Full-support Recall@10 | p50 latency | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| `es_bm25` | 0.7927 | 0.7619 | 0.8258 | 0.6707 | 88.74 ms | 194.52 ms |
| `es_dense` | 0.8720 | 0.8408 | 0.9110 | 0.7683 | 186.31 ms | 563.67 ms |
| `es_hybrid` | 0.8963 | 0.8625 | 0.9162 | 0.8171 | 340.94 ms | 888.57 ms |
| `es_iterative_hybrid` | 0.7012 | 0.3279 | 0.2224 | 0.4756 | 1841.30 ms | 3253.06 ms |

### Kết luận

- `es_hybrid` là baseline mạnh nhất trên 100k docs theo quality.
- Dense retrieval trở nên quan trọng hơn khi corpus lớn hơn: `es_dense` vượt `es_bm25` về Recall@10 và full-support Recall@10.
- Iterative context ban đầu bị query drift nặng và latency cao.
- Sau khi thêm iterative variants và giảm fanout, iterative tốt hơn nhưng vẫn chưa phù hợp làm default.

Report và artifacts:

```text
docs/sprint2/100k-multihop-iteration-report.md
evaluation/results/es_100k_baseline.json
evaluation/results/es_100k_iterative_compare.json
evaluation/runs/100k_baseline/
evaluation/runs/100k_iterative/
```

## 6. Bổ sung Dataset tiếng Việt: VimQA

### Mục tiêu

Khảo sát dataset tiếng Việt VimQA để xem có thể dùng để test retrieval tương tự HotpotQA hay không, và cần xử lý khác gì so với HotpotQA tiếng Anh.

### Phạm vi sử dụng VimQA

Trong hướng này, VimQA chỉ được dùng cho bài toán **retrieval phục vụ multi-hop reasoning**, không dùng làm bài toán sinh câu trả lời end-to-end.

Cụ thể:

- Input của hệ thống là `question`.
- Output cần đánh giá là evidence/context được retrieve đúng.
- Field `answer` không phải target chính của retriever; chỉ giữ lại làm metadata để phân tích lỗi hoặc kiểm tra downstream sau này.
- Metric chính vẫn là retrieval metrics như `recall@k`, `mrr@k`, `ndcg@k`, latency.
- Nếu cần đánh giá multi-hop rõ hơn, có thể tách context thành sentence/pseudo-hop evidence sau baseline context-level.

Điểm cần ghi rõ: VimQA có nội dung nhiều câu/fact gần với multi-hop reasoning, nhưng gold evidence hiện nằm trong một `context` đã ghép sẵn. Vì vậy benchmark đầu tiên nên đo khả năng retrieve đúng evidence context, sau đó mới thử pseudo-hop/sentence-level retrieval.

### Dataset

Files:

```text
docs/data/vimqa/train_vimqa.json
docs/data/vimqa/test_vimqa.json
```

Schema:

```json
{
  "question": "...",
  "context": "...",
  "answer": "..."
}
```

### Preview cấu trúc data: HotpotQA vs VimQA

Điểm khác biệt lớn nhất là HotpotQA trong codebase đang ở format retrieval benchmark chuẩn, còn VimQA là QA record đã kèm sẵn context.

| Thành phần | HotpotQA hiện tại | VimQA hiện tại |
|---|---|---|
| Corpus/document | Tách riêng qua `docs_iter()` | Chưa tách riêng; nằm trong field `context` của từng QA row |
| Query | Tách riêng qua `queries_iter()` | Field `question` trong từng row |
| Qrels/evidence label | Tách riêng qua `qrels_iter()`, một query có thể có nhiều support docs | Chưa có qrels riêng; có thể tự sinh bằng mapping question -> context |
| Answer | Không nằm trong retrieval benchmark path hiện tại | Field `answer`, gồm cả span answer và đúng/không |
| Multi-hop evidence | Nhiều support documents rời | Evidence thường đã được ghép trong một context ngắn |

Preview HotpotQA theo format retrieval:

```json
{
  "document": {
    "doc_id": "974",
    "text": "Augusta Ada King-Noel, Countess of Lovelace ..."
  },
  "query": {
    "query_id": "5ae5669755429960a22e02ec",
    "text": "Which of the campaign that brought out the term Vichy Republican on social media was formally launched on June 16, 2015, at Trump Tower in New York City?"
  },
  "qrels": [
    {"query_id": "5ae5669755429960a22e02ec", "doc_id": "49892372", "relevance": 1},
    {"query_id": "5ae5669755429960a22e02ec", "doc_id": "46979246", "relevance": 1}
  ]
}
```

Preview VimQA theo format QA local:

```json
{
  "question": "Đội bóng Boca Juniors mà Diego Maradona đã chơi có trụ sở tại La Boca, gần Buenos Aires phải không?",
  "context": "Ông đã chơi cho Argentinos Juniors, Boca Juniors, Barcelona, Napoli, Sevilla và Newell's Old Boys ... Club Atlético Boca Juniors là 1 câu lạc bộ bóng đá chuyên nghiệp của Argentina, có trụ sở tại La Boca, gần Buenos Aires.",
  "answer": "đúng"
}
```

Nếu convert VimQA sang retrieval benchmark, một record sẽ được tách lại thành:

```json
{
  "document": {
    "doc_id": "vimqa_ctx_<hash(context)>",
    "text": "<context>"
  },
  "query": {
    "query_id": "vimqa_test_000000",
    "text": "<question>"
  },
  "qrel": {
    "query_id": "vimqa_test_000000",
    "doc_id": "vimqa_ctx_<hash(context)>",
    "relevance": 1
  },
  "answer_metadata": "<answer, chỉ dùng để phân tích/diagnostic>"
}
```

Vì vậy, VimQA có thể dùng để benchmark retrieval phục vụ multi-hop reasoning, nhưng cần một bước adapter/convert rõ ràng trước khi chạy cùng pipeline Elasticsearch. Trong phạm vi này, hệ thống chỉ cần retrieve evidence/context liên quan; không dùng VimQA để huấn luyện hoặc đánh giá module sinh câu trả lời.

### EDA summary

| Split | Rows | Unique questions | Unique contexts | Duplicate context rows | Unique answers |
|---|---:|---:|---:|---:|---:|
| Train | 8,041 | 7,935 | 3,198 | 4,843 | 2,130 |
| Test | 1,003 | 989 | 900 | 103 | 599 |

| Split | Boolean answers | Span exact-in-context | Context p50 | Context sentences p50 |
|---|---:|---:|---:|---:|
| Train | 48.90% | 99.54% | 62 tokens | 2 |
| Test | 30.11% | 92.87% | 54 tokens | 2 |

Train/test overlap:

| Metric | Value |
|---|---:|
| Exact context overlap train-test | 475 contexts |
| Test contexts appearing in train | 52.78% |
| Exact question overlap train-test | 69 questions |

### Nhận xét

VimQA không phải BEIR-style retrieval benchmark native như HotpotQA. Mỗi sample đã có `context` kèm theo, nên cần convert thành retrieval proxy:

```text
question -> query
unique context -> document
question-context mapping -> qrel
answer -> metadata tham khảo, không dùng làm target chính
```

Khuyến nghị task name:

```text
VimQA Multi-hop Evidence Retrieval
```

### Xử lý tiếng Việt

Khác với HotpotQA tiếng Anh, VimQA cần chú ý:

- Giữ dấu tiếng Việt; không strip accents ở baseline chính.
- Normalize Unicode về NFC và collapse whitespace.
- BM25 standard analyzer có thể dùng baseline, nhưng tiếng Việt có multi-syllable words nên có thể thử Vietnamese tokenizer/analyzer sau.
- Không nên kết luận dense retrieval bằng English model `BAAI/bge-small-en-v1.5`.

Embedding model khuyến nghị:

1. Baseline nhanh, ít đổi code/index: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
2. Stronger multilingual experiment: `BAAI/bge-m3`, cần đổi index dims lên 1024.

### Trạng thái

Đã có EDA và strategy report cho hướng retrieval/multi-hop reasoning, chưa implement adapter/index/benchmark chính thức.

Report:

```text
docs/data/vimqa/vimqa-eda-retrieval-strategy.md
```

## 7. Tổng hợp kết quả kỹ thuật

### Method đang nên làm default

```text
es_hybrid = BM25 + dense kNN + RRF
```

Lý do:

- Tốt nhất trên nano benchmark.
- Ổn định nhất trong paraphrase robustness benchmark.
- Tốt nhất overall trên 100k docs về Recall/nDCG/MRR/full-support.
- Latency chấp nhận hơn iterative variants.

### Method nên giữ experimental

```text
es_iterative_sentence
es_iterative_hybrid
es_iterative_title
es_iterative_fast
```

Lý do:

- Có tín hiệu cải thiện full-support nhỏ trong một số config.
- Nhưng ranking MRR/nDCG chưa tốt.
- Latency và fanout cao hơn hybrid.
- Cần chain scoring/reranking trước khi làm default.

### Dataset tiếng Việt

VimQA nên được đưa vào như dataset riêng, không trộn với HotpotQA:

```text
HotpotQA = native multi-hop document retrieval benchmark
VimQA = Vietnamese multi-hop evidence retrieval benchmark derived from QA examples
```

## 8. Hạn chế hiện tại

1. 100k corpus là prefix subset, chưa phải full 5.23M HotpotQA corpus.
2. Benchmark 100k chỉ có 82 validation queries sau khi filter gold docs nằm trong index.
3. Iterative search chưa có chain reranking, nên ranking quality thấp hơn hybrid.
4. Paraphrase benchmark dùng synonym substitution deterministic, chưa phải natural/LLM paraphrase.
5. VimQA mới có EDA/strategy, chưa có adapter native và chưa benchmark chính thức.
6. Embedding model hiện tại `BAAI/bge-small-en-v1.5` phù hợp baseline tiếng Anh, chưa phù hợp kết luận cho tiếng Việt.

## 9. Đề xuất Sprint tiếp theo

1. Implement dataset adapter layer cho HotpotQA/VimQA.
2. Chạy VimQA Multi-hop Evidence Retrieval benchmark với BM25, dense multilingual, hybrid multilingual.
3. Thử `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` cho VimQA vì cùng 384 dims với index hiện tại.
4. Thêm chain scoring/reranking cho iterative search để cải thiện MRR/nDCG.
5. Scale HotpotQA tiếp lên 500k/1M docs nếu tài nguyên cho phép.
6. Bổ sung latency breakdown: embedding time, ES search time, fusion time.

## 10. Links nhanh

| Hạng mục | Link |
|---|---|
| Paraphrase robustness report | `docs/sprint1/paraphrase-robustness-report.md` |
| 100k + iterative report | `docs/sprint2/100k-multihop-iteration-report.md` |
| VimQA EDA/strategy report | `docs/data/vimqa/vimqa-eda-retrieval-strategy.md` |
| 100k baseline result | `evaluation/results/es_100k_baseline.json` |
| 100k iterative compare result | `evaluation/results/es_100k_iterative_compare.json` |
| Paraphrase summary CSV | `evaluation/results/paraphrase_summary.csv` |






