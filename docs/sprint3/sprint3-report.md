# Sprint 3 HotpotQA 5M TurboVec Hybrid Retrieval Report

## 1. Goal and Scope

Sprint 3 scaled HotpotQA retrieval from nano experiments to the full 5,233,329-document corpus. The final architecture uses Elasticsearch for BM25 and document storage, TurboVec for compressed dense retrieval, and application-layer Reciprocal Rank Fusion for hybrid ranking.

Status: implemented. Full corpus staging, BM25 ingest, BGE-small embedding shards, TurboVec index build, full 200-query benchmark, tuning sweeps, API method exposure, and focused validation are complete.

Out of scope remains unchanged: VimQA integration, answer generation, LLM reasoning, embedding fine-tuning, reranker training, frontend redesign, and making iterative multihop retrieval the default.

## 2. Hardware

Measured local run environment:

- OS: Microsoft Windows 11 Home Single Language
- CPU: Intel(R) Core(TM) i5-10300H CPU @ 2.50GHz
- RAM: 15.8 GB
- Python: 3.12.4
- Elasticsearch: Docker Compose service `elasticsearch`, image `docker.elastic.co/elasticsearch/elasticsearch:8.15.1`
- Dense model: `BAAI/bge-small-en-v1.5`

## 3. Dataset and Corpus Size

Corpus source: HotpotQA full corpus staged from BEIR/Hugging Face-compatible data.

Completed artifact:

- `artifacts/hotpotqa_full/staging/manifest.json`: `docs_written=5,233,329`, `files_written=105`, `docs_per_file=50000`, `numeric_id_start=0`, `numeric_id_end=5,233,328`

Benchmark split:

- `beir/hotpotqa/dev`
- `max_queries=200`
- `top_k=10`

The plan command used `beir/hotpotqa`, but the benchmark runner requires a split with queries and qrels. The measured runs therefore use `beir/hotpotqa/dev`.

## 4. Architecture

Accepted decision: `docs/decisions/0006-sprint3-dense-backend.md`.

- Elasticsearch: BM25 lexical index and final document hydration store.
- TurboVec: compressed dense vector index with `IdMapIndex`, 4-bit quantization, and `uint64` numeric ids.
- Application layer: BM25 and dense rankings fused with RRF for `tv_hybrid`.
- Legacy Elasticsearch dense/hybrid methods remain available for nano or vector-enabled indexes.

## 5. Index and Build Artifacts

Elasticsearch BM25 index:

- Index: `hotpotqa_full_bm25_v1`
- Validated count: `5,233,329`
- BM25-only mapping excludes dense vectors and keeps `numeric_id` as a long field.

Embedding artifacts:

- Directory: `artifacts/hotpotqa_full/embeddings/`
- Shards: 105 `.float16.npy`, 105 `.ids.npy`, and 105 `.meta.json` files
- Model: `BAAI/bge-small-en-v1.5`
- Dimension: 384
- Vector dtype: `float16`
- ID dtype: `uint64`

TurboVec artifacts:

- Index: `artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim`
- Config: `artifacts/hotpotqa_full/turbovec/config.json`
- Config values: `docs=5,233,329`, `shards=105`, `dim=384`, `bit_width=4`
- Index size: 1,067,602,206 bytes

## 6. Benchmark Configuration

Primary command:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_v1 --methods es_bm25,tv_dense,tv_hybrid --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 30 --output evaluation/results/hotpotqa_full/tv_full_200.json --run-dir evaluation/runs/hotpotqa_full
```

Tuning commands:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_v1 --methods tv_hybrid --top-k 10 --max-queries 200 --candidate-k 50 --num-candidates 50 --rrf-k 30 --output evaluation/results/hotpotqa_full/tune_k50_rrf30.json --run-dir evaluation/runs/hotpotqa_full/tune_k50_rrf30
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_v1 --methods tv_hybrid --top-k 10 --max-queries 200 --candidate-k 200 --num-candidates 200 --rrf-k 30 --output evaluation/results/hotpotqa_full/tune_k200_rrf30.json --run-dir evaluation/runs/hotpotqa_full/tune_k200_rrf30
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_v1 --methods tv_hybrid --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 60 --output evaluation/results/hotpotqa_full/tune_k100_rrf60.json --run-dir evaluation/runs/hotpotqa_full/tune_k100_rrf60
```

## 7. Accuracy Metrics

Primary 200-query benchmark (`evaluation/results/hotpotqa_full/tv_full_200.json`):

| Method | precision@10 | recall@10 | mrr@10 | ndcg@10 | full_support_recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `es_bm25` | 0.1205 | 0.6025 | 0.7108 | 0.5727 | 0.365 |
| `tv_dense` | 0.1445 | 0.7225 | 0.8472 | 0.7082 | 0.515 |
| `tv_hybrid` | 0.1500 | 0.7500 | 0.8681 | 0.7286 | 0.545 |

`tv_hybrid` improves full-support recall by +0.180 absolute over BM25 on the measured 200-query split. `tv_dense` also beats BM25, confirming the TurboVec dense path is useful on the full corpus.

