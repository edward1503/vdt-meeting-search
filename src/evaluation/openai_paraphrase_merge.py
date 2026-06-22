from __future__ import annotations

import csv
import json
from pathlib import Path


def merge_candidate_files(input_paths: list[Path], output_tsv: Path, output_jsonl: Path) -> int:
    rows: list[dict[str, str]] = []
    fieldnames: list[str] = []
    for path in input_paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            if reader.fieldnames and not fieldnames:
                fieldnames = list(reader.fieldnames)
            for row in reader:
                rows.append(dict(row))

    if not fieldnames and rows:
        fieldnames = list(rows[0].keys())
    output_tsv.parent.mkdir(parents=True, exist_ok=True)
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    with output_tsv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    output_jsonl.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return len(rows)
