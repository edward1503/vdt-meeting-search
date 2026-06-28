from __future__ import annotations

from src.retrieval.reranker import CrossEncoderReranker, dedupe_hits, rerank_hits


class FakeScorer:
    def predict(self, pairs):
        scores = []
        for _, document in pairs:
            scores.append(10.0 if "gold" in document else 1.0)
        return scores


def test_dedupe_hits_preserves_first_hit_and_merges_sources() -> None:
    hits = [
        {"doc_id": "d1", "title": "First", "text": "one", "source": "bm25", "score": 3.0},
        {"doc_id": "d2", "title": "Second", "text": "two", "source": "dense", "score": 2.0},
        {"doc_id": "d1", "title": "Dense First", "text": "ignored", "source": "dense", "score": 9.0},
    ]

    deduped = dedupe_hits(hits)

    assert [hit["doc_id"] for hit in deduped] == ["d1", "d2"]
    assert deduped[0]["title"] == "First"
    assert deduped[0]["source"] == "bm25+dense"


def test_rerank_hits_orders_by_model_score_and_keeps_original_score() -> None:
    hits = [
        {"doc_id": "d1", "title": "Plain", "text": "ordinary text", "score": 0.8, "source": "bm25"},
        {"doc_id": "d2", "title": "Gold", "text": "gold evidence", "score": 0.1, "source": "dense"},
    ]

    reranked = rerank_hits("query", hits, FakeScorer(), top_k=2)

    assert [hit["doc_id"] for hit in reranked] == ["d2", "d1"]
    assert reranked[0]["score"] == 10.0
    assert reranked[0]["reranker_score"] == 10.0
    assert reranked[0]["pre_rerank_score"] == 0.1
    assert reranked[0]["source"] == "dense+rerank"


def test_cross_encoder_reranker_lazy_loads_model(monkeypatch) -> None:
    created = []

    class FakeCrossEncoder:
        def __init__(self, model_name: str) -> None:
            created.append(model_name)

        def predict(self, pairs):
            return [0.5 for _ in pairs]

    monkeypatch.setattr("src.retrieval.reranker._load_cross_encoder_class", lambda: FakeCrossEncoder)

    reranker = CrossEncoderReranker("fake-model")

    assert created == []
    assert reranker.predict([("q", "doc")]) == [0.5]
    assert created == ["fake-model"]
