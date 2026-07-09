# Reranker vs RRF Ablation Design

## Purpose

Evaluate whether a reranker improves HotpotQA full-corpus retrieval quality over the current `tv_hybrid` RRF baseline, while separating ranking failures from candidate-generation failures.

The work is benchmark-only. It must not change the default API method, dashboard behavior, Redis cache keys, Elasticsearch mappings, or prepared corpus/index artifacts.

## Current Context

The current HotpotQA default is `tv_hybrid`: BM25 candidates and TurboVec dense candidates fused with Reciprocal Rank Fusion. Prior Sprint 5 diagnostics showed that top-10 runs cannot prove reranker readiness because they do not expose enough candidate depth. The next proof needs deeper candidate runs and a direct reranker comparison.

Local runtime was checked before this design:

- FastAPI health on `http://localhost:8001/health` returned OK.
- Elasticsearch on `localhost:9200` returned cluster information.
- The embedding service on `localhost:8010/embed` returned an embedding.
- Docker containers for frontend, API, Redis, and Elasticsearch were running.

## Scope

In scope:

- Add a benchmark-only reranker path named `tv_hybrid_rerank`.
- Generate deeper RRF candidate artifacts for diagnostics.
- Compare `tv_hybrid` and `tv_hybrid_rerank` on the same query budgets.
- Produce a concise ablation report with quality and latency metrics.
- Keep tests focused on dispatch, candidate construction, reranker ordering, and report generation.

Out of scope:

- Making reranker the runtime default.
- Frontend controls for reranker.
- Training or fine-tuning a reranker.
- Changing Elasticsearch or TurboVec indexes.
- Running full BEIR test-split claims unless explicitly requested after the pilot.

## Query Budget

Use staged budgets so the system can fail fast before expensive reranking:

1. Smoke: 5 queries, used to validate command wiring, output files, and report shape.
2. Pilot: 50 queries, used to estimate quality and latency.
3. Decision pilot: 200 queries, aligned with existing project-progress HotpotQA runs.

Do not start a larger run until the prior budget completes and writes valid JSON/TREC artifacts.

## Runtime Preflight

Before any benchmark run, check:

- `GET http://localhost:8001/health`
- `GET http://localhost:9200`
- `POST http://localhost:8010/embed`
- `docker ps` for `vdt-hotpotqa-api`, `vdt-hotpotqa-elasticsearch`, and `vdt-hotpotqa-redis`

If dense runtime is unavailable, skip the reranker benchmark cleanly and record the blocker in the report. Unit tests and offline report-generation tests should still run.

## Architecture

### Candidate Diagnostics

Run `tv_hybrid` with top-100 output depth and feed the TREC run into `scripts/ranking_diagnostics.py`.

The diagnostics answer:

- How often all support documents are present by candidate depth.
- How often failures are `missing_candidate`, `partial_candidate_support`, or `candidate_ranked_low`.
- Whether reranking is theoretically capable of improving top-10 results.

### Reranker Method

Add a benchmark-only method `tv_hybrid_rerank` to `src/evaluation/benchmark_es.py` and the TurboVec retriever boundary.

For each query:

1. Retrieve BM25 candidates and TurboVec dense candidates using the same `candidate_k` inputs as `tv_hybrid`.
2. Fuse or dedupe the candidate pool without truncating to top-10.
3. Score `(query, title + text)` pairs with a local reranker model.
4. Sort by reranker score and return top-k results.

The reranker should be lazy-loaded so normal `tv_hybrid` and API startup do not pay the model-loading cost.

Expose the reranker model through a `--reranker-model` CLI option and record the selected model in benchmark config and the report. Use `cross-encoder/ms-marco-MiniLM-L-6-v2` only as the default smoke-test model because it is small and easy to run locally; treat it as a generic cross-encoder baseline, not as a HotpotQA-optimized reranker. Pilot and decision runs may override this with a stronger reranker model when the local environment can load it. If the environment lacks the dependency or model, the benchmark should fail with a clear message rather than silently falling back to RRF.

### Report

Create the report at `docs/sprint5/reranker-rrf-ablation-report.md`. The report should include:

- Commands used for smoke, pilot, and decision pilot.
- Artifact paths for JSON and TREC outputs.
- The reranker model used for each run, including whether it is a generic baseline or a stronger override.
- Metrics table for `tv_hybrid` vs `tv_hybrid_rerank`: `full_support_recall@10`, `recall@10`, `mrr@10`, `ndcg@10`, latency p50/p95, and QPS.
- Candidate diagnostics summary: candidate recall, missing candidate count, partial support count, candidate-ranked-low count.
- Recommendation: keep RRF, tune candidate generation, or continue reranker work.

## Data Flow

```text
HotpotQA queries/qrels
  -> tv_hybrid deep candidate run
  -> ranking diagnostics report
  -> tv_hybrid_rerank benchmark run
  -> metrics + TREC outputs
  -> ablation report
```

## Error Handling

- Missing API, Elasticsearch, embedding service, or Docker runtime: stop benchmark execution and write a report note if report generation has started.
- Missing reranker dependency/model: raise a clear configuration error for `tv_hybrid_rerank`.
- Empty candidate pool: return an empty result list for that query and preserve metrics behavior.
- Partial artifacts from failed runs: do not claim ablation results; record the failed command and failure point.

## Testing

Unit tests:

- `classify_method` accepts `tv_hybrid_rerank`.
- Benchmark dispatch calls the reranker path with `candidate_k`, `rrf_k`, and `top_k`.
- Candidate dedupe preserves stable document identity and fields.
- A fake reranker can reorder candidates deterministically.
- Report helper can summarize two benchmark result files and one diagnostics JSON.

Integration or smoke tests:

- Run existing benchmark unit tests.
- Run a 5-query smoke benchmark if runtime preflight passes.
- Run ranking diagnostics against the smoke/deep TREC run.

## Success Criteria

The ablation is successful when:

- The repo can generate candidate diagnostics at a deeper depth than top-10.
- `tv_hybrid_rerank` can be benchmarked without changing runtime defaults.
- The report compares reranker and RRF on at least the smoke budget, and ideally the 50-query pilot.
- The report states whether the evidence justifies a 200-query decision pilot or larger run.