## 8. Latency and QPS

Primary 200-query benchmark:

| Method | p50 ms | p95 ms | p99 ms | QPS |
| --- | ---: | ---: | ---: | ---: |
| `es_bm25` | 126.3355 | 359.6319 | 731.5949 | 5.9315 |
| `tv_dense` | 572.2161 | 868.0033 | 1214.8422 | 1.2499 |
| `tv_hybrid` | 1004.3562 | 3089.2229 | 4072.7476 | 0.7935 |

BM25 remains the fastest path. TurboVec dense and hybrid improve retrieval quality at the cost of embedding, vector search, fusion, and hydration overhead.

## 9. Tuning Results

All tuning runs use `tv_hybrid`, 200 queries, and `top_k=10`.

| Config | precision@10 | recall@10 | ndcg@10 | full_support_recall@10 | p50 ms | p95 ms | QPS | Artifact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `k=50, rrf=30` | 0.1480 | 0.7400 | 0.7214 | 0.535 | 694.3532 | 2053.6018 | 0.8918 | `evaluation/results/hotpotqa_full/tune_k50_rrf30.json` |
| `k=100, rrf=30` | 0.1500 | 0.7500 | 0.7286 | 0.545 | 1004.3562 | 3089.2229 | 0.7935 | `evaluation/results/hotpotqa_full/tv_full_200.json` |
| `k=200, rrf=30` | 0.1495 | 0.7475 | 0.7282 | 0.540 | 811.1356 | 2528.6700 | 0.8488 | `evaluation/results/hotpotqa_full/tune_k200_rrf30.json` |
| `k=100, rrf=60` | 0.1490 | 0.7450 | 0.7246 | 0.535 | 919.7449 | 2111.4717 | 0.7895 | `evaluation/results/hotpotqa_full/tune_k100_rrf60.json` |

Recommended default method: `tv_hybrid`.

Recommended operating point for this laptop: `candidate_k=50`, `num_candidates=50`, `rrf_k=30`. It keeps full-support recall within 0.010 absolute of the best measured config while reducing p95 latency by about 1.0 second versus `k=100, rrf=30`.

Quality-first operating point: `candidate_k=100`, `num_candidates=100`, `rrf_k=30`.

## 10. API and Demo Notes

The API now accepts and routes:

- `es_bm25`
- `es_dense`
- `es_hybrid`
- `es_iterative_hybrid`
- `tv_dense`
- `tv_hybrid`
- `tv_filtered_hybrid`

`DEFAULT_SEARCH_METHOD` now defaults to `tv_hybrid`. TurboVec methods route through `TurboVecHybridRetriever` and include `latency_breakdown_ms` in uncached responses when timing data is available. The `/stats` endpoint reports both ES and TurboVec methods.

Focused API validation:

```text
python -m pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q
9 passed, 3 warnings
```

## 11. Limitations

- Benchmarks ran on one Windows laptop with approximately 16 GB RAM; latency should be remeasured on target deployment hardware before production claims.
- `tv_filtered_hybrid` now uses BM25 `numeric_id` candidates as a TurboVec allowlist before RRF fusion. It still needs a fresh full benchmark before it can replace broad `tv_hybrid` as the recommended default.
- Query embedding is local and synchronous in the benchmark/API path, which dominates part of dense and hybrid latency.
- BM25 is still the best low-latency fallback when quality requirements are relaxed.
- Harness tool registry queries fail in this workspace because the installed durable schema lacks the newer `tool` table; backlog item `Repair Harness tool registry schema install` tracks that process issue.

## 12. Next Steps

1. Benchmark the implemented `tv_filtered_hybrid` allowlist path against broad `tv_hybrid` on the same 200-query and full-dev settings.
2. Cache query embeddings for repeated benchmark/API queries.
3. Consider lowering API `HYBRID_BM25_K` and `HYBRID_DENSE_K` to 50 for laptop demos, while keeping 100 for quality-first evaluation.
4. Re-run the benchmark on target deployment hardware and record a platform-specific latency table.

## Acceptance Evidence

```text
python scripts/es_hotpotqa.py validate --index hotpotqa_full_bm25_v1 --expected-count 5233329
count_matches=true

python -m pytest tests/test_benchmark_es.py tests/test_turbovec_retriever.py -q
10 passed

python -m pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q
9 passed, 3 warnings

python scripts/verify_sprint3_benchmark.py
status=ok, queries=200, tv_hybrid_full_support_recall@10=0.545
```

Primary artifacts:

- `artifacts/hotpotqa_full/staging/manifest.json`
- `artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim`
- `artifacts/hotpotqa_full/turbovec/config.json`
- `evaluation/results/hotpotqa_full/tv_full_200.json`
- `evaluation/results/hotpotqa_full/tune_k50_rrf30.json`
- `evaluation/results/hotpotqa_full/tune_k200_rrf30.json`
- `evaluation/results/hotpotqa_full/tune_k100_rrf60.json`
- `evaluation/runs/hotpotqa_full/*.trec`
