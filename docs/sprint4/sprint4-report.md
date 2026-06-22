# Sprint 4 Report: Retrieval Robustness, Metadata Search, VimQA, and Dataset Runtime

Ngày tổng hợp: 2026-06-21

## Executive Summary

Sprint 4 đã hoàn tất các workstream chính trong kế hoạch: HotpotQA paraphrase robustness, iterative retrieval improvement, synthetic metadata search, VimQA retrieval pipeline, và dataset-first runtime để truy vấn HotpotQA/VimQA trong cùng một API/UI.

Theo Harness matrix hiện tại, `US-S4-001` đến `US-S4-011` đều ở trạng thái `implemented`. Sprint này không đổi default HotpotQA retrieval khỏi `tv_hybrid`, vì thử nghiệm Bridge-RRF chưa vượt baseline. Sprint cũng không claim leaderboard hoặc paper-comparable; toàn bộ số liệu là project-progress evidence trên local artifacts.

Kết quả nổi bật:

- Paraphrase benchmark hoàn tất 4 query sets, mỗi set 200 query: `original_200`, `mild_200`, `strong_200`, `lexical_strong_200`.
- `lexical_strong_200` là stress set thật: `tv_hybrid` giảm full-support@10 từ `0.535` xuống `0.480`, còn `tv_dense` giảm từ `0.515` xuống `0.495`.
- Bridge-RRF two-hop chạy smoke 50 và pilot 200 query, nhưng không thắng `tv_hybrid`: `0.520` vs `0.535` full-support@10.
- Synthetic metadata đã được generate cho toàn bộ 5,233,329 HotpotQA documents với `author`, `created_at`, `modified_at`.
- Metadata demo cho thấy filter `author=Nguyen An` thu hẹp corpus còn 40,886 docs; author + January 2024 còn 1,793 docs.
- VimQA đã được stage thành retrieval proxy gồm 3,623 documents, 9,044 queries, 9,044 qrels; full benchmark đã chạy trên 9,044 queries.
- VimQA full benchmark: `es_bm25` recall@10 `0.9627`, `es_dense` BKAI `0.8716`, `es_hybrid` `0.9644`; default VimQA nên là BM25 vì rank-sensitive metrics và latency tốt hơn.
- Dataset-first API/UI đã có `/datasets/{dataset_id}/...`, dataset selector, Search/Queries/Benchmark/Indexes/Metadata/History/Status theo dataset, embedding health, metadata controls, loading feedback, và query suggestions giữ đúng `query_id` để hiện gold support.
- `start.sh` là entrypoint runtime mới: chạy host GPU embedding service, warm cả HotpotQA 384-dim và VimQA 768-dim, rồi bật Docker Compose.

## Scope Và Non-Goals

Sprint 4 bắt đầu với bốn workstream chính trong `docs/sprint4/plan.md`:

1. Kiểm tra robustness khi HotpotQA query bị paraphrase.
2. Thử cải tiến iterative retrieval bằng evidence-chain metrics và Bridge-RRF.
3. Thêm synthetic metadata search cho demo meeting-search.
4. Xây minimal VimQA retrieval pipeline.

Trong quá trình triển khai, Sprint 4 mở rộng thêm một runtime workstream thực tế: dataset-first API/UI refactor để HotpotQA và VimQA có thể được truy vấn riêng trong cùng một app, kèm host GPU multi-model embedding service.

Các non-goals vẫn giữ nguyên:

- Không làm Redis cache hardening trong Sprint 4.
- Không thêm LLM query rewrite, cross-encoder reranking, MDR training, hoặc Beam Retrieval training.
- Không claim BEIR, leaderboard, hoặc paper-comparable.
- Không dùng synthetic metadata như HotpotQA truth thật.
- Không đổi dashboard default khỏi `tv_hybrid` nếu benchmark không chứng minh cải thiện.

## Harness Completion Matrix

