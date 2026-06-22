from __future__ import annotations

import json
from pathlib import Path

from scripts.stage_vimqa import stage_vimqa


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def test_stage_vimqa_writes_staging_queries_qrels_and_manifest(tmp_path):
    train_path = tmp_path / "train_vimqa.json"
    test_path = tmp_path / "test_vimqa.json"
    output_dir = tmp_path / "artifacts"
    result_dir = tmp_path / "results"
    write_rows(train_path, [{"question": "Thủ đô Việt Nam?", "context": "Hà Nội là thủ đô Việt Nam.", "answer": "Hà Nội"}])
    write_rows(test_path, [{"question": "Việt Nam có thủ đô nào?", "context": "Hà Nội là thủ đô Việt Nam.", "answer": "Hà Nội"}])

    summary = stage_vimqa(
        train_path=train_path,
        test_path=test_path,
        staging_dir=output_dir / "staging",
        results_dir=result_dir,
        docs_per_file=100,
    )

    assert summary["documents"] == 1
    assert summary["queries"] == 2
    manifest = json.loads((output_dir / "staging" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "vimqa"
    first_doc = json.loads((output_dir / "staging" / "docs-00000.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert first_doc["numeric_id"] == 0
    assert first_doc["content"] == "Hà Nội là thủ đô Việt Nam."
    assert first_doc["source_split"] == "train,test"
    query_header = (result_dir / "vimqa_queries.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert query_header == "query_id\tsource_query_id\tquery\tsplit\tanswer"
    qrels_header = (result_dir / "vimqa_qrels.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert qrels_header == "query_id\tdoc_id\trelevance"
