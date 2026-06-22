# Synthetic Metadata Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `US-S4-005` by generating deterministic synthetic `author`, `created_at`, and `modified_at` metadata artifacts for the full 5,233,329-document HotpotQA staging corpus.

**Architecture:** This is an offline artifact-generation task only. The generator reads existing staging JSONL shards line-by-line, writes enriched JSONL shards to a separate metadata directory, and records manifest statistics. It does not mutate source staging shards, does not append metadata to `content` or `embedding_text`, does not rebuild embeddings, and does not create or update an Elasticsearch index.

**Tech Stack:** Python 3, pytest, existing HotpotQA staging JSONL files, existing Harness CLI.

---

## Scope

This plan implements only `US-S4-005 Synthetic Meeting Metadata Generator`.

Included:
- Generate 128 realistic synthetic display authors.
- Generate deterministic `created_at` dates across 730 days starting `2024-01-01`.
- Generate deterministic `modified_at` dates where 35 percent of docs have `modified_at > created_at` by 1 to 44 days.
- Preserve all existing HotpotQA staging fields unchanged.
- Write smoke and full metadata artifacts under `artifacts/hotpotqa_full/metadata_smoke/` and `artifacts/hotpotqa_full/metadata/`.
- Update `US-S4-005` story evidence and Harness matrix after proof exists.

Excluded:
- No Elasticsearch mapping or ingest changes.
- No API `/search` changes.
- No TurboVec, dense, hybrid, or BM25 query-path changes.
- No dashboard controls.
- No paraphrase artifacts or Bridge-RRF files.

## File Structure

- Create `src/data/synthetic_metadata.py`: pure generation rules and JSONL shard writing.
- Create `scripts/generate_synthetic_metadata.py`: CLI wrapper for smoke and full artifact generation.
- Create `tests/test_synthetic_metadata.py`: unit tests for deterministic metadata, date rules, untouched content fields, shard writing, and manifest stats.
- Modify `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-005-synthetic-asr-meeting-metadata-generator.md`: final evidence after tests and artifact generation pass.

## Data Contract

Input row from `artifacts/hotpotqa_full/staging/docs-*.jsonl`:

```json
{
  "numeric_id": 42,
  "doc_id": "doc-alpha",
  "title": "Arthur's Magazine",
  "text": "Arthur's Magazine was an American literary periodical...",
  "url": "",
  "content": "Arthur's Magazine\nArthur's Magazine was an American literary periodical...",
  "embedding_text": "Arthur's Magazine\nArthur's Magazine was an American literary periodical..."
}
```

Output row in `artifacts/hotpotqa_full/metadata/docs-*.jsonl`:

```json
{
  "numeric_id": 42,
  "doc_id": "doc-alpha",
  "title": "Arthur's Magazine",
  "text": "Arthur's Magazine was an American literary periodical...",
  "url": "",
  "content": "Arthur's Magazine\nArthur's Magazine was an American literary periodical...",
  "embedding_text": "Arthur's Magazine\nArthur's Magazine was an American literary periodical...",
  "author": "Le Long",
  "created_at": "2024-02-12",
  "modified_at": "2024-02-12"
}
```

The original fields must remain equal after JSON parsing. Metadata is added as separate JSON fields only.

## Generation Rules

Use `numeric_id` as the stable seed when present. Fallback to the first 16 hex chars of `sha256(doc_id)` when `numeric_id` is missing.

```python
LAST_NAMES = ["Nguyen", "Tran", "Le", "Pham", "Hoang", "Phan", "Vu", "Vo"]
FIRST_NAMES = [
    "An", "Binh", "Chau", "Dat", "Giang", "Ha", "Hanh", "Hieu",
    "Huy", "Khanh", "Lan", "Linh", "Long", "Mai", "Minh", "Nam",
]
DISPLAY_AUTHORS = [f"{last} {first}" for last in LAST_NAMES for first in FIRST_NAMES]
```

This yields exactly 128 synthetic display names.

```python
seed = stable_document_seed(doc_id, numeric_id)
author = DISPLAY_AUTHORS[seed % len(DISPLAY_AUTHORS)]
created_at = date(2024, 1, 1) + timedelta(days=seed % 730)
if seed % 100 < 35:
    modified_at = created_at + timedelta(days=1 + ((seed // 100) % 44))
else:
    modified_at = created_at
```

Expected distribution on the full corpus:
- 128 authors.
- About 40,885 docs per author.
- `created_at` spans `2024-01-01` through `2025-12-30`.
- About 35 percent of docs have `modified_at > created_at`.
- About 65 percent of docs have `modified_at == created_at`.
- `modified_at` is never earlier than `created_at`.

---

### Task 1: Unit Tests for Metadata Rules

**Files:**
- Create: `tests/test_synthetic_metadata.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_synthetic_metadata.py` with:

