# Redis Retrieval Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden Redis cache correctness and add reusable partial caches for embeddings and `tv_filtered_hybrid` BM25 candidates.

**Architecture:** Keep Redis as an optional infrastructure optimization. Add deterministic cache key builders and a small JSON cache adapter, then inject that adapter into the existing FastAPI and retriever construction paths. Ranking semantics stay owned by Elasticsearch, TurboVec, and RRF fusion; cache layers only skip repeated work when the retrieval signature matches.

**Tech Stack:** Python 3, FastAPI, Redis Python client, Elasticsearch retriever, TurboVec retriever, pytest.

---

## File Structure

- Create `src/retrieval/cache_keys.py`: pure functions for query normalization and cache key construction.
- Create `src/retrieval/cache_store.py`: small Redis/Null JSON cache adapters with safe failure behavior.
- Modify `src/core/config.py`: add TTL settings for embedding and BM25 candidate caches.
- Modify `src/api/main.py`: use signature-aware final response cache keys and pass cache adapters into retrievers.
- Modify `src/retrieval/elasticsearch_retriever.py`: support optional embedding cache.
- Modify `src/retrieval/turbovec_retriever.py`: support optional embedding cache and BM25 candidate cache.
- Add `tests/test_cache_keys.py`: deterministic key and invalidation coverage.
- Extend `tests/test_api_cache.py`: API-level cache key and Redis fallback coverage.
- Extend `tests/test_elasticsearch_retriever.py`: Elasticsearch embedding cache coverage.
- Extend `tests/test_turbovec_retriever.py`: TurboVec embedding and BM25 candidate cache coverage.
- Update `docs/stories/epics/E03-sprint3-turbovec/US-S3-013-redis-retrieval-cache.md`: evidence after validation.

## Task 1: Pure Cache Key Builders

**Files:**
- Create: `src/retrieval/cache_keys.py`
- Create: `tests/test_cache_keys.py`

- [ ] **Step 1: Write failing tests for normalized, signature-aware keys**

Create `tests/test_cache_keys.py`:

```python
from src.retrieval.cache_keys import (
    build_bm25_cache_key,
    build_embedding_cache_key,
    build_search_response_cache_key,
    normalize_query_for_cache,
)


def test_normalize_query_for_cache_collapses_space_and_lowercases() -> None:
    assert normalize_query_for_cache("  What   Is\nHotPotQA?  ") == "what is hotpotqa?"


def test_search_response_key_changes_when_tuning_changes() -> None:
    base = build_search_response_cache_key(
        index="hotpotqa_full_current",
        query="  Who connects Alpha and Beta? ",
        method="tv_hybrid",
        top_k=10,
        signature={"bm25_k": 50, "dense_k": 100, "rrf_k": 30, "tv_index": "a.tvim"},
    )
    changed = build_search_response_cache_key(
        index="hotpotqa_full_current",
        query="who connects alpha and beta?",
        method="tv_hybrid",
        top_k=10,
        signature={"bm25_k": 100, "dense_k": 100, "rrf_k": 30, "tv_index": "a.tvim"},
    )

    assert base.startswith("search:v2:")
    assert changed.startswith("search:v2:")
    assert base != changed


def test_embedding_key_is_scoped_by_model_and_dimension() -> None:
    key_a = build_embedding_cache_key(
        query="Who connects Alpha and Beta?",
        model_name="BAAI/bge-small-en-v1.5",
        dims=384,
    )
    key_b = build_embedding_cache_key(
        query="Who connects Alpha and Beta?",
        model_name="different-model",
        dims=384,
    )

    assert key_a.startswith("embedding:v1:")
    assert key_a != key_b


def test_bm25_key_is_scoped_by_index_and_candidate_count() -> None:
    key_a = build_bm25_cache_key(index="hotpotqa_full_current", query="Alpha", bm25_k=50)
    key_b = build_bm25_cache_key(index="hotpotqa_full_current", query="Alpha", bm25_k=100)

    assert key_a.startswith("bm25:v1:")
    assert key_a != key_b
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `python -m pytest tests/test_cache_keys.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.retrieval.cache_keys'`.

- [ ] **Step 3: Implement cache key helpers**

Create `src/retrieval/cache_keys.py`:

