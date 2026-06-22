# VimQA Pipeline Report

## Summary

VimQA is now staged as a retrieval proxy and indexed in Elasticsearch for BM25 and BKAI dense/hybrid retrieval. The full benchmark covers all 9,044 VimQA queries on the local Docker/Elasticsearch profile.

## Artifacts

| Artifact | Path / name |
| --- | --- |
| Staging JSONL | `artifacts/vimqa/all/staging/docs-00000.jsonl` |
| Staging manifest | `artifacts/vimqa/all/staging/manifest.json` |
| Query TSV | `evaluation/results/vimqa/vimqa_queries.tsv` |
| Qrels TSV | `evaluation/results/vimqa/vimqa_qrels.tsv` |
| BM25 result | `evaluation/results/vimqa/bm25_vimqa_1000.json` |
| BKAI dense/hybrid result | `evaluation/results/vimqa/dense_bkai_vimqa_1000.json` |
| BM25 full result | `evaluation/results/vimqa/bm25_vimqa_full.json` |
| BKAI dense/hybrid full result | `evaluation/results/vimqa/dense_bkai_vimqa_full.json` |
| TREC runs | `evaluation/runs/vimqa/` |

Manifest counts:

```text
documents = 3,623
queries = 9,044
qrels = 9,044
```

## Commands

Stage VimQA:

```powershell
python scripts/stage_vimqa.py --docs-per-file 5000
```

Create and ingest BM25:

```powershell
docker compose up -d elasticsearch
python scripts/es_hotpotqa.py create-bm25-index --index vimqa_all_bm25_v1 --alias vimqa_all_bm25_current --reset
python scripts/es_hotpotqa.py ingest-bm25 --index vimqa_all_bm25_v1 --staging-dir artifacts/vimqa/all/staging --progress-dir artifacts/vimqa/all/progress/bm25 --batch-size 1000
python scripts/es_hotpotqa.py validate --index vimqa_all_bm25_current --expected-count 3623
```

Create and ingest BKAI dense vectors:

```powershell
python scripts/es_hotpotqa.py create-index --index vimqa_all_dense_bkai_v1 --alias vimqa_all_dense_bkai_current --dims 768 --reset
python scripts/es_hotpotqa.py ingest --index vimqa_all_dense_bkai_v1 --staging-dir artifacts/vimqa/all/staging --progress-dir artifacts/vimqa/all/progress/dense_bkai --model bkai-foundation-models/vietnamese-bi-encoder --batch-size 64
python scripts/es_hotpotqa.py validate --index vimqa_all_dense_bkai_current --expected-count 3623
```

Run pilot benchmarks:

```powershell
python -m src.evaluation.benchmark_es --dataset vimqa/all --index vimqa_all_bm25_current --methods es_bm25 --top-k 10 --max-queries 1000 --query-file evaluation/results/vimqa/vimqa_queries.tsv --qrels-file evaluation/results/vimqa/vimqa_qrels.tsv --output evaluation/results/vimqa/bm25_vimqa_1000.json --run-dir evaluation/runs/vimqa
```

```powershell
python -m src.evaluation.benchmark_es --dataset vimqa/all --index vimqa_all_dense_bkai_current --methods es_bm25,es_dense,es_hybrid --top-k 10 --max-queries 1000 --query-file evaluation/results/vimqa/vimqa_queries.tsv --qrels-file evaluation/results/vimqa/vimqa_qrels.tsv --model bkai-foundation-models/vietnamese-bi-encoder --num-candidates 500 --candidate-k 50 --rrf-k 30 --output evaluation/results/vimqa/dense_bkai_vimqa_1000.json --run-dir evaluation/runs/vimqa
```

Run full benchmarks:

```powershell
python -m src.evaluation.benchmark_es --dataset vimqa/all --index vimqa_all_bm25_current --methods es_bm25 --top-k 10 --query-file evaluation/results/vimqa/vimqa_queries.tsv --qrels-file evaluation/results/vimqa/vimqa_qrels.tsv --output evaluation/results/vimqa/bm25_vimqa_full.json --run-dir evaluation/runs/vimqa
```

```powershell
python -m src.evaluation.benchmark_es --dataset vimqa/all --index vimqa_all_dense_bkai_current --methods es_dense,es_hybrid --top-k 10 --query-file evaluation/results/vimqa/vimqa_queries.tsv --qrels-file evaluation/results/vimqa/vimqa_qrels.tsv --model bkai-foundation-models/vietnamese-bi-encoder --num-candidates 500 --candidate-k 50 --rrf-k 30 --output evaluation/results/vimqa/dense_bkai_vimqa_full.json --run-dir evaluation/runs/vimqa
```

## Full Results

The table below reports all 9,044 queries.

| Method | Recall@10 | MRR@10 | nDCG@10 | p50 ms | p95 ms | QPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `es_bm25` | 0.9627 | 0.8606 | 0.8859 | 57.9400 | 84.4191 | 16.3922 |
| `es_dense` BKAI | 0.8716 | 0.7272 | 0.7625 | 83.7323 | 115.0396 | 10.5955 |
| `es_hybrid` BM25+BKAI RRF | 0.9644 | 0.8277 | 0.8609 | 176.0548 | 206.3031 | 1.2394 |

## Pilot Results

The table below reports the first 1,000 queries.

| Method | Recall@10 | MRR@10 | nDCG@10 | p50 ms | p95 ms | QPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `es_bm25` on BM25 index | 0.987 | 0.9113 | 0.9300 | 52.3291 | 63.2800 | 18.7042 |
| `es_bm25` on dense BKAI index | 0.987 | 0.9113 | 0.9300 | 59.8943 | 96.5966 | 16.3988 |
| `es_dense` BKAI | 0.891 | 0.7507 | 0.7852 | 83.8668 | 116.3407 | 8.9515 |
| `es_hybrid` BM25+BKAI RRF | 0.983 | 0.8647 | 0.8935 | 179.4866 | 204.2746 | 5.4791 |

## Interpretation

BM25 is the strongest rank-sensitive method on the full conversion. That matches the dataset shape: VimQA questions have high lexical overlap with their paired contexts, and each query has one gold context.

BKAI dense retrieval works, but it does not beat BM25. Hybrid RRF is slightly higher on recall@10 than BM25 on the full run, but it adds latency and lowers rank-sensitive metrics in this configuration. The dashboard default for VimQA should therefore start with BM25 or present BM25 as the reference method until a later Vietnamese dense tuning pass shows a clear win.

## Caveats

- Full benchmarks were completed for all 9,044 queries, but the runner has no progress output while a method is running. Long runs should gain progress logging or query batching before repeated tuning.
- This is a QA-derived retrieval proxy, not a native BEIR benchmark.
- Train and test contexts are unioned into one corpus by design; this makes all query gold contexts retrievable but means the result is dataset-readiness evidence rather than a held-out retrieval claim.
- The BKAI model card recommends Vietnamese word segmentation for local input. This MVP uses the existing SentenceTransformer path without adding a segmentation stage.

## Next Steps

1. Add progress logging or query batching for full 9,044-query benchmark runs.
2. Use these artifacts to implement dataset-first API profiles for `hotpotqa` and `vimqa`.
3. Add synthetic VimQA metadata after dataset-scoped endpoints exist.
