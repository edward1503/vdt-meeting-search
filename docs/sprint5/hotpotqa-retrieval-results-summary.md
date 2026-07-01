# HotpotQA Retrieval Results Summary

## Executive Summary

The strongest HotpotQA method from the current Sprint 5 experiments is:

```text
tv_bridge_title_entities_rrf
beam_size = 1
max_bridge_terms = 6
```

On the 200-query `beir/hotpotqa/dev` pilot, it keeps `full_support_recall@10 = 0.6200` while reducing p95 latency from `2670.3591 ms` to `1224.9911 ms` compared with the earlier quality-first bridge setting.

The key conclusion is that broad ingest changes were not the main source of quality gain. The meaningful gain came from bridge-aware second-support retrieval: use the first retrieved support-like document as an entity/title bridge to retrieve the missing second support document.

## Result Ladder

| Stage | Method | Full-support@10 | Recall@10 | nDCG@10 | p95 latency | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| BM25 baseline | `es_bm25` | 0.3650 | 0.6025 | 0.5727 | 359.6319 ms | Useful lexical baseline |
| Title-aware BM25 | `es_bm25_title` | 0.3650 | 0.6050 | 0.5786 | 316.9459 ms | Keep as ablation only |
| Hybrid baseline | `tv_hybrid` | 0.5450 | 0.7500 | 0.7291 | 1146.5764 ms | Strong simple baseline |
| Bridge quality-first | `tv_bridge_title_entities_rrf`, beam 3, terms 8 | 0.6200 | 0.7850 | 0.7398 | 2670.3591 ms | Best quality before tuning |
| Bridge tuned | `tv_bridge_title_entities_rrf`, beam 1, terms 6 | 0.6200 | 0.7775 | 0.7382 | 1224.9911 ms | Recommended next config |

## What Was Learned

### 1. Document EDA

HotpotQA documents in the staged full corpus are short:

| Metric | Value |
| --- | ---: |
| Sampled docs | 525,000 |
| Staging shards sampled | 105 |
| Content tokens p50 | 39 |
| Content tokens p95 | 111 |
| Content tokens p99 | 160 |

This makes broad passage chunking a weak first move. Most documents already behave like passages, while HotpotQA evaluation still expects document-level qrels.

Source:

- `docs/data/hotpotqa/hotpotqa_document_strategy_eda_report.md`
- `evaluation/results/hotpotqa_full/document_strategy_eda.json`

### 2. Title-Aware BM25

Title-aware indexing improved ordinary lexical metrics slightly, but did not improve `full_support_recall@10`.

| Method | Full-support@10 | Recall@10 | MRR@10 | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| `es_bm25` | 0.3650 | 0.6025 | 0.7108 | 0.5727 |
| `es_bm25_title` | 0.3650 | 0.6050 | 0.7159 | 0.5786 |

Decision: keep `es_bm25_title` as an explicit ablation, not a default.

Sources:

- `docs/sprint5/title-aware-bm25-ablation-report.md`
- `evaluation/results/hotpotqa_full/title_aware_bm25_200.json`

### 3. Bridge-Aware Retrieval

The first bridge-aware experiment targeted the dominant HotpotQA failure pattern: one support document appears, but the second support document is missing.

| Method | Full-support@10 | Recall@10 | nDCG@10 | p95 latency |
| --- | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.5450 | 0.7500 | 0.7291 | 1146.5764 ms |
| `tv_two_hop_bridge_rrf` | 0.5600 | 0.7450 | 0.6999 | 2773.5883 ms |
| `tv_bridge_title_entities_rrf` | 0.6200 | 0.7850 | 0.7398 | 2670.3591 ms |

Diagnostics:

| Method | Success | Partial support | Missing candidate |
| --- | ---: | ---: | ---: |
| `tv_hybrid` | 109 | 82 | 9 |
| `tv_bridge_title_entities_rrf` | 124 | 66 | 10 |

Decision: bridge-aware title/entity expansion is the first method here that materially improves the primary HotpotQA metric.

Sources:

- `docs/sprint5/bridge-aware-second-support-report.md`
- `evaluation/results/hotpotqa_full/bridge_title_entities/bridge_title_entities_200.json`
- `evaluation/results/hotpotqa_full/bridge_title_entities/second_support_diagnostics.json`

### 4. Bridge Tuning

The tuning grid showed that wide beam search was not necessary for the observed gain.

| Config | Beam | Terms | Full-support@10 | Recall@10 | nDCG@10 | p95 latency | QPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `beam1_terms6` | 1 | 6 | 0.6200 | 0.7775 | 0.7382 | 1224.9911 ms | 1.1034 |
| `beam2_terms4` | 2 | 4 | 0.6100 | 0.7825 | 0.7430 | 1758.8852 ms | 0.7452 |
| `beam2_terms6` | 2 | 6 | 0.6200 | 0.7850 | 0.7423 | 2593.4644 ms | 0.6062 |
| `beam2_terms8` | 2 | 8 | 0.6200 | 0.7850 | 0.7399 | 1827.7998 ms | 0.6896 |
| `beam3_terms8` | 3 | 8 | 0.6200 | 0.7850 | 0.7398 | 2670.3591 ms | 0.5206 |

Decision: use `beam1_terms6` as the next operating point. Keep `beam2_terms8` as a quality fallback.

Sources:

- `docs/sprint5/bridge-aware-tuning-report.md`
- `evaluation/results/hotpotqa_full/bridge_title_entities_tuning/summary.json`
- `evaluation/results/hotpotqa_full/bridge_title_entities_tuning/tuning_diagnostics.json`

## Current Recommendation

For the next HotpotQA experiment, use:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_current --methods tv_bridge_title_entities_rrf --top-k 10 --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --beam-size 1 --max-bridge-terms 6 --output evaluation/results/hotpotqa_full/bridge_title_entities_tuned_larger_dev.json --run-dir evaluation/runs/hotpotqa_full/bridge_title_entities_tuned_larger_dev
```

Do not promote this to the default runtime method yet. First run a larger dev/test evaluation and confirm the 200-query pilot holds.

## Presentation Claim

Use this wording:

> Our ingest pipeline made full-corpus retrieval reliable, but EDA showed HotpotQA documents are already short, so broad passage chunking was not the best first quality lever. Title-aware indexing improved lexical metrics slightly but did not improve full-support recall. The real gain came from bridge-aware second-support retrieval: use the first-hop document title/entity signal to retrieve the missing support document. Tuned bridge retrieval improved full-support@10 from 0.545 to 0.620 while keeping p95 close to the original hybrid baseline.

## Durable Records

| Story | Artifact |
| --- | --- |
| `US-S5-009` | HotpotQA document strategy EDA |
| `US-S5-010` | Title-aware BM25 ablation |
| `US-S5-011` | Bridge-aware second-support retrieval |
| `US-S5-012` | Bridge-aware retrieval tuning |
