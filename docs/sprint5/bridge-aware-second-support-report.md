# Bridge-Aware Second-Support Retrieval Report

## Summary

The bridge-aware title/entity ablation improved HotpotQA `full_support_recall@10` from `0.545` to `0.620` on the 200-query `beir/hotpotqa/dev` pilot.

This is the first ingest/retrieval follow-up in this thread that moved the main HotpotQA metric materially. The method is slower than one-shot `tv_hybrid`, but it is slightly faster and clearly better than the older `tv_two_hop_bridge_rrf` pilot under the same runtime settings.

## Goal

Improve HotpotQA `full_support_recall@10` by targeting queries where one support document is retrieved but the second support document is missing.

## Method

`tv_bridge_title_entities_rrf` is a benchmark-only method. It starts from first-hop `tv_hybrid` candidates, builds focused bridge queries from title/entity/lead-sentence terms, retrieves second-hop candidates, ranks evidence chains, and flattens them into a top-k document list.

## Commands

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_current --methods tv_hybrid,tv_two_hop_bridge_rrf,tv_bridge_title_entities_rrf --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --beam-size 3 --max-bridge-terms 8 --output evaluation/results/hotpotqa_full/bridge_title_entities/bridge_title_entities_200.json --run-dir evaluation/runs/hotpotqa_full/bridge_title_entities
```

## Results

Source: `evaluation/results/hotpotqa_full/bridge_title_entities/bridge_title_entities_200.json`.

| Method | Recall@10 | MRR@10 | nDCG@10 | Full-support@10 | p50 latency | p95 latency | QPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.7500 | 0.8691 | 0.7291 | 0.5450 | 535.2074 ms | 1146.5764 ms | 1.2979 |
| `tv_two_hop_bridge_rrf` | 0.7450 | 0.8512 | 0.6999 | 0.5600 | 1969.0927 ms | 2773.5883 ms | 0.4924 |
| `tv_bridge_title_entities_rrf` | 0.7850 | 0.8541 | 0.7398 | 0.6200 | 1820.3986 ms | 2670.3591 ms | 0.5206 |

## Diagnostics

Source: `evaluation/results/hotpotqa_full/bridge_title_entities/second_support_diagnostics.json`.

The top-10 diagnostics were generated from the benchmark TREC files and a first-200-query HotpotQA qrels TSV exported to `evaluation/results/hotpotqa_full/bridge_title_entities/hotpotqa_dev_200_qrels.tsv`.

| Method | Success | Partial support | Missing candidate | Candidate recall@10 |
| --- | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 109 | 82 | 9 | 0.7500 |
| `tv_two_hop_bridge_rrf` | 112 | 74 | 14 | 0.7450 |
| `tv_bridge_title_entities_rrf` | 124 | 66 | 10 | 0.7850 |

Compared with `tv_hybrid`, the new bridge method converts 15 more queries into full-support success and reduces partial-support failures by 16 queries. That is exactly the failure mode targeted by the experiment.

## Decision

Keep `tv_bridge_title_entities_rrf` as the strongest benchmark-only HotpotQA candidate from this branch so far.

Do not make it the default runtime method yet because p95 latency is still about 2.67 seconds on the 200-query pilot. The next experiment should tune the same method for latency and robustness, not return to ingest tweaks:

- reduce `beam_size` from 3 to 2;
- compare `max_bridge_terms` 4, 6, and 8;
- run a deeper candidate diagnostic if a top-50/top-100 run artifact is needed;
- only consider default promotion if the tuned method keeps most of the `full_support@10` gain with acceptable latency.