| Story | Nội dung | Trạng thái | Proof chính |
| --- | --- | --- | --- |
| `US-S4-001` | Sprint 4 initiative setup | implemented | `docs/sprint4/plan.md`, E04 epic README, story skeletons; Redis cache hardening out of scope. |
| `US-S4-002` | HotpotQA paraphrase export protocol | implemented | `docs/sprint4/paraphrase-protocol.md`; accepted=603, `mild_200=200`, `strong_200=200`, `lexical_strong_200=200`, regeneration_needed=0. |
| `US-S4-003` | Kaggle/OpenAI paraphrase roundtrip validator | implemented | 416 merged candidates, 400 selected natural rows, regeneration empty; validator tests 7 passed. |
| `US-S4-004` | Full-corpus paraphrase robustness benchmark | implemented | Final report compares mild/strong/lexical_strong; validator/notebook tests 7 passed. |
| `US-S4-005` | Synthetic metadata generator | implemented | Full metadata artifact: 5,233,329 docs, 105 shard files, 128 synthetic authors, 1,831,684 modified docs. |
| `US-S4-006` | Metadata-aware retrieval path | implemented | Metadata mapping/filter path; unit/API suite 55 passed, adjacent tests 2 passed; smoke index 50,000 docs. |
| `US-S4-007` | Metadata demo report | implemented | `docs/sprint4/metadata-demo-report.md`; scenario artifact counts 5 scenarios over full corpus; scenario tests 2 passed. |
| `US-S4-008` | VimQA benchmark pipeline research | implemented | 9,044-query full benchmark; BM25/dense/hybrid metrics reported; indexes validated at 3,623 docs. |
| `US-S4-009` | Iterative retrieval improvement | implemented | Chain metrics and `tv_two_hop_bridge_rrf`; focused tests 19 passed; smoke 50 and pilot 200 artifacts. |
| `US-S4-010` | Lexical-strong paraphrase profile | implemented | `lexical_strong_200` generated, validated, benchmarked; full-support@10 table added. |
| `US-S4-011` | Dataset-first API/UI runtime refactor | implemented | Dataset endpoints/UI, metadata controls, embedding health, VimQA benchmark dashboard, query-id suggestions; backend/frontend/browser proofs recorded. |

## Workstream 1: HotpotQA Paraphrase Robustness

Sprint 4 tạo pipeline end-to-end để benchmark retrieval khi query HotpotQA bị viết lại:

```text
200 source queries
  -> OpenAI-compatible paraphrase generation
  -> local validation and regeneration
  -> lexical diversity audit
  -> benchmark 4 retrieval methods
  -> report and charts
```

Protocol và report chính:

```text
docs/sprint4/paraphrase-protocol.md
docs/sprint4/paraphrase-robustness-report.md
```

Pipeline giữ `source_query_id` để qrels của query gốc vẫn là source of truth sau khi paraphrase text thay đổi.

### Final Query Sets

| Query set | Số rows | Vai trò |
| --- | ---: | --- |
| `original_200` | 200 | Baseline source queries. |
| `mild_200` | 200 | Rewrite nhẹ, gần câu gốc. |
| `strong_200` | 200 | Reorder/cấu trúc mạnh hơn, nhưng vẫn còn nhiều lexical anchor. |
| `lexical_strong_200` | 200 | Stress set bắt buộc đổi non-entity content words. |

Artifacts cuối:

```text
artifacts/hotpotqa_full/paraphrase/validated/original_200.tsv
artifacts/hotpotqa_full/paraphrase/validated/mild_200.tsv
artifacts/hotpotqa_full/paraphrase/validated/strong_200.tsv
artifacts/hotpotqa_full/paraphrase/validated/lexical_strong_200.tsv
artifacts/hotpotqa_full/paraphrase/validated/summary.json
artifacts/hotpotqa_full/paraphrase/validated/accepted.tsv
artifacts/hotpotqa_full/paraphrase/validated/rejected.tsv
artifacts/hotpotqa_full/paraphrase/validated/regeneration_needed.tsv
```

Final validation outcome:

