# Sprint prompt-based search - AMI scope

## 1. Mục tiêu

Sprint này thử các hướng prompt/query-understanding cho bài toán meeting search, nhưng giữ nguyên scope data hiện tại: AMI current index gồm 171 meetings, 5347 chunks, embedding `sentence-transformers/all-MiniLM-L6-v2`, và qrels `data/eval/ami_qrels.json`.

Mục tiêu không thay đổi parser/chunking/index của Sprint 1. Các phương pháp chỉ can thiệp ở query side hoặc fusion/ranking side để xem prompt-based search có cải thiện retrieval hay không.

## 2. Research summary

Các hướng liên quan:

- Query expansion / Query2doc: dùng prompt hoặc LLM sinh pseudo-document/expanded query để bổ sung ngữ cảnh truy vấn. Query2doc báo cáo pseudo-documents từ LLM có thể giúp query disambiguation và cải thiện cả sparse/dense retrieval trên các benchmark ad-hoc IR.
- HyDE: dùng LLM sinh hypothetical document từ query, sau đó embed hypothetical document để retrieve tài liệu thật. Điểm mạnh là biến query ngắn thành representation giàu ngữ cảnh hơn; điểm yếu là pseudo-document có thể chứa chi tiết giả.
- BM25 / lexical retrieval: baseline sparse/keyword lâu đời, hữu ích khi query chứa từ khóa cụ thể, tên entity, hoặc phrase xuất hiện trực tiếp trong transcript.
- Reciprocal Rank Fusion (RRF): fusion theo rank, đơn giản và ổn định khi cần kết hợp nhiều ranking list mà không cần calibrate score giữa hệ khác nhau.
- LLM reranking: dùng LLM/chunk reranker đánh giá candidate snippets sau first-stage retrieval. Phù hợp nếu có API/model đủ mạnh, nhưng chi phí và latency cao hơn. Sprint này chưa benchmark LLM thật vì local scope hiện tại không giả định API key/network ổn định.

Nguồn tham khảo chính:

- HyDE: https://arxiv.org/abs/2212.10496
- Query2doc: https://arxiv.org/abs/2303.07678
- RRF: https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
- BM25 overview: https://www.microsoft.com/en-us/research/event/microsoft-sigir-2018/conference-analytics/

## 3. Các phương pháp đã implement

File chính:

- `src/search/prompt_methods.py`
- `src/search/searcher.py`
- `evaluation/benchmark_prompt_search.py`

Các method hiện hỗ trợ qua API/eval:

| Method | Ý tưởng | Có LLM thật? | Ghi chú |
|--------|---------|--------------|---------|
| `embedding` | Baseline Sprint 1: embed query gốc rồi FAISS search | Không | Giữ nguyên default behavior |
| `rule_expansion` | Lightweight NLU: normalize query, bỏ stopwords, thêm domain synonym/related terms | Không | Local, deterministic, rẻ |
| `hyde_template` | HyDE-style template pseudo-document rồi embed | Không | Mô phỏng HyDE offline bằng template, chưa gọi LLM |
| `multi_query_rrf` | Tạo query variants: original, normalized, expanded, HyDE-template; search từng cái rồi RRF | Không | Tăng recall tiềm năng nhưng latency cao hơn |
| `hybrid_rrf` | Dense embedding + lexical BM25-like search, fusion bằng RRF | Không | Dùng lexical index local trên chunks |

API `/search` có thêm optional field:

```json
{
  "query": "meetings about battery life and power consumption",
  "top_k": 10,
  "method": "multi_query_rrf"
}
```

Frontend Search view cũng có selector để thử `Semantic`, `Rules`, `HyDE`, `Multi-query`, `Hybrid`.

## 4. Benchmark command

```bash
python -m evaluation.benchmark_prompt_search --qrels data/eval/ami_qrels.json --top-k 5 --output evaluation/results/prompt_search_benchmark_ami.json
```

Có thể chạy từng method:

```bash
python -m evaluation.run_eval --qrels data/eval/ami_qrels.json --top-k 5 --method embedding
python -m evaluation.run_eval --qrels data/eval/ami_qrels.json --top-k 5 --method hybrid_rrf
```

## 5. Kết quả AMI hiện tại

Kết quả lưu tại `evaluation/results/prompt_search_benchmark_ami.json`.

