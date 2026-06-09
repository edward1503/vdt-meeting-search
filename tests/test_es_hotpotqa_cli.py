from __future__ import annotations

from pathlib import Path

import scripts.es_hotpotqa as cli
from scripts.es_hotpotqa import done_marker_path, select_pending_files


def test_done_marker_path_uses_staging_file_stem(tmp_path):
    assert done_marker_path(tmp_path, Path("docs-00042.jsonl")) == tmp_path / "docs-00042.done"


def test_select_pending_files_skips_done_markers_and_applies_limit(tmp_path):
    staging = tmp_path / "staging"
    progress = tmp_path / "progress"
    staging.mkdir()
    progress.mkdir()
    for name in ["docs-00000.jsonl", "docs-00001.jsonl", "docs-00002.jsonl"]:
        (staging / name).write_text("{}\n", encoding="utf-8")
    (progress / "docs-00000.done").write_text("{}", encoding="utf-8")

    selected = select_pending_files(staging, progress, max_files=1)

    assert [path.name for path in selected] == ["docs-00001.jsonl"]


def test_main_dispatches_ingest_subcommand(monkeypatch, tmp_path):
    called = {}

    def fake_ingest(args):
        called["command"] = args.command

    monkeypatch.setattr(cli, "ingest", fake_ingest)
    monkeypatch.setattr(
        "sys.argv",
        ["es_hotpotqa.py", "ingest", "--staging-dir", str(tmp_path), "--progress-dir", str(tmp_path)],
    )

    cli.main()

    assert called == {"command": "ingest"}
