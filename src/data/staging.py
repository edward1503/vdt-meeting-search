from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from src.data.ingest_eda import make_ingest_content


def normalize_document(raw_doc: Any) -> dict[str, str]:
    doc_id = str(getattr(raw_doc, "doc_id"))
    title = _collapse(getattr(raw_doc, "title", "") or "")
    text = _collapse(getattr(raw_doc, "text", "") or "")
    url = str(getattr(raw_doc, "url", "") or "")
    content = make_ingest_content(title, text)
    return {
        "doc_id": doc_id,
        "title": title,
        "text": text,
        "url": url,
        "content": content,
        "embedding_text": content,
    }


def write_staging_shards(raw_docs: Iterable[Any], output_dir: Path, docs_per_file: int = 50_000) -> dict[str, int | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_written = 0
    files_written = 0
    current = None
    try:
        for raw_doc in raw_docs:
            if docs_written % docs_per_file == 0:
                if current is not None:
                    current.close()
                current = (output_dir / f"docs-{files_written:05d}.jsonl").open("w", encoding="utf-8")
                files_written += 1
            row = normalize_document(raw_doc)
            row["numeric_id"] = docs_written
            current.write(json.dumps(row, ensure_ascii=False) + "\n")
            docs_written += 1
    finally:
        if current is not None:
            current.close()
    manifest = {
        "docs_written": docs_written,
        "files_written": files_written,
        "docs_per_file": docs_per_file,
        "numeric_id_start": 0 if docs_written else None,
        "numeric_id_end": docs_written - 1 if docs_written else None,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_staging_manifest(staging_dir: Path) -> dict[str, Any]:
    manifest_path = staging_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"missing staging manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def validate_staging_manifest(staging_dir: Path, expected_docs: int | None = None) -> dict[str, Any]:
    manifest = load_staging_manifest(staging_dir)
    files = list(iter_staging_files(staging_dir))
    files_written = int(manifest.get("files_written", -1))
    if len(files) != files_written:
        raise ValueError(f"files_written={files_written} but found {len(files)} staging files")
    docs_written = int(manifest.get("docs_written", -1))
    if expected_docs is not None and docs_written != expected_docs:
        raise ValueError(f"docs_written={docs_written} but expected {expected_docs}")
    return manifest


def iter_staging_files(staging_dir: Path):
    yield from sorted(staging_dir.glob("docs-*.jsonl"))


def _collapse(value: str) -> str:
    return " ".join(str(value or "").split())
