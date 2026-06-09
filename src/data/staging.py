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


def write_staging_shards(raw_docs: Iterable[Any], output_dir: Path, docs_per_file: int = 50_000) -> dict[str, int]:
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
            current.write(json.dumps(normalize_document(raw_doc), ensure_ascii=False) + "\n")
            docs_written += 1
    finally:
        if current is not None:
            current.close()
    manifest = {"docs_written": docs_written, "files_written": files_written, "docs_per_file": docs_per_file}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def iter_staging_files(staging_dir: Path):
    yield from sorted(staging_dir.glob("docs-*.jsonl"))


def _collapse(value: str) -> str:
    return " ".join(str(value or "").split())