| Chỉ số | Giá trị |
| --- | ---: |
| Final candidates sau merge/regenerate | 668 |
| Accepted candidates | 603 |
| Selected benchmark rows | 600 |
| `natural_mild` selected | 200 |
| `natural_strong` selected | 200 |
| `lexical_strong` selected | 200 |
| Missing sau regeneration | 0 |

### Lexical Strength Audit

| Set | Median content-change | Mean content Jaccard | No new content terms | Kết luận |
| --- | ---: | ---: | ---: | --- |
| `mild_200` | 0.0976 | 0.8041 | 89/200 | Gần câu gốc, nhiều keyword giữ nguyên. |
| `strong_200` | 0.2727 | 0.6114 | 23/200 | Đổi rõ hơn mild, nhưng vẫn còn nhiều anchor. |
| `lexical_strong_200` | 0.5000 | 0.3407 | 0/200 | Đủ mạnh để stress lexical retrieval. |

### Benchmark Results

Benchmark outputs:

```text
evaluation/results/hotpotqa_full/paraphrase_final/original_200.json
evaluation/results/hotpotqa_full/paraphrase_final/mild_200.json
evaluation/results/hotpotqa_full/paraphrase_final/strong_200.json
evaluation/results/hotpotqa_full/paraphrase_final/lexical_strong_200.json
evaluation/results/hotpotqa_full/paraphrase_final/summary.json
```

Metric chính là `full_support_recall@10`.

| Method | Original | Mild | Strong | Lexical Strong |
| --- | ---: | ---: | ---: | ---: |
| `es_bm25` | 0.365 | 0.365 | 0.375 | 0.340 |
| `tv_dense` | 0.515 | 0.515 | 0.515 | 0.495 |
| `tv_hybrid` | 0.535 | 0.515 | 0.515 | 0.480 |
| `tv_filtered_hybrid` | 0.430 | 0.435 | 0.440 | 0.395 |

Delta từ original:

| Method | Δ Mild | Δ Strong | Δ Lexical Strong |
| --- | ---: | ---: | ---: |
| `es_bm25` | +0.000 | +0.010 | -0.025 |
| `tv_dense` | +0.000 | +0.000 | -0.020 |
| `tv_hybrid` | -0.020 | -0.020 | -0.055 |
| `tv_filtered_hybrid` | +0.005 | +0.010 | -0.035 |

Interpretation:

- `mild` và `strong` chưa làm BM25 tụt rõ vì vẫn giữ nhiều keyword.
- `lexical_strong` mới tạo áp lực thật lên lexical overlap.
- `tv_dense` ổn định nhất dưới lexical substitution.
- `tv_hybrid` tốt nhất trên original nhưng tụt mạnh nhất trên lexical strong.
- Giữ `tv_hybrid` làm default demo vẫn hợp lý, nhưng report phải ghi rõ robustness gap.

Charts:

```text
docs/sprint4/assets/paraphrase_full_support_decay.png
docs/sprint4/assets/paraphrase_relative_decay.png
docs/sprint4/assets/paraphrase_full_support_decay.svg
docs/sprint4/assets/paraphrase_relative_decay.svg
```

## Workstream 2: Iterative Retrieval Improvement

Sprint 4 thêm evidence-chain metrics và method benchmark-only `tv_two_hop_bridge_rrf`.

Report:

```text
docs/sprint4/retrieval-improvement-report.md
```

Implemented slice:

- `SearchHit` có optional chain metadata: `chain_rank`, `chain_doc_ids`.
- Evaluation metrics có `full_support_recall@2`, `full_support_recall@5`, `full_support_recall@10`.
- Chain-aware metrics: `chain_recall@1`, `chain_recall@5`, `chain_mrr`.
- `TurboVecHybridRetriever.search_two_hop_bridge_rrf` cho benchmark path.
- Benchmark dispatcher hỗ trợ `tv_two_hop_bridge_rrf`, `beam_size`, `max_bridge_terms`.

Method flow:

