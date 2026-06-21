# Host GPU Multi-Model Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one `start.sh` bring up the host GPU embedding service plus Docker runtime, with HotpotQA and VimQA embeddings both served by the host GPU process.

**Architecture:** Keep PyTorch and SentenceTransformers on the host. Extend the embedding server into a small multi-model FastAPI service keyed by `model_id`, route VimQA Elasticsearch dense/hybrid query embeddings through that service, and add `start.sh` as the single startup orchestration script.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SentenceTransformers, Torch CUDA, Docker Compose, PowerShell/Git Bash runtime, pytest.

---

## File Structure

- Modify `scripts/embedding_server.py`: add model registry, `model_id`, explicit device option, loaded model health details.
- Modify `src/retrieval/elasticsearch_retriever.py`: add `embedding_model_id` and include it in remote embedding payloads.
- Modify `src/retrieval/turbovec_retriever.py`: allow remote embedding client to optionally include `model_id` while preserving HotpotQA default payload.
- Modify `src/api/main.py`: pass remote embedding URL and dataset model id to VimQA retriever, and show VimQA `embedding_service_url` in stats.
- Create `start.sh`: stop/reject stale embedding service, start host GPU embedding, warm HotpotQA and VimQA models, run compose, smoke endpoints.
- Create `tests/test_embedding_server.py`: prove multi-model default and VimQA behavior without loading real models.
- Modify `tests/test_turbovec_retriever.py`: prove existing HotpotQA remote payload remains backward compatible.
- Modify `tests/test_api_es_config.py`: prove VimQA stats and retriever factory use remote embedding service.

## Task 1: Embedding Server Multi-Model API

**Files:**
- Create: `tests/test_embedding_server.py`
- Modify: `scripts/embedding_server.py`

- [ ] **Step 1: Write failing embedding server tests**

Create `tests/test_embedding_server.py` with tests that inject a fake `sentence_transformers` module and assert:

```python
from __future__ import annotations

import sys
from types import ModuleType

import numpy as np
from fastapi.testclient import TestClient


def test_embedding_server_defaults_to_hotpotqa_and_accepts_vimqa_model_id(monkeypatch):
    from scripts.embedding_server import create_app

    loaded: list[tuple[str, str]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, device: str | None = None) -> None:
            loaded.append((model_name, device or "auto"))
            self.model_name = model_name

        def encode(self, texts, normalize_embeddings=True, convert_to_numpy=True):
            dim = 768 if "vietnamese" in self.model_name else 384
            return np.ones((len(texts), dim), dtype=np.float32)

    fake_module = ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    app = create_app(device="cuda", warmup=False)
    client = TestClient(app)

    hotpotqa = client.post("/embed", json={"text": "hello"})
    vimqa = client.post("/embed", json={"text": "xin chao", "model_id": "vimqa"})
    health = client.get("/health")

    assert hotpotqa.status_code == 200
    assert len(hotpotqa.json()["embedding"]) == 384
    assert vimqa.status_code == 200
    assert len(vimqa.json()["embedding"]) == 768
    assert loaded == [
        ("BAAI/bge-small-en-v1.5", "cuda"),
        ("bkai-foundation-models/vietnamese-bi-encoder", "cuda"),
    ]
    assert health.json()["loaded_models"] == {"hotpotqa": 384, "vimqa": 768}


def test_embedding_server_rejects_unknown_model_id():
    from scripts.embedding_server import create_app

    client = TestClient(create_app(device="cpu", warmup=False))

    response = client.post("/embed", json={"text": "hello", "model_id": "missing"})

    assert response.status_code == 404
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_embedding_server.py -q
```

Expected: FAIL because `create_app()` does not accept `device`, `EmbedRequest` has no `model_id`, and health has no `loaded_models`.

- [ ] **Step 3: Implement server registry**

Update `scripts/embedding_server.py` so:

- `MODEL_REGISTRY` maps `hotpotqa` to BGE dim 384 and `vimqa` to BKAI dim 768.
- `EmbedRequest` has `model_id: str = "hotpotqa"`.
- `create_app(model_name=None, device="auto", warmup=True)` uses `SentenceTransformer(spec.model_name, device=resolved_device)`.
- `/embed` looks up `model_id`, returns 404 for unknown models, and stores loaded dimensions.
- `/health` returns `status`, `model`, `device`, `torch_cuda_available`, and `loaded_models`.
- `parse_args()` adds `--device auto|cpu|cuda`.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_embedding_server.py -q
```

Expected: `2 passed`.

## Task 2: Remote Embedding Payload Carries Dataset Model Id

**Files:**
- Modify: `src/retrieval/elasticsearch_retriever.py`
- Modify: `src/retrieval/turbovec_retriever.py`
- Modify: `tests/test_turbovec_retriever.py`

- [ ] **Step 1: Write failing Elasticsearch remote payload test**

Append to `tests/test_turbovec_retriever.py`:

```python
def test_elasticsearch_retriever_remote_embedding_includes_model_id(monkeypatch):
    import json

    from src.retrieval.elasticsearch_retriever import ElasticsearchRetriever

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"embedding":[0.1,0.2,0.3]}'

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("src.retrieval.elasticsearch_retriever.request.urlopen", fake_urlopen)

    retriever = ElasticsearchRetriever(
        es=object(),
        index="vimqa_all_dense_bkai_current",
        model_name="bkai-foundation-models/vietnamese-bi-encoder",
        embedding_service_url="http://embedding:8010/embed",
        embedding_timeout_seconds=11,
        embedding_model_id="vimqa",
    )

    assert retriever._embed_query("xin chao") == [0.1, 0.2, 0.3]
    assert captured["body"] == {"text": "xin chao", "model_id": "vimqa"}
    assert captured["timeout"] == 11
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_turbovec_retriever.py::test_elasticsearch_retriever_remote_embedding_includes_model_id -q
```

Expected: FAIL because `ElasticsearchRetriever.__init__()` does not accept `embedding_model_id`.

- [ ] **Step 3: Implement model id support**

Update `ElasticsearchRetriever.__init__()` with `embedding_model_id: str = ""`, store it, and in `_embed_query_remote()` send `{"text": query}` plus `model_id` when set.

Update `RemoteEmbeddingClient` in `src/retrieval/turbovec_retriever.py` similarly, but keep default `embedding_model_id=""` so existing HotpotQA test still expects `{"text":"hello"}`.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_turbovec_retriever.py::test_remote_embedding_client_returns_2d_float32_vector tests/test_turbovec_retriever.py::test_elasticsearch_retriever_remote_embedding_includes_model_id -q
```