```python
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

WHITESPACE_RE = re.compile(r"\s+")


def normalize_query_for_cache(query: str) -> str:
    return WHITESPACE_RE.sub(" ", query.strip()).lower()


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_search_response_cache_key(
    *,
    index: str,
    query: str,
    method: str,
    top_k: int,
    signature: dict[str, Any],
) -> str:
    return "search:v2:" + _digest(
        {
            "index": index,
            "method": method,
            "query": normalize_query_for_cache(query),
            "top_k": int(top_k),
            "signature": signature,
        }
    )


def build_embedding_cache_key(*, query: str, model_name: str, dims: int | None = None) -> str:
    return "embedding:v1:" + _digest(
        {
            "query": normalize_query_for_cache(query),
            "model_name": model_name,
            "dims": dims,
        }
    )


def build_bm25_cache_key(*, index: str, query: str, bm25_k: int) -> str:
    return "bm25:v1:" + _digest(
        {
            "index": index,
            "query": normalize_query_for_cache(query),
            "bm25_k": int(bm25_k),
        }
    )
```

- [ ] **Step 4: Run the key tests and verify they pass**

Run: `python -m pytest tests/test_cache_keys.py -q`
Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/retrieval/cache_keys.py tests/test_cache_keys.py
git commit -m "feat: add retrieval cache key helpers"
```

## Task 2: Safe JSON Cache Adapter

**Files:**
- Create: `src/retrieval/cache_store.py`
- Modify: `tests/test_api_cache.py`

- [ ] **Step 1: Write failing tests for safe cache behavior**

Append to `tests/test_api_cache.py`:

```python
from src.retrieval.cache_store import NullJsonCache, RedisJsonCache


def test_null_json_cache_always_misses() -> None:
    cache = NullJsonCache()

    assert cache.get_json("key") is None
    cache.set_json("key", {"ok": True}, ttl_seconds=10)
    assert cache.get_json("key") is None


def test_redis_json_cache_ignores_client_failures() -> None:
    class BrokenRedis:
        def get(self, key):
            raise RuntimeError("redis down")

        def setex(self, key, ttl, value):
            raise RuntimeError("redis down")

    cache = RedisJsonCache(BrokenRedis())

    assert cache.get_json("key") is None
    cache.set_json("key", {"ok": True}, ttl_seconds=10)
```

- [ ] **Step 2: Run targeted tests and verify failure**

Run: `python -m pytest tests/test_api_cache.py::test_null_json_cache_always_misses tests/test_api_cache.py::test_redis_json_cache_ignores_client_failures -q`
Expected: FAIL with import error for `src.retrieval.cache_store`.

- [ ] **Step 3: Implement safe JSON cache adapters**

Create `src/retrieval/cache_store.py`:

```python
from __future__ import annotations

import json
from typing import Any, Protocol


class JsonCache(Protocol):
    def get_json(self, key: str) -> Any | None: ...

    def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None: ...


class NullJsonCache:
    def get_json(self, key: str) -> None:
        return None

    def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        return None


class RedisJsonCache:
    def __init__(self, client: Any) -> None:
        self.client = client

    def get_json(self, key: str) -> Any | None:
        try:
            raw = self.client.get(key)
            if not raw:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        try:
            self.client.setex(key, int(ttl_seconds), json.dumps(payload))
        except Exception:
            return
```

- [ ] **Step 4: Run targeted tests and verify pass**

Run: `python -m pytest tests/test_api_cache.py::test_null_json_cache_always_misses tests/test_api_cache.py::test_redis_json_cache_ignores_client_failures -q`
Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/retrieval/cache_store.py tests/test_api_cache.py
git commit -m "feat: add safe redis json cache adapter"
```

## Task 3: Signature-Aware Final Response Cache

**Files:**
- Modify: `src/core/config.py`
- Modify: `src/api/main.py`
- Modify: `tests/test_api_cache.py`

- [ ] **Step 1: Update tests for final response cache invalidation**

Replace the existing `test_build_search_cache_key_is_stable_and_scoped` in `tests/test_api_cache.py` with:

```python
from src.api.main import build_search_cache_key


def test_build_search_cache_key_is_stable_normalized_and_signature_scoped() -> None:
    key_a = build_search_cache_key(
        index="hotpotqa_nano_current",
        query="  What occupations do   both Ian Hunter and Rob Thomas have? ",
        method="tv_hybrid",
        top_k=10,
        signature={"bm25_k": 50, "dense_k": 100, "rrf_k": 30},
    )
    key_b = build_search_cache_key(
        index="hotpotqa_nano_current",
        query="what occupations do both ian hunter and rob thomas have?",
        method="tv_hybrid",
        top_k=10,
        signature={"bm25_k": 50, "dense_k": 100, "rrf_k": 30},
    )
    key_c = build_search_cache_key(
        index="hotpotqa_nano_current",
        query="what occupations do both ian hunter and rob thomas have?",
        method="tv_hybrid",
        top_k=10,
        signature={"bm25_k": 100, "dense_k": 100, "rrf_k": 30},
    )

    assert key_a == key_b
    assert key_a.startswith("search:v2:")
    assert key_a != key_c
```

