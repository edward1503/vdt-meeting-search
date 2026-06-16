# Docker TurboVec Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing API Docker container run TurboVec dense search by loading the mounted `.tvim` artifact directly, while keeping embeddings outside the API image through the existing embedding HTTP service.

**Architecture:** Do not create a TurboVec service. The API container installs `turbovec` and `numpy`, loads `/app/artifacts/.../*.tvim`, calls Elasticsearch for BM25 and hydration, and calls `EMBEDDING_SERVICE_URL` for query embeddings. Frontend and API contracts stay unchanged.

**Tech Stack:** Python 3.12, FastAPI, Docker Compose, TurboVec, NumPy, Elasticsearch, existing local embedding server.

---

## File Structure

- Modify `requirements-api.txt`: add only `numpy` and `turbovec==0.8.0`.
- Modify `src/retrieval/turbovec_retriever.py`: add a remote embedding client and make `from_paths()` use it when `embedding_service_url` is configured.
- Modify `src/api/main.py`: pass `settings.embedding_service_url` and `settings.embedding_timeout_seconds` into `TurboVecHybridRetriever.from_paths()`; include TurboVec path in `/stats`.
- Modify `docker-compose.yml`: expose `TURBOVEC_INDEX_PATH` to the API container with the existing full artifact path as the default.
- Modify `tests/test_turbovec_retriever.py`: prove remote embedding client shape and `from_paths()` selection.
- Modify `tests/test_api_es_config.py`: prove `/stats` exposes TurboVec runtime fields and API factory forwards embedding service settings.
- Update `docs/stories/epics/E03-sprint3-turbovec/US-S3-014-docker-turbovec-runtime.md`: record evidence after validation.

## Task 1: Remote Embedding Client For TurboVec

**Files:**
- Modify: `src/retrieval/turbovec_retriever.py`
- Modify: `tests/test_turbovec_retriever.py`

- [ ] **Step 1: Write failing test for remote embedding client**

Append to `tests/test_turbovec_retriever.py`:

```python
def test_remote_embedding_client_returns_2d_float32_vector(monkeypatch):
    import io
    from src.retrieval.turbovec_retriever import RemoteEmbeddingClient

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"embedding":[0.25,0.75]}'

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = req.data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("src.retrieval.turbovec_retriever.request.urlopen", fake_urlopen)

    client = RemoteEmbeddingClient("http://embedding:8010/embed", timeout_seconds=7)
    vector = client.encode(["hello"], normalize_embeddings=True, convert_to_numpy=True)

    assert captured["url"] == "http://embedding:8010/embed"
    assert captured["body"] == b'{"text":"hello"}'
    assert captured["timeout"] == 7
    assert vector.dtype == np.float32
    assert vector.shape == (1, 2)
    assert vector.tolist() == [[0.25, 0.75]]
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest tests/test_turbovec_retriever.py::test_remote_embedding_client_returns_2d_float32_vector -q`

Expected: FAIL with `ImportError` or `AttributeError` because `RemoteEmbeddingClient` does not exist.

- [ ] **Step 3: Implement `RemoteEmbeddingClient`**

In `src/retrieval/turbovec_retriever.py`, add imports near the top:

```python
import json
from urllib import request
```

Add this class above `ElasticsearchNumericDocStore`:

```python
class RemoteEmbeddingClient:
    def __init__(self, embedding_service_url: str, timeout_seconds: int = 30) -> None:
        self.embedding_service_url = embedding_service_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def encode(self, texts: list[str], normalize_embeddings: bool = True, convert_to_numpy: bool = True) -> np.ndarray:
        if len(texts) != 1:
            raise ValueError("RemoteEmbeddingClient supports exactly one query at a time")
        payload = json.dumps({"text": texts[0]}, separators=(",", ":")).encode("utf-8")
        req = request.Request(
            self.embedding_service_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return np.asarray([[float(value) for value in body["embedding"]]], dtype=np.float32)
```

- [ ] **Step 4: Run the remote embedding test**

