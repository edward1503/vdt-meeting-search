# HotpotQA Full Test Benchmark And Paper Comparison

Ngày cập nhật: 2026-06-30

## Executive Summary

Hệ thống trong project này là một **full-corpus evidence retrieval workspace** cho HotpotQA/VimQA, không chỉ là một script benchmark. Với HotpotQA, hệ thống ingest 5,233,329 Wikipedia documents, build Elasticsearch BM25 index, build TurboVec dense index nén 4-bit, rồi phục vụ retrieval qua FastAPI/React dashboard với các mode lexical, dense, hybrid và bridge-aware multi-hop retrieval.

Benchmark full `beir/hotpotqa/test` đã chạy xong trên 7,405 queries với hai phương pháp đại diện cho hệ thống HotpotQA hiện tại:

1. `tv_hybrid`: baseline hybrid BM25 + TurboVec dense, fuse bằng RRF.
2. `tv_bridge_title_entities_rrf`: bridge-aware retrieval đã tune ở `beam_size=1`, `max_bridge_terms=6`.

Kết quả chính: bridge-aware retrieval tăng `full_support_recall@10` từ `0.5175` lên `0.6008`, tức +8.33 điểm tuyệt đối. Đây là metric quan trọng nhất cho HotpotQA retrieval trong project, vì một query multi-hop chỉ được tính thành công khi toàn bộ support documents xuất hiện trong top-10.

Trade-off: bridge-aware retrieval chậm hơn đáng kể. p95 latency tăng từ `760.9212 ms` lên `1598.3422 ms`, QPS giảm từ `1.9147` xuống `0.7321`. Ngoài ra `MRR@10` giảm nhẹ từ `0.8413` xuống `0.8251`, nghĩa là bridge method ưu tiên lấy đủ bộ support hơn là đẩy support đầu tiên lên rank sớm nhất.

So với các paper/benchmark bên ngoài, claim an toàn nhất là:

> Trên cùng họ benchmark BEIR HotpotQA test, `tv_bridge_title_entities_rrf` đạt `nDCG@10=0.7120`, cao hơn các baseline Pyserini BEIR như BM25 multifield `0.603`, SPLADE++ `0.687`, Contriever `0.638`, và gần BGE-base `0.726`. Tuy nhiên, `full_support_recall@10=0.6008` là metric retrieval evidence coverage nội bộ của project, không phải answer EM/F1 hoặc supporting-fact F1 như các HotpotQA QA papers.

## System Under Test

### What The System Is

Project này xây một retrieval workspace có thể chạy thực tế trên full corpus:

```text
Raw corpus / queries
  -> staging with stable doc_id + numeric_id
  -> Elasticsearch BM25 index for lexical search, filters, and hydration
  -> BGE embeddings + TurboVec 4-bit dense index for semantic search
  -> FastAPI retrieval service
  -> React dashboard for search, query browsing, benchmark display, support overlay
```

Với HotpotQA, bài toán không phải chỉ "tìm một document liên quan". Mỗi query thường cần đủ hai supporting documents. Vì vậy hệ thống dùng `full_support_recall@k` làm metric chính bên cạnh `nDCG`, `Recall`, `MRR`, latency và QPS.

### Main Components

| Component | Role in system | HotpotQA evidence |
| --- | --- | --- |
| Dataset staging | Chuẩn hóa corpus/query/qrels, giữ stable `doc_id` và `numeric_id` | 5,233,329 docs, 7,405 test queries |
| Elasticsearch | BM25 lexical retrieval, document hydration, metadata/filter store | `hotpotqa_full_bm25_current` |
| Embedding service | Host-GPU BGE query embedding service | `BAAI/bge-small-en-v1.5`, 384-dim |
| TurboVec | Dense retrieval trên compressed full-corpus vector index | 4-bit `.tvim` artifact for HotpotQA |
| RRF fusion | Fuse BM25 and dense rankings without score calibration | Used by `tv_hybrid` |
| Bridge retriever | Build second-hop bridge queries from first-hop title/entity evidence | Used by `tv_bridge_title_entities_rrf` |
| FastAPI + React UI | Dataset-first workspace, search/debug/benchmark surfaces | HotpotQA and VimQA profiles |
| Redis / SQLite | Cache repeated retrieval responses and store local search history | Demo/runtime support |

