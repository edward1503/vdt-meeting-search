from __future__ import annotations

import csv
import json
from pathlib import Path

from src.evaluation.openai_paraphrase_merge import merge_candidate_files


FIELDS = ["variant_query_id", "source_query_id", "paraphrase_profile", "paraphrased_query"]


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_merge_candidate_files_preserves_order_and_writes_jsonl(tmp_path: Path):
    original = tmp_path / "original.tsv"
    retry = tmp_path / "retry.tsv"
    output_tsv = tmp_path / "merged.tsv"
    output_jsonl = tmp_path / "merged.jsonl"
    _write(original, [{"variant_query_id": "q1__natural_mild__1", "source_query_id": "q1", "paraphrase_profile": "natural_mild", "paraphrased_query": "same"}])
    _write(retry, [{"variant_query_id": "q1__natural_mild__regen1", "source_query_id": "q1", "paraphrase_profile": "natural_mild", "paraphrased_query": "new wording"}])

    count = merge_candidate_files([original, retry], output_tsv, output_jsonl)

    assert count == 2
    with output_tsv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    assert [row["variant_query_id"] for row in rows] == ["q1__natural_mild__1", "q1__natural_mild__regen1"]
    jsonl_rows = [json.loads(line) for line in output_jsonl.read_text(encoding="utf-8").splitlines()]
    assert jsonl_rows[1]["paraphrased_query"] == "new wording"


def test_merge_candidate_files_skips_missing_optional_inputs(tmp_path: Path):
    original = tmp_path / "original.tsv"
    output_tsv = tmp_path / "merged.tsv"
    output_jsonl = tmp_path / "merged.jsonl"
    _write(original, [{"variant_query_id": "q1", "source_query_id": "q1", "paraphrase_profile": "natural_mild", "paraphrased_query": "query"}])

    count = merge_candidate_files([original, tmp_path / "missing.tsv"], output_tsv, output_jsonl)

    assert count == 1