Run: `python -m pytest tests/test_turbovec_retriever.py::test_remote_embedding_client_returns_2d_float32_vector -q`

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/retrieval/turbovec_retriever.py tests/test_turbovec_retriever.py
git commit -m "feat: add remote embedding client for turbovec"
```

## Task 2: Make `from_paths()` Prefer Remote Embeddings

**Files:**
- Modify: `src/retrieval/turbovec_retriever.py`
- Modify: `tests/test_turbovec_retriever.py`

- [ ] **Step 1: Write failing test for remote embedder selection**

Append to `tests/test_turbovec_retriever.py`:

```python
def test_turbovec_from_paths_uses_remote_embedder_when_url_is_configured(monkeypatch):
    from src.retrieval import turbovec_retriever

    class FakeIdMapIndex:
        @staticmethod
        def load(path):
            return {"loaded": path}

    class FakeTurboVecModule:
        IdMapIndex = FakeIdMapIndex

    monkeypatch.setitem(__import__("sys").modules, "turbovec", FakeTurboVecModule())

    retriever = turbovec_retriever.TurboVecHybridRetriever.from_paths(
        bm25_retriever=object(),
        es=object(),
        index="hotpotqa_full_bm25_current",
        tv_index_path="/app/artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim",
        model_name="BAAI/bge-small-en-v1.5",
        embedding_service_url="http://host.docker.internal:8010/embed",
        embedding_timeout_seconds=9,
    )

    assert isinstance(retriever.embedder, turbovec_retriever.RemoteEmbeddingClient)
    assert retriever.embedder.embedding_service_url == "http://host.docker.internal:8010/embed"
    assert retriever.embedder.timeout_seconds == 9
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest tests/test_turbovec_retriever.py::test_turbovec_from_paths_uses_remote_embedder_when_url_is_configured -q`

Expected: FAIL because `from_paths()` does not accept `embedding_service_url`.

- [ ] **Step 3: Update `from_paths()` signature and selection**

Replace the current `from_paths()` in `src/retrieval/turbovec_retriever.py` with:

```python
    @classmethod
    def from_paths(
        cls,
        bm25_retriever: Any,
        es: Any,
        index: str,
        tv_index_path: str,
        model_name: str,
        embedding_service_url: str = "",
        embedding_timeout_seconds: int = 30,
    ) -> "TurboVecHybridRetriever":
        from turbovec import IdMapIndex

        if embedding_service_url:
            embedder = RemoteEmbeddingClient(embedding_service_url, timeout_seconds=embedding_timeout_seconds)
        else:
            from sentence_transformers import SentenceTransformer

            embedder = SentenceTransformer(model_name)

        return cls(
            bm25_retriever=bm25_retriever,
            tv_index=IdMapIndex.load(tv_index_path),
            embedder=embedder,
            docstore=ElasticsearchNumericDocStore(es, index),
        )
```

- [ ] **Step 4: Run TurboVec unit tests**

Run: `python -m pytest tests/test_turbovec_retriever.py -q`

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/retrieval/turbovec_retriever.py tests/test_turbovec_retriever.py
git commit -m "feat: use remote embeddings for docker turbovec"
```

## Task 3: Wire API Settings And Stats

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api_es_config.py`

- [ ] **Step 1: Add failing stats test**

Append to `tests/test_api_es_config.py`:

```python
def test_stats_exposes_turbovec_runtime_path():
    from src.api import main

    payload = main.stats()

    assert "turbovec_index_path" in payload
    assert "default_search_method" in payload
```

- [ ] **Step 2: Add failing factory wiring test**

Append to `tests/test_api_es_config.py`:

```python
def test_get_tv_retriever_passes_embedding_service_settings(monkeypatch):
    from src.api import main

    captured = {}

    class FakeElasticsearch:
        def __init__(self, *args, **kwargs):
            pass

    class FakeTV:
        @classmethod
        def from_paths(cls, **kwargs):
            captured.update(kwargs)
            return "tv"

    main.get_tv_retriever.cache_clear()
    monkeypatch.setattr("elasticsearch.Elasticsearch", FakeElasticsearch)
    monkeypatch.setattr(main, "TurboVecHybridRetriever", FakeTV)

    assert main.get_tv_retriever() == "tv"
    assert captured["embedding_service_url"] == main.settings.embedding_service_url
    assert captured["embedding_timeout_seconds"] == main.settings.embedding_timeout_seconds
```

- [ ] **Step 3: Run tests and verify failure**

Run: `python -m pytest tests/test_api_es_config.py::test_stats_exposes_turbovec_runtime_path tests/test_api_es_config.py::test_get_tv_retriever_passes_embedding_service_settings -q`

Expected: FAIL because stats and factory do not expose/pass these values yet.

- [ ] **Step 4: Update `/stats`**

In `src/api/main.py`, add these keys to `stats()` return payload:

```python
        "default_search_method": settings.default_search_method,
        "turbovec_index_path": str(settings.turbovec_index_path),
        "turbovec_dim": settings.turbovec_dim,
        "turbovec_bit_width": settings.turbovec_bit_width,
```

- [ ] **Step 5: Update `get_tv_retriever()` factory**

In `src/api/main.py`, add arguments to `TurboVecHybridRetriever.from_paths()`:

```python
        embedding_service_url=settings.embedding_service_url,
        embedding_timeout_seconds=settings.embedding_timeout_seconds,
```

- [ ] **Step 6: Run API config tests**

Run: `python -m pytest tests/test_api_es_config.py -q`

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add src/api/main.py tests/test_api_es_config.py
git commit -m "feat: expose docker turbovec runtime settings"
```

