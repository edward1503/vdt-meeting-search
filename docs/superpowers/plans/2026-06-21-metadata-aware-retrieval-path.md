# Metadata-Aware Retrieval Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `US-S4-006` so search can filter and display synthetic `author`, `created_at`, and `modified_at` metadata through Elasticsearch BM25 and TurboVec filtered hybrid retrieval.

**Architecture:** Metadata is a structured hard filter, not embedding text. Elasticsearch stores metadata as `keyword`/`date` fields and applies filters in `bool.filter`; TurboVec filtered hybrid uses filtered BM25 hits as a numeric-id allowlist. API requests with metadata filters auto-route `tv_hybrid` to `tv_filtered_hybrid`, while `tv_dense` rejects filters in v1.

**Tech Stack:** Python 3, pytest, FastAPI/Pydantic, Elasticsearch Python client, TurboVec existing index, Harness CLI.

---

## Scope

Included:
- Optional metadata mapping for BM25 indexes: `author: keyword`, `created_at: date`, `modified_at: date`.
- BM25 ingest copies metadata fields from `artifacts/hotpotqa_full/metadata/` rows when present.
- BM25 query builder supports `author`, `created_at_from/to`, and `modified_at_from/to` filters.
- Search hit payloads include `author`, `created_at`, and `modified_at` when indexed.
- API `/search` accepts metadata filter fields and includes them in cache keys.
- `tv_hybrid` with filters uses `tv_filtered_hybrid` as the effective method.
- `tv_dense` with filters returns HTTP 400.
- Representative one-shard metadata Elasticsearch smoke proves filtered search works.

Excluded:
- No dashboard controls.
- No metadata demo report; that is `US-S4-007`.
- No dense embedding rebuild.
- No metadata appended to `content` or `embedding_text`.
- No `tv_two_hop_bridge_rrf` metadata support in this MVP.

## Current Workspace Note

At planning time, `src/retrieval/turbovec_retriever.py` and `tests/test_turbovec_retriever.py` already have unrelated working-tree modifications. Before implementation, inspect those files and preserve existing changes. Do not reset or overwrite them.

## Behavioral Contract

Metadata filter shape:

```json
{
  "author": "Nguyen An",
  "created_at_from": "2024-01-01",
  "created_at_to": "2024-01-31",
  "modified_at_from": "2024-01-01",
  "modified_at_to": "2024-02-15"
}
```

| Requested method | No metadata filters | With metadata filters |
| --- | --- | --- |
| `es_bm25` | BM25 over configured index | BM25 with `bool.filter` |
| `tv_dense` | Dense over full TurboVec index | HTTP 400 |
| `tv_hybrid` | Existing BM25 + dense RRF | Auto-route to `tv_filtered_hybrid` |
| `tv_filtered_hybrid` | Existing BM25 candidate allowlist | Filtered BM25 candidate allowlist |

If filtered BM25 returns no candidates, `tv_filtered_hybrid` returns `[]`. It must not fall back to full dense search because filters are hard constraints.

## Files

- Modify `src/retrieval/elasticsearch_retriever.py`.
- Modify `scripts/es_hotpotqa.py`.
- Modify `src/retrieval/turbovec_retriever.py`.
- Modify `src/api/main.py`.
- Modify `frontend/src/lib/api.ts` for types only.
- Modify `tests/test_elasticsearch_retriever.py`.
- Modify `tests/test_es_hotpotqa_cli.py`.
- Modify `tests/test_turbovec_retriever.py`.
- Modify `tests/test_api_es_config.py`.
- Modify `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-006-metadata-aware-retrieval-path.md` after proof exists.

---

### Task 1: Elasticsearch Mapping, Ingest, Query, and Hit Metadata

**Files:**
- Modify: `src/retrieval/elasticsearch_retriever.py`
- Modify: `tests/test_elasticsearch_retriever.py`

- [ ] **Step 1: Write failing tests**