```python
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
        {"numeric_id": 0, "doc_id": "d0", "title": "T0", "text": "Body 0", "url": "", "content": "T0\nBody 0", "embedding_text": "T0\nBody 0"},
        {"numeric_id": 35, "doc_id": "d35", "title": "T35", "text": "Body 35", "url": "", "content": "T35\nBody 35", "embedding_text": "T35\nBody 35"},
    ]
    (staging / "docs-00000.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    manifest = write_metadata_shards(staging, output)

    assert manifest["synthetic"] is True
    assert manifest["docs_written"] == 2
    assert manifest["files_written"] == 1
    assert manifest["metadata_fields"] == ["author", "created_at", "modified_at"]
    assert manifest["author_count"] == 128
    assert manifest["modified_docs"] == 1
    assert manifest["unchanged_docs"] == 1
    assert manifest["embedding_text_policy"] == "unchanged content-only text; synthetic metadata is not embedded"

    enriched_rows = [json.loads(line) for line in (output / "docs-00000.jsonl").read_text(encoding="utf-8").splitlines()]
    assert enriched_rows[0]["author"] == "Nguyen An"
    assert enriched_rows[0]["modified_at"] > enriched_rows[0]["created_at"]
    assert enriched_rows[1]["modified_at"] == enriched_rows[1]["created_at"]
    assert enriched_rows[0]["embedding_text"] == "T0\nBody 0"
    assert json.loads((output / "manifest.json").read_text(encoding="utf-8")) == manifest
```

- [ ] **Step 2: Run tests to verify they fail before implementation**

Run:

```powershell
python -m pytest tests/test_synthetic_metadata.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'src.data.synthetic_metadata'`.

---

### Task 2: Metadata Generator Module

**Files:**
- Create: `src/data/synthetic_metadata.py`
- Test: `tests/test_synthetic_metadata.py`

- [ ] **Step 1: Implement generator module**

Create `src/data/synthetic_metadata.py` with:

```python
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.data.staging import iter_staging_files

LAST_NAMES = ["Nguyen", "Tran", "Le", "Pham", "Hoang", "Phan", "Vu", "Vo"]
FIRST_NAMES = [
    "An", "Binh", "Chau", "Dat", "Giang", "Ha", "Hanh", "Hieu",
    "Huy", "Khanh", "Lan", "Linh", "Long", "Mai", "Minh", "Nam",
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
```

- [ ] **Step 2: Run focused tests**

Run:

```powershell
python -m pytest tests/test_synthetic_metadata.py -q
```

Expected: all tests pass.

---

### Task 3: CLI Wrapper

**Files:**
- Create: `scripts/generate_synthetic_metadata.py`
- Modify: `tests/test_synthetic_metadata.py`

- [ ] **Step 1: Add CLI dispatch test**

