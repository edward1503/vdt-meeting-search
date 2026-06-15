# 0006 Sprint 3 Dense Backend

Date: 2026-06-14

## Status

Accepted

## Context

Sprint 3 needs full-scale dense retrieval over 5,233,329 HotpotQA documents on a local Windows/Python 3.12 environment with about 16 GB RAM. The existing Elasticsearch dense-vector path is useful for nano and legacy experiments, but full-scale Elasticsearch vector indexing has high RAM and HNSW overhead risk.

## Decision

Use Elasticsearch as the BM25 lexical index and document store. Use TurboVec `IdMapIndex` with 4-bit quantization as the full-scale dense retrieval backend. Fuse Elasticsearch BM25 and TurboVec dense rankings in the application layer with Reciprocal Rank Fusion. Preserve the existing Elasticsearch dense/hybrid path for nano and legacy experiments.

## Alternatives Considered

1. Elasticsearch `dense_vector` for full corpus. Rejected for Sprint 3 because memory overhead is too risky on the target local hardware.
2. BM25-only full-scale retrieval. Rejected as the final target because Sprint 3 explicitly needs dense and hybrid comparison.
3. 2-bit TurboVec quantization first. Rejected for the initial build because BGE-small has 384 dimensions and 4-bit is the safer quality baseline.

## Consequences

Positive:

- Keeps Elasticsearch indexing simpler for the full corpus.
- Makes dense index build/load independent from Elasticsearch.
- Allows BM25, dense, and hybrid benchmarks to be compared cleanly.

Tradeoffs:

- Requires stable `numeric_id` propagation across staging, embeddings, TurboVec, and Elasticsearch hydration.
- Adds a second retrieval runtime and artifact lifecycle.
- API startup must handle optional TurboVec index availability without breaking BM25 fallback.

## Follow-Up

- Implement numeric-id validation before full artifact builds.
- Record benchmark evidence before making `tv_hybrid` the default API method.