### Retrieval Methods In The System

| Method | Status | Purpose |
| --- | --- | --- |
| `es_bm25` | Runtime baseline | Fast lexical retrieval and exact entity matching |
| `tv_dense` | Runtime/benchmark path | Semantic dense retrieval over TurboVec |
| `tv_hybrid` | Current practical HotpotQA baseline | BM25 + dense RRF, good quality/speed balance |
| `tv_filtered_hybrid` | Metadata/filter-oriented path | Hybrid retrieval under filter constraints |
| `tv_bridge_title_entities_rrf` | Quality-first benchmark method | Multi-hop/second-support retrieval for HotpotQA |

Nói gọn: `tv_hybrid` là method dễ dùng hơn cho interactive demo; `tv_bridge_title_entities_rrf` là method chất lượng tốt nhất trong benchmark full test, nhưng chậm hơn nên chưa nên coi là default runtime nếu chưa tối ưu latency.

### Main Contribution Of The System

1. **Full-corpus retrieval engineering**: chạy HotpotQA ở quy mô 5.23M documents, không còn là nano/demo corpus.
2. **Compressed dense retrieval**: dùng TurboVec 4-bit để giữ dense retrieval local-friendly.
3. **Hybrid retrieval workspace**: Elasticsearch làm lexical/filter/hydration, TurboVec làm semantic retrieval, RRF làm fusion.
4. **Multi-hop evidence metric**: đánh giá bằng `full_support@k`, đúng hơn cho HotpotQA so với chỉ precision/recall document rời rạc.
5. **Bridge-aware retrieval**: thêm bước second-hop từ title/entity evidence để giảm lỗi thiếu support document thứ hai.
6. **Usable inspection surface**: API/UI có dataset profiles, query browser, benchmark surface, highlight/support overlay, metadata search path.

## Evaluation Protocol

| Item | Value |
| --- | --- |
| Dataset | `beir/hotpotqa/test` |
| Queries | 7,405 |
| Corpus/index | `hotpotqa_full_bm25_current` |
| Top-k | 10 |
| Embedding model | `BAAI/bge-small-en-v1.5` |
| Dense index | TurboVec 4-bit HotpotQA full corpus |
| Candidate settings | `candidate_k=100`, `num_candidates=100`, `rrf_k=30` |
| Bridge settings | `first_hop_k=5`, `second_hop_k=10`, `beam_size=1`, `max_bridge_terms=6` |

Artifacts:

- `evaluation/results/hotpotqa_full/test_full/tv_hybrid_test_full.json`
- `evaluation/results/hotpotqa_full/test_full/tv_bridge_title_entities_rrf_beam1_terms6_test_full.json`
- `evaluation/runs/hotpotqa_full/test_tv_hybrid/tv_hybrid_beir_hotpotqa_test_top10.trec`
- `evaluation/runs/hotpotqa_full/test_bridge_tuned/tv_bridge_title_entities_rrf_beir_hotpotqa_test_top10.trec`
- `logs/hotpotqa_test_benchmark.stdout.log`

## Methods

### `tv_hybrid`

`tv_hybrid` là baseline hybrid retrieval hiện tại. Method này chạy BM25 trên Elasticsearch và dense search trên TurboVec, sau đó fuse hai ranking bằng Reciprocal Rank Fusion. Ưu điểm là đơn giản, nhanh hơn bridge method, và MRR cao. Điểm yếu là với HotpotQA, one-shot query thường tìm được một support document nhưng thiếu support document thứ hai.

### `tv_bridge_title_entities_rrf`

`tv_bridge_title_entities_rrf` nhắm trực tiếp vào lỗi thiếu support thứ hai. Method này:

1. chạy first-hop `tv_hybrid`;
2. lấy top bridge candidates;
3. tạo bridge query từ question + title/entity/lead terms của first-hop document;
4. chạy second-hop retrieval;
5. rank evidence chains;
6. flatten các chain tốt nhất thành top-k documents.