```text
question
  -> tv_hybrid hop 1
  -> top beam first-hop documents
  -> bridge query = question + first-hop title + selected first-hop terms
  -> tv_hybrid hop 2 per bridge document
  -> candidate chains (p1, p2)
  -> RRF-style chain score
  -> flattened ranked documents with chain metadata
```

Unit proof:

```text
python -m pytest tests/test_metrics.py tests/test_turbovec_retriever.py tests/test_benchmark_es.py -q
=> 19 passed
```

50-query smoke artifact:

```text
evaluation/results/hotpotqa_full/bridge_rrf/bridge_rrf_smoke_50.json
```

| Method | full_support@2 | full_support@5 | full_support@10 | nDCG@10 | p95 ms | QPS | Chain recall@5 | Chain MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.300 | 0.440 | 0.460 | 0.6659 | 4215.9710 | 0.3707 | n/a | n/a |
| `tv_two_hop_bridge_rrf` | 0.120 | 0.420 | 0.480 | 0.6260 | 3761.5026 | 0.3962 | 0.320 | 0.2083 |

200-query pilot artifacts:

```text
evaluation/results/hotpotqa_full/bridge_rrf/bridge_rrf_pilot_200.json
evaluation/runs/hotpotqa_full/bridge_rrf/tv_hybrid_beir_hotpotqa_dev_top10.trec
evaluation/runs/hotpotqa_full/bridge_rrf/tv_two_hop_bridge_rrf_beir_hotpotqa_dev_top10.trec
```

| Method | full_support@2 | full_support@5 | full_support@10 | Recall@10 | MRR@10 | nDCG@10 | p95 ms | QPS | Chain recall@1 | Chain recall@5 | Chain MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.330 | 0.475 | 0.535 | 0.740 | 0.8608 | 0.7214 | 2080.4528 | 0.8313 | n/a | n/a | n/a |
| `tv_two_hop_bridge_rrf` | 0.170 | 0.450 | 0.520 | 0.735 | 0.8468 | 0.6916 | 2832.7420 | 0.5281 | 0.170 | 0.390 | 0.2589 |

Decision:

- Success rule yêu cầu `tv_two_hop_bridge_rrf` tăng `full_support_recall@10` ít nhất `+0.05` so với `tv_hybrid`, đồng thời p95 không quá `2.5x`.
- Kết quả thực tế: `0.520` vs `0.535`, tức không thắng quality baseline.
- p95 `2832.7420 ms` vẫn trong guardrail so với `2080.4528 ms`, nhưng quality không đủ.
- Default vẫn là `tv_hybrid`.

## Workstream 3: Synthetic Metadata Search

Sprint 4 generate metadata synthetic cho HotpotQA full corpus, không đụng nội dung gốc và không append metadata vào dense embedding text.

Metadata fields:

```text
author
created_at
modified_at
```

Generator proof:

```text
python -m pytest tests/test_synthetic_metadata.py -q
=> 7 passed
```

Artifacts:

```text
artifacts/hotpotqa_full/metadata/manifest.json
artifacts/hotpotqa_full/metadata_smoke/manifest.json
```

Full artifact counts:

| Field | Value |
| --- | ---: |
| Documents written | 5,233,329 |
| Metadata shard files | 105 |
| Synthetic authors | 128 |
| Modified docs | 1,831,684 |
| Unchanged docs | 3,401,645 |

`US-S4-006` thêm metadata-aware search path:

- Elasticsearch mapping index `author` như keyword, `created_at`/`modified_at` như date.
- `es_bm25` apply filters trong filter context.
- BM25 ingest copy metadata khi staging row có metadata.
- Search hit payload expose `author`, `created_at`, `modified_at`.
- `tv_hybrid` với metadata filters route sang `tv_filtered_hybrid` vì cần BM25-side hard prefilter.
- `tv_dense` với metadata filters trả HTTP 400, vì dense-only path v1 không enforce metadata constraints.

Validation:

```text
python -m pytest tests/test_elasticsearch_retriever.py tests/test_es_hotpotqa_cli.py tests/test_turbovec_retriever.py tests/test_api_es_config.py -q
=> 55 passed, 3 warnings

python -m pytest tests/test_api_cache.py tests/test_search_history.py -q
=> 2 passed, 3 warnings
```

