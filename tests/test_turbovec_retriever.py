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