## Task 4: Minimal Docker Dependency And Env Wiring

**Files:**
- Modify: `requirements-api.txt`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add API image dependencies**

Modify `requirements-api.txt` to include:

```text
numpy==2.3.5
turbovec==0.8.0
```

Do not add `sentence-transformers` to `requirements-api.txt` in this migration. The API container should use `EMBEDDING_SERVICE_URL` for embeddings.

- [ ] **Step 2: Add Docker env for TurboVec path**

In `docker-compose.yml`, add this line under `api.environment`:

```yaml
      - TURBOVEC_INDEX_PATH=${TURBOVEC_INDEX_PATH:-/app/artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim}
```

Keep this existing mount unchanged:

```yaml
      - ./artifacts:/app/artifacts
```

- [ ] **Step 3: Run a local dependency smoke command**

Run: `python -m pytest tests/test_api_es_config.py tests/test_turbovec_retriever.py -q`

Expected: PASS.

- [ ] **Step 4: Build the API image**

Run: `docker compose build api`

Expected: build succeeds and installs `turbovec` without installing `sentence-transformers`.

- [ ] **Step 5: Commit Task 4**

```bash
git add requirements-api.txt docker-compose.yml
git commit -m "build: install turbovec in api container"
```

## Task 5: Full-Corpus Docker Smoke Demo

**Files:**
- Modify: `docs/stories/epics/E03-sprint3-turbovec/US-S3-014-docker-turbovec-runtime.md`

- [ ] **Step 1: Start the embedding server on the host**

Run from repo root:

```powershell
python scripts/embedding_server.py --host 0.0.0.0 --port 8010
```

Expected: service listens at `http://localhost:8010/embed`.

- [ ] **Step 2: Start Docker with full runtime overrides**

Run in a second PowerShell:

```powershell
$env:ELASTICSEARCH_INDEX="hotpotqa_full_bm25_current"
$env:TURBOVEC_INDEX_PATH="/app/artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim"
$env:DEFAULT_SEARCH_METHOD="tv_hybrid"
$env:HYBRID_BM25_K="50"
$env:HYBRID_DENSE_K="50"
$env:RRF_K="30"
docker compose up -d elasticsearch redis api frontend
```

Expected: `api` and `frontend` containers become healthy/running.

- [ ] **Step 3: Verify `/stats` through Docker API**

Run:

```powershell
Invoke-RestMethod http://localhost:8001/stats | ConvertTo-Json -Depth 5
```

Expected payload contains:

```json
{
  "index": "hotpotqa_full_bm25_current",
  "default_search_method": "tv_hybrid",
  "turbovec_index_path": "/app/artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim",
  "embedding_service_url": "http://host.docker.internal:8010/embed"
}
```

- [ ] **Step 4: Verify `tv_dense` through Docker API**

Run:

```powershell
Invoke-RestMethod `
  -Uri http://localhost:8001/search `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"query":"What occupations do both Ian Hunter and Rob Thomas have?","method":"tv_dense","top_k":5}'
```

Expected: response contains non-empty `results`, `method` equals `tv_dense`, and no import error for `sentence_transformers` appears in API logs.

- [ ] **Step 5: Verify `tv_hybrid` through frontend**

Open `http://localhost:3001`, select or run `tv_hybrid`, and issue:

```text
What occupations do both Ian Hunter and Rob Thomas have?
```

Expected: dashboard displays ranked results and latency. This proves frontend/backend wiring did not need a contract change.

- [ ] **Step 6: Record Harness proof**

Run:

```powershell
.\scripts\bin\harness-cli.exe story update --id US-S3-014 --status implemented --unit 1 --integration 1 --e2e 1 --platform 1 --evidence "Docker API built with turbovec; /stats exposed full runtime; tv_dense and tv_hybrid returned results through Docker API/frontend"
```

- [ ] **Step 7: Update story evidence and commit**

Replace the `## Evidence` section in `docs/stories/epics/E03-sprint3-turbovec/US-S3-014-docker-turbovec-runtime.md` with the exact commands and observed outputs, then run:

```bash
git add docs/stories/epics/E03-sprint3-turbovec/US-S3-014-docker-turbovec-runtime.md
git commit -m "docs: record docker turbovec runtime proof"
```

## Self-Review

- Spec coverage: the plan installs only the minimum Docker dependencies, keeps embeddings external, wires the API factory, exposes runtime stats, and validates Docker plus frontend smoke behavior.
- Placeholder scan: there are no placeholder implementation steps; each task has exact file paths, code snippets, commands, and expected outcomes.
- Type consistency: `RemoteEmbeddingClient.encode()` matches the existing embedder interface used by `_embed_query()`, returning a 2D `np.float32` array.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-16-docker-turbovec-runtime.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.