Platform smoke:

```text
hotpotqa_full_metadata_smoke_v1
hotpotqa_full_metadata_current
count = 50,000
query = Anarchism
filter = author=Nguyen An
example result = doc_id=12, author=Nguyen An, created_at=2024-01-01, modified_at=2024-01-02
```

Metadata demo report:

```text
docs/sprint4/metadata-demo-report.md
evaluation/results/hotpotqa_full/metadata/scenario_summary.json
```

Scenario proof:

```text
python -m pytest tests/test_metadata_demo_scenarios.py -q
=> 2 passed
```

Full-corpus narrowing results:

| Scenario | Effective method | Filters | Matching docs | Narrowing |
| --- | --- | --- | ---: | ---: |
| `content_only_anarchism` | `es_bm25` | none | 5,233,329 | 0.0000% |
| `author_nguyen_an` | `es_bm25` | `author=Nguyen An` | 40,886 | 99.2187% |
| `created_january_2024` | `es_bm25` | `created_at=2024-01-01..2024-01-31` | 222,239 | 95.7534% |
| `modified_mid_january_2024` | `es_bm25` | `modified_at=2024-01-10..2024-01-20` | 60,589 | 98.8422% |
| `hybrid_author_created_january` | `tv_filtered_hybrid` | `author=Nguyen An`, January 2024 | 1,793 | 99.9657% |

Later UI follow-up in `US-S4-011` exposed these filters on the Search page for HotpotQA and shows metadata unsupported for VimQA.

## Workstream 4: VimQA Retrieval Pipeline

Sprint 4 converted local VimQA JSON into a retrieval proxy:

```text
question -> query
unique normalized context -> document
question-context relation -> qrel
```

Design/report:

```text
docs/sprint4/vimqa-benchmark-design.md
docs/sprint4/vimqa-pipeline-report.md
```

Generated artifacts:

```text
artifacts/vimqa/all/staging/docs-00000.jsonl
artifacts/vimqa/all/staging/manifest.json
evaluation/results/vimqa/vimqa_queries.tsv
evaluation/results/vimqa/vimqa_qrels.tsv
evaluation/runs/vimqa/
```

Corpus shape:

| Item | Count |
| --- | ---: |
| Unique context documents | 3,623 |
| Queries | 9,044 |
| Qrels | 9,044 |

Validation and staging evidence:

```text
python -m pytest tests/test_stage_vimqa.py tests/test_vimqa_dataset.py -q
=> 3 passed

python -m pytest tests/test_elasticsearch_retriever.py tests/test_stage_vimqa.py -q
=> 19 passed

python -m pytest tests/test_benchmark_es.py -q
=> 11 passed

python scripts/stage_vimqa.py --docs-per-file 5000
=> wrote 3,623 documents, 9,044 queries, 9,044 qrels
```

Indexes:

| Alias | Purpose | Validation |
| --- | --- | --- |
| `vimqa_all_bm25_current` | BM25 over Vietnamese contexts | expected count 3,623 passed |
| `vimqa_all_dense_bkai_current` | BKAI dense vector/hybrid | expected count 3,623 passed |

Dense model:

```text
bkai-foundation-models/vietnamese-bi-encoder
dims = 768
backend = Elasticsearch dense_vector
```

Full benchmark artifacts:

```text
evaluation/results/vimqa/bm25_vimqa_full.json
evaluation/results/vimqa/dense_bkai_vimqa_full.json
```

Full 9,044-query results:

| Method | Recall@10 | MRR@10 | nDCG@10 | p50 ms | p95 ms | QPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `es_bm25` | 0.9627 | 0.8606 | 0.8859 | 57.9400 | 84.4191 | 16.3922 |
| `es_dense` BKAI | 0.8716 | 0.7272 | 0.7625 | 83.7323 | 115.0396 | 10.5955 |
| `es_hybrid` BM25+BKAI RRF | 0.9644 | 0.8277 | 0.8609 | 176.0548 | 206.3031 | 1.2394 |

