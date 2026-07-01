from __future__ import annotations

import inspect
import sys
from types import ModuleType

import numpy as np
from fastapi.testclient import TestClient


def test_embedding_server_defaults_to_hotpotqa_and_accepts_vimqa_model_id(monkeypatch):
    from scripts.embedding_server import create_app

    loaded: list[tuple[str, str, dict[str, object] | None]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, device: str | None = None, model_kwargs: dict[str, object] | None = None) -> None:
            loaded.append((model_name, device or "auto", model_kwargs))
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
        ("BAAI/bge-small-en-v1.5", "cuda", {"low_cpu_mem_usage": False}),
        ("bkai-foundation-models/vietnamese-bi-encoder", "cuda", {"low_cpu_mem_usage": False}),
    ]
    assert health.json()["loaded_models"] == {"hotpotqa": 384, "vimqa": 768}


def test_embedding_server_rejects_unknown_model_id():
    from scripts.embedding_server import create_app

    client = TestClient(create_app(device="cpu", warmup=False))

    response = client.post("/embed", json={"text": "hello", "model_id": "missing"})

    assert response.status_code == 404

def test_embedding_endpoint_runs_on_event_loop_thread_for_cuda():
    from scripts.embedding_server import create_app

    app = create_app(device="cuda", warmup=False)
    embed_route = next(route for route in app.routes if getattr(route, "path", "") == "/embed")

    assert inspect.iscoroutinefunction(embed_route.endpoint)