- [ ] **Step 2: Run API cache tests and verify failure**

Run: `python -m pytest tests/test_api_cache.py -q`
Expected: FAIL because `build_search_cache_key` does not accept `signature` yet.

- [ ] **Step 3: Add cache TTL settings**

Modify `src/core/config.py` inside `Settings`:

```python
    embedding_cache_ttl_seconds: int = int(os.getenv("EMBEDDING_CACHE_TTL_SECONDS", "86400"))
    bm25_cache_ttl_seconds: int = int(os.getenv("BM25_CACHE_TTL_SECONDS", "3600"))
```

- [ ] **Step 4: Wire signature-aware search keys in `src/api/main.py`**

Add imports:

```python
from src.retrieval.cache_keys import build_search_response_cache_key
from src.retrieval.cache_store import NullJsonCache, RedisJsonCache
```

Replace `build_search_cache_key` with:

```python
def build_search_cache_key(*, index: str, query: str, method: str, top_k: int, signature: dict[str, Any]) -> str:
    return build_search_response_cache_key(
        index=index,
        query=query,
        method=method,
        top_k=top_k,
        signature=signature,
    )
```

Add this helper below `get_redis_client()`:

```python
def get_json_cache() -> Any:
    client = get_redis_client()
    if client is None:
        return NullJsonCache()
    return RedisJsonCache(client)
```

Add this helper near the method constants:

```python
def build_retrieval_signature(method: str) -> dict[str, Any]:
    signature: dict[str, Any] = {
        "embedding_model": settings.embedding_model,
        "elasticsearch_num_candidates": settings.elasticsearch_num_candidates,
    }
    if method in TV_METHODS:
        signature.update(
            {
                "turbovec_index_path": str(settings.turbovec_index_path),
                "turbovec_bit_width": settings.turbovec_bit_width,
                "turbovec_dim": settings.turbovec_dim,
                "hybrid_bm25_k": settings.hybrid_bm25_k,
                "hybrid_dense_k": settings.hybrid_dense_k,
                "rrf_k": settings.rrf_k,
            }
        )
    return signature
```

In `search()`, update cache key construction:

```python
    cache_key = build_search_cache_key(
        index=settings.elasticsearch_index,
        query=request.query,
        method=method,
        top_k=request.top_k,
        signature=build_retrieval_signature(method),
    )
```

- [ ] **Step 5: Run focused API tests**

Run: `python -m pytest tests/test_api_cache.py tests/test_api_es_config.py -q`
Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/core/config.py src/api/main.py tests/test_api_cache.py
git commit -m "feat: scope search cache by retrieval signature"
```

## Task 4: Embedding Cache for ES and TurboVec Dense Paths

**Files:**
- Modify: `src/retrieval/elasticsearch_retriever.py`
- Modify: `src/retrieval/turbovec_retriever.py`
- Modify: `src/api/main.py`
- Modify: `tests/test_elasticsearch_retriever.py`
- Modify: `tests/test_turbovec_retriever.py`

- [ ] **Step 1: Add failing Elasticsearch embedding cache test**

Append to `tests/test_elasticsearch_retriever.py`:

```python
def test_elasticsearch_retriever_reuses_cached_embedding() -> None:
    from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

    class FakeCache:
        def __init__(self):
            self.values = {}
            self.writes = []

        def get_json(self, key):
            return self.values.get(key)

        def set_json(self, key, payload, ttl_seconds):
            self.values[key] = payload
            self.writes.append((key, payload, ttl_seconds))

    class FakeModel:
        calls = 0

        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            self.calls += 1
            return [[0.1, 0.2]]

    cache = FakeCache()
    model = FakeModel()
    retriever = ElasticsearchRetriever(
        es=None,
        index="idx",
        model_name="model",
        model=model,
        embedding_cache=cache,
        embedding_cache_ttl_seconds=60,
    )

    assert retriever._embed_query("Alpha") == [0.1, 0.2]
    assert retriever._embed_query(" alpha ") == [0.1, 0.2]
    assert model.calls == 1
    assert cache.writes[0][2] == 60
