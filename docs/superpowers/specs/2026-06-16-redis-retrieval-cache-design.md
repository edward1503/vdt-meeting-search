# Redis Retrieval Cache Design

Date: 2026-06-16
Story: US-S3-013
Lane: normal

## Goal

Make Redis caching safer and more useful for the existing FastAPI retrieval path without changing ranking semantics, frontend contracts, or the current Docker development topology.

## Current State

The `/search` endpoint in `src/api/main.py` already caches complete search responses in Redis when `REDIS_URL` is configured. The key currently scopes by Elasticsearch index, query string, method, and top-k.

TurboVec is local to the API process. `tv_dense`, `tv_hybrid`, and `tv_filtered_hybrid` load and query a local `.tvim` artifact through `TurboVecHybridRetriever`. Elasticsearch usually runs in Docker and provides BM25 retrieval, document hydration, and candidate allowlists. The local embedding HTTP service is separate from TurboVec and is used when `EMBEDDING_SERVICE_URL` is configured.

## Design

### Cache Boundaries

Caching should happen at three boundaries, in this order:

1. Final response cache for repeated identical `/search` requests.
2. Embedding cache for repeated dense/hybrid query encoding.
3. BM25 candidate cache for `tv_filtered_hybrid` allowlist construction.

The final response cache remains the broadest and safest fast path. Embedding cache is shared by Elasticsearch dense retrieval and TurboVec dense retrieval. BM25 candidate cache is limited to TurboVec filtered hybrid because that method pays a BM25 cost before dense local search.

### Cache Key Rules

All cache keys should use a normalized query string:

- Trim leading and trailing whitespace.
- Collapse internal whitespace to one space.
- Lowercase for cache identity.

Final search response keys must include every ranking-affecting value available at the API boundary:

- cache namespace/version
- Elasticsearch index
- method
- normalized query
- top-k
- embedding model
- Elasticsearch candidate count for Elasticsearch dense/hybrid methods
- TurboVec artifact path or configured artifact identifier for TurboVec methods
- `HYBRID_BM25_K`, `HYBRID_DENSE_K`, and `RRF_K` for TurboVec hybrid methods

Embedding keys must include:

- cache namespace/version
- embedding model
- normalized query
- embedding dimension when known

BM25 candidate keys must include:

- cache namespace/version
- Elasticsearch index
- normalized query
- BM25 candidate count

### Failure Behavior

Redis remains optional. Read failures become cache misses. Write failures are ignored after debug logging. A cache bug must not block search, history recording, or benchmark flows.

### API Compatibility

The `/search` request and response contract stays compatible. The existing `cache_hit` field continues to describe final response cache hits. Partial cache hits should be visible through `latency_breakdown_ms` only if they can be represented without breaking existing consumers, for example `embedding_cache: 1.0` or `bm25_cache: 1.0`.

### Validation

Unit tests should cover deterministic keys, parameter invalidation, embedding cache hit/miss behavior, BM25 candidate cache hit/miss behavior, and Redis failure fallback. Existing API integration tests should keep proving that TurboVec routes through `get_tv_retriever()` and returns `latency_breakdown_ms`.

Performance claims require measured before/after timings using repeated queries. Without a fresh benchmark or smoke timing run, the implementation should claim correctness and cache coverage only.

## Non-Goals

- No frontend redesign.
- No ranking algorithm change.
- No Redis cluster, persistence, or deployment change.
- No replacement of Elasticsearch or TurboVec.
- No new database schema.