Config test dùng tuning tốt nhất từ pilot dev 200-query: `beam_size=1`, `max_bridge_terms=6`.

## Full Test Results

### Headline Quality

| Method | nDCG@10 | Recall@10 | MRR@10 | Full-support@10 |
| --- | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.7001 | 0.7305 | **0.8413** | 0.5175 |
| `tv_bridge_title_entities_rrf` | **0.7120** | **0.7585** | 0.8251 | **0.6008** |
| Delta | +0.0119 | +0.0280 | -0.0162 | **+0.0833** |

Đọc nhanh: bridge method thắng ở mục tiêu chính `full_support@10`, nhưng hy sinh một ít `MRR@10`.

### Evidence Coverage

| Method | Full-support@2 | Full-support@5 | Full-support@10 | Any-support@10 | Success / 7,405 | Partial support | Missing support |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.2849 | 0.4362 | 0.5175 | **0.9436** | 3,832 | 3,155 | 418 |
| `tv_bridge_title_entities_rrf` | **0.2924** | **0.5097** | **0.6008** | 0.9161 | **4,449** | **2,335** | 621 |
| Delta | +0.0075 | +0.0735 | **+0.0833** | -0.0275 | **+617** | **-820** | +203 |

Đọc nhanh: bridge method convert thêm 617 queries thành full-support success và giảm 820 partial-support failures. Đây là bằng chứng rõ nhất rằng method đang giải đúng lỗi "có một support nhưng thiếu support còn lại". `Any-support@10` giảm vì bridge method dành slot cho second-hop candidates, nên ít query chỉ có một support dễ ở top-10 hơn.

### Latency Trade-Off

| Method | p50 ms | p95 ms | p99 ms | QPS |
| --- | ---: | ---: | ---: | ---: |
| `tv_hybrid` | **403.4576** | **760.9212** | **1188.6671** | **1.9147** |
| `tv_bridge_title_entities_rrf` | 881.9076 | 1598.3422 | 2446.6885 | 0.7321 |
| Delta | +478.4500 | +837.4210 | +1258.0214 | -1.1826 |

Interpretation:

- Bridge method có gain lớn nhất ở `full_support_recall@10`, đúng với mục tiêu kéo support document còn thiếu.
- Gain ở `full_support@5` cũng lớn: `0.4362 -> 0.5097`, tức method không chỉ nhồi support vào cuối top-10.
- `MRR@10` giảm nhẹ vì ranking chuyển từ "support đầu tiên thật cao" sang "đủ cặp support".
- Latency tăng khoảng 2.10 lần ở p95, nên bridge method phù hợp làm quality-first benchmark path hơn là default interactive path nếu chưa tối ưu thêm.

## Dev Pilot Versus Full Test