Append to `tests/test_synthetic_metadata.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails before CLI exists**

Run:

```powershell
python -m pytest tests/test_synthetic_metadata.py::test_generate_synthetic_metadata_cli_dispatches -q
```

Expected: fail with `ModuleNotFoundError: No module named 'scripts.generate_synthetic_metadata'`.

- [ ] **Step 3: Implement CLI**

Create `scripts/generate_synthetic_metadata.py` with:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.synthetic_metadata import write_metadata_shards


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic HotpotQA metadata shards")
    parser.add_argument("--staging-dir", type=Path, default=Path("artifacts/hotpotqa_full/staging"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/hotpotqa_full/metadata"))
    parser.add_argument("--max-files", type=int, default=None)
    args = parser.parse_args()

    manifest = write_metadata_shards(args.staging_dir, args.output_dir, max_files=args.max_files)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run unit tests**

Run:

```powershell
python -m pytest tests/test_synthetic_metadata.py -q
```

Expected: all tests pass.

---

### Task 4: Smoke Artifact Generation

**Files:**
- Read: `artifacts/hotpotqa_full/staging/`
- Create: `artifacts/hotpotqa_full/metadata_smoke/`

- [ ] **Step 1: Check Python tool availability through Harness**

Run:

```powershell
.\scripts\bin\harness-cli.exe query tools --capability benchmark --status present
```

Expected: Python is present. If not present, skip the smoke and record missing capability as Harness friction.

- [ ] **Step 2: Run one-shard smoke**

Run:

```powershell
python scripts/generate_synthetic_metadata.py --staging-dir artifacts/hotpotqa_full/staging --output-dir artifacts/hotpotqa_full/metadata_smoke --max-files 1
```

Expected: command exits 0 and prints manifest JSON with `synthetic: true`, `files_written: 1`, and positive `docs_written`.

- [ ] **Step 3: Inspect smoke manifest**

Run:

```powershell
Get-Content artifacts/hotpotqa_full/metadata_smoke/manifest.json
```

Expected: manifest includes `metadata_fields`, `author_count: 128`, `modified_docs`, `unchanged_docs`, and `embedding_text_policy`.

- [ ] **Step 4: Inspect a few smoke rows**

Run:

```powershell
Get-Content artifacts/hotpotqa_full/metadata_smoke/docs-00000.jsonl -TotalCount 3
```

Expected: each row has `author`, `created_at`, `modified_at`, and still has the original `embedding_text` field.

---

### Task 5: Full Artifact Generation

**Files:**
- Read: `artifacts/hotpotqa_full/staging/`
- Create: `artifacts/hotpotqa_full/metadata/`

- [ ] **Step 1: Run full corpus generation**

Run:

```powershell
python scripts/generate_synthetic_metadata.py --staging-dir artifacts/hotpotqa_full/staging --output-dir artifacts/hotpotqa_full/metadata
```

Expected: command exits 0 and writes `docs-00000.jsonl` through `docs-00104.jsonl` plus `manifest.json` when the full staging artifact is present.

- [ ] **Step 2: Verify full manifest**

Run:

```powershell
Get-Content artifacts/hotpotqa_full/metadata/manifest.json
```

Expected values:
- `synthetic = true`
- `docs_written = 5233329`
- `files_written = 105`
- `author_count = 128`
- `metadata_fields = ["author", "created_at", "modified_at"]`
- `embedding_text_policy = unchanged content-only text; synthetic metadata is not embedded`

- [ ] **Step 3: Count output shards**

Run:

```powershell
(Get-ChildItem artifacts/hotpotqa_full/metadata/docs-*.jsonl | Measure-Object).Count
```

Expected: `105`.

---

### Task 6: Story and Harness Closeout

**Files:**
- Modify: `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-005-synthetic-asr-meeting-metadata-generator.md`

- [ ] **Step 1: Append story evidence**

Add this evidence bullet, replacing counts only if the actual manifest differs because the local staging artifact is incomplete:

```markdown
- 2026-06-20: Added deterministic synthetic metadata artifact generation for `author`, `created_at`, and `modified_at` using 128 realistic synthetic display authors and a 35 percent modified-date rule. The generator writes separate metadata shards and preserves `content` plus `embedding_text` unchanged. Proof: `python -m pytest tests/test_synthetic_metadata.py -q` passed. Smoke artifact: `artifacts/hotpotqa_full/metadata_smoke/manifest.json`. Full artifact: `artifacts/hotpotqa_full/metadata/manifest.json` with `docs_written=5233329`, `files_written=105`, `synthetic=true`, and `author_count=128`.
```

- [ ] **Step 2: Update durable story row**

Run only after tests and artifact proof exist:

```powershell
.\scripts\bin\harness-cli.exe story update --id US-S4-005 --status implemented --unit 1 --integration 0 --e2e 0 --platform 1
```

- [ ] **Step 3: Record trace**

Read `docs/TRACE_SPEC.md` and inspect `git status --short`, then run:

```powershell
.\scripts\bin\harness-cli.exe trace --summary "Implemented Sprint 4 synthetic metadata artifact generation" --story US-S4-005 --agent codex --outcome completed --actions "added synthetic metadata tests,implemented metadata generator,added CLI,ran unit tests,generated smoke and full artifacts,updated story evidence" --read "docs/sprint4/plan.md,docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-005-synthetic-asr-meeting-metadata-generator.md,src/data/staging.py,docs/TRACE_SPEC.md" --changed "src/data/synthetic_metadata.py,scripts/generate_synthetic_metadata.py,tests/test_synthetic_metadata.py,docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-005-synthetic-asr-meeting-metadata-generator.md,artifacts/hotpotqa_full/metadata_smoke/manifest.json,artifacts/hotpotqa_full/metadata/manifest.json" --friction "none"
```

---

## Final Verification Bundle

Before claiming completion, run:

```powershell
python -m pytest tests/test_synthetic_metadata.py -q
python scripts/generate_synthetic_metadata.py --staging-dir artifacts/hotpotqa_full/staging --output-dir artifacts/hotpotqa_full/metadata_smoke --max-files 1
python scripts/generate_synthetic_metadata.py --staging-dir artifacts/hotpotqa_full/staging --output-dir artifacts/hotpotqa_full/metadata
.\scripts\bin\harness-cli.exe query matrix
git status --short
```

Expected:
- Unit tests pass.
- Smoke artifact exists.
- Full metadata artifact exists with 105 shards and 5,233,329 docs.
- `US-S4-005` is implemented in the Harness matrix only after proof exists.
- No Elasticsearch, API, TurboVec, benchmark, or paraphrase files were edited for this story.

## Handoff to Search Pipeline Work

After this plan is complete, `US-S4-006` should get a separate implementation plan for:
- Metadata-aware Elasticsearch mapping and ingest.
- API metadata filter fields and cache keys.
- `tv_hybrid` plus metadata filter auto-routing to `tv_filtered_hybrid`.
- `tv_dense` filter rejection.
- Filter correctness and latency smoke tests.
