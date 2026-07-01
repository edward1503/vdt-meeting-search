from __future__ import annotations

import json
from pathlib import Path


def test_vimqa_synthetic_metadata_artifact_matches_staging_shape() -> None:
    metadata_dir = Path("artifacts/vimqa/all/metadata")
    manifest = json.loads((metadata_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["synthetic"] is True
    assert manifest["source_staging_dir"].replace("\\", "/") == "artifacts/vimqa/all/staging"
    assert manifest["docs_written"] == 3623
    assert manifest["files_written"] == 1
    assert manifest["metadata_fields"] == ["author", "created_at", "modified_at"]
    assert manifest["author_count"] == 128
    assert manifest["embedding_text_policy"] == "unchanged content-only text; synthetic metadata is not embedded"


def test_vimqa_synthetic_metadata_preserves_vietnamese_content_text() -> None:
    row = json.loads(Path("artifacts/vimqa/all/metadata/docs-00000.jsonl").read_text(encoding="utf-8").splitlines()[0])

    assert row["doc_id"].startswith("vimqa_ctx_")
    assert row["numeric_id"] == 0
    assert row["author"] == "Nguyen An"
    assert row["created_at"] == "2024-01-01"
    assert row["modified_at"] == "2024-01-02"
    assert row["embedding_text"] == row["content"]
    assert "điện ảnh" in row["content"]