| Method | Precision@5 | Recall@5 | MRR@5 | Avg latency | P50 latency | P95 latency |
|--------|-------------|----------|-------|-------------|-------------|-------------|
| `embedding` | 0.6000 | 1.0000 | 1.0000 | 33.1720 ms | 9.4357 ms | 242.3443 ms |
| `rule_expansion` | 0.3200 | 0.5333 | 0.4833 | 9.7193 ms | 9.3049 ms | 11.7718 ms |
| `hyde_template` | 0.4000 | 0.6667 | 0.7667 | 10.8459 ms | 10.1644 ms | 13.5874 ms |
| `multi_query_rrf` | 0.4600 | 0.7667 | 0.9333 | 38.3663 ms | 37.3982 ms | 42.3101 ms |
| `hybrid_rrf` | 0.3000 | 0.5000 | 0.5917 | 37.8827 ms | 36.4554 ms | 58.9285 ms |

## 6. Nhận xét

Baseline `embedding` vẫn tốt nhất trên qrels AMI hiện tại. Đây không hẳn là bằng chứng embedding luôn tốt nhất; nó phản ánh đúng hạn chế đã ghi ở Sprint 1: qrels nhỏ, chỉ 10 query, và có bias vì được tạo từ việc inspect kết quả semantic search ban đầu.

`rule_expansion` bị tụt mạnh. Nguyên nhân có thể là expansion dictionary nhỏ và dễ thêm noise. Ví dụ query về `battery life` bị kéo thêm nhiều term như `energy`, `charging`, làm vector query dịch khỏi wording mà qrels ban đầu ưu ái.

`hyde_template` tốt hơn rule expansion nhưng vẫn thấp hơn baseline. Template pseudo-document giúp query có dạng giống transcript hơn, nhưng vì chưa dùng LLM thật nên nội dung còn generic, dễ kéo vào các cuộc họp có từ khóa chung như requirements/design/decision.

`multi_query_rrf` là biến thể prompt-based ổn nhất trong nhóm mới: Recall@5 = 0.7667 và MRR@5 = 0.9333. Nó tận dụng baseline original query nhưng vẫn thêm variants. Nhược điểm là latency cao hơn vì embed/search nhiều query.

`hybrid_rrf` chưa tốt trong qrels này. BM25-like lexical local có thể bắt keyword exact, nhưng transcript AMI có nhiều từ phổ thông và chunk có speaker prefix, nên lexical signal dễ bị noise. Hybrid sẽ hữu ích hơn nếu có query chứa tên người, phrase rất cụ thể, hoặc nếu lexical index được tuning tốt hơn.

## 7. Ưu nhược điểm theo hướng sản phẩm

| Hướng | Ưu điểm | Nhược điểm | Khi nên dùng |
|-------|---------|------------|--------------|
| Baseline embedding | Đơn giản, mạnh với paraphrase, đang thắng qrels hiện tại | Khó xử lý filter/constraint cụ thể, có thể miss exact keyword | Default search |
| Rule/NLU expansion | Rẻ, deterministic, không cần API key | Dễ thêm noise, cần curate dictionary/domain rules | Query ngắn, domain terms ổn định |
| HyDE/template | Có thể làm query giàu ngữ cảnh hơn | Template local còn generic; LLM thật có chi phí và hallucination risk | Query mơ hồ, cần pseudo context |
| Multi-query RRF | Robust hơn single expansion, không cần calibrate score | Latency tăng theo số variants | Khi muốn tăng recall và có thể chịu thêm latency |
| Hybrid lexical+dense | Bắt exact terms/entity tốt | Cần tuning BM25, field weights, phrase matching | Search theo tên speaker, entity, phrase, metadata |
| LLM reranking | Có thể hiểu intent sâu, rerank snippet theo tiêu chí prompt | Chậm, tốn tiền, cần guardrail và eval riêng | Sau first-stage retrieval, top 20-50 candidates |

## 8. Kết luận đề xuất

Trong scope AMI/qrels hiện tại, nên giữ `embedding` làm default. Trong các hướng prompt-based offline đã thử, `multi_query_rrf` là ứng viên đáng giữ lại nhất vì MRR vẫn cao và ít rơi tự do hơn rule/hybrid.

Không nên claim rule-based expansion hoặc hybrid tốt hơn ở Sprint này. Việc đúng hơn là báo cáo rằng prompt expansion/fusion đã được implement và benchmark, nhưng qrels hiện tại đang ưu ái baseline semantic; cần mở rộng qrels độc lập với query khó hơn để đánh giá công bằng.

Bước tiếp theo nếu muốn test LLM thật: thêm một `llm_hyde` hoặc `llm_query2doc` strategy dùng API để sinh 1-3 pseudo-documents, cache output theo query để benchmark reproducible, rồi chạy lại cùng `ami_qrels`. Sau đó mới cân nhắc LLM reranking trên top 20 chunks/meetings.