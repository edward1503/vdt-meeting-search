from __future__ import annotations

import json
from pathlib import Path


def test_ranking_diagnostics_buckets_missing_and_low_ranked_candidates(tmp_path: Path) -> None:
    from scripts.ranking_diagnostics import analyze_runs, load_qrels_tsv, load_trec_run

    qrels_path = tmp_path / "queries.tsv"
    qrels_path.write_text(
        "query_id\tquery\tsupport_doc_ids\n"
        "q1\talpha\td1,d2\n"
        "q2\tbeta\td9\n",
        encoding="utf-8",
    )
    run_path = tmp_path / "toy.trec"
    run_path.write_text(
        "q1 Q0 d3 1 3.0 tv_hybrid\n"
        "q1 Q0 d1 2 2.0 tv_hybrid\n"
        "q1 Q0 d2 4 1.0 tv_hybrid\n"
        "q2 Q0 d1 1 3.0 tv_hybrid\n",
        encoding="utf-8",
    )

    qrels = load_qrels_tsv(qrels_path)
    run = load_trec_run(run_path)
    analysis = analyze_runs(qrels, {"tv_hybrid": run}, target_k=2, candidate_depth=4)

    method = analysis["methods"]["tv_hybrid"]
    assert method["queries"] == 2
    assert method["full_support_at_k"] == 0.0
    assert method["candidate_recall_at_depth"] == 0.5
    assert method["failure_buckets"] == {
        "candidate_ranked_low": 1,
        "missing_candidate": 1,
        "partial_candidate_support": 0,
        "success": 0,
    }
    assert analysis["per_query"]["q1"]["tv_hybrid"]["bucket"] == "candidate_ranked_low"
    assert analysis["per_query"]["q2"]["tv_hybrid"]["bucket"] == "missing_candidate"


def test_ranking_diagnostics_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    import subprocess

    qrels_path = tmp_path / "queries.tsv"
    qrels_path.write_text("query_id\tquery\tsupport_doc_ids\nq1\talpha\td1\n", encoding="utf-8")
    run_path = tmp_path / "toy.trec"
    run_path.write_text("q1 Q0 d1 1 1.0 es_bm25\n", encoding="utf-8")
    output_path = tmp_path / "diagnostics.json"
    report_path = tmp_path / "report.md"

    result = subprocess.run(
        [
            "python",
            "scripts/ranking_diagnostics.py",
            "--qrels-tsv",
            str(qrels_path),
            "--run",
            f"es_bm25={run_path}",
            "--target-k",
            "1",
            "--candidate-depth",
            "1",
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["methods"]["es_bm25"]["failure_buckets"]["success"] == 1
    report = report_path.read_text(encoding="utf-8")
    assert "# Sprint 5 Ranking Diagnostics" in report
    assert "es_bm25" in report
