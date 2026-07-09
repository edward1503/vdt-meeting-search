# US-S5-006 VimQA Synthetic Metadata Artifact

## Status

implemented

## Lane

normal

## Product Contract

VimQA has an offline synthetic metadata shard generated with the same rules used
for HotpotQA metadata experiments: each document receives deterministic
`author`, `created_at`, and `modified_at` fields while `embedding_text` remains
the original content-only text.

This story does not enable VimQA runtime metadata filters. Runtime filtering
requires a VimQA Elasticsearch index that has been rebuilt or ingested with the
metadata-enriched documents.

## Relevant Product Docs

- `docs/sprint5/plan.md`
- `docs/stories/epics/E05-sprint5-explainable-retrieval/README.md`
- `artifacts/vimqa/all/metadata/manifest.json`

## Acceptance Criteria

- VimQA synthetic metadata is generated from `artifacts/vimqa/all/staging` into
  `artifacts/vimqa/all/metadata`.
- The generated manifest records `docs_written=3623`, `files_written=1`, and
  metadata fields `author`, `created_at`, and `modified_at`.
- Metadata generation preserves Vietnamese `content` and keeps
  `embedding_text == content` so metadata does not pollute dense embeddings.
- Dataset profile behavior remains unchanged: VimQA metadata filters stay
  unsupported until a metadata-aware VimQA index exists.

## Design Notes

- Commands: `python scripts/generate_synthetic_metadata.py --staging-dir artifacts/vimqa/all/staging --output-dir artifacts/vimqa/all/metadata`
- Queries: none
- API: none
- Tables: none
- Domain rules: reuse `src.data.synthetic_metadata` deterministic author/date policy
- UI surfaces: none

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id <id> --unit 1 --integration 1 --e2e 0 --platform 0`.

| Layer | Expected proof |
| --- | --- |
| Unit | `python -m pytest tests/test_vimqa_synthetic_metadata.py tests/test_synthetic_metadata.py -q` |
| Integration | Artifact manifest matches VimQA staging shape and first row preserves content/embedding text. |
| E2E | Not applicable; runtime VimQA filter support is intentionally unchanged. |
| Platform | Local artifact exists under `artifacts/vimqa/all/metadata`. |
| Release | Not applicable. |

## Harness Delta

Added story coverage for the VimQA synthetic metadata artifact so Sprint 5 can
distinguish offline metadata evidence from runtime metadata filter support.

## Evidence

- Artifact: `artifacts/vimqa/all/metadata/docs-00000.jsonl`
- Manifest: `artifacts/vimqa/all/metadata/manifest.json`
- Manifest values: `docs_written=3623`, `files_written=1`, `metadata_fields=["author", "created_at", "modified_at"]`, `modified_docs=1283`, `unchanged_docs=2340`.
- Verification: `python -m pytest tests/test_vimqa_synthetic_metadata.py tests/test_synthetic_metadata.py -q` => 9 passed.