```

- [ ] **Step 2: Add failing TurboVec embedding cache test**

Append to `tests/test_turbovec_retriever.py`:

```python
def test_turbovec_retriever_reuses_cached_embedding() -> None:
    class FakeCache:
        def __init__(self):
            self.values = {}

        def get_json(self, key):
            return self.values.get(key)

        def set_json(self, key, payload, ttl_seconds):
            self.values[key] = payload

    class FakeEmbedder:
        calls = 0

        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            self.calls += 1
            return np.array([[1.0, 0.0]], dtype=np.float32)

    embedder = FakeEmbedder()
    retriever = TurboVecHybridRetriever(
        bm25_retriever=None,
        tv_index=None,
        embedder=embedder,
        docstore=None,
        model_name="model",
        embedding_cache=FakeCache(),
        embedding_cache_ttl_seconds=60,
        embedding_dims=2,
    )

    assert retriever._embed_query("Alpha").tolist() == [[1.0, 0.0]]
    assert retriever._embed_query(" alpha ").tolist() == [[1.0, 0.0]]
    assert embedder.calls == 1
```

- [ ] **Step 3: Run targeted tests and verify failure**

Run: `python -m pytest tests/test_elasticsearch_retriever.py::test_elasticsearch_retriever_reuses_cached_embedding tests/test_turbovec_retriever.py::test_turbovec_retriever_reuses_cached_embedding -q`
Expected: FAIL because retriever constructors do not accept cache arguments.

- [ ] **Step 4: Implement ES embedding cache**

In `src/retrieval/elasticsearch_retriever.py`, import the key builder:

```python
from src.retrieval.cache_keys import build_embedding_cache_key
```

Extend `ElasticsearchRetriever.__init__`:

```python
        embedding_cache: Any | None = None,
        embedding_cache_ttl_seconds: int = 86400,
```

Set fields:

```python
        self.embedding_cache = embedding_cache
        self.embedding_cache_ttl_seconds = embedding_cache_ttl_seconds
```

Replace `_embed_query` with:

```python
    def _embed_query(self, query: str) -> list[float]:
        cache_key = build_embedding_cache_key(query=query, model_name=self.model_name)
        if self.embedding_cache is not None:
            cached = self.embedding_cache.get_json(cache_key)
            if isinstance(cached, list):
                return [float(value) for value in cached]

        if self.embedding_service_url:
            vector = self._embed_query_remote(query)
        else:
            vector = _vector_to_list(self._model().encode([query], normalize_embeddings=True, convert_to_numpy=True)[0])

        if self.embedding_cache is not None:
            self.embedding_cache.set_json(cache_key, vector, self.embedding_cache_ttl_seconds)
        return vector
```

- [ ] **Step 5: Implement TurboVec embedding cache**

In `src/retrieval/turbovec_retriever.py`, import the key builder:

```python
from src.retrieval.cache_keys import build_embedding_cache_key
```

Extend `TurboVecHybridRetriever.__init__`:

```python
    def __init__(
        self,
        bm25_retriever: Any,
        tv_index: Any,
        embedder: Any,
        docstore: Any,
        model_name: str = "",
        embedding_cache: Any | None = None,
        embedding_cache_ttl_seconds: int = 86400,
        embedding_dims: int | None = None,
    ) -> None:
```

Set fields:

```python
        self.model_name = model_name
        self.embedding_cache = embedding_cache
        self.embedding_cache_ttl_seconds = embedding_cache_ttl_seconds
        self.embedding_dims = embedding_dims
```

Update `from_paths()` to pass the model name and dimensions:

```python
            model_name=model_name,
            embedding_dims=384,
```

Replace `_embed_query` with:

```python
    def _embed_query(self, query: str) -> np.ndarray:
        cache_key = build_embedding_cache_key(query=query, model_name=self.model_name, dims=self.embedding_dims)
        if self.embedding_cache is not None:
            cached = self.embedding_cache.get_json(cache_key)
            if isinstance(cached, list):
                return np.asarray([cached], dtype=np.float32)

        vector = self.embedder.encode([query], normalize_embeddings=True, convert_to_numpy=True)
        vector = np.asarray(vector, dtype=np.float32)
        if self.embedding_cache is not None:
            self.embedding_cache.set_json(cache_key, [float(value) for value in vector[0].tolist()], self.embedding_cache_ttl_seconds)
        return vector
```

- [ ] **Step 6: Wire cache into API retriever factories**

In `src/api/main.py`, update `get_es_retriever()`:

```python
        embedding_cache=get_json_cache(),
        embedding_cache_ttl_seconds=settings.embedding_cache_ttl_seconds,
