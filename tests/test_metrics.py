from __future__ import annotations

from src.evaluation.metrics import evaluate_rankings
from src.retrieval.base import SearchHit


def test_evaluate_rankings_reports_full_support_at_2_5_and_10():
    qrels = {"q1": {"d1": 1.0, "d2": 1.0}, "q2": {"d3": 1.0, "d4": 1.0}}
    runs = {
        "q1": [
            SearchHit(doc_id="d1", score=1.0, rank=1, method="m"),
            SearchHit(doc_id="d2", score=0.9, rank=2, method="m"),
        ],
        "q2": [
            SearchHit(doc_id="x1", score=1.0, rank=1, method="m"),
            SearchHit(doc_id="x2", score=0.9, rank=2, method="m"),
            SearchHit(doc_id="d3", score=0.8, rank=3, method="m"),
            SearchHit(doc_id="x3", score=0.7, rank=4, method="m"),
            SearchHit(doc_id="d4", score=0.6, rank=5, method="m"),
        ],
    }

    metrics = evaluate_rankings(qrels, runs, {"q1": 10.0, "q2": 20.0}, k=10)

    assert metrics["full_support_recall@2"] == 0.5
    assert metrics["full_support_recall@5"] == 1.0
    assert metrics["full_support_recall@10"] == 1.0


def test_evaluate_rankings_reports_chain_metrics_when_chain_output_exists():
    qrels = {"q1": {"bridge": 1.0, "answer": 1.0}, "q2": {"a": 1.0, "b": 1.0}}
    runs = {
        "q1": [
            SearchHit(
                doc_id="bridge",
                score=2.0,
                rank=1,
                method="tv_two_hop_bridge_rrf",
                chain_rank=1,
                chain_doc_ids=("bridge", "answer"),
            ),
            SearchHit(
                doc_id="answer",
                score=1.9,
                rank=2,
                method="tv_two_hop_bridge_rrf",
                chain_rank=1,
                chain_doc_ids=("bridge", "answer"),
            ),
        ],
        "q2": [
            SearchHit(
                doc_id="a",
                score=1.0,
                rank=1,
                method="tv_two_hop_bridge_rrf",
                chain_rank=1,
                chain_doc_ids=("a", "x"),
            ),
            SearchHit(
                doc_id="b",
                score=0.9,
                rank=2,
                method="tv_two_hop_bridge_rrf",
                chain_rank=2,
                chain_doc_ids=("a", "b"),
            ),
        ],
    }

    metrics = evaluate_rankings(qrels, runs, {"q1": 10.0, "q2": 20.0}, k=10)

    assert metrics["chain_recall@1"] == 0.5
    assert metrics["chain_recall@5"] == 1.0
    assert metrics["chain_mrr"] == 0.75
