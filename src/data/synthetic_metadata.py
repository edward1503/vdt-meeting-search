from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.data.staging import iter_staging_files

LAST_NAMES = ["Nguyen", "Tran", "Le", "Pham", "Hoang", "Phan", "Vu", "Vo"]
FIRST_NAMES = [
    "An",
    "Binh",
    "Chau",
    "Dat",
    "Giang",
    "Ha",
    "Hanh",
    "Hieu",
    "Huy",
    "Khanh",
    "Lan",
    "Linh",
    "Long",
    "Mai",
    "Minh",
    "Nam",
]
DISPLAY_AUTHORS = [f"{last} {first}" for last in LAST_NAMES for first in FIRST_NAMES]
METADATA_FIELDS = ["author", "created_at", "modified_at"]
BASE_DATE = date(2024, 1, 1)
CREATED_DAY_SPAN = 730
MODIFIED_PERCENT = 35
MAX_MODIFIED_OFFSET_DAYS = 44


def stable_document_seed(doc_id: str, numeric_id: int | str | None = None) -> int:
    if numeric_id is not None and str(numeric_id).strip() != "":
        return int(numeric_id)
    digest = hashlib.sha256(str(doc_id).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def generate_metadata(doc_id: str, numeric_id: int | str | None = None) -> dict[str, str]:
    seed = stable_document_seed(doc_id, numeric_id)
    created_at = BASE_DATE + timedelta(days=seed % CREATED_DAY_SPAN)
    if seed % 100 < MODIFIED_PERCENT:
        modified_at = created_at + timedelta(days=1 + ((seed // 100) % MAX_MODIFIED_OFFSET_DAYS))
    else:
        modified_at = created_at
    return {
        "author": DISPLAY_AUTHORS[seed % len(DISPLAY_AUTHORS)],
        "created_at": created_at.isoformat(),
        "modified_at": modified_at.isoformat(),
    }


def enrich_staging_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = generate_metadata(doc_id=str(row.get("doc_id", "")), numeric_id=row.get("numeric_id"))
    return {**row, **metadata}


def write_metadata_shards(staging_dir: Path, output_dir: Path, max_files: int | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_written = 0
    files_written = 0
    modified_docs = 0
    unchanged_docs = 0
    min_created_at: str | None = None
    max_created_at: str | None = None
    min_modified_at: str | None = None
    max_modified_at: str | None = None

    source_files = list(iter_staging_files(staging_dir))
    if max_files is not None:
        source_files = source_files[:max_files]

    for source_path in source_files:
        target_path = output_dir / source_path.name
        file_docs = 0
        with source_path.open("r", encoding="utf-8") as source, target_path.open("w", encoding="utf-8") as target:
            for line in source:
                if not line.strip():
                    continue
                enriched = enrich_staging_row(json.loads(line))
                target.write(json.dumps(enriched, ensure_ascii=False) + "\n")
                docs_written += 1
                file_docs += 1

                created_at = str(enriched["created_at"])
                modified_at = str(enriched["modified_at"])
                min_created_at = created_at if min_created_at is None else min(min_created_at, created_at)
                max_created_at = created_at if max_created_at is None else max(max_created_at, created_at)
                min_modified_at = modified_at if min_modified_at is None else min(min_modified_at, modified_at)
                max_modified_at = modified_at if max_modified_at is None else max(max_modified_at, modified_at)
                if modified_at > created_at:
                    modified_docs += 1
                else:
                    unchanged_docs += 1
        if file_docs:
            files_written += 1

    manifest = {
        "synthetic": True,
        "source_staging_dir": str(staging_dir),
        "docs_written": docs_written,
        "files_written": files_written,
        "metadata_fields": METADATA_FIELDS,
        "author_count": len(DISPLAY_AUTHORS),
        "author_policy": "128 realistic synthetic display names generated from Vietnamese-style last/first name combinations; not real HotpotQA metadata",
        "created_at_policy": "deterministic date spread over 730 days from 2024-01-01",
        "modified_at_policy": "35 percent of documents have modified_at later than created_at by 1 to 44 days",
        "embedding_text_policy": "unchanged content-only text; synthetic metadata is not embedded",
        "modified_docs": modified_docs,
        "unchanged_docs": unchanged_docs,
        "min_created_at": min_created_at,
        "max_created_at": max_created_at,
        "min_modified_at": min_modified_at,
        "max_modified_at": max_modified_at,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
