# VimQA Semantic Metadata Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing HotpotQA semantic metadata search contract to VimQA and document the algorithm.

**Architecture:** Reuse the same opt-in API contract: `semantic_metadata=true` produces an execution plan with original query, effective query, parsed metadata filters, and explanation chips. Add Vietnamese query frames to the deterministic parser and allow the VimQA dataset profile to pass metadata filters through the existing Elasticsearch metadata-aware retriever path. Keep metadata out of embeddings.

**Tech Stack:** Python/FastAPI/Pydantic backend, Elasticsearch retriever metadata filters, React/Vite existing UI, pytest, Harness story/matrix records.

---

## File Structure

- Modify `src/retrieval/metadata_query_parser.py`: add Vietnamese semantic metadata frames and author cues while preserving existing English behavior.
- Modify `src/api/dataset_profiles.py`: mark VimQA as metadata-filter capable now that `artifacts/vimqa/all/metadata` exists and the ES retriever path supports generic metadata filters.
- Modify `tests/test_metadata_query_parser.py`: add failing tests for Vietnamese VimQA-style semantic metadata queries.
- Modify `tests/test_semantic_metadata_api.py`: add failing dataset-scoped VimQA API test proving the same execution plan behavior as HotpotQA.
- Create `docs/sprint5/vimqa-semantic-metadata-search-report.md`: explain algorithm, data flow, limitations, and validation.
- Create `docs/stories/epics/E05-sprint5-explainable-retrieval/US-S5-007-vimqa-semantic-metadata-search.md`: story evidence.
- Update `docs/stories/epics/E05-sprint5-explainable-retrieval/README.md`: list the new story.

## Tasks

### Task 1: RED tests

- [ ] Add parser tests for `tài liệu về <topic> của <author> trước <date>` and `văn bản về <topic> bởi <author> sau <date>`.
- [ ] Add API test for `dataset_search("vimqa", SearchRequest(... semantic_metadata=True))` capturing effective query and metadata filters.
- [ ] Run `python -m pytest tests/test_metadata_query_parser.py tests/test_semantic_metadata_api.py -q` and confirm the new tests fail for missing VimQA behavior.

### Task 2: GREEN implementation

- [ ] Extend semantic prefix regex/cue handling for Vietnamese forms.
- [ ] Keep parsed output shape identical to HotpotQA: `content_query`, `metadata_filters`, `parsed_chips`, `warnings`.
- [ ] Set VimQA profile `supports_metadata_filters=True` so the same API/retriever path can run.
- [ ] Run the focused tests and confirm pass.

### Task 3: Docs and Harness

- [ ] Write the algorithm report describing parse-first search, filter construction, retrieval routing, explanation chips, and why metadata is not embedded.
- [ ] Add the US-S5-007 story and update the Sprint 5 epic README.
- [ ] Register/update Harness story proof.

### Task 4: Validation

- [ ] Run focused parser/API tests.
- [ ] Run related metadata tests if time permits.
- [ ] Run `git diff --check`.
- [ ] Record Harness trace with validation evidence.