Expected: both pass.

## Task 3: Route VimQA Dense/Hybrid Through Host Embedding Service

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api_es_config.py`

- [ ] **Step 1: Write failing API tests**

Append tests to `tests/test_api_es_config.py` that assert:

```python
def test_vimqa_stats_reports_embedding_service_url():
    from src.api import main

    payload = main.dataset_stats("vimqa")

    assert payload["embedding_service_url"] == main.settings.embedding_service_url


def test_get_es_retriever_for_vimqa_uses_remote_embedding_service(monkeypatch):
    from src.api import main

    captured = {}

    class FakeElasticsearch:
        def __init__(self, *args, **kwargs):
            pass

    class FakeRetriever:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    main.get_es_retriever_for_profile.cache_clear()
    monkeypatch.setattr("elasticsearch.Elasticsearch", FakeElasticsearch)
    monkeypatch.setattr(main, "ElasticsearchRetriever", FakeRetriever)

    main.get_es_retriever_for_profile("vimqa")

    assert captured["embedding_service_url"] == main.settings.embedding_service_url
    assert captured["embedding_model_id"] == "vimqa"
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_api_es_config.py::test_vimqa_stats_reports_embedding_service_url tests/test_api_es_config.py::test_get_es_retriever_for_vimqa_uses_remote_embedding_service -q
```

Expected: FAIL because VimQA stats currently reports empty embedding URL and the retriever does not receive `embedding_model_id`.

- [ ] **Step 3: Implement API routing**

Add helper `embedding_model_id_for_profile(profile)` returning profile id for non-HotpotQA profiles and empty string for HotpotQA default. Pass `settings.embedding_service_url` when a profile has dense methods or TurboVec. Pass `embedding_model_id="vimqa"` for VimQA.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_api_es_config.py::test_vimqa_stats_reports_embedding_service_url tests/test_api_es_config.py::test_get_es_retriever_for_vimqa_uses_remote_embedding_service -q
```

Expected: both pass.

## Task 4: Add Unified Startup Script

**Files:**
- Create: `start.sh`
- Modify: `README.md`

- [ ] **Step 1: Create `start.sh`**

Create a POSIX shell script that:

- checks `docker`, `python`, and `nvidia-smi`;
- stops a stale `.runtime/embedding_server.pid` process when it is this repo's embedding server;
- rejects port 8010 if occupied by a non-embedding process;
- starts `CUDA_VISIBLE_DEVICES=0 python scripts/embedding_server.py --host 0.0.0.0 --port 8010 --device cuda`;
- writes logs under `logs/` and PID under `.runtime/`;
- polls `http://127.0.0.1:8010/health`;
- warms `hotpotqa` and `vimqa` with `/embed`, requiring dims 384 and 768;
- runs `docker compose up -d --build elasticsearch redis api frontend`;
- checks API container can hit `host.docker.internal:8010/health`;
- smokes `/datasets` and HotpotQA `tv_hybrid`.

- [ ] **Step 2: Add README usage**

Document:

```bash
./start.sh
```

and explain that it manages the host GPU embedding service plus Docker Compose.

- [ ] **Step 3: Syntax smoke**

Run:

```powershell
bash -n start.sh
```

Expected: exit 0, or if `bash` is unavailable, record a clean skip and rely on runtime execution.

## Task 5: Verification And Runtime Startup

**Files:** no new code files.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_embedding_server.py tests/test_turbovec_retriever.py tests/test_api_es_config.py -q
```

Expected: pass.

- [ ] **Step 2: Start runtime**

Run:

```powershell
bash start.sh
```

If Git Bash is unavailable on Windows, run the equivalent PowerShell sequence and report that `start.sh` was syntax-checked but not executed.

- [ ] **Step 3: Smoke HotpotQA and VimQA**

Run:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/datasets/vimqa/stats
POST /datasets/hotpotqa/search method=tv_hybrid top_k=3
POST /datasets/vimqa/search method=es_dense top_k=3
POST /datasets/vimqa/search method=es_hybrid top_k=3
```

Expected: all search calls return HTTP 200 with non-empty results.

## Self-Review

- Spec coverage: covers multi-model host GPU embedding, VimQA remote embedding routing, fail-hard startup, compose startup, and verification.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: `model_id` is the external embedding server request field; `embedding_model_id` is the retriever constructor field.
