from __future__ import annotations

import numpy as np

from src.retrieval.turbovec_retriever import TurboVecHybridRetriever


def test_tv_hybrid_fuses_bm25_and_dense_and_preserves_hydrated_order():
    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            assert method == "bm25"
            return [
                {"doc_id": "d1", "numeric_id": 1, "title": "A", "source": "bm25"},
                {"doc_id": "d2", "numeric_id": 2, "title": "B", "source": "bm25"},
            ]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            assert queries.shape == (1, 2)
            return np.array([[0.9, 0.8]], dtype=np.float32), np.array([[2, 3]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            assert texts == ["query"]
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            docs = {
                2: {"doc_id": "d2", "numeric_id": 2, "title": "B"},
                3: {"doc_id": "d3", "numeric_id": 3, "title": "C"},
                1: {"doc_id": "d1", "numeric_id": 1, "title": "A"},
            }
            return [docs[int(numeric_id)] for numeric_id in numeric_ids]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )

    hits = retriever.search("query", method="tv_hybrid", top_k=2, bm25_k=2, dense_k=2, rrf_k=30)

    assert [hit["doc_id"] for hit in hits] == ["d2", "d1"]
    assert hits[0]["source"] == "bm25+dense"

def test_tv_filtered_hybrid_uses_bm25_numeric_ids_as_turbovec_allowlist():
    calls = []

    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            assert query == "query"
            assert method == "bm25"
            assert top_k == 4
            return [
                {"doc_id": "d2", "numeric_id": 2, "title": "B", "source": "bm25"},
                {"doc_id": "d1", "numeric_id": 1, "title": "A", "source": "bm25"},
                {"doc_id": "missing-id", "title": "Missing", "source": "bm25"},
                {"doc_id": "d2-duplicate", "numeric_id": 2, "title": "Dup", "source": "bm25"},
            ]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            calls.append({"k": k, "allowlist": allowlist})
            assert queries.shape == (1, 2)
            return np.array([[0.9, 0.8]], dtype=np.float32), np.array([[2, 1]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            assert texts == ["query"]
            assert normalize_embeddings is True
            assert convert_to_numpy is True
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            docs = {
                1: {"doc_id": "d1", "numeric_id": 1, "title": "A"},
                2: {"doc_id": "d2", "numeric_id": 2, "title": "B"},
            }
            return [docs[int(numeric_id)] for numeric_id in numeric_ids]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )

    hits = retriever.search("query", method="tv_filtered_hybrid", top_k=2, bm25_k=4, dense_k=10, rrf_k=30)

    assert calls[0]["k"] == 2
    assert calls[0]["allowlist"].dtype == np.uint64
    assert calls[0]["allowlist"].tolist() == [2, 1]
    assert [hit["doc_id"] for hit in hits] == ["d2", "d1"]
    assert hits[0]["source"] == "bm25+dense"
    assert "allowlist" in retriever.last_timing_ms

def test_tv_filtered_hybrid_falls_back_to_broad_dense_when_allowlist_is_empty():
    calls = []

    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            return [
                {"doc_id": "d1", "title": "A", "source": "bm25"},
                {"doc_id": "d2", "numeric_id": None, "title": "B", "source": "bm25"},
            ]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            calls.append({"k": k, "allowlist": allowlist})
            return np.array([[0.7]], dtype=np.float32), np.array([[3]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            return [{"doc_id": "d3", "numeric_id": 3, "title": "C"}]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )

    hits = retriever.search("query", method="tv_filtered_hybrid", top_k=2, bm25_k=2, dense_k=5, rrf_k=30)

    assert calls == [{"k": 5, "allowlist": None}]
    assert [hit["doc_id"] for hit in hits] == ["d1", "d3"]

def test_remote_embedding_client_returns_2d_float32_vector(monkeypatch):
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
