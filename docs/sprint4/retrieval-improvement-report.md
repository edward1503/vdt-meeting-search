# Sprint 4 Retrieval Improvement Report

## Scope

This report covers `US-S4-009`: evidence-chain metrics and the benchmark-only
`tv_two_hop_bridge_rrf` retrieval method. Redis cache hardening, dashboard
defaults, LLM rewriting, cross-encoder reranking, MDR training, and Beam
Retrieval training are out of scope.

## Implemented Slice

- Added optional chain metadata to `SearchHit`: `chain_rank` and
  `chain_doc_ids`.
- Extended evaluation metrics to report `full_support_recall@2`,
  `full_support_recall@5`, and `full_support_recall@10` for top-10 runs.
- Added chain-aware metrics when retrieval output contains chain metadata:
  `chain_recall@1`, `chain_recall@5`, and `chain_mrr`.
- Added `TurboVecHybridRetriever.search_two_hop_bridge_rrf` as a benchmark-only
  two-hop method.
- Registered `tv_two_hop_bridge_rrf` in `src.evaluation.benchmark_es` with
  `beam_size` and `max_bridge_terms` hyperparameters.

## Method

`tv_two_hop_bridge_rrf` runs:

```text
question
  -> tv_hybrid hop 1
  -> top beam first-hop documents
  -> bridge query = question + first-hop title + selected first-hop terms
  -> tv_hybrid hop 2 per bridge document
  -> candidate chains (p1, p2)
  -> lightweight RRF-style chain score
  -> flattened ranked documents with chain metadata
```

## Hyperparameters

- `first_hop_k` / config alias `hop1_top_k`
- `second_hop_k` / config alias `hop2_top_k`
- `beam_size`
- `max_bridge_terms`
- `candidate_k`
- `rrf_k`

## Unit Verification

Command:

```powershell
python -m pytest tests/test_metrics.py tests/test_turbovec_retriever.py tests/test_benchmark_es.py -q
```

Result:

```text
19 passed in 0.31s
```

Coverage:

- Multi-cutoff full-support metrics.
- Chain recall and chain MRR metrics.
- Bridge query construction.
- Two-hop Bridge-RRF chain flattening and metadata.
- Benchmark dispatcher and config serialization for `tv_two_hop_bridge_rrf`.

## Integration Smoke Status

Runtime preflight passed before benchmark execution:

```text
Elasticsearch http://localhost:9200: ready, cluster green
hotpotqa_full_bm25_current count: 5,233,329
Embedding service http://localhost:8010/embed: ready, dim=384
TurboVec artifact: artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim, 1,067,602,206 bytes
```

50-query smoke command:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_current --methods tv_hybrid,tv_two_hop_bridge_rrf --top-k 10 --max-queries 50 --candidate-k 50 --num-candidates 50 --rrf-k 30 --first-hop-k 3 --second-hop-k 5 --beam-size 2 --max-bridge-terms 6 --output evaluation/results/hotpotqa_full/bridge_rrf/bridge_rrf_smoke_50.json --run-dir evaluation/runs/hotpotqa_full/bridge_rrf
```

50-query smoke result:

| Method | full_support@2 | full_support@5 | full_support@10 | nDCG@10 | p95 ms | QPS | Chain recall@5 | Chain MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.300 | 0.440 | 0.460 | 0.6659 | 4215.9710 | 0.3707 | n/a | n/a |
| `tv_two_hop_bridge_rrf` | 0.120 | 0.420 | 0.480 | 0.6260 | 3761.5026 | 0.3962 | 0.320 | 0.2083 |

50-query artifact:

```text
evaluation/results/hotpotqa_full/bridge_rrf/bridge_rrf_smoke_50.json
```

## Sprint 4 Pilot

200-query pilot command:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_current --methods tv_hybrid,tv_two_hop_bridge_rrf --top-k 10 --max-queries 200 --candidate-k 50 --num-candidates 50 --rrf-k 30 --first-hop-k 3 --second-hop-k 5 --beam-size 2 --max-bridge-terms 6 --output evaluation/results/hotpotqa_full/bridge_rrf/bridge_rrf_pilot_200.json --run-dir evaluation/runs/hotpotqa_full/bridge_rrf
```

200-query pilot result:

| Method | full_support@2 | full_support@5 | full_support@10 | Recall@10 | MRR@10 | nDCG@10 | p95 ms | QPS | Chain recall@1 | Chain recall@5 | Chain MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `tv_hybrid` | 0.330 | 0.475 | 0.535 | 0.740 | 0.8608 | 0.7214 | 2080.4528 | 0.8313 | n/a | n/a | n/a |
| `tv_two_hop_bridge_rrf` | 0.170 | 0.450 | 0.520 | 0.735 | 0.8468 | 0.6916 | 2832.7420 | 0.5281 | 0.170 | 0.390 | 0.2589 |

Pilot artifacts:

```text
evaluation/results/hotpotqa_full/bridge_rrf/bridge_rrf_pilot_200.json
evaluation/runs/hotpotqa_full/bridge_rrf/tv_hybrid_beir_hotpotqa_dev_top10.trec
evaluation/runs/hotpotqa_full/bridge_rrf/tv_two_hop_bridge_rrf_beir_hotpotqa_dev_top10.trec
```

## Existing Elasticsearch Iterative Methods

The existing `es_iterative_hybrid`, `es_iterative_title`,
`es_iterative_sentence`, and `es_iterative_fast` methods are ruled out for the
active full-corpus Sprint 4 benchmark because they call the legacy Elasticsearch
hybrid/dense path. The active full-corpus alias `hotpotqa_full_bm25_current`
has fields `content`, `doc_id`, `numeric_id`, `text`, `title`, and `url`; it
does not contain the `embedding` dense vector field required by the ES dense
path. The Sprint 4 comparison therefore uses `tv_hybrid` as the full-corpus
runtime baseline.

## Decision Rule

Do not change the dashboard or default method unless `tv_two_hop_bridge_rrf`
improves `full_support_recall@10` by at least `+0.05` over `tv_hybrid` while
keeping p95 latency within `2.5x` of `tv_hybrid` on the Sprint 4 pilot.

## Current Status

`US-S4-009` is implemented for the benchmark path. The current Bridge-RRF
configuration did not meet the Sprint 4 success rule: `full_support_recall@10`
was 0.520 versus 0.535 for `tv_hybrid` on the 200-query pilot, so it does not
improve by the required `+0.05`. p95 latency stayed within the `2.5x` guardrail
at about `1.36x`, but quality did not justify changing the default. Keep
`tv_hybrid` as the dashboard/default method.