```

Update `get_tv_retriever()` call to `TurboVecHybridRetriever.from_paths()`:

```python
        embedding_cache=get_json_cache(),
        embedding_cache_ttl_seconds=settings.embedding_cache_ttl_seconds,
        embedding_dims=settings.turbovec_dim,
```

Update `from_paths()` signature to accept those arguments and pass them into the constructor.

- [ ] **Step 7: Run focused retriever tests**

Run: `python -m pytest tests/test_elasticsearch_retriever.py tests/test_turbovec_retriever.py -q`
Expected: PASS.

- [ ] **Step 8: Commit Task 4**

```bash
git add src/api/main.py src/retrieval/elasticsearch_retriever.py src/retrieval/turbovec_retriever.py tests/test_elasticsearch_retriever.py tests/test_turbovec_retriever.py
git commit -m "feat: cache dense query embeddings"
```

## Task 5: BM25 Candidate Cache for `tv_filtered_hybrid`

**Files:**
- Modify: `src/retrieval/turbovec_retriever.py`
- Modify: `src/api/main.py`
- Modify: `tests/test_turbovec_retriever.py`

- [ ] **Step 1: Add failing BM25 candidate cache test**

Append to `tests/test_turbovec_retriever.py`:

```python
def test_tv_filtered_hybrid_reuses_cached_bm25_candidates() -> None:
    class FakeCache:
        def __init__(self):
            self.values = {}
            self.writes = []

        def get_json(self, key):
            return self.values.get(key)

        def set_json(self, key, payload, ttl_seconds):
            self.values[key] = payload
            self.writes.append((key, payload, ttl_seconds))

    class FakeESRetriever:
        index = "idx"
        calls = 0

        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            self.calls += 1
            return [{"doc_id": "d1", "numeric_id": 1, "title": "A", "source": "bm25"}]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            return np.array([[0.9]], dtype=np.float32), np.array([[1]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            return [{"doc_id": "d1", "numeric_id": 1, "title": "A"}]

    bm25 = FakeESRetriever()
    cache = FakeCache()
    retriever = TurboVecHybridRetriever(
        bm25_retriever=bm25,
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
        model_name="model",
        bm25_cache=cache,
        bm25_cache_ttl_seconds=60,
    )

    retriever.search("Alpha", method="tv_filtered_hybrid", top_k=1, bm25_k=4, dense_k=4, rrf_k=30)
    retriever.search(" alpha ", method="tv_filtered_hybrid", top_k=1, bm25_k=4, dense_k=4, rrf_k=30)

    assert bm25.calls == 1
    assert cache.writes[0][2] == 60
```

- [ ] **Step 2: Run targeted test and verify failure**

Run: `python -m pytest tests/test_turbovec_retriever.py::test_tv_filtered_hybrid_reuses_cached_bm25_candidates -q`
Expected: FAIL because `TurboVecHybridRetriever` does not accept `bm25_cache` yet.

- [ ] **Step 3: Implement BM25 cache in TurboVec retriever**

In `src/retrieval/turbovec_retriever.py`, import:

```python
from src.retrieval.cache_keys import build_bm25_cache_key, build_embedding_cache_key
```

Extend constructor arguments:

```python
        bm25_cache: Any | None = None,
        bm25_cache_ttl_seconds: int = 3600,
```

Set fields:

```python
        self.bm25_cache = bm25_cache
        self.bm25_cache_ttl_seconds = bm25_cache_ttl_seconds
```

Add helper:

```python
    def _search_bm25_candidates(self, query: str, bm25_k: int) -> list[dict[str, Any]]:
        index = str(getattr(self.bm25_retriever, "index", ""))
        cache_key = build_bm25_cache_key(index=index, query=query, bm25_k=bm25_k)
        if self.bm25_cache is not None:
            cached = self.bm25_cache.get_json(cache_key)
            if isinstance(cached, list):
                return [dict(hit) for hit in cached if isinstance(hit, dict)]

        hits = self.bm25_retriever.search(query, "bm25", bm25_k)
        if self.bm25_cache is not None:
            self.bm25_cache.set_json(cache_key, hits, self.bm25_cache_ttl_seconds)
        return hits
```

In `_search_filtered_hybrid()`, replace:

```python
        bm25_hits = self.bm25_retriever.search(query, "bm25", bm25_k)
```

with:

```python
        bm25_hits = self._search_bm25_candidates(query, bm25_k)
```

- [ ] **Step 4: Wire BM25 cache into API factory**

In `src/api/main.py`, pass cache settings into `TurboVecHybridRetriever.from_paths()`:

```python
        bm25_cache=get_json_cache(),
        bm25_cache_ttl_seconds=settings.bm25_cache_ttl_seconds,
```

Update `from_paths()` signature and constructor call to accept and forward `bm25_cache` and `bm25_cache_ttl_seconds`.

- [ ] **Step 5: Run TurboVec tests**

Run: `python -m pytest tests/test_turbovec_retriever.py -q`
Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add src/api/main.py src/retrieval/turbovec_retriever.py tests/test_turbovec_retriever.py
git commit -m "feat: cache filtered hybrid bm25 candidates"
```

## Task 6: Validation, Harness Evidence, and Documentation

**Files:**
- Modify: `docs/stories/epics/E03-sprint3-turbovec/US-S3-013-redis-retrieval-cache.md`
- Optionally modify: `README.md` if new cache env vars should be documented for users.

- [ ] **Step 1: Run unit validation**

Run: `python -m pytest tests/test_api_cache.py tests/test_cache_keys.py tests/test_elasticsearch_retriever.py tests/test_turbovec_retriever.py -q`
Expected: PASS.

- [ ] **Step 2: Run integration-adjacent API validation**

Run: `python -m pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q`
Expected: PASS.

- [ ] **Step 3: Run full focused cache/retrieval validation**

Run: `python -m pytest tests/test_elasticsearch_retriever.py tests/test_turbovec_retriever.py tests/test_benchmark_es.py tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q`
Expected: PASS.

- [ ] **Step 4: Record Harness story proof**

Run:

```powershell
.\scripts\bin\harness-cli.exe story update --id US-S3-013 --status implemented --unit 1 --integration 1 --e2e 0 --platform 0 --evidence "python -m pytest tests/test_elasticsearch_retriever.py tests/test_turbovec_retriever.py tests/test_benchmark_es.py tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q passed"
```

Expected: story row updates without error.

- [ ] **Step 5: Update story evidence**

Replace the `## Evidence` section in `docs/stories/epics/E03-sprint3-turbovec/US-S3-013-redis-retrieval-cache.md` with the exact validation commands and pass results from Steps 1-3.

- [ ] **Step 6: Record trace**

Run:

```powershell
.\scripts\bin\harness-cli.exe trace --summary "Implemented Redis retrieval cache hardening and partial caches" --story US-S3-013 --agent codex --outcome completed --actions "added cache key helpers,added safe Redis JSON cache,wired final search cache signature,added embedding cache,added BM25 candidate cache,ran focused pytest validation" --read "docs/superpowers/plans/2026-06-16-redis-retrieval-cache.md,src/api/main.py,src/retrieval/elasticsearch_retriever.py,src/retrieval/turbovec_retriever.py,tests/test_api_cache.py,tests/test_elasticsearch_retriever.py,tests/test_turbovec_retriever.py" --changed "src/retrieval/cache_keys.py,src/retrieval/cache_store.py,src/core/config.py,src/api/main.py,src/retrieval/elasticsearch_retriever.py,src/retrieval/turbovec_retriever.py,tests/test_cache_keys.py,tests/test_api_cache.py,tests/test_elasticsearch_retriever.py,tests/test_turbovec_retriever.py,docs/stories/epics/E03-sprint3-turbovec/US-S3-013-redis-retrieval-cache.md" --friction "none"
```

Expected: trace tier meets normal-lane requirement.

- [ ] **Step 7: Commit Task 6**

```bash
git add docs/stories/epics/E03-sprint3-turbovec/US-S3-013-redis-retrieval-cache.md README.md
git commit -m "docs: record redis retrieval cache validation"
```

If `README.md` was not changed, run:

```bash
git add docs/stories/epics/E03-sprint3-turbovec/US-S3-013-redis-retrieval-cache.md
git commit -m "docs: record redis retrieval cache validation"
```

## Self-Review

- Spec coverage: final response cache safety is covered by Tasks 1 and 3; embedding cache is covered by Task 4; BM25 candidate cache is covered by Task 5; validation and Harness evidence are covered by Task 6.
- Placeholder scan: the plan contains no placeholder implementation steps; every code task includes concrete code and a focused command.
- Type consistency: cache key helpers return strings, cache adapters expose `get_json` and `set_json`, and retrievers accept optional cache objects through constructor injection.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-16-redis-retrieval-cache.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.
