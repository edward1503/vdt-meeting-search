# Reranker vs RRF Ablation

Scope: 200-query pilot ablation. This is not a paper-comparable claim; small metric deltas need a larger split before final conclusions.

## Artifacts

- RRF benchmark: `evaluation\results\hotpotqa_full\reranker_ablation\tv_hybrid_200.json`
- Reranker benchmark: `evaluation\results\hotpotqa_full\reranker_ablation\tv_hybrid_rerank_200.json`
- Candidate diagnostics: `evaluation\results\hotpotqa_full\reranker_ablation\diagnostics_200.json`
- RRF TREC run: `evaluation\runs\hotpotqa_full\reranker_ablation\tv_hybrid_beir_hotpotqa_dev_top10.trec`
- Reranker TREC run: `evaluation\runs\hotpotqa_full\reranker_ablation\tv_hybrid_rerank_beir_hotpotqa_dev_top10.trec`
- Reranker model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Candidate budget: 100

## Metric Summary

| Method | Metric cutoff | Full support | Recall | MRR | nDCG | p50 latency ms | p95 latency ms | QPS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tv_hybrid | 10 | 0.5450 | 0.7500 | 0.8691 | 0.7291 | 631.8788 | 2061.4370 | 0.9043 |
| tv_hybrid_rerank | 10 | 0.5450 | 0.7550 | 0.9268 | 0.7464 | 963.9905 | 1304.2816 | 0.8774 |

## Paired Full-Support Movement

- Evaluated paired queries: 200
- RRF-only successes: 14
- Reranker-only successes: 14
- Both success: 95
- Both fail: 77
- net reranker wins: 0

## Candidate Diagnostics

- Candidate recall@depth: 0.8325
- Missing candidate: 3
- Partial candidate support: 61
- Candidate ranked low: 27
- Success at target cutoff: 109

## Recommendation Rule

Continue reranker work only if the reranker creates meaningful paired wins over RRF and the latency increase is acceptable for the target demo/research use case. If candidate diagnostics show many missing candidates, improve candidate generation before investing more in reranking.
