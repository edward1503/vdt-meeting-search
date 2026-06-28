from __future__ import annotations

from pathlib import Path

from scripts.reranker_rrf_ablation_report import build_report, compare_full_support_wins


def test_compare_full_support_wins_counts_paired_changes(tmp_path: Path) -> None:
    qrels = {"q1": {"d1"}, "q2": {"d2"}, "q3": {"d3"}}
    rrf = {
        "q1": [{"doc_id": "d1", "rank": 1}],
        "q2": [{"doc_id": "x", "rank": 1}],
        "q3": [{"doc_id": "d3", "rank": 1}],
    }
    rerank = {
        "q1": [{"doc_id": "x", "rank": 1}],
        "q2": [{"doc_id": "d2", "rank": 1}],
        "q3": [{"doc_id": "d3", "rank": 1}],
    }

    summary = compare_full_support_wins(qrels, rrf, rerank, target_k=10)

    assert summary == {
        "queries": 3,
        "rrf_only_success": 1,
        "reranker_only_success": 1,
        "both_success": 1,
        "both_fail": 0,
        "net_reranker_wins": 0,
    }


def test_build_report_includes_model_metrics_diagnostics_and_caveat(tmp_path: Path) -> None:
    rrf_result = {
        "config": {"max_queries": 200, "top_k": 10, "candidate_k": 50},
        "results": [
            {
                "method": "tv_hybrid",
                "metrics": {
                    "full_support_recall@10": 0.55,
                    "recall@10": 0.75,
                    "mrr@10": 0.6,
                    "ndcg@10": 0.65,
                    "latency_p50_ms": 500,
                    "latency_p95_ms": 1000,
                    "qps": 1.0,
                },
            }
        ],
    }
    rerank_result = {
        "config": {"max_queries": 200, "top_k": 10, "candidate_k": 50, "reranker_model": "fake-reranker"},
        "results": [
            {
                "method": "tv_hybrid_rerank",
                "metrics": {
                    "full_support_recall@10": 0.6,
                    "recall@10": 0.78,
                    "mrr@10": 0.62,
                    "ndcg@10": 0.67,
                    "latency_p50_ms": 1500,
                    "latency_p95_ms": 2000,
                    "qps": 0.5,
                },
            }
        ],
    }
    diagnostics = {
        "methods": {
            "tv_hybrid": {
                "candidate_recall_at_depth": 0.9,
                "failure_buckets": {
                    "missing_candidate": 2,
                    "partial_candidate_support": 3,
                    "candidate_ranked_low": 4,
                    "success": 5,
                },
            }
        }
    }

    report = build_report(
        rrf_result=rrf_result,
        rerank_result=rerank_result,
        diagnostics=diagnostics,
        paired_summary={
            "queries": 200,
            "rrf_only_success": 4,
            "reranker_only_success": 8,
            "both_success": 100,
            "both_fail": 88,
            "net_reranker_wins": 4,
        },
        rrf_path=Path("rrf.json"),
        rerank_path=Path("rerank.json"),
        diagnostics_path=Path("diag.json"),
        rrf_run_path=Path("rrf.trec"),
        rerank_run_path=Path("rerank.trec"),
    )

    assert "# Reranker vs RRF Ablation" in report
    assert "fake-reranker" in report
    assert "200-query pilot" in report
    assert "not a paper-comparable claim" in report
    assert "| tv_hybrid_rerank | 0.6000 |" in report
    assert "p50 latency ms" in report
    assert "| tv_hybrid_rerank | 0.6000 | 0.7800 | 0.6200 | 0.6700 | 1500.0000 | 2000.0000 | 0.5000 |" in report
    assert "RRF TREC run: `rrf.trec`" in report
    assert "Reranker TREC run: `rerank.trec`" in report
    assert "net reranker wins: 4" in report
    assert "## Candidate Diagnostics" in report
    assert "Candidate recall@depth: 0.9000" in report
    assert "Missing candidate: 2" in report
    assert "Partial candidate support: 3" in report
    assert "Candidate ranked low: 4" in report
    assert "Success at target cutoff: 5" in report
