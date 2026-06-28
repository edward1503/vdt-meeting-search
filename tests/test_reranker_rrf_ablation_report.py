from __future__ import annotations

from pathlib import Path

import pytest

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
        "config": {"max_queries": 200, "top_k": 100, "candidate_k": 50},
        "results": [
            {
                "method": "tv_hybrid",
                "metrics": {
                    "full_support_recall@100": 0.55,
                    "recall@100": 0.75,
                    "mrr@100": 0.6,
                    "ndcg@100": 0.65,
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
    assert "p50 latency ms" in report
    assert "| Method | Metric cutoff | Full support | Recall | MRR | nDCG | p50 latency ms | p95 latency ms | QPS |" in report
    assert "| tv_hybrid | 100 | 0.5500 | 0.7500 | 0.6000 | 0.6500 | 500.0000 | 1000.0000 | 1.0000 |" in report
    assert "| tv_hybrid_rerank | 10 | 0.6000 | 0.7800 | 0.6200 | 0.6700 | 1500.0000 | 2000.0000 | 0.5000 |" in report
    assert "RRF TREC run: `rrf.trec`" in report
    assert "Reranker TREC run: `rerank.trec`" in report
    assert "net reranker wins: 4" in report
    assert "## Candidate Diagnostics" in report
    assert "Candidate recall@depth: 0.9000" in report
    assert "Missing candidate: 2" in report
    assert "Partial candidate support: 3" in report
    assert "Candidate ranked low: 4" in report
    assert "Success at target cutoff: 5" in report


def test_build_report_labels_small_runs_as_smoke() -> None:
    report = build_report(
        rrf_result={
            "config": {"top_k": 10},
            "results": [
                {
                    "method": "tv_hybrid",
                    "metrics": {
                        "full_support_recall@10": 0.1,
                        "recall@10": 0.2,
                        "mrr@10": 0.3,
                        "ndcg@10": 0.4,
                        "latency_p50_ms": 50,
                        "latency_p95_ms": 100,
                        "qps": 2.0,
                    },
                }
            ],
        },
        rerank_result={
            "config": {"top_k": 10, "reranker_model": "fake-reranker"},
            "results": [
                {
                    "method": "tv_hybrid_rerank",
                    "metrics": {
                        "full_support_recall@10": 0.2,
                        "recall@10": 0.3,
                        "mrr@10": 0.4,
                        "ndcg@10": 0.5,
                        "latency_p50_ms": 60,
                        "latency_p95_ms": 120,
                        "qps": 1.0,
                    },
                }
            ],
        },
        diagnostics={
            "methods": {
                "tv_hybrid": {
                    "candidate_recall_at_depth": 0.0,
                    "failure_buckets": {
                        "missing_candidate": 0,
                        "partial_candidate_support": 0,
                        "candidate_ranked_low": 0,
                        "success": 0,
                    },
                }
            }
        },
        paired_summary={
            "queries": 5,
            "rrf_only_success": 0,
            "reranker_only_success": 0,
            "both_success": 0,
            "both_fail": 5,
            "net_reranker_wins": 0,
        },
        rrf_path=Path("rrf.json"),
        rerank_path=Path("rerank.json"),
        diagnostics_path=Path("diag.json"),
    )

    assert "5-query smoke ablation" in report


def test_build_report_falls_back_to_config_or_metric_query_count() -> None:
    report = build_report(
        rrf_result={
            "config": {"top_k": 10, "queries": 123},
            "results": [
                {
                    "method": "tv_hybrid",
                    "metrics": {
                        "full_support_recall@10": 0.1,
                        "recall@10": 0.2,
                        "mrr@10": 0.3,
                        "ndcg@10": 0.4,
                        "latency_p50_ms": 50,
                        "latency_p95_ms": 100,
                        "qps": 2.0,
                    },
                }
            ],
        },
        rerank_result={
            "config": {"top_k": 10, "reranker_model": "fake-reranker"},
            "results": [
                {
                    "method": "tv_hybrid_rerank",
                    "metrics": {
                        "queries": 75,
                        "full_support_recall@10": 0.2,
                        "recall@10": 0.3,
                        "mrr@10": 0.4,
                        "ndcg@10": 0.5,
                        "latency_p50_ms": 60,
                        "latency_p95_ms": 120,
                        "qps": 1.0,
                    },
                }
            ],
        },
        diagnostics={
            "methods": {
                "tv_hybrid": {
                    "candidate_recall_at_depth": 0.0,
                    "failure_buckets": {
                        "missing_candidate": 0,
                        "partial_candidate_support": 0,
                        "candidate_ranked_low": 0,
                        "success": 0,
                    },
                }
            }
        },
        paired_summary={
            "queries": 0,
            "rrf_only_success": 0,
            "reranker_only_success": 0,
            "both_success": 0,
            "both_fail": 0,
            "net_reranker_wins": 0,
        },
        rrf_path=Path("rrf.json"),
        rerank_path=Path("rerank.json"),
        diagnostics_path=Path("diag.json"),
    )

    assert "75-query pilot ablation" in report


def test_build_report_raises_for_missing_method_or_metric() -> None:
    base_result = {
        "config": {"top_k": 10},
        "results": [
            {
                "method": "tv_hybrid",
                "metrics": {
                    "full_support_recall@10": 0.1,
                    "recall@10": 0.2,
                    "mrr@10": 0.3,
                    "ndcg@10": 0.4,
                    "latency_p50_ms": 50,
                    "latency_p95_ms": 100,
                    "qps": 2.0,
                },
            }
        ],
    }

    with pytest.raises(ValueError, match="Missing result row for method tv_hybrid_rerank"):
        build_report(
            rrf_result=base_result,
            rerank_result={"config": {"top_k": 10}, "results": []},
            diagnostics={
                "methods": {
                    "tv_hybrid": {
                        "candidate_recall_at_depth": 0.0,
                        "failure_buckets": {
                            "missing_candidate": 0,
                            "partial_candidate_support": 0,
                            "candidate_ranked_low": 0,
                            "success": 0,
                        },
                    }
                }
            },
            paired_summary={"queries": 5},
            rrf_path=Path("rrf.json"),
            rerank_path=Path("rerank.json"),
            diagnostics_path=Path("diag.json"),
        )

    missing_metric_result = {
        "config": {"top_k": 10},
        "results": [{"method": "tv_hybrid_rerank", "metrics": {"recall@10": 0.3}}],
    }
    with pytest.raises(ValueError, match="Missing metric full_support_recall@10 for method tv_hybrid_rerank"):
        build_report(
            rrf_result=base_result,
            rerank_result=missing_metric_result,
            diagnostics={
                "methods": {
                    "tv_hybrid": {
                        "candidate_recall_at_depth": 0.0,
                        "failure_buckets": {
                            "missing_candidate": 0,
                            "partial_candidate_support": 0,
                            "candidate_ranked_low": 0,
                            "success": 0,
                        },
                    }
                }
            },
            paired_summary={"queries": 5},
            rrf_path=Path("rrf.json"),
            rerank_path=Path("rerank.json"),
            diagnostics_path=Path("diag.json"),
        )


def test_build_report_raises_for_missing_diagnostics() -> None:
    rrf_result = {
        "config": {"top_k": 10},
        "results": [
            {
                "method": "tv_hybrid",
                "metrics": {
                    "full_support_recall@10": 0.1,
                    "recall@10": 0.2,
                    "mrr@10": 0.3,
                    "ndcg@10": 0.4,
                    "latency_p50_ms": 50,
                    "latency_p95_ms": 100,
                    "qps": 2.0,
                },
            }
        ],
    }
    rerank_result = {
        "config": {"top_k": 10},
        "results": [
            {
                "method": "tv_hybrid_rerank",
                "metrics": {
                    "full_support_recall@10": 0.2,
                    "recall@10": 0.3,
                    "mrr@10": 0.4,
                    "ndcg@10": 0.5,
                    "latency_p50_ms": 60,
                    "latency_p95_ms": 120,
                    "qps": 1.0,
                },
            }
        ],
    }

    with pytest.raises(ValueError, match="Missing diagnostics for method tv_hybrid"):
        build_report(
            rrf_result=rrf_result,
            rerank_result=rerank_result,
            diagnostics={"methods": {}},
            paired_summary={"queries": 5},
            rrf_path=Path("rrf.json"),
            rerank_path=Path("rerank.json"),
            diagnostics_path=Path("diag.json"),
        )

    with pytest.raises(ValueError, match="Missing diagnostics field failure_buckets.partial_candidate_support"):
        build_report(
            rrf_result=rrf_result,
            rerank_result=rerank_result,
            diagnostics={
                "methods": {
                    "tv_hybrid": {
                        "candidate_recall_at_depth": 0.0,
                        "failure_buckets": {"missing_candidate": 0},
                    }
                }
            },
            paired_summary={"queries": 5},
            rrf_path=Path("rrf.json"),
            rerank_path=Path("rerank.json"),
            diagnostics_path=Path("diag.json"),
        )
