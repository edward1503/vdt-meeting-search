# Title-Aware BM25 Ablation Report

## Summary

The title-aware BM25 ablation was implemented and benchmarked on the full HotpotQA corpus. It should not replace the current retrieval default.

The ablation slightly improved standard document-level metrics over the existing `es_bm25` baseline, but it did not improve the most important HotpotQA metric: `full_support_recall@10`. The result supports the EDA report's caution: strengthening title/entity fields is cheap and clean, but the dominant failure mode still appears to be missing the second support document rather than weak first-hop lexical matching.

## Index

| Field | Value |
| --- | --- |
| Index | `hotpotqa_full_titleaware_bm25_v1` |
| Alias | `hotpotqa_full_titleaware_bm25_current` |
| Documents | 5,233,329 |
| Staging source | `artifacts/hotpotqa_full/staging` |
| Progress dir | `artifacts/hotpotqa_full/progress/titleaware_bm25` |
| Progress markers | 105 |

Title-aware indexed fields:

- `title_exact`
- `lead_sentence`
- `title_repeat_content`

Title-aware query fields:

```text
title^3
title_exact^4
title_repeat_content^1.5
lead_sentence^1.2
content
```

## Commands

```powershell
python scripts/es_hotpotqa.py create-bm25-index --index hotpotqa_full_titleaware_bm25_v1 --alias hotpotqa_full_titleaware_bm25_current --reset --title-aware
python scripts/es_hotpotqa.py ingest-bm25 --index hotpotqa_full_titleaware_bm25_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress/titleaware_bm25 --batch-size 1000 --title-aware
python scripts/es_hotpotqa.py validate --index hotpotqa_full_titleaware_bm25_current --expected-count 5233329
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_titleaware_bm25_current --methods es_bm25_title --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 30 --output evaluation/results/hotpotqa_full/title_aware_bm25_200.json --run-dir evaluation/runs/hotpotqa_full/title_aware_bm25
```

## Results

Baseline source: `evaluation/results/hotpotqa_full/tv_full_200.json`.

Title-aware source: `evaluation/results/hotpotqa_full/title_aware_bm25_200.json`.

| Method | Recall@10 | MRR@10 | nDCG@10 | Full-support@10 | p50 latency | p95 latency | QPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `es_bm25` | 0.6025 | 0.7108 | 0.5727 | 0.365 | 126.3355 ms | 359.6319 ms | 5.9315 |
| `es_bm25_title` | 0.6050 | 0.7159 | 0.5786 | 0.365 | 111.5174 ms | 316.9459 ms | 6.6254 |

## Interpretation

Title-aware BM25 is a small positive lexical ablation:

- Recall@10 improved by 0.0025.
- MRR@10 improved by 0.0051.
- nDCG@10 improved by 0.0059.
- p95 latency improved from 359.6319 ms to 316.9459 ms in this pilot.

But it did not improve `full_support_recall@10`, which stayed at 0.365. This means the ablation did not solve the core HotpotQA requirement of retrieving both support documents in top 10.

## Decision

Keep `es_bm25_title` as an explicit benchmark method and index ablation, but do not make it the default retrieval path.

The next quality experiment should target bridge/second-support retrieval directly, for example:

- two-hop candidate generation with deeper candidate diagnostics;
- bridge-aware query expansion from the first support candidate;
- entity/title logging for partial-support failures;
- dense or hybrid reranking focused on the missing second support document.