Add tests for: `build_bm25_index_body(include_metadata=True)` contains `author` keyword and date fields; `bm25_bulk_action` copies metadata fields; `build_bm25_query(..., metadata_filters=...)` creates `bool.must` plus `bool.filter`; `ElasticsearchRetriever.search(..., metadata_filters=...)` passes filters and returns metadata from `_source`.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_elasticsearch_retriever.py -q`

Expected: fails because `include_metadata` and `metadata_filters` are unsupported.

- [ ] **Step 3: Implement support**

Add `METADATA_FIELDS`, `BM25_SOURCE_FIELDS`, `metadata_mapping_properties()`, and `build_metadata_filter_clauses()` in `src/retrieval/elasticsearch_retriever.py`. Change `build_bm25_index_body(shards=1, include_metadata=False)`, `bm25_bulk_action`, `build_bm25_query(query, top_k, metadata_filters=None)`, `ElasticsearchRetriever.search(..., metadata_filters=None)`, and `_search_body`.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_elasticsearch_retriever.py -q`

Expected: pass.

---

### Task 2: Elasticsearch CLI Metadata Flags

**Files:**
- Modify: `scripts/es_hotpotqa.py`
- Modify: `tests/test_es_hotpotqa_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add tests proving `create-bm25-index --metadata` creates metadata mappings and `search --author "Nguyen An" --created-at-from 2024-01-01` passes `metadata_filters` into `retriever.search`. Use fake `_client` and fake `ElasticsearchRetriever`; do not require Elasticsearch for unit tests.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_es_hotpotqa_cli.py -q`

Expected: fails because CLI flags are absent.

- [ ] **Step 3: Implement CLI flags**

Add `--metadata` to `create-bm25-index`; add `--author`, `--created-at-from`, `--created-at-to`, `--modified-at-from`, and `--modified-at-to` to `search`. Add `metadata_filters_from_args(args)` and pass the resulting dict to `retriever.search`.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_es_hotpotqa_cli.py tests/test_elasticsearch_retriever.py -q`

Expected: pass.

---

### Task 3: TurboVec Filtered Hybrid Metadata Threading

**Files:**
- Modify: `src/retrieval/turbovec_retriever.py`
- Modify: `tests/test_turbovec_retriever.py`

- [ ] **Step 1: Inspect existing dirty files**

Run: `git diff -- src/retrieval/turbovec_retriever.py tests/test_turbovec_retriever.py`

Read current edits and preserve them.

- [ ] **Step 2: Write failing tests**

Add tests proving: docstore hydration requests/returns metadata fields; `tv_filtered_hybrid` passes `metadata_filters` into BM25 retriever; metadata-filtered empty BM25 candidates return `[]` and do not call TurboVec dense search.

- [ ] **Step 3: Run RED**

Run: `python -m pytest tests/test_turbovec_retriever.py -q`

Expected: fails because metadata filters are not threaded and hydration excludes metadata.

- [ ] **Step 4: Implement threading**

Add metadata fields to docstore `_source`, copy them into hydrated docs, add `metadata_filters` to `TurboVecHybridRetriever.search`, pass filters to `_search_hybrid` and `_search_filtered_hybrid`, call BM25 retriever with `metadata_filters`, and return `[]` on empty allowlist when filters exist.

- [ ] **Step 5: Run GREEN**

Run: `python -m pytest tests/test_turbovec_retriever.py tests/test_elasticsearch_retriever.py -q`

Expected: pass.

---

### Task 4: API Request, Cache Key, Routing, and Result Payload

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api_es_config.py`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Write failing API tests**