| Method / split | Queries | Recall@10 | nDCG@10 | Full-support@10 | p95 ms | QPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid`, dev pilot | 200 | 0.7500 | 0.7291 | 0.5450 | 1146.5764 | 1.2979 |
| `tv_bridge_title_entities_rrf`, dev tuned | 200 | 0.7775 | 0.7382 | 0.6200 | 1224.9911 | 1.1034 |
| `tv_hybrid`, full test | 7,405 | 0.7305 | 0.7001 | 0.5175 | 760.9212 | 1.9147 |
| `tv_bridge_title_entities_rrf`, full test | 7,405 | 0.7585 | 0.7120 | 0.6008 | 1598.3422 | 0.7321 |

Kết luận generalization: gain của bridge method giữ được trên full test. Pilot dev tăng `full_support@10` +0.0750; full test tăng +0.0833. Chất lượng giảm nhẹ khi chuyển từ 200-query dev pilot sang full test, nhưng pattern chính không biến mất.

## Comparison With External Benchmarks And Papers

### Direct Retrieval Comparison: BEIR / Pyserini

Pyserini BEIR regression table báo kết quả HotpotQA test với cùng kiểu metric `nDCG@10` và `R@100`. Các số nDCG@10 HotpotQA trong bảng main results gồm:

| Rank by nDCG@10 | System | nDCG@10 | Comparison note |
| ---: | --- | ---: | --- |
| 1 | BGE-base-en-v1.5 | 0.726 | Strong dense baseline; larger model than our BGE-small |
| 2 | `tv_bridge_title_entities_rrf` | 0.7120 | This project, quality-first bridge method |
| 3 | `tv_hybrid` | 0.7001 | This project, simpler hybrid baseline |
| 4 | SPLADE++ CoCondenser-EnsembleDistil | 0.687 | Sparse neural retrieval |
| 5 | Contriever MS MARCO | 0.638 | Dense retriever |
| 6 | BM25 flat | 0.633 | Lucene baseline |
| 7 | BM25 multifield | 0.603 | Title/content BM25 baseline |

Reading:

- `tv_bridge_title_entities_rrf` is competitive on BEIR-style `nDCG@10`: above Pyserini BM25, SPLADE++, and Contriever rows, but below the Pyserini BGE-base row.
- This is encouraging because our dense side uses `BAAI/bge-small-en-v1.5` plus a compressed TurboVec index, not a flat BGE-base Faiss setup.
- The comparison should still be framed as "near BEIR retrieval baselines" rather than a leaderboard claim, because index construction, document fields, model size, quantization, and latency environment differ.

Source: Pyserini BEIR regressions, HotpotQA row and evaluation commands: <https://castorini.github.io/pyserini/2cr/beir.html>

### HotpotQA Original Paper

The HotpotQA paper defines the task around multi-hop Wikipedia QA and stresses that questions require reasoning over multiple supporting documents/sentences. It reports answer EM/F1, supporting-fact EM/F1, and joint EM/F1 for QA systems.

Our benchmark is not the same task. We evaluate the retriever before any reader/answer generator. Therefore:

- Do compare conceptually: both care about retrieving enough evidence for multi-hop reasoning.
- Do not compare our `full_support_recall@10` directly with answer F1 or supporting-fact F1.
- Presentation-safe wording: "Our result measures whether the retrieval layer returns all gold support documents in top-10; it is a prerequisite for answer generation, not an answer score."

Source: HotpotQA paper / homepage: <https://aclanthology.org/D18-1259/> and <https://hotpotqa.github.io/>

### MDR: Multi-Hop Dense Retrieval

MDR is the closest conceptual reference to our bridge-aware direction: recursively retrieve support passages for complex open-domain questions. The public MDR repo defines:

- `PR`: at least one supporting passage included in retrieved passages;
- `P-EM`: both supporting passages included;
- `Path Recall`: whether any top-k retrieved chain matches the ground-truth support chain.

On 7,405 HotpotQA validation samples, the MDR repo reports top-1 chain retrieval:

| MDR metric | Reported value |
| --- | ---: |
| Avg PR | 0.8428 |
| Avg P-EM | 0.6593 |
| Avg 1-Recall | 0.7907 |
| Path Recall | 0.6593 |

Our closest internal metric is `full_support_recall@10=0.6008`, but it is not the same as MDR `P-EM` because MDR evaluates learned dense passage chains in its own processed HotpotQA setup, while this project evaluates document-level top-10 retrieval over BEIR HotpotQA with TurboVec/BM25 hybrid infrastructure.

Interpretation: our bridge method reaches the same family of evidence-completeness goal, but remains a heuristic retrieval method. MDR is a trained multi-hop retriever and should be treated as a stronger research baseline, not as a directly matched engineering baseline.

Source: MDR repo expected retrieval results: <https://github.com/facebookresearch/multihop_dense_retrieval>

### Beam Retrieval

Beam Retrieval is a supervised multi-hop retrieval system in a reading-comprehension candidate-passage setting. It reports retrieval EM/F1 on HotpotQA dev:

| System | HotpotQA Retrieval EM | HotpotQA Retrieval F1 |
| --- | ---: | ---: |
| FE2H | 96.32 | 98.02 |
| Smoothing R3 | 96.85 | 98.32 |
| Beam Retrieval, beam size 1 | 97.29 | 98.55 |
| Beam Retrieval, beam size 2 | 97.52 | 98.68 |

These numbers are much higher than our full-corpus `full_support@10`, but they are not comparable. Beam Retrieval evaluates over HotpotQA distractor/reading-comprehension candidate passages where each question has a small candidate set, while our task retrieves from a 5.23M-document full corpus index.

The useful comparison is architectural: both methods show that modeling evidence as a sequence/beam can improve multi-hop retrieval. Our implementation is a lightweight, unsupervised bridge heuristic; Beam Retrieval is an end-to-end trained retriever.

Source: End-to-End Beam Retrieval for Multi-Hop Question Answering: <https://arxiv.org/html/2308.08973v2>

### IRCoT

IRCoT interleaves chain-of-thought generation with retrieval. Its central claim is that one-step retrieve-and-read is insufficient for multi-step QA because later retrieval depends on intermediate reasoning state.

This supports the same direction as our result:

- `tv_hybrid` is a one-shot retrieval baseline.
- `tv_bridge_title_entities_rrf` adds an intermediate bridge state from first-hop evidence.
- The full test gain in `full_support@10` suggests that even a simple non-LLM bridge state helps evidence completeness.

But IRCoT is a reasoning/retrieval loop with an LLM and downstream QA evaluation, not a pure retriever benchmark comparable by one table.

Source: IRCoT ACL paper: <https://aclanthology.org/2023.acl-long.557/>

## What We Can Claim

Strong claims:

- Full HotpotQA test benchmark completed on 7,405 queries for `tv_hybrid` and tuned `tv_bridge_title_entities_rrf`.
- Tuned bridge retrieval improves `full_support_recall@10` by +8.33 absolute points over `tv_hybrid`.
- The improvement from the 200-query dev pilot generalizes to the full test split.
- On BEIR-style `nDCG@10`, `tv_bridge_title_entities_rrf=0.7120` is competitive with several published/reproduced BEIR retrieval baselines and close to Pyserini BGE-base `0.726`.

Claims to avoid:

- Do not say we beat HotpotQA QA papers. They report answer/supporting-fact/joint QA metrics.
- Do not compare `full_support_recall@10` directly with supporting-fact F1.
- Do not claim production latency. The benchmark is local runtime evidence.
- Do not claim learned multi-hop retrieval. The current bridge method is heuristic and benchmark-only.

## Recommendation

Use `tv_bridge_title_entities_rrf` as the quality-first HotpotQA retrieval method in the report/slide deck, with this concise message:

> On full BEIR HotpotQA test, bridge-aware retrieval improves complete evidence coverage from 51.75% to 60.08% in top-10. The cost is latency: p95 rises from 0.76s to 1.60s. This makes bridge retrieval the strongest benchmark method, while `tv_hybrid` remains the better interactive default unless we optimize the second-hop path.

Next engineering steps:

1. Reduce bridge latency by caching first-hop/hop-2 embedding calls and avoiding redundant hydration.
2. Add deeper diagnostics for full test: success, partial support, missing candidate, and bridge query failure buckets.
3. Evaluate a learned or LLM-assisted bridge query generator only after diagnostics show query construction is the bottleneck.
4. If aiming for paper-style HotpotQA QA comparison, add a reader/LLM answer stage and report answer EM/F1, supporting-fact EM/F1, and joint EM/F1 separately.

## References

- Pyserini BEIR regressions: <https://castorini.github.io/pyserini/2cr/beir.html>
- BEIR paper: <https://arxiv.org/abs/2104.08663>
- HotpotQA paper: <https://aclanthology.org/D18-1259/>
- HotpotQA homepage: <https://hotpotqa.github.io/>
- MDR repo: <https://github.com/facebookresearch/multihop_dense_retrieval>
- MDR paper: <https://arxiv.org/abs/2009.12756>
- Beam Retrieval paper: <https://arxiv.org/html/2308.08973v2>
- IRCoT paper: <https://aclanthology.org/2023.acl-long.557/>
