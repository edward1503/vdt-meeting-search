# Sprint 3 HotpotQA 5M TurboVec Hybrid Retrieval Report

## 1. Goal and Scope

Sprint 3 builds the full-scale retrieval path for HotpotQA using Elasticsearch for BM25/document storage, TurboVec for dense retrieval, and application-layer RRF for hybrid fusion.

Current implementation status: code paths and focused tests are implemented. Full 5,233,329-document staging is complete. Elasticsearch ingest, embedding generation, TurboVec full-index build, and 200-query benchmark remain pending platform jobs.

## 2. Hardware

Pending measurement for full run. Target local environment is Windows/Python 3.12 with approximately 16 GB RAM.

## 3. Dataset and Corpus Size

Target corpus: HotpotQA full corpus with 5,233,329 documents.

Completed artifact:`n`n- `artifacts/hotpotqa_full/staging/manifest.json`: docs_written=5,233,329, files_written=105, numeric_id_start=0, numeric_id_end=5,233,328

## 4. Architecture

Accepted decision: `docs/decisions/0006-sprint3-dense-backend.md`.

- Elasticsearch: BM25 lexical index and document store.
- TurboVec: compressed dense vector index using `IdMapIndex` and 4-bit quantization.
- Application layer: RRF fusion for `tv_hybrid`.
- Legacy Elasticsearch dense/hybrid methods remain available for nano or vector-enabled indexes.

## 5. Index and Build Artifacts

Implemented artifact-producing commands:

```powershell
python scripts/embed_hotpotqa.py --staging-dir artifacts/hotpotqa_full/staging --embedding-dir artifacts/hotpotqa_full/embeddings --progress-dir artifacts/hotpotqa_full/progress/embed --batch-size 64
python scripts/build_turbovec.py --embedding-dir artifacts/hotpotqa_full/embeddings --output artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim --config-output artifacts/hotpotqa_full/turbovec/config.json --dim 384 --bit-width 4
```

Pending artifacts:

- `artifacts/hotpotqa_full/embeddings/*.float16.npy`
- `artifacts/hotpotqa_full/embeddings/*.ids.npy`
- `artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim`
- `artifacts/hotpotqa_full/turbovec/config.json`

## 6. Benchmark Configuration

Implemented methods:

- `es_bm25`
- `tv_dense`
- `tv_hybrid`
- `tv_filtered_hybrid`

Primary pending command:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa --index hotpotqa_full_bm25_v1 --methods es_bm25,tv_dense,tv_hybrid --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 30 --output evaluation/results/hotpotqa_full/tv_full_200.json --run-dir evaluation/runs/hotpotqa_full
```

## 7. Accuracy Metrics

Pending full benchmark. Expected metrics are `precision@10`, `recall@10`, `mrr@10`, 
dcg@10`, and `full_support_recall@10`.

## 8. Latency and QPS

Pending full benchmark. The API now includes `latency_breakdown_ms` for TurboVec methods with embed, BM25, TurboVec, fusion, and hydration timings when available.

## 9. Tuning Results

Pending full benchmark and tuning runs.

## 10. API and Demo Notes

The API accepts:

- `es_bm25`
- `es_dense`
- `es_hybrid`
- `es_iterative_hybrid`
- `tv_dense`
- `tv_hybrid`
- `tv_filtered_hybrid`

TurboVec retriever loading is lazy and only happens when a `tv_*` method is requested.

## 11. Limitations

- Full-corpus artifact jobs have not been run in this implementation pass.
- `tv_filtered_hybrid` currently uses the same broad dense search path as `tv_hybrid`; allowlist optimization remains a follow-up.
- Harness tool registry queries still fail because the installed schema does not include the newer tool table.

## 12. Next Steps

1. Run one-file staging smoke and validate numeric ids.
2. Stage the full HotpotQA corpus and validate `docs_written=5233329`.
3. Build and validate the full BM25 Elasticsearch index.
4. Generate embedding shards.
5. Build and load the full TurboVec index.
6. Run the 200-query benchmark and tuning commands.
7. Update this report with measured accuracy, latency, QPS, and final default-method recommendation.

## Acceptance Evidence So Far

```text
python -m pytest -q
55 passed, 3 warnings
```


