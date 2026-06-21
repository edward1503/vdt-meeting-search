from __future__ import annotations

import json


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_dataset_embedding_health_reports_ready_loaded_profile_model(monkeypatch) -> None:
    from src.api import main

    captured = {}
    monkeypatch.setattr(main, "embedding_service_url_for_profile", lambda profile: "http://embedding.local/embed")

    def fake_urlopen(url: str, timeout: int):
        captured["url"] = url
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "status": "ok",
                "device": "cuda",
                "torch_cuda_available": True,
                "loaded_models": {"hotpotqa": 384, "vimqa": 768},
            }
        )

    monkeypatch.setattr(main.urlrequest, "urlopen", fake_urlopen)

    payload = main.dataset_embedding_health("vimqa")

    assert captured["url"].endswith("/health")
    assert payload["dataset_id"] == "vimqa"
    assert payload["model_id"] == "vimqa"
    assert payload["expected_dim"] == 768
    assert payload["loaded_dim"] == 768
    assert payload["status"] == "ready"
    assert payload["torch_cuda_available"] is True


def test_dataset_embedding_health_reports_warming_when_model_not_loaded(monkeypatch) -> None:
    from src.api import main

    monkeypatch.setattr(main, "embedding_service_url_for_profile", lambda profile: "http://embedding.local/embed")
    monkeypatch.setattr(
        main.urlrequest,
        "urlopen",
        lambda url, timeout: FakeResponse({"status": "ok", "loaded_models": {"hotpotqa": 384}}),
    )

    payload = main.dataset_embedding_health("vimqa")

    assert payload["status"] == "warming"
    assert payload["loaded_dim"] is None


def test_dataset_embedding_health_reports_offline_when_service_errors(monkeypatch) -> None:
    from src.api import main

    monkeypatch.setattr(main, "embedding_service_url_for_profile", lambda profile: "http://embedding.local/embed")

    def fail_urlopen(url: str, timeout: int):
        raise OSError("connection refused")

    monkeypatch.setattr(main.urlrequest, "urlopen", fail_urlopen)

    payload = main.dataset_embedding_health("hotpotqa")

    assert payload["status"] == "offline"
    assert "connection refused" in payload["error"]