Interpretation:

- BM25 is strongest for rank-sensitive metrics and latency.
- Hybrid gets the highest recall@10 by a tiny margin (`0.9644` vs `0.9627`) but is slower and lower on MRR/nDCG.
- Dense BKAI works but does not beat BM25 in this dataset shape.
- VimQA default in UI should be `es_bm25`.

Caveats:

- VimQA is a QA-derived retrieval proxy, not a native BEIR dataset.
- Train/test contexts are unioned so the gold context is retrievable; this is readiness evidence, not held-out benchmark proof.
- Existing runner lacks progress logging for long 9,044-query runs.

## Workstream 5: Dataset-First API/UI Runtime

Sprint 4 ended with `US-S4-011`, a dataset-first runtime refactor that made the demo usable for both HotpotQA and VimQA.

New dataset-scoped endpoints:

```text
GET  /datasets
GET  /datasets/{dataset_id}/stats
GET  /datasets/{dataset_id}/queries
GET  /datasets/{dataset_id}/benchmarks
GET  /datasets/{dataset_id}/embedding-health
POST /datasets/{dataset_id}/search
```

Legacy HotpotQA endpoints remain compatible during migration:

```text
/stats
/queries
/benchmark
/search
```

The React UI now uses a dataset selector and routes these views through the active dataset:

```text
Search
Queries
Benchmark
Indexes
Metadata
History
System Status
```

Important behavior decisions:

- One API process and one UI serve both datasets.
- Canonical endpoint shape is `/datasets/{dataset_id}/...`.
- UI is query/read-only inspection oriented; no index rebuild/edit controls.
- HotpotQA supports metadata filters.
- VimQA shows metadata unsupported.
- VimQA benchmark UI emphasizes recall/MRR/nDCG instead of HotpotQA full-support metrics.

### Runtime And Embedding Service

`start.sh` became the primary runtime entrypoint:

```text
./start.sh
```

It does the following:

1. Checks `docker`, host `python`, and `nvidia-smi`.
2. Starts or reuses host embedding service on port `8010`.
3. Runs `scripts/embedding_server.py --device cuda --no-warmup` when needed.
4. Warms HotpotQA embedding model and checks 384 dimensions.
5. Warms VimQA embedding model and checks 768 dimensions.
6. Checks whether Docker Compose containers already exist; builds only when missing.
7. Starts `elasticsearch`, `redis`, `api`, and `frontend`.
8. Verifies API container can reach `host.docker.internal:8010/health`.
9. Smokes `/datasets` and a HotpotQA `tv_hybrid` search.

Embedding service model registry:

| Model id | Model | Dim |
| --- | --- | ---: |
| `hotpotqa` | `BAAI/bge-small-en-v1.5` | 384 |
| `vimqa` | `bkai-foundation-models/vietnamese-bi-encoder` | 768 |

Status Overview now includes dataset-scoped embedding health. Runtime smoke recorded:

```text
HotpotQA: hotpotqa:384/384 READY
VimQA: vimqa:768/768 READY
CUDA: true
```

### UI Follow-Ups Completed

After the main dataset-first refactor, several UI/runtime follow-ups were completed:

- Search page added HotpotQA metadata controls: `author`, `created_at` range, `modified_at` range.
- VimQA metadata controls are disabled and labeled unsupported.
- Search button and results area show loading feedback while a query is running.
- System Status shows embedding model health.
- VimQA Benchmark/Status display the full 9,044-query benchmark instead of stale pilot-only numbers.
- HotpotQA suggestion chips now use TSV-backed `queryId`, so Gold Support no longer shows `Unavailable` for preset queries.

Representative proof from `US-S4-011`:

```text
python -m pytest tests/test_api_dataset_profiles.py tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q
=> 36 passed

python -m pytest tests/test_elasticsearch_retriever.py tests/test_turbovec_retriever.py -q
=> 28 passed

python -m pytest tests/test_search_ui_metadata.py tests/test_frontend_dataset_state.py -q
=> 4 passed after query-id suggestion fix

docker compose exec -T frontend npm run lint
=> TypeScript passed
```

