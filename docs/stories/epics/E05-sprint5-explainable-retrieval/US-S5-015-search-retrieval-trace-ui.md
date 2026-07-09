# US-S5-015 Search Retrieval Trace UI

## Status

implemented

## Lane

normal

## Product Contract

The Search workspace should show how a query moved through the retrieval pipeline. After a search completes, the API response includes a structured `retrieval_trace`, and the UI renders a compact Search Pipeline panel with step labels, summaries, and elapsed milliseconds when available.

## Relevant Product Docs

- `docs/architecture/current-architecture.md`
- `docs/sprint5/multihop-retrieval-methods.md`

## Acceptance Criteria

- Search responses include `retrieval_trace` for runtime searches.
- TurboVec hybrid traces show metadata parsing, BM25, BGE query embedding, TurboVec dense search, RRF fusion, hydration, and support overlay.
- The Search UI renders a Retrieval Trace / Search Pipeline panel after a response and a pipeline skeleton while loading.
- Existing result cards, support overlay, metadata parsing, and search history continue to work.

## Design Notes

- API: build trace entries from the effective method, metadata execution plan, latency breakdown, and support summary.
- UI surfaces: `SearchView` renders `RetrievalTrace` above the result list and expands `SearchingIndicator` into a lightweight pipeline skeleton.
- Non-goal: live streaming status and intermediate BM25/dense candidate document lists remain future work.

## Validation

| Layer | Expected proof |
| --- | --- |
| Unit | `python -m pytest tests/test_api_es_config.py tests/test_search_ui_metadata.py tests/test_frontend_dataset_state.py -q` |
| Integration | Covered by API search tests with fake retrievers. |
| E2E | Not required for this narrow UI/API trace panel. |
| Platform | Frontend lint/tooling skipped because Harness has no present `frontend-lint` capability. |
| Release | Not required. |

## Harness Delta

No harness policy changes. Existing frontend-lint capability gap remains outside this story.

## Evidence

- RED backend proof: `python -m pytest tests/test_api_es_config.py::test_search_routes_turbovec_methods_to_turbovec_retriever -q` failed with `KeyError: 'retrieval_trace'`.
- RED UI proof: `python -m pytest tests/test_search_ui_metadata.py::test_search_view_renders_retrieval_trace_pipeline -q` failed because `RetrievalTrace` was absent.
- GREEN proof: `python -m pytest tests/test_api_es_config.py tests/test_search_ui_metadata.py tests/test_frontend_dataset_state.py -q` passed with 40 tests.
