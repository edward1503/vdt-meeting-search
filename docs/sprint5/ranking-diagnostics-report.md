# Sprint 5 Ranking Diagnostics

This report analyzes existing ranked runs to separate candidate-generation failures from ranking failures.

Target cutoff: top-10
Candidate depth: top-10
Queries: 200

## Method Summary

| Method | Full support@k | Any support@k | Candidate recall@depth | Missing candidate | Partial candidate support | Candidate ranked low | Success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| es_bm25 | 0.3650 | 0.8400 | 0.6025 | 32 | 95 | 0 | 73 |
| tv_dense | 0.5150 | 0.9300 | 0.7225 | 14 | 83 | 0 | 103 |
| tv_hybrid | 0.5450 | 0.9550 | 0.7500 | 9 | 82 | 0 | 109 |
| tv_filtered_hybrid | 0.4550 | 0.9050 | 0.6800 | 19 | 90 | 0 | 91 |

## Interpretation Rule

- `missing_candidate`: reranking cannot fix these queries because relevant documents are absent from the analyzed candidate depth.
- `partial_candidate_support`: at least one relevant document is present, but not all required support appears by the analyzed candidate depth.
- `candidate_ranked_low`: all required support appears by candidate depth, but not by the target cutoff; this is the clearest reranker-ready bucket.
- `success`: all known support documents appear by the target cutoff.

## Current Limitation

This first-pass report uses the available top-10 TREC runs. It can identify top-10 success and missing/partial support at top-10, but it cannot yet prove candidate@50 or candidate@100 reranker readiness. A deeper run should be generated before making a final reranker decision.
