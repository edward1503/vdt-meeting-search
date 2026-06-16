# Remove Legacy Search Methods Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove unused legacy Elasticsearch dense/hybrid methods from the Docker demo API and frontend while keeping TurboVec search and BM25 baseline available.

**Architecture:** The API should expose only `es_bm25`, `tv_dense`, `tv_hybrid`, and `tv_filtered_hybrid`. `es_bm25` remains because TurboVec hybrid still uses BM25 through the Elasticsearch retriever and it is useful as a lexical baseline. Frontend method menus and history actions should derive from the API-supported runtime and no longer advertise legacy ES dense/hybrid modes.

**Tech Stack:** FastAPI/Python retrieval API, React/TypeScript frontend, pytest, TypeScript compiler lint script, Harness CLI.

---

### Task 1: Backend Public Method Surface

**Files:**
- Modify: `tests/test_api_es_config.py`
- Modify: `src/api/main.py`

- [x] **Step 1: Write the failing backend tests**

Add assertions that `es_dense`, `es_hybrid`, and `es_iterative_hybrid` are absent from `main.METHODS`, absent from `/stats`, and rejected by `/search` with HTTP 400. Keep `es_bm25` and all `tv_*` methods asserted as supported.

- [x] **Step 2: Run focused pytest to verify RED**

Run: `python -m pytest tests/test_api_es_config.py -q`
Expected: tests fail because legacy ES methods are still exposed.

- [x] **Step 3: Remove legacy ES dense/hybrid methods from API**

Set `ES_METHODS = {"es_bm25"}` and `ES_METHOD_MAP = {"es_bm25": "bm25"}`. Leave the fallback ES routing in place so `es_bm25` still works.

- [x] **Step 4: Run focused pytest to verify GREEN**

Run: `python -m pytest tests/test_api_es_config.py tests/test_api_cache.py -q`
Expected: pass.

### Task 2: Frontend Method Surface

**Files:**
- Modify: `frontend/src/components/SearchView.tsx`
- Modify: `frontend/src/components/QueriesView.tsx`
- Modify: `frontend/src/lib/api.ts`

- [x] **Step 1: Remove legacy method labels/fallbacks**

Remove labels and fallback entries for `es_dense`, `es_hybrid`, and `es_iterative_hybrid`. Keep labels for `tv_hybrid`, `tv_dense`, `tv_filtered_hybrid`, and `es_bm25`.

- [x] **Step 2: Update query history rerun buttons**

Change history rerun default/action methods from `es_hybrid` and `es_iterative_hybrid` to `tv_hybrid` and `es_bm25` so the UI cannot submit removed methods.

- [x] **Step 3: Run frontend verification**

Run: `cd frontend; npm run lint`
Expected: pass.

### Task 3: Harness Evidence and Runtime Smoke

**Files:**
- Modify: `docs/stories/epics/E03-sprint3-turbovec/US-S3-014-docker-turbovec-runtime.md`

- [x] **Step 1: Record cleanup evidence**

Append a short note that the Docker runtime no longer exposes legacy ES dense/hybrid methods and list the supported methods.

- [x] **Step 2: Run runtime smoke if services are up**

Check `/stats` and one `tv_hybrid` search through `localhost:8001`. Confirm legacy method submission returns 400.

- [x] **Step 3: Run Harness story verify**

Run: `.\scripts\bin\harness-cli.exe story verify US-S3-014`
Expected: pass.

### Task 4: Commit

**Files:**
- Commit all intentional changes from Tasks 1-3.

- [x] **Step 1: Inspect diff**

Run: `git diff --stat` and `git diff --check`.

- [x] **Step 2: Commit**

Run: `git add ...` for touched files only, then `git commit -m "chore: remove legacy search methods"`.
