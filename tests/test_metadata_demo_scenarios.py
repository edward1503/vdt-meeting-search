from __future__ import annotations

import json


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_metadata_demo_report_counts_filter_narrowing_and_hybrid_scope(tmp_path):
    from scripts.metadata_demo_scenarios import build_metadata_demo_report

    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "manifest.json").write_text(
        json.dumps(
            {
                "synthetic": True,
                "docs_written": 4,
                "metadata_fields": ["author", "created_at", "modified_at"],
                "embedding_text_policy": "unchanged content-only text; synthetic metadata is not embedded",
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        metadata_dir / "docs-00000.jsonl",
        [
            {"doc_id": "d1", "title": "Anarchism", "author": "Nguyen An", "created_at": "2024-01-01", "modified_at": "2024-01-02"},
            {"doc_id": "d2", "title": "Bridge", "author": "Nguyen An", "created_at": "2024-02-01", "modified_at": "2024-02-01"},
            {"doc_id": "d3", "title": "Calendar", "author": "Tran Binh", "created_at": "2024-01-15", "modified_at": "2024-01-20"},
            {"doc_id": "d4", "title": "Delta", "author": "Le Chau", "created_at": "2025-01-01", "modified_at": "2025-01-01"},
        ],
    )

    output_path = tmp_path / "scenario_summary.json"
    report = build_metadata_demo_report(
        metadata_dir=metadata_dir,
        output_path=output_path,
        scenarios=[
            {"name": "content_only", "mode": "content_only", "query": "Anarchism", "filters": {}},
            {"name": "author_filtered", "mode": "metadata_filtered", "query": "Anarchism", "filters": {"author": "Nguyen An"}},
            {
                "name": "metadata_content_hybrid",
                "mode": "metadata_content_hybrid",
                "query": "Anarchism",
                "method": "tv_hybrid",
                "filters": {"author": "Nguyen An", "created_at_from": "2024-01-01", "created_at_to": "2024-01-31"},
            },
        ],
    )

    assert report["synthetic"] is True
    assert report["baseline_docs"] == 4
    assert report["scenarios"][0]["matched_docs"] == 4
    assert report["scenarios"][1]["matched_docs"] == 2
    assert report["scenarios"][1]["narrowing_pct"] == 50.0
    assert report["scenarios"][2]["matched_docs"] == 1
    assert report["scenarios"][2]["effective_method"] == "tv_filtered_hybrid"
    assert report["scenarios"][2]["metadata_filter_scope"] == "hard_prefilter"
    assert report["scenarios"][2]["sample_results"][0]["doc_id"] == "d1"
    assert json.loads(output_path.read_text(encoding="utf-8")) == report


def test_metadata_demo_cli_writes_summary(tmp_path, monkeypatch, capsys):
    import scripts.metadata_demo_scenarios as cli

    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "manifest.json").write_text(json.dumps({"synthetic": True, "docs_written": 1}), encoding="utf-8")
    _write_jsonl(
        metadata_dir / "docs-00000.jsonl",
        [{"doc_id": "d1", "author": "Nguyen An", "created_at": "2024-01-01", "modified_at": "2024-01-02"}],
    )
    output_path = tmp_path / "summary.json"
    monkeypatch.setattr(
        "sys.argv",
        ["metadata_demo_scenarios.py", "--metadata-dir", str(metadata_dir), "--output", str(output_path)],
    )

    cli.main()

    assert output_path.exists()
    assert '"scenario_count"' in capsys.readouterr().out
