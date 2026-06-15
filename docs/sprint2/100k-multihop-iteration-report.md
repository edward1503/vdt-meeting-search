# 100k HotpotQA Multi-hop Iteration Report

Ngày cập nhật: 2026-06-12

## Tóm tắt

Đã scale Elasticsearch baseline từ nano 5,090 docs lên subset 100,000 docs của BEIR HotpotQA. Do nguồn BEIR chính tải rất chậm và timeout, corpus được stage từ Hugging Face `BeIR/hotpotqa` nhưng vẫn giữ format staging/index hiện tại: `doc_id`, `title`, `text`, `content`, `embedding_text` và vector BGE 384 chiều.

Benchmark dùng 82 validation queries có đủ toàn bộ gold documents nằm trong 100k index, tạo từ `BeIR/hotpotqa-qrels`. Cách lọc này giúp so sánh method công bằng hơn trên 100k prefix subset.

## Data And Index

| Thành phần | Giá trị |
|---|---:|
| Corpus source | `BeIR/hotpotqa` HF corpus split |
| Indexed docs | 100,000 |
| Index | `hotpotqa_100k_v1` |
| Alias | `hotpotqa_100k_current` |
| Embedding model | `BAAI/bge-small-en-v1.5` |
| Filtered validation queries | 82 |
| Filtered qrels | 164 |

Artifacts chính:

```text
artifacts/hotpotqa_100k/staging/
artifacts/hotpotqa_100k/eval/queries_100k_validation.tsv
artifacts/hotpotqa_100k/eval/qrels_100k_validation.tsv
evaluation/results/es_100k_baseline.json
evaluation/results/es_100k_iterative_compare.json
```

## Baseline 100k

Config: `top_k=10`, `candidate_k=100`, `num_candidates=1000`, `first_hop_k=5`, `second_hop_k=10`, `context_chars=256`.

| Method | Recall@10 | nDCG@10 | MRR@10 | Full-support Recall@10 | p50 latency | p95 latency | QPS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `es_bm25` | 0.7927 | 0.7619 | 0.8258 | 0.6707 | 88.74 ms | 194.52 ms | 9.6768 |
| `es_dense` | 0.8720 | 0.8408 | 0.9110 | 0.7683 | 186.31 ms | 563.67 ms | 1.4987 |
| `es_hybrid` | **0.8963** | **0.8625** | **0.9162** | **0.8171** | 340.94 ms | 888.57 ms | 2.4365 |
| `es_iterative_hybrid` | 0.7012 | 0.3279 | 0.2224 | 0.4756 | 1841.30 ms | 3253.06 ms | 0.4963 |

Nhận xét: `es_hybrid` là baseline mạnh nhất theo quality. Iterative context ban đầu bị query drift và latency cao khi dùng fanout lớn.

## Iterative Improvements

Config: `top_k=10`, `candidate_k=50`, `num_candidates=300`, `first_hop_k=3`, `second_hop_k=5`, `rrf_k=30`.

| Method | Expansion | Recall@10 | nDCG@10 | MRR@10 | Full-support Recall@10 | p50 latency | p95 latency | QPS |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `es_hybrid` | single-shot | **0.8963** | **0.8598** | **0.9106** | 0.8171 | **213.80 ms** | **469.85 ms** | 0.9159 |
| `es_iterative_hybrid` | question + title + context prefix | 0.8902 | 0.6403 | 0.6507 | 0.8171 | 834.36 ms | 1385.74 ms | 1.0708 |
| `es_iterative_title` | question + title | 0.8720 | 0.5482 | 0.4507 | 0.7927 | 692.96 ms | 903.60 ms | 1.3964 |
| `es_iterative_sentence` | question + title + selected sentence | 0.8902 | 0.6287 | 0.6064 | **0.8293** | 787.05 ms | 1000.13 ms | 1.2500 |
| `es_iterative_fast` | title-only, lower fanout | 0.8659 | 0.5573 | 0.4731 | 0.7805 | 635.19 ms | 718.16 ms | **1.5588** |

## Interpretation

`es_hybrid` vẫn là lựa chọn tốt nhất để serve vì ranking tốt nhất và latency thấp nhất trong nhóm chất lượng cao. Các biến thể iterative đã cải thiện mạnh so với iterative context ban đầu khi giảm `candidate_k`, `num_candidates`, `first_hop_k`, và `second_hop_k`.

`es_iterative_sentence` là biến thể multi-hop đáng chú ý nhất: full-support Recall@10 đạt 0.8293, cao hơn `es_hybrid` 0.8171. Tuy nhiên MRR/nDCG thấp hơn nhiều, nghĩa là method này tìm đủ evidence tốt hơn một chút nhưng xếp hạng evidence chưa tốt và latency vẫn cao hơn hybrid khoảng 3.7 lần theo p50.

`es_iterative_fast` giảm p95 latency xuống 718.16 ms, tốt hơn các iterative variants khác, nhưng quality giảm so với hybrid. Đây là cấu hình phù hợp để demo trade-off latency/quality, chưa nên làm default.

## Report Positioning

Kết luận nên trình bày:

```text
Sau khi scale lên 100k docs, hybrid BM25 + dense + RRF vẫn là baseline mạnh nhất. Iterative multi-hop retrieval có thể tăng nhẹ khả năng lấy đủ supporting documents khi dùng sentence-aware expansion, nhưng cần reranking hoặc chain scoring tốt hơn để cải thiện MRR/nDCG và latency. Vì vậy, hướng tiếp theo là giữ hybrid làm default, dùng iterative sentence-aware như experimental mode, sau đó nghiên cứu reranker, MDR hoặc IRCoT khi data/index full-scale ổn định hơn.
```

## Limitations

- 100k corpus là prefix subset, không phải full 5.23M corpus.
- Benchmark chỉ giữ 82 validation queries có toàn bộ gold docs nằm trong 100k index.
- Latency có thể có outlier do local machine, Elasticsearch cache, và query embedding warmup.
- Kết quả hiện là retrieval-only, chưa có reader để chấm Answer F1 hoặc Joint F1.

## Next Steps

1. Thêm chain reranking cho iterative results để cải thiện MRR/nDCG.
2. Thử selected-sentence expansion với scoring tốt hơn lexical overlap.
3. Scale tiếp lên 500k hoặc 1M khi download/index resources ổn định.
4. Chuẩn bị data chain và hard negatives nếu muốn test MDR.
5. Chuẩn bị LLM reasoning traces, cost tracking, và answer eval nếu muốn test IRCoT.
