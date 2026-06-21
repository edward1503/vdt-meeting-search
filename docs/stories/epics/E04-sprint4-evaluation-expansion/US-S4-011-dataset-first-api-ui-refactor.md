# US-S4-011 Dataset-First API and UI Runtime Refactor

## Status

planned

## Lane

high-risk

## Product Contract

The Docker demo can expose HotpotQA and VimQA as separate dataset workspaces from one API/frontend runtime. Users choose a dataset first, then use dataset-scoped Search, Queries, Benchmarks, Indexes, and Metadata views. Dataset separation is expressed through canonical endpoint namespaces such as `/datasets/hotpotqa/search` and `/datasets/vimqa/search`; Sprint 4 must not duplicate the UI or API service per dataset. The refactor must preserve existing HotpotQA legacy endpoints until the frontend has migrated.

## Relevant Product Docs

- `docs/sprint4/plan.md`
- `docs/superpowers/plans/2026-06-21-vimqa-data-before-api-refactor.md`
- `docs/architecture/current-architecture.md`
- `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-008-vimqa-benchmark-pipeline-research.md`

## Acceptance Criteria

- API exposes dataset profile discovery through `GET /datasets`.
- API exposes dataset-scoped stats, queries, search, and benchmark endpoints.
- HotpotQA and VimQA are queried through separate dataset namespaces under `/datasets/{dataset_id}/...`, while sharing one API process and one UI.
- `hotpotqa` and `vimqa` profiles declare their index, language, methods, default method, dense backend, embedding model, vector dims, and readiness state.
- Existing `/stats`, `/queries`, `/search`, and `/benchmark` endpoints remain compatible during migration.
- Search cache keys include dataset id, index, method, model, query, query id, and top-k.
- Frontend uses a dataset-first workspace model: choose dataset first, then navigate Search, Queries, Benchmarks, Indexes, and Metadata within that dataset.
- Frontend is query/read-only inspection oriented for this story; it must not add index management, metadata schema editing, or benchmark orchestration controls.
- VimQA benchmark UI emphasizes single-context retrieval metrics, not HotpotQA full-support metrics.
- Docker docs explain lightweight UI/API, search runtime, index/benchmark runtime, and full demo runtime.

## Design Notes

- Do this after `US-S4-008` has staged and benchmarked VimQA, so the API profiles can point at real artifacts.
- A single API process should serve multiple dataset profiles in the first implementation.
- Separate API containers or duplicated dataset-specific UI apps are a future option only if model/runtime isolation becomes necessary; they are out of Sprint 4 scope.
- The canonical endpoint shape is `/datasets/{dataset_id}/...`; do not add `/vimqa/search` or `/hotpotqa/search` aliases unless a future notebook or demo explicitly needs those shortcuts.
- Keep TurboVec scoped to HotpotQA unless a later VimQA scale-up requires it.
- Keep VimQA default retrieval method as `es_bm25` for the first dataset-first UI.
- Metadata filters fit the same dataset-scoped search request shape. HotpotQA can show metadata filters as supported; VimQA must show metadata filters as unsupported in Sprint 4.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-011 --unit 1 --integration 1 --e2e 1 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Dataset profile registry, cache key, and request-shape tests. |
| Integration | API tests for `/datasets`, `/datasets/{id}/stats`, `/datasets/{id}/queries`, `/datasets/{id}/search`, and `/datasets/{id}/benchmarks`. |
| E2E | Frontend dataset switcher smoke through Docker. |
| Platform | Docker runtime docs and smoke showing HotpotQA and VimQA profiles are visible. |
| Release | Not required. |

## Harness Delta

This story records the new follow-up created from the decision to process VimQA data/retrieval first, then refactor API/UI into dataset-first workspaces.

## Evidence

- 2026-06-21: Detailed implementation plan prepared for review at `docs/superpowers/plans/2026-06-21-dataset-first-api-ui-refactor.md`. Plan keeps the story in `planned` status, preserves legacy HotpotQA endpoint compatibility, adds explicit Indexes and Metadata workspace views, and defers implementation until human approval.
- 2026-06-21: Review decision captured: use one API process and one UI; expose HotpotQA/VimQA through `/datasets/{dataset_id}/...` endpoint namespaces; keep the UI query/read-only; keep VimQA default method as `es_bm25`; show VimQA metadata filters as unsupported.
- Planned implementation evidence still required: backend dataset/API/cache/history tests, frontend lint/typecheck, and Docker/API smoke when runtime indexes are available.
