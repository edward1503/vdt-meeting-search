from __future__ import annotations

from pathlib import Path

from scripts.semantic_metadata_eval import build_semantic_queries, compare_semantic_runs


def test_build_semantic_queries_from_metadata_rows(tmp_path: Path) -> None:
    rows = [
        {
            "doc_id": "d1",
            "title": "Anarchism",
            "text": "Anarchism history",
            "author": "Nguyen An",
            "created_at": "2024-01-10",
            "modified_at": "2024-01-12",
        },
        {
            "doc_id": "d2",
            "title": "Ozone",
            "text": "Ozone chemistry",
            "author": "Tran Binh",
            "created_at": "2024-02-10",
            "modified_at": "2024-02-20",
        },
    ]
    queries = build_semantic_queries(rows, limit=2)

    assert queries[0]["query"].startswith("find documents about Anarchism by Nguyen An")
    assert queries[0]["content_query"] == "Anarchism"
    assert queries[0]["metadata_filters"]["author"] == "Nguyen An"
    assert queries[0]["relevant_doc_ids"] == ["d1"]


def test_compare_semantic_runs_reports_expected_settings(tmp_path: Path) -> None:
    queries = [{"query_id": "smq1", "relevant_doc_ids": ["d1"]}]
    runs = {
        "content_only_original": {"smq1": ["d2"]},
        "manual_filter": {"smq1": ["d1"]},
        "parsed_metadata": {"smq1": ["d1"]},
    }

    summary = compare_semantic_runs(queries, runs, top_k=1)

    assert summary["content_only_original"]["recall@1"] == 0.0
    assert summary["manual_filter"]["recall@1"] == 1.0
    assert summary["parsed_metadata"]["recall@1"] == 1.0