Add tests proving: cache keys include metadata filters; `SearchRequest` accepts filter fields; `es_bm25` passes filters to ES retriever; `tv_dense` with filters raises HTTP 400; `tv_hybrid` with filters calls TV retriever as `tv_filtered_hybrid` and includes `requested_method`, `metadata_filter_scope`, and metadata result fields.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_api_es_config.py -q`

Expected: fails because request filters, routing, and cache key support are absent.

- [ ] **Step 3: Implement API support**

Add optional filter fields to `SearchRequest`; add `build_metadata_filters(request)`; add `effective_search_method(method, metadata_filters)`; include filters in `build_search_cache_key`; reject `tv_dense` with filters; use effective method for retrieval; include `requested_method` only when it differs; include `metadata_filters`, `metadata_filter_scope: "hard_prefilter"`, and metadata fields in result rows.

- [ ] **Step 4: Update frontend API types only**

In `frontend/src/lib/api.ts`, add optional `author`, `created_at`, `modified_at` to `SearchResult`, define `SearchFilters`, extend `SearchResponse`, and allow `searchHotpotQA(..., filters: SearchFilters = {})`. Do not add UI controls.

- [ ] **Step 5: Run GREEN**

Run: `python -m pytest tests/test_api_es_config.py tests/test_turbovec_retriever.py tests/test_elasticsearch_retriever.py -q`

Expected: pass.

---

### Task 5: Metadata Index Smoke

**Files:**
- Read: `artifacts/hotpotqa_full/metadata_smoke/`
- Create: `artifacts/hotpotqa_full/progress/metadata_smoke/`
- External service: Elasticsearch if available.

- [ ] **Step 1: Query Harness tool registry**

Run: `.\scripts\bin\harness-cli.exe query tools --capability service-runtime --status present`

If Docker/Elasticsearch is absent, skip integration smoke cleanly and record missing runtime as trace friction. Do not mark integration/platform proof complete without a smoke substitute.

- [ ] **Step 2: Create and ingest one-shard metadata index**

Run:

```powershell
python scripts/es_hotpotqa.py create-bm25-index --index hotpotqa_full_metadata_smoke_v1 --alias hotpotqa_full_metadata_current --metadata --reset
python scripts/es_hotpotqa.py ingest-bm25 --index hotpotqa_full_metadata_smoke_v1 --staging-dir artifacts/hotpotqa_full/metadata_smoke --progress-dir artifacts/hotpotqa_full/progress/metadata_smoke --max-files 1
python scripts/es_hotpotqa.py validate --index hotpotqa_full_metadata_current --expected-count 50000
```

Expected: index count is 50,000.

- [ ] **Step 3: Run filtered search smoke**

Run: `python scripts/es_hotpotqa.py search --index hotpotqa_full_metadata_current --method bm25 --query Anarchism --author "Nguyen An" --top-k 5`

Expected: command exits 0 and returned hits include `author: Nguyen An`.

---

### Task 6: Story, Harness, and Final Verification

**Files:**
- Modify: `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-006-metadata-aware-retrieval-path.md`

- [ ] **Step 1: Run final focused tests**

Run: `python -m pytest tests/test_elasticsearch_retriever.py tests/test_es_hotpotqa_cli.py tests/test_turbovec_retriever.py tests/test_api_es_config.py -q`

Expected: pass.

- [ ] **Step 2: Run adjacent API/cache tests**

Run: `python -m pytest tests/test_api_cache.py tests/test_search_history.py -q`

Expected: pass.

- [ ] **Step 3: Update story evidence**

Append a dated evidence bullet to `US-S4-006` with test commands, smoke index commands, and explicit note that dashboard controls were not implemented.

- [ ] **Step 4: Update durable story row**

If focused tests pass and metadata index smoke passes, run: `.\scripts\bin\harness-cli.exe story update --id US-S4-006 --status implemented --unit 1 --integration 1 --e2e 0 --platform 1`

Use `--e2e 1` only if dashboard/browser controls are implemented and verified, which this plan excludes.

- [ ] **Step 5: Record trace**

Read `docs/TRACE_SPEC.md`, inspect `git status --short`, then record a standard trace with intake id `83`, story `US-S4-006`, files read, files changed, verification commands, and any runtime friction.

## Final Verification Bundle

Before claiming completion, run:

```powershell
python -m pytest tests/test_elasticsearch_retriever.py tests/test_es_hotpotqa_cli.py tests/test_turbovec_retriever.py tests/test_api_es_config.py -q
python -m pytest tests/test_api_cache.py tests/test_search_history.py -q
.\scripts\bin\harness-cli.exe query matrix
git status --short
```

Expected:
- Unit/API focused tests pass.
- Adjacent cache/history tests pass.
- `US-S4-006` is implemented only after smoke proof exists or a documented runtime substitute is accepted.
- `US-S4-007` remains planned.
