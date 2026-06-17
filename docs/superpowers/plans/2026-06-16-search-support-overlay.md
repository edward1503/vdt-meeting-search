# Search Support Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show whether Search results hit HotpotQA gold support documents without manually comparing doc IDs.

**Architecture:** Extend `/search` with an optional `query_id`, a `support` summary object, and per-result `is_support`. Use query-id qrels when available and fall back to exact query text matching for free-form searches. Frontend passes `query_id` from Queries/History presets when available and renders a compact support coverage panel plus result badges.

**Tech Stack:** FastAPI/Python API, React/TypeScript frontend, pytest, Vite TypeScript lint, Harness CLI.

---

### Task 1: Backend Search Contract

**Files:**
- Modify: `tests/test_api_es_config.py`
- Modify: `src/api/main.py`

- [x] **Step 1: Write failing tests**

Add tests that `find_support_doc_ids(query, query_id="q1")` returns qrels by id even when query text differs, and that `/search` responses contain `support` plus `is_support` flags.

- [x] **Step 2: Verify RED**

Run: `python -m pytest tests/test_api_es_config.py -q`
Expected: fail because `query_id`, `support`, and `is_support` are missing.

- [x] **Step 3: Implement minimal backend support overlay**

Add optional `query_id` to `SearchRequest`, include it in the Redis cache key, compute support summary before writing cache/history, and mark results whose `doc_id` appears in the support set.

- [x] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q`
Expected: pass.

### Task 2: Frontend Search UI

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/SearchView.tsx`
- Modify: `frontend/src/components/QueriesView.tsx`
- Modify: `frontend/src/components/HistoryView.tsx`

- [x] **Step 1: Update types and API client**

Add `queryId?: string`, `is_support?: boolean`, and `support` types. Let `searchHotpotQA` accept an optional query id and send `query_id` when present.

- [x] **Step 2: Pass query ids through page flows**

Queries page sends selected `query.id`. Search presets can carry query id from Query/History flows.

- [x] **Step 3: Render support overlay**

Search page displays `Gold Support: found/total`, `Recall@k`, missing support doc ids, and a `SUPPORT HIT` badge on result cards.

- [x] **Step 4: Verify frontend**

Run: `cd frontend; npm run lint`
Expected: pass.

### Task 3: Runtime Smoke and Harness Evidence

**Files:**
- Modify: `docs/stories/epics/E03-sprint3-turbovec/US-S3-014-docker-turbovec-runtime.md`

- [x] **Step 1: Runtime smoke**

Call Docker API `/search` with a known `query_id`, verify support summary is present, and verify at least support availability is surfaced.

- [x] **Step 2: Harness verify**

Run: `.\scripts\bin\harness-cli.exe story verify US-S3-014`
Expected: pass.

### Task 4: Commit

**Files:**
- Commit only files changed for this feature.

- [x] **Step 1: Diff check**

Run: `git diff --check` and inspect `git status --short`.

- [x] **Step 2: Commit**

Run: `git commit -m "feat: show search support coverage"`.
