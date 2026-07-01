from __future__ import annotations

import json
from datetime import date

from src.data.synthetic_metadata import (
    DISPLAY_AUTHORS,
    enrich_staging_row,
    generate_metadata,
    stable_document_seed,
    write_metadata_shards,
)


def test_display_authors_has_128_realistic_synthetic_names():
    assert len(DISPLAY_AUTHORS) == 128
    assert len(set(DISPLAY_AUTHORS)) == 128
    assert DISPLAY_AUTHORS[0] == "Nguyen An"
    assert DISPLAY_AUTHORS[15] == "Nguyen Nam"
    assert DISPLAY_AUTHORS[16] == "Tran An"
    assert DISPLAY_AUTHORS[127] == "Vo Nam"


def test_stable_document_seed_prefers_numeric_id_and_falls_back_to_doc_id_hash():
    assert stable_document_seed("doc-alpha", 42) == 42
    assert stable_document_seed("doc-alpha", "42") == 42
    assert stable_document_seed("doc-alpha", None) == stable_document_seed("doc-alpha", "")
    assert stable_document_seed("doc-alpha", None) != stable_document_seed("doc-beta", None)


def test_generate_metadata_is_deterministic_and_date_ordered():
    first = generate_metadata(doc_id="doc-alpha", numeric_id=42)
    second = generate_metadata(doc_id="doc-alpha", numeric_id="42")

    assert first == second
    assert first == {
        "author": DISPLAY_AUTHORS[42],
        "created_at": "2024-02-12",
        "modified_at": "2024-02-12",
    }
    assert date.fromisoformat(first["modified_at"]) >= date.fromisoformat(first["created_at"])


def test_generate_metadata_modifies_35_percent_of_numeric_id_sample():
    rows = [generate_metadata(doc_id=f"d{idx}", numeric_id=idx) for idx in range(10_000)]
    modified = sum(1 for row in rows if row["modified_at"] > row["created_at"])

    assert modified == 3_500


def test_enrich_staging_row_preserves_content_and_embedding_text():
    row = {
        "numeric_id": 42,
        "doc_id": "doc-alpha",
        "title": "Arthur's Magazine",
        "text": "Body",
        "url": "",
        "content": "Arthur's Magazine\nBody",
        "embedding_text": "Arthur's Magazine\nBody",
    }

    enriched = enrich_staging_row(row)

    assert enriched["doc_id"] == row["doc_id"]
    assert enriched["numeric_id"] == row["numeric_id"]
    assert enriched["title"] == row["title"]
    assert enriched["text"] == row["text"]
    assert enriched["url"] == row["url"]
    assert enriched["content"] == row["content"]
    assert enriched["embedding_text"] == row["embedding_text"]
    assert enriched["author"] == DISPLAY_AUTHORS[42]
    assert enriched["created_at"] == "2024-02-12"
    assert enriched["modified_at"] == "2024-02-12"


def test_write_metadata_shards_writes_enriched_rows_and_manifest(tmp_path):
    staging = tmp_path / "staging"
    output = tmp_path / "metadata"
    staging.mkdir()
    rows = [
        {
            "numeric_id": 0,
            "doc_id": "d0",
            "title": "T0",
            "text": "Body 0",
            "url": "",
            "content": "T0\nBody 0",
            "embedding_text": "T0\nBody 0",
        },
        {
            "numeric_id": 35,
            "doc_id": "d35",
            "title": "T35",
            "text": "Body 35",
            "url": "",
            "content": "T35\nBody 35",
            "embedding_text": "T35\nBody 35",
        },
    ]
    (staging / "docs-00000.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )

    manifest = write_metadata_shards(staging, output)

    assert manifest["synthetic"] is True
    assert manifest["docs_written"] == 2
    assert manifest["files_written"] == 1
    assert manifest["metadata_fields"] == ["author", "created_at", "modified_at"]
    assert manifest["author_count"] == 128
    assert manifest["author_policy"].endswith("not real dataset metadata")
    assert manifest["modified_docs"] == 1
    assert manifest["unchanged_docs"] == 1
    assert manifest["embedding_text_policy"] == "unchanged content-only text; synthetic metadata is not embedded"

    enriched_rows = [
        json.loads(line) for line in (output / "docs-00000.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert enriched_rows[0]["author"] == "Nguyen An"
    assert enriched_rows[0]["modified_at"] > enriched_rows[0]["created_at"]
    assert enriched_rows[1]["modified_at"] == enriched_rows[1]["created_at"]
    assert enriched_rows[0]["embedding_text"] == "T0\nBody 0"
    assert json.loads((output / "manifest.json").read_text(encoding="utf-8")) == manifest


def test_generate_synthetic_metadata_cli_dispatches(monkeypatch, tmp_path, capsys):
    import scripts.generate_synthetic_metadata as cli

    captured = {}

    def fake_write_metadata_shards(staging_dir, output_dir, max_files=None):
        captured.update({"staging_dir": staging_dir, "output_dir": output_dir, "max_files": max_files})
        return {"synthetic": True, "docs_written": 2, "files_written": 1}

    monkeypatch.setattr(cli, "write_metadata_shards", fake_write_metadata_shards)
    monkeypatch.setattr(
        "sys.argv",
        [
            "generate_synthetic_metadata.py",
            "--staging-dir",
            str(tmp_path / "staging"),
            "--output-dir",
            str(tmp_path / "metadata"),
            "--max-files",
            "1",
        ],
    )

    cli.main()

    assert captured == {"staging_dir": tmp_path / "staging", "output_dir": tmp_path / "metadata", "max_files": 1}
    assert '"docs_written": 2' in capsys.readouterr().out
