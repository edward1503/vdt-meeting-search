from __future__ import annotations

import json
from collections import namedtuple

from src.data.staging import iter_staging_files, normalize_document, write_staging_shards


def test_normalize_document_builds_one_doc_one_embedding_text():
    raw_type = namedtuple("RawDoc", ["doc_id", "title", "text", "url"])
    row = normalize_document(raw_type("d1", " Ada ", " First\n programmer. ", "u"))

    assert row == {
        "doc_id": "d1",
        "title": "Ada",
        "text": "First programmer.",
        "url": "u",
        "content": "Ada\nFirst programmer.",
        "embedding_text": "Ada\nFirst programmer.",
    }


def test_write_staging_shards_creates_jsonl_cache(tmp_path):
    raw_type = namedtuple("RawDoc", ["doc_id", "title", "text", "url"])
    docs = [raw_type(str(idx), "T", f"body {idx}", "") for idx in range(5)]

    manifest = write_staging_shards(docs, tmp_path, docs_per_file=2)

    assert manifest == {"docs_written": 5, "files_written": 3, "docs_per_file": 2}
    files = list(iter_staging_files(tmp_path))
    assert [path.name for path in files] == ["docs-00000.jsonl", "docs-00001.jsonl", "docs-00002.jsonl"]
    first_row = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
    assert first_row["doc_id"] == "0"
