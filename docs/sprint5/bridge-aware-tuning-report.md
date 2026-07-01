# Bridge-Aware Retrieval Tuning Report

## Summary

The tuning grid found a better operating point for `tv_bridge_title_entities_rrf`: `beam_size=1`, `max_bridge_terms=6`.

It keeps `full_support_recall@10=0.6200`, matching the quality-first `beam_size=3`, `max_bridge_terms=8` run, while reducing p95 latency from `2670.3591 ms` to `1224.9911 ms`.

## Baseline

Quality-first baseline from `US-S5-011`:

| Beam | Terms | Full-support@10 | Recall@10 | nDCG@10 | p95 latency | QPS |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 8 | 0.6200 | 0.7850 | 0.7398 | 2670.3591 ms | 0.5206 |

## Tuning Grid

Sources:

- `evaluation/results/hotpotqa_full/bridge_title_entities_tuning/summary.json`
- `evaluation/results/hotpotqa_full/bridge_title_entities_tuning/tuning_diagnostics.json`

| Config | Beam | Terms | Full-support@10 | Recall@10 | nDCG@10 | p95 latency | QPS | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `beam1_terms6` | 1 | 6 | 0.6200 | 0.7775 | 0.7382 | 1224.9911 ms | 1.1034 | Recommended latency-balanced config |
| `beam2_terms4` | 2 | 4 | 0.6100 | 0.7825 | 0.7430 | 1758.8852 ms | 0.7452 | Reject: loses full-support |
| `beam2_terms6` | 2 | 6 | 0.6200 | 0.7850 | 0.7423 | 2593.4644 ms | 0.6062 | Reject: little latency gain |
| `beam2_terms8` | 2 | 8 | 0.6200 | 0.7850 | 0.7399 | 1827.7998 ms | 0.6896 | Quality fallback |

## Diagnostics

| Config | Success | Partial support | Missing candidate | Candidate recall@10 |
| --- | ---: | ---: | ---: | ---: |
| `beam1_terms6` | 124 | 63 | 13 | 0.7775 |
| `beam2_terms4` | 122 | 69 | 9 | 0.7825 |
| `beam2_terms6` | 124 | 66 | 10 | 0.7850 |
| `beam2_terms8` | 124 | 66 | 10 | 0.7850 |

`beam1_terms6` preserves the same 124/200 full-support successes as the original quality-first configuration. Its tradeoff is slightly lower recall@10 and more missing-candidate cases than the beam-2 configs, but the p95 latency drop is large enough to make it the best next operating point.

## Decision

Use `tv_bridge_title_entities_rrf` with `beam_size=1` and `max_bridge_terms=6` for the next HotpotQA experiment.

Keep `beam_size=2`, `max_bridge_terms=8` as the quality fallback if later evaluation shows the beam-1 config is less stable on larger query sets. Do not promote either method as the default runtime path until a larger run confirms the 200-query pilot.
