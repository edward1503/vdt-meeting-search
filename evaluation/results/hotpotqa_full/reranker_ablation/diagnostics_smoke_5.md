# Sprint 5 Ranking Diagnostics

This report analyzes existing ranked runs to separate candidate-generation failures from ranking failures.

Target cutoff: top-10
Candidate depth: top-100
Queries: 5

## Method Summary

| Method | Full support@k | Any support@k | Candidate recall@depth | Missing candidate | Partial candidate support | Candidate ranked low | Success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tv_hybrid | 0.2000 | 1.0000 | 0.6000 | 0 | 4 | 0 | 1 |

## Interpretation Rule

- `missing_candidate`: reranking cannot fix these queries because relevant documents are absent from the analyzed candidate depth.
- `partial_candidate_support`: at least one relevant document is present, but not all required support appears by the analyzed candidate depth.
- `candidate_ranked_low`: all required support appears by candidate depth, but not by the target cutoff; this is the clearest reranker-ready bucket.
- `success`: all known support documents appear by the target cutoff.

## Current Limitation

This first-pass report uses the available top-10 TREC runs. It can identify top-10 success and missing/partial support at top-10, but it cannot yet prove candidate@50 or candidate@100 reranker readiness. A deeper run should be generated before making a final reranker decision.