Browser/API smoke evidence:

- HotpotQA metadata controls rendered and sent compact filters.
- VimQA metadata unsupported state rendered disabled.
- Status Overview showed both embedding health rows.
- Benchmark page showed VimQA 9,044-query metrics.
- HotpotQA preset query `5ac4401b5542997ea680ca4c` sent `query_id` and UI showed `Gold Support Found 1/2`.

## Final Runtime Shape

HotpotQA flow:

```text
Select HotpotQA
  -> Queries loads evaluation/results/hotpotqa_full_dev_queries.tsv
  -> Search posts to /datasets/hotpotqa/search
  -> Methods include es_bm25, tv_dense, tv_hybrid, tv_filtered_hybrid
  -> Benchmark emphasizes full_support_recall@10
  -> Metadata filters are supported
```

VimQA flow:

```text
Select VimQA
  -> Queries loads evaluation/results/vimqa/vimqa_queries.tsv
  -> Search posts to /datasets/vimqa/search
  -> Methods include es_bm25, es_dense, es_hybrid
  -> Default method is es_bm25
  -> Benchmark emphasizes recall@10, MRR@10, nDCG@10
  -> Metadata filters are unsupported in Sprint 4
```

Docker/runtime services:

```text
frontend: http://localhost:3001
api:      http://localhost:8001
ES:       http://localhost:9200
Redis:    compose internal redis:6379
Embed:    host http://localhost:8010
```

## Key Decisions

1. Keep `tv_hybrid` as the HotpotQA default. Bridge-RRF did not beat quality baseline.
2. Treat `lexical_strong_200` as the true paraphrase stress set. `mild`/`strong` are still useful but too lexical-overlap-heavy.
3. Keep synthetic metadata out of dense embedding text. Metadata is filter/display only in Sprint 4.
4. Use one API and one UI for HotpotQA/VimQA. Separate services are not needed yet.
5. Use BM25 as the VimQA default because it wins rank-sensitive metrics and latency.
6. Keep GPU/PyTorch dependencies on the host embedding service, not inside the API container.
7. Use dataset-scoped API namespaces instead of `/vimqa/search` or `/hotpotqa/search` shortcuts.

## Remaining Follow-Ups

These are not Sprint 4 blockers, but they are the next useful steps:

1. Add progress logging or batching for long 9,044-query VimQA benchmark runs.
2. Add a dedicated validation command that checks all Sprint 4 report artifacts exist and match expected counts.
3. Tune VimQA dense/hybrid only if there is a clear research goal; current BM25 baseline is already strong.
4. Revisit Bridge-RRF with better bridge-term selection or reranking only if the goal is multi-hop quality research.
5. Decide whether synthetic metadata should later become real meeting metadata schema, separate from HotpotQA demo metadata.
6. Add richer UI display for result metadata if the demo needs inspection beyond filter controls.
7. Consider favicon/static asset cleanup; browser smoke currently logs a harmless missing favicon request.

## Final Assessment

Sprint 4 is complete as an evaluation-expansion sprint. It produced concrete artifacts, reports, benchmark outputs, and a usable dataset-first demo runtime.

The strongest product outcome is that the system moved from a HotpotQA-only full-corpus retrieval demo into a two-dataset inspection workspace:

```text
HotpotQA full-corpus retrieval
  + paraphrase robustness evidence
  + metadata-filter demo evidence
  + iterative retrieval experiment evidence

VimQA retrieval proxy
  + staged corpus/query/qrels artifacts
  + BM25/dense/hybrid full benchmark evidence

One UI/API runtime
  + dataset-scoped endpoints
  + dataset selector
  + benchmark/status/search views per dataset
  + GPU host embedding service for both embedding models
```

The most important scientific caveat is unchanged: these are local project-progress results, not leaderboard or paper-comparable claims.
