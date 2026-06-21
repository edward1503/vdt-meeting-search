from __future__ import annotations

from pathlib import Path


def test_vimqa_benchmark_dashboard_uses_full_query_config_and_all_methods() -> None:
    from src.api import main
    from src.api.dataset_profiles import get_dataset_profile

    payload = main.build_dataset_benchmark_dashboard(get_dataset_profile("vimqa"))
    current = payload["current"]

    assert current["config"]["queries"] == 9044
    assert current["config"]["methods"] == ["es_bm25", "es_dense", "es_hybrid"]
    assert current["config"]["benchmark_scope"] == "Full VimQA query set with 9,044 labeled queries"
    assert [row["method"] for row in current["results"]] == ["es_bm25", "es_dense", "es_hybrid"]


def test_vimqa_stats_exposes_full_benchmark_query_count() -> None:
    from src.api import main

    payload = main.dataset_stats("vimqa")

    assert payload["benchmark_query_count"] == 9044


def test_benchmark_view_has_vimqa_specific_protocol_copy() -> None:
    source = Path("frontend/src/components/BenchmarkView.tsx").read_text(encoding="utf-8")

    assert "protocolRows" in source
    assert "Full VimQA query set" in source
    assert "9,044 labeled queries" in source
    assert "full beir/hotpotqa/test" in source


def test_status_view_uses_dataset_benchmark_count_instead_of_hardcoded_cases() -> None:
    source = Path("frontend/src/components/StatusView.tsx").read_text(encoding="utf-8")

    assert "benchmark_query_count" in source
    assert 'value="50" unit="cases"' not in source
