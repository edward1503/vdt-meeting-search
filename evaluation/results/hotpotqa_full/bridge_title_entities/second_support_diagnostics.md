# Sprint 5 Ranking Diagnostics

This report analyzes existing ranked runs to separate candidate-generation failures from ranking failures.

Target cutoff: top-10
Candidate depth: top-10
Queries: 200

## Method Summary

| Method | Full support@k | Any support@k | Candidate recall@depth | Missing candidate | Partial candidate support | Candidate ranked low | Success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tv_hybrid | 0.5450 | 0.9550 | 0.7500 | 9 | 82 | 0 | 109 |
| tv_two_hop_bridge_rrf | 0.5600 | 0.9300 | 0.7450 | 14 | 74 | 0 | 112 |
| tv_bridge_title_entities_rrf | 0.6200 | 0.9500 | 0.7850 | 10 | 66 | 0 | 124 |

## Interpretation Rule

- `missing_candidate`: reranking cannot fix these queries because relevant documents are absent from the analyzed candidate depth.
- `partial_candidate_support`: at least one relevant document is present, but not all required support appears by the analyzed candidate depth.
- `candidate_ranked_low`: all required support appears by candidate depth, but not by the target cutoff; this is the clearest reranker-ready bucket.
- `success`: all known support documents appear by the target cutoff.

## Current Limitation

This first-pass report uses the available top-10 TREC runs. It can identify top-10 success and missing/partial support at top-10, but it cannot yet prove candidate@50 or candidate@100 reranker readiness. A deeper run should be generated before making a final reranker decision.
