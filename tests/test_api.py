"""Integration tests cho API (mock search_meetings để không cần ES sống)."""

from fastapi.testclient import TestClient

import src.api.main as main
from src.api.main import app

client = TestClient(app)


def test_search_returns_results(monkeypatch):
    def fake_search(**kwargs):
        return {"query": kwargs["query"], "mode": kwargs["mode"], "parsed": ["source=ami"],
                "filters": {}, "results": [{"meeting_id": "ami_x", "title": "X", "score": 0.5,
                                            "evidence": [], "participants": [], "date": None}]}
    monkeypatch.setattr(main, "search_meetings", fake_search)
    resp = client.post("/search", json={"query": "ami meeting about design"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["meeting_id"] == "ami_x"
    assert body["parsed"] == ["source=ami"]


def test_search_rejects_empty_query():
    resp = client.post("/search", json={"query": ""})
    assert resp.status_code == 422


def test_ingest_requires_api_key():
    meeting = {"meeting_id": "qmsum_x", "source": "qmsum",
               "turns": [{"text": "hello"}]}
    resp = client.post("/meetings", json=meeting)  # thiếu X-API-Key
    assert resp.status_code == 401


def test_ingest_with_valid_key(monkeypatch):
    monkeypatch.setattr(main, "_reindex_meeting", lambda meeting: 1)
    meeting = {"meeting_id": "qmsum_x", "source": "qmsum",
               "turns": [{"text": "hello"}]}
    resp = client.post("/meetings", json=meeting,
                       headers={"X-API-Key": main.settings.ingest_api_key})
    assert resp.status_code == 201
    assert resp.json()["indexed_chunks"] == 1
