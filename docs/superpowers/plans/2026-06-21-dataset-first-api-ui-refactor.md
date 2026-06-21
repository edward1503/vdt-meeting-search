# Dataset-First API And UI Runtime Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `US-S4-011`: one FastAPI/React runtime where users choose a dataset workspace (`hotpotqa` or `vimqa`) first, then use dataset-scoped Search, Queries, Benchmarks, Indexes, Metadata, Status, and History without breaking legacy HotpotQA endpoints.

**Architecture:** Add a backend dataset profile registry as the source of truth for dataset ids, indexes, methods, query/qrels files, benchmark artifacts, and runtime readiness. Expose canonical dataset namespaces under `/datasets/{dataset_id}/...`, so VimQA and HotpotQA are queried through separate endpoint paths without duplicating API services or UI code. Refactor the frontend around an `activeDatasetId` state and dataset-scoped API client methods, preserving the existing views while changing their data source and dataset-specific labels.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, Elasticsearch retrievers, Redis cache, React 19, Vite, TypeScript, lucide icons, Docker Compose, Harness CLI.

---

## Scope Check

This plan covers one high-risk story with two tightly coupled subsystems:

1. Dataset-scoped backend API contract.
2. Dataset-first frontend workspace.

The work is kept as a single plan because the frontend cannot be meaningfully completed without the new backend contract, and the backend acceptance criteria require frontend migration proof. VimQA data activation is already complete in `US-S4-008`; this plan does not restage or rebenchmark VimQA.

Approved scope boundaries from review:

- Use one API process and one React UI. Do not create separate HotpotQA/VimQA services, Docker profiles, or duplicated UI apps in Sprint 4.
- Treat `/datasets/vimqa/...` and `/datasets/hotpotqa/...` as the dataset-specific endpoint surfaces. Do not add extra `/vimqa/search` or `/hotpotqa/search` aliases unless a later demo/notebook specifically needs them.
- Keep the UI as a query and inspection surface only. Do not add index create/delete/rebuild buttons, mapping editors, metadata schema editors, or benchmark orchestration controls.
- Keep VimQA default search method as `es_bm25`.
- Show VimQA metadata filters as unsupported in the UI; search, queries, benchmark, indexes, history, and status still work for VimQA.

## Approved User Flow

### Initial Load

The frontend calls `GET /datasets` once during app startup and stores the returned dataset profiles. The selected dataset lives in `activeDatasetId`; default is `hotpotqa` unless the backend returns a different `default_dataset_id`.

```text
GET /datasets
-> default_dataset_id = hotpotqa
-> datasets = [hotpotqa profile, vimqa profile]
-> frontend activeDatasetId = hotpotqa
```

### Dataset Selector

The sidebar selector switches `activeDatasetId`. Every view reads the active profile and calls endpoints under that dataset namespace.

```text
activeDatasetId = vimqa
Search     -> POST /datasets/vimqa/search
Queries    -> GET  /datasets/vimqa/queries
Benchmark  -> GET  /datasets/vimqa/benchmarks
Status     -> GET  /datasets/vimqa/stats
Indexes    -> profile/stats for vimqa
Metadata   -> profile metadata capability for vimqa
History    -> records include dataset_id and Run Again restores that dataset
```

Switching to HotpotQA uses the same UI components but changes the endpoint namespace:

```text
activeDatasetId = hotpotqa
Search     -> POST /datasets/hotpotqa/search
Queries    -> GET  /datasets/hotpotqa/queries
Benchmark  -> GET  /datasets/hotpotqa/benchmarks
Status     -> GET  /datasets/hotpotqa/stats
```

### Queries To Search

When the active dataset is VimQA, `QueriesView` calls `GET /datasets/vimqa/queries?limit=10&offset=0&search=`. The backend loads `evaluation/results/vimqa/vimqa_queries.tsv` and `evaluation/results/vimqa/vimqa_qrels.tsv`, then returns query rows with gold context ids.

Pressing `Run Default` on a query does not search inside `QueriesView`; it creates a search preset and navigates to `SearchView`:

```typescript
{
  datasetId: "vimqa",
  queryId: "vimqa_test_000001",
  query: "Hà Nội là thủ đô của nước nào?",
  method: "es_bm25",
  topK: 10,
  autoRun: true,
}
```

`SearchView` then calls `POST /datasets/vimqa/search` with that preset.

### Search Isolation

Dataset isolation is enforced on the backend by `DatasetProfile`, not by UI conditionals alone.

```text
dataset_id = vimqa
-> index = vimqa_all_dense_bkai_current
-> query file = evaluation/results/vimqa/vimqa_queries.tsv
-> qrels file = evaluation/results/vimqa/vimqa_qrels.tsv
-> methods = es_bm25, es_dense, es_hybrid
-> default_method = es_bm25
-> metadata_filters = unsupported
```

```text
dataset_id = hotpotqa
-> index = hotpotqa_full_bm25_current
-> methods = es_bm25, tv_dense, tv_hybrid, tv_filtered_hybrid
-> default_method = tv_hybrid
-> metadata_filters = supported
```

The search response includes `dataset_id`, `query_id`, ranked results, latency, support summary, and cache/history metadata. The cache key and history row both include `dataset_id`, preventing HotpotQA and VimQA searches from colliding.

### Benchmark Flow

When the active dataset is VimQA, `BenchmarkView` calls `GET /datasets/vimqa/benchmarks`. The backend reads VimQA benchmark artifacts and the UI emphasizes single-context retrieval metrics: `recall@10`, `mrr@10`, `ndcg@10`, latency, and QPS.

When the active dataset is HotpotQA, `BenchmarkView` calls `GET /datasets/hotpotqa/benchmarks` and emphasizes HotpotQA multi-hop evidence metrics, especially `full_support_recall@10`.

### Indexes And Metadata Views

`IndexesView` is read-only. It displays the active dataset's index alias, dense backend, embedding model, vector dimensions, query/qrels files, benchmark files, and readiness. It does not manage Elasticsearch indexes.

`MetadataView` is read-only. HotpotQA displays metadata filters as enabled with supported fields; VimQA displays metadata filters as unsupported while keeping search/query/benchmark flows available.

## Current System Findings

- `src/api/main.py` currently exposes legacy HotpotQA-first endpoints: `/stats`, `/queries`, `/benchmark`, `/search`.
- Runtime configuration is global through `src/core/config.py`: one `DATASET_ID`, one `ELASTICSEARCH_INDEX`, one `EMBEDDING_MODEL`, one TurboVec path.
- `src/api/main.py` has duplicate/dead code after the first `return response` in `search()`. The refactor should extract helpers and remove the unreachable tail.
- Redis search cache keys currently include index, method, query, query id, top-k, and metadata filters, but not dataset id or model.
- Search history does not store dataset id. The story acceptance allows migration; this plan adds a nullable/backfilled `dataset_id` column safely.
- HotpotQA uses TurboVec methods: `es_bm25`, `tv_dense`, `tv_hybrid`, `tv_filtered_hybrid`.
- VimQA artifacts exist and are Elasticsearch-based: `vimqa_all_bm25_current`, `vimqa_all_dense_bkai_current`, `evaluation/results/vimqa/vimqa_queries.tsv`, `evaluation/results/vimqa/vimqa_qrels.tsv`, `bm25_vimqa_full.json`, `dense_bkai_vimqa_full.json`.
- Frontend views are HotpotQA-centric but reusable: `SearchView`, `QueriesView`, `BenchmarkView`, `StatusView`, `HistoryView`. The story also needs lightweight `IndexesView` and `MetadataView` surfaces so the workspace navigation explicitly covers Indexes and Metadata without adding index management features.

## File Structure

### Backend

- Create `src/api/dataset_profiles.py`: dataset registry, profile dataclass, profile lookup, benchmark file declarations, runtime profile serialization.
- Modify `src/api/main.py`: shared dataset-scoped helpers, new `/datasets` endpoints, legacy endpoint wrappers, dataset-aware cache key, dataset-aware search support lookup, profile-specific retriever builders.
- Modify `src/api/history.py`: add `dataset_id` column with safe migration and return it in history rows.
- Modify `tests/test_api_dataset_profiles.py`: registry unit tests.
- Modify `tests/test_api_es_config.py`: dataset-scoped endpoint, request-shape, search routing, and support-summary tests.
- Modify `tests/test_api_cache.py`: cache key includes dataset id, index, method, model, query, query id, top-k, metadata filters.
- Modify `tests/test_search_history.py`: history migration and dataset id persistence.

### Frontend

- Modify `frontend/src/types.ts`: dataset profile/status/search/benchmark types and `SearchPreset.datasetId`.
- Modify `frontend/src/lib/api.ts`: dataset-scoped client functions with legacy fallback helpers removed from view usage.
- Modify `frontend/src/App.tsx`: load dataset profiles, keep `activeDatasetId`, pass active profile into views.
- Modify `frontend/src/components/Sidebar.tsx`: app title becomes dataset-neutral; add compact dataset selector.
- Modify `frontend/src/components/TopBar.tsx`: show active dataset label/language/readiness.
- Modify `frontend/src/components/SearchView.tsx`: use profile methods/default method/suggestions; call dataset-scoped search.
- Modify `frontend/src/components/QueriesView.tsx`: call dataset-scoped queries; copy and gold-document labels adapt to dataset.
- Modify `frontend/src/components/BenchmarkView.tsx`: call dataset-scoped benchmark; HotpotQA emphasizes full-support, VimQA emphasizes recall/MRR/nDCG.
- Create `frontend/src/components/IndexesView.tsx`: show active dataset index alias, dense backend, vector dimensions, benchmark files, and readiness.
- Create `frontend/src/components/MetadataView.tsx`: show metadata filter capability, supported filter fields for HotpotQA, and VimQA unsupported-state copy.
- Modify `frontend/src/components/StatusView.tsx`: call dataset-scoped stats; dataflow labels adapt to HotpotQA/VimQA.

### Docs And Harness

- Modify `README.md`: document dataset-first runtime and legacy endpoint compatibility.
- Modify `docs/architecture/current-architecture.md`: add dataset profile registry and dataset-scoped API layer.
- Modify `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-011-dataset-first-api-ui-refactor.md`: update design/evidence after implementation.
- Update Harness matrix with `harness-cli story update` only after verification passes.

---

## Backend Contract

### Dataset Profile JSON Shape

`GET /datasets` returns:

```json
{
  "default_dataset_id": "hotpotqa",
  "datasets": [
    {
      "id": "hotpotqa",
      "label": "HotpotQA Full Corpus",
      "language": "en",
      "task_type": "multi-hop retrieval",
      "dataset_id": "beir/hotpotqa/dev",
      "index": "hotpotqa_full_bm25_current",
      "methods": ["es_bm25", "tv_dense", "tv_hybrid", "tv_filtered_hybrid"],
      "default_method": "tv_hybrid",
      "dense_backend": "turbovec",
      "embedding_model": "BAAI/bge-small-en-v1.5",
      "vector_dims": 384,
      "query_file": "evaluation/results/hotpotqa_full_dev_queries.tsv",
      "qrels_file": null,
      "readiness": "ready",
      "supports_metadata_filters": true,
      "primary_metric": "full_support_recall@10"
    },
    {
      "id": "vimqa",
      "label": "VimQA Retrieval Proxy",
      "language": "vi",
      "task_type": "single-context retrieval",
      "dataset_id": "vimqa/all",
      "index": "vimqa_all_dense_bkai_current",
      "methods": ["es_bm25", "es_dense", "es_hybrid"],
      "default_method": "es_bm25",
      "dense_backend": "elasticsearch_dense_vector",
      "embedding_model": "bkai-foundation-models/vietnamese-bi-encoder",
      "vector_dims": 768,
      "query_file": "evaluation/results/vimqa/vimqa_queries.tsv",
      "qrels_file": "evaluation/results/vimqa/vimqa_qrels.tsv",
      "readiness": "ready",
      "supports_metadata_filters": false,
      "primary_metric": "recall@10"
    }
  ]
}
```

### New Endpoints

```text
GET  /datasets
GET  /datasets/{dataset_id}/stats
GET  /datasets/{dataset_id}/queries?limit=10&offset=0&search=
GET  /datasets/{dataset_id}/benchmarks
POST /datasets/{dataset_id}/search
```

### Legacy Endpoint Compatibility

Legacy endpoints stay active and delegate to `hotpotqa`:

```text
GET  /stats       -> /datasets/hotpotqa/stats semantics
GET  /queries     -> /datasets/hotpotqa/queries semantics
GET  /benchmark   -> /datasets/hotpotqa/benchmarks semantics
POST /search      -> /datasets/hotpotqa/search semantics
```

---

## Task 1: Add Dataset Profile Registry

**Files:**
- Create: `src/api/dataset_profiles.py`
- Create: `tests/test_api_dataset_profiles.py`

- [ ] **Step 1: Write failing profile registry tests**

Create `tests/test_api_dataset_profiles.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from src.api.dataset_profiles import DatasetProfile, get_dataset_profile, list_dataset_profiles


def test_dataset_registry_exposes_hotpotqa_and_vimqa_profiles() -> None:
    profiles = list_dataset_profiles()

    assert [profile.id for profile in profiles] == ["hotpotqa", "vimqa"]
    hotpotqa = get_dataset_profile("hotpotqa")
    vimqa = get_dataset_profile("vimqa")

    assert hotpotqa.label == "HotpotQA Full Corpus"
    assert hotpotqa.language == "en"
    assert hotpotqa.index == "hotpotqa_full_bm25_current"
    assert hotpotqa.methods == ("es_bm25", "tv_dense", "tv_hybrid", "tv_filtered_hybrid")
    assert hotpotqa.default_method == "tv_hybrid"
    assert hotpotqa.dense_backend == "turbovec"
    assert hotpotqa.embedding_model == "BAAI/bge-small-en-v1.5"
    assert hotpotqa.vector_dims == 384
    assert hotpotqa.primary_metric == "full_support_recall@10"

    assert vimqa.label == "VimQA Retrieval Proxy"
    assert vimqa.language == "vi"
    assert vimqa.index == "vimqa_all_dense_bkai_current"
    assert vimqa.methods == ("es_bm25", "es_dense", "es_hybrid")
    assert vimqa.default_method == "es_bm25"
    assert vimqa.dense_backend == "elasticsearch_dense_vector"
    assert vimqa.embedding_model == "bkai-foundation-models/vietnamese-bi-encoder"
    assert vimqa.vector_dims == 768
    assert vimqa.primary_metric == "recall@10"


def test_dataset_profile_serializes_paths_as_strings() -> None:
    profile = get_dataset_profile("vimqa")
    payload = profile.to_public_dict()

    assert payload["id"] == "vimqa"
    assert payload["query_file"] == "evaluation/results/vimqa/vimqa_queries.tsv"
    assert payload["qrels_file"] == "evaluation/results/vimqa/vimqa_qrels.tsv"
    assert payload["benchmark_files"] == [
        "evaluation/results/vimqa/bm25_vimqa_full.json",
        "evaluation/results/vimqa/dense_bkai_vimqa_full.json",
    ]


def test_unknown_dataset_profile_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_dataset_profile("unknown")
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
python -m pytest tests/test_api_dataset_profiles.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'src.api.dataset_profiles'`.

- [ ] **Step 3: Implement profile registry**

Create `src/api/dataset_profiles.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.core.config import ROOT_DIR

Readiness = Literal["ready", "partial", "missing"]


@dataclass(frozen=True)
class DatasetProfile:
    id: str
    label: str
    language: str
    task_type: str
    dataset_id: str
    index: str
    methods: tuple[str, ...]
    default_method: str
    dense_backend: str
    embedding_model: str
    vector_dims: int | None
    query_file: Path | None
    qrels_file: Path | None
    benchmark_files: tuple[Path, ...]
    readiness: Readiness
    supports_metadata_filters: bool
    primary_metric: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "language": self.language,
            "task_type": self.task_type,
            "dataset_id": self.dataset_id,
            "index": self.index,
            "methods": list(self.methods),
            "default_method": self.default_method,
            "dense_backend": self.dense_backend,
            "embedding_model": self.embedding_model,
            "vector_dims": self.vector_dims,
            "query_file": _relative_path(self.query_file),
            "qrels_file": _relative_path(self.qrels_file),
            "benchmark_files": [_relative_path(path) for path in self.benchmark_files],
            "readiness": self.readiness,
            "supports_metadata_filters": self.supports_metadata_filters,
            "primary_metric": self.primary_metric,
        }


def _relative_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return path.as_posix()


DATASET_PROFILES: tuple[DatasetProfile, ...] = (
    DatasetProfile(
        id="hotpotqa",
        label="HotpotQA Full Corpus",
        language="en",
        task_type="multi-hop retrieval",
        dataset_id="beir/hotpotqa/dev",
        index="hotpotqa_full_bm25_current",
        methods=("es_bm25", "tv_dense", "tv_hybrid", "tv_filtered_hybrid"),
        default_method="tv_hybrid",
        dense_backend="turbovec",
        embedding_model="BAAI/bge-small-en-v1.5",
        vector_dims=384,
        query_file=ROOT_DIR / "evaluation" / "results" / "hotpotqa_full_dev_queries.tsv",
        qrels_file=None,
        benchmark_files=(
            ROOT_DIR / "evaluation" / "results" / "hotpotqa_full" / "tv_full_200.json",
            ROOT_DIR / "evaluation" / "results" / "hotpotqa_full" / "tv_filtered_full_200.json",
        ),
        readiness="ready",
        supports_metadata_filters=True,
        primary_metric="full_support_recall@10",
    ),
    DatasetProfile(
        id="vimqa",
        label="VimQA Retrieval Proxy",
        language="vi",
        task_type="single-context retrieval",
        dataset_id="vimqa/all",
        index="vimqa_all_dense_bkai_current",
        methods=("es_bm25", "es_dense", "es_hybrid"),
        default_method="es_bm25",
        dense_backend="elasticsearch_dense_vector",
        embedding_model="bkai-foundation-models/vietnamese-bi-encoder",
        vector_dims=768,
        query_file=ROOT_DIR / "evaluation" / "results" / "vimqa" / "vimqa_queries.tsv",
        qrels_file=ROOT_DIR / "evaluation" / "results" / "vimqa" / "vimqa_qrels.tsv",
        benchmark_files=(
            ROOT_DIR / "evaluation" / "results" / "vimqa" / "bm25_vimqa_full.json",
            ROOT_DIR / "evaluation" / "results" / "vimqa" / "dense_bkai_vimqa_full.json",
        ),
        readiness="ready",
        supports_metadata_filters=False,
        primary_metric="recall@10",
    ),
)


def list_dataset_profiles() -> list[DatasetProfile]:
    return list(DATASET_PROFILES)


def get_dataset_profile(dataset_id: str) -> DatasetProfile:
    normalized = dataset_id.strip().lower()
    for profile in DATASET_PROFILES:
        if profile.id == normalized:
            return profile
    raise KeyError(dataset_id)
```

- [ ] **Step 4: Run test to verify GREEN**

Run:

```powershell
python -m pytest tests/test_api_dataset_profiles.py -q
```

Expected: `3 passed`.

---

## Task 2: Make Query/Qrels Loading Dataset-Aware

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api_es_config.py`

- [ ] **Step 1: Add failing tests for VimQA query loading and support lookup**

Append to `tests/test_api_es_config.py`:

```python
def test_load_query_examples_accepts_vimqa_query_tsv(tmp_path):
    from src.api import main

    query_file = tmp_path / "vimqa_queries.tsv"
    query_file.write_text(
        "query_id\tsource_query_id\tquery\tsplit\tanswer\n"
        "vimqa_test_000001\tvimqa_test_000001\tHà Nội là gì?\ttest\tthủ đô\n",
        encoding="utf-8",
    )
    qrels_file = tmp_path / "vimqa_qrels.tsv"
    qrels_file.write_text(
        "query_id\tdoc_id\trelevance\n"
        "vimqa_test_000001\tvimqa_ctx_abc\t1\n",
        encoding="utf-8",
    )

    rows = main.load_query_examples_from_files(query_file=query_file, qrels_file=qrels_file)

    assert rows == [
        {
            "query_id": "vimqa_test_000001",
            "query": "Hà Nội là gì?",
            "support_doc_ids": ["vimqa_ctx_abc"],
            "support_doc_count": 1,
            "split": "test",
            "answer": "thủ đô",
        }
    ]


def test_find_support_doc_ids_uses_dataset_profile(monkeypatch):
    from src.api import main
    from src.api.dataset_profiles import get_dataset_profile

    monkeypatch.setattr(
        main,
        "get_dataset_query_examples",
        lambda profile: [{"query_id": "vimqa_test_000001", "query": "Hà Nội là gì?", "support_doc_ids": ["vimqa_ctx_abc"]}],
    )

    support = main.find_support_doc_ids_for_profile(
        get_dataset_profile("vimqa"),
        query="different text",
        query_id="vimqa_test_000001",
    )

    assert support == ["vimqa_ctx_abc"]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_api_es_config.py::test_load_query_examples_accepts_vimqa_query_tsv tests/test_api_es_config.py::test_find_support_doc_ids_uses_dataset_profile -q
```

Expected: fail because `load_query_examples_from_files`, `get_dataset_query_examples`, or `find_support_doc_ids_for_profile` do not exist.

- [ ] **Step 3: Add dataset-aware query helpers**

Modify `src/api/main.py` imports:

```python
from src.api.dataset_profiles import DatasetProfile, get_dataset_profile, list_dataset_profiles
```

Add helpers near existing query loading functions:

```python
def load_qrels_tsv(path: Path | None) -> dict[str, list[str]]:
    if path is None or not path.exists():
        return {}
    qrels: dict[str, list[str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            query_id = str(row.get("query_id", "")).strip()
            doc_id = str(row.get("doc_id", "")).strip()
            relevance = float(row.get("relevance") or 1.0)
            if query_id and doc_id and relevance > 0:
                qrels.setdefault(query_id, []).append(doc_id)
    return qrels


def load_query_examples_from_files(query_file: Path, qrels_file: Path | None = None) -> list[dict[str, Any]]:
    qrels_by_query = load_qrels_tsv(qrels_file)
    with query_file.open("r", encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle, delimiter="\t"):
            query_id = str(row.get("query_id") or row.get("variant_query_id") or "").strip()
            query_text = str(row.get("query") or row.get("original_query") or "").strip()
            support_doc_ids = qrels_by_query.get(query_id)
            if support_doc_ids is None:
                support_doc_ids = [doc_id.strip() for doc_id in row.get("support_doc_ids", "").split(",") if doc_id.strip()]
            item = {
                "query_id": query_id,
                "query": query_text,
                "support_doc_ids": support_doc_ids,
                "support_doc_count": len(support_doc_ids),
            }
            if row.get("split"):
                item["split"] = row["split"]
            if row.get("answer"):
                item["answer"] = row["answer"]
            rows.append(item)
    return rows


@lru_cache(maxsize=8)
def get_dataset_query_examples(profile_id: str) -> list[dict[str, Any]]:
    profile = get_dataset_profile(profile_id)
    if profile.query_file is not None and profile.query_file.exists():
        return load_query_examples_from_files(profile.query_file, profile.qrels_file)
    if profile.id == "hotpotqa":
        try:
            return load_dataset_query_examples(profile.dataset_id)
        except Exception:
            return load_query_examples(profile.query_file or QUERY_EXAMPLES_PATH)
    return []


def find_support_doc_ids_for_profile(profile: DatasetProfile, query: str, query_id: str | None = None) -> list[str]:
    normalized_query_id = (query_id or "").strip()
    rows = get_dataset_query_examples(profile.id)
    if normalized_query_id:
        for row in rows:
            if str(row.get("query_id", "")).strip() == normalized_query_id:
                return [str(doc_id) for doc_id in row.get("support_doc_ids", [])]

    normalized = query.strip().lower()
    for row in rows:
        if str(row.get("query", "")).strip().lower() == normalized:
            return [str(doc_id) for doc_id in row.get("support_doc_ids", [])]
    return []
```

Keep legacy wrappers:

```python
@lru_cache(maxsize=1)
def get_query_examples() -> list[dict[str, Any]]:
    return get_dataset_query_examples("hotpotqa")


def find_support_doc_ids(query: str, query_id: str | None = None) -> list[str]:
    return find_support_doc_ids_for_profile(get_dataset_profile("hotpotqa"), query, query_id)
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_api_es_config.py::test_load_query_examples_accepts_vimqa_query_tsv tests/test_api_es_config.py::test_find_support_doc_ids_uses_dataset_profile -q
```

Expected: `2 passed`.

---

## Task 3: Add Dataset-Scoped Cache Key And History Dataset Id

**Files:**
- Modify: `src/api/main.py`
- Modify: `src/api/history.py`
- Modify: `tests/test_api_cache.py`
- Modify: `tests/test_search_history.py`

- [ ] **Step 1: Write failing cache key test**

Replace or extend `tests/test_api_cache.py`:

```python
from src.api.main import build_search_cache_key


def test_build_search_cache_key_includes_dataset_index_method_model_query_topk_and_filters() -> None:
    base = build_search_cache_key(
        dataset_id="hotpotqa",
        index="hotpotqa_full_bm25_current",
        model="BAAI/bge-small-en-v1.5",
        query="What occupations do both Ian Hunter and Rob Thomas have?",
        method="tv_hybrid",
        top_k=10,
        query_id="q1",
    )
    different_dataset = build_search_cache_key(
        dataset_id="vimqa",
        index="hotpotqa_full_bm25_current",
        model="BAAI/bge-small-en-v1.5",
        query="What occupations do both Ian Hunter and Rob Thomas have?",
        method="tv_hybrid",
        top_k=10,
        query_id="q1",
    )
    different_model = build_search_cache_key(
        dataset_id="hotpotqa",
        index="hotpotqa_full_bm25_current",
        model="bkai-foundation-models/vietnamese-bi-encoder",
        query="What occupations do both Ian Hunter and Rob Thomas have?",
        method="tv_hybrid",
        top_k=10,
        query_id="q1",
    )
    filtered = build_search_cache_key(
        dataset_id="hotpotqa",
        index="hotpotqa_full_bm25_current",
        model="BAAI/bge-small-en-v1.5",
        query="What occupations do both Ian Hunter and Rob Thomas have?",
        method="tv_hybrid",
        top_k=10,
        query_id="q1",
        metadata_filters={"author": "Nguyen An"},
    )

    assert base.startswith("search:v3:")
    assert base != different_dataset
    assert base != different_model
    assert base != filtered
```

- [ ] **Step 2: Write failing history dataset test**

Append to `tests/test_search_history.py`:

```python
def test_history_store_records_dataset_id(tmp_path):
    from src.api.history import SearchHistoryStore

    store = SearchHistoryStore(tmp_path / "history.sqlite3")
    store.init_db()

    history_id = store.record_search(
        dataset_id="vimqa",
        query="Hà Nội là gì?",
        method="es_bm25",
        top_k=10,
        latency_ms=12.5,
        cache_hit=False,
        results=[{"doc_id": "vimqa_ctx_1", "title": "VimQA context", "score": 1.0, "rank": 1}],
        support_doc_ids=["vimqa_ctx_1"],
    )

    row = store.get_history(history_id)

    assert row is not None
    assert row["dataset_id"] == "vimqa"
```

- [ ] **Step 3: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_api_cache.py tests/test_search_history.py::test_history_store_records_dataset_id -q
```

Expected: failures because cache key lacks required `dataset_id`/`model`, and history store does not accept `dataset_id`.

- [ ] **Step 4: Implement cache key v3**

In `src/api/main.py`, replace duplicate `build_search_cache_key` definitions with one function:

```python
def build_search_cache_key(
    *,
    dataset_id: str = "hotpotqa",
    index: str,
    model: str,
    query: str,
    method: str,
    top_k: int,
    query_id: str | None = None,
    metadata_filters: dict[str, str] | None = None,
) -> str:
    payload = json.dumps(
        {
            "dataset_id": dataset_id,
            "index": index,
            "method": method,
            "metadata_filters": metadata_filters or {},
            "model": model,
            "query": query.strip(),
            "query_id": (query_id or "").strip(),
            "top_k": top_k,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"search:v3:{digest}"
```

- [ ] **Step 5: Implement history dataset migration**

Modify `src/api/history.py`:

```python
def init_db(self) -> None:
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    with self._connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                dataset_id TEXT NOT NULL DEFAULT 'hotpotqa',
                query TEXT NOT NULL,
                method TEXT NOT NULL,
                top_k INTEGER NOT NULL,
                latency_ms REAL NOT NULL,
                cache_hit INTEGER NOT NULL,
                result_count INTEGER NOT NULL,
                top_docs_json TEXT NOT NULL,
                support_doc_ids_json TEXT NOT NULL
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(query_history)").fetchall()}
        if "dataset_id" not in columns:
            conn.execute("ALTER TABLE query_history ADD COLUMN dataset_id TEXT NOT NULL DEFAULT 'hotpotqa'")
        conn.commit()
```

Change `record_search` signature and insert:

```python
def record_search(
    self,
    *,
    dataset_id: str = "hotpotqa",
    query: str,
    method: str,
    top_k: int,
    latency_ms: float,
    cache_hit: bool,
    results: list[dict[str, Any]],
    support_doc_ids: list[str],
) -> int:
    ...
    cursor = conn.execute(
        """
        INSERT INTO query_history (
            dataset_id, query, method, top_k, latency_ms, cache_hit, result_count, top_docs_json, support_doc_ids_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (dataset_id, query, method, top_k, latency_ms, 1 if cache_hit else 0, len(results), json.dumps(top_docs, ensure_ascii=False), json.dumps(support_doc_ids, ensure_ascii=False)),
    )
```

Return dataset id in `_row_to_dict`:

```python
"dataset_id": str(row["dataset_id"]),
```

- [ ] **Step 6: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_api_cache.py tests/test_search_history.py -q
```

Expected: all selected tests pass.

---

## Task 4: Add Dataset-Scoped API Endpoints

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api_es_config.py`

- [ ] **Step 1: Write failing dataset endpoint tests**

Append to `tests/test_api_es_config.py`:

```python
def test_datasets_endpoint_lists_profiles():
    from src.api import main

    payload = main.datasets()

    assert payload["default_dataset_id"] == "hotpotqa"
    assert [item["id"] for item in payload["datasets"]] == ["hotpotqa", "vimqa"]


def test_dataset_stats_returns_profile_runtime_fields():
    from src.api import main

    payload = main.dataset_stats("vimqa")

    assert payload["dataset_profile"]["id"] == "vimqa"
    assert payload["dataset_id"] == "vimqa/all"
    assert payload["index"] == "vimqa_all_dense_bkai_current"
    assert payload["methods"] == ["es_bm25", "es_dense", "es_hybrid"]
    assert payload["default_search_method"] == "es_bm25"
    assert payload["primary_metric"] == "recall@10"


def test_dataset_queries_uses_profile(monkeypatch):
    from src.api import main

    monkeypatch.setattr(
        main,
        "get_dataset_query_examples",
        lambda profile_id: [
            {"query_id": "v1", "query": "Hà Nội là gì?", "support_doc_ids": ["ctx1"], "support_doc_count": 1, "answer": "thủ đô"}
        ],
    )

    payload = main.dataset_queries("vimqa", limit=10, offset=0, search="")

    assert payload["dataset_id"] == "vimqa"
    assert payload["queries"][0]["query_id"] == "v1"
    assert payload["queries"][0]["answer"] == "thủ đô"


def test_dataset_benchmarks_combines_vimqa_result_files(tmp_path, monkeypatch):
    from src.api import main
    from src.api.dataset_profiles import DatasetProfile

    bm25 = tmp_path / "bm25.json"
    dense = tmp_path / "dense.json"
    bm25.write_text('{"config":{"dataset_id":"vimqa/all","queries":2},"results":[{"method":"es_bm25","metrics":{"recall@10":0.9,"mrr@10":0.8,"ndcg@10":0.85,"queries":2}}]}', encoding="utf-8")
    dense.write_text('{"config":{"dataset_id":"vimqa/all","queries":2},"results":[{"method":"es_dense","metrics":{"recall@10":0.7,"mrr@10":0.6,"ndcg@10":0.65,"queries":2}}]}', encoding="utf-8")
    profile = DatasetProfile(
        id="vimqa", label="VimQA Retrieval Proxy", language="vi", task_type="single-context retrieval", dataset_id="vimqa/all",
        index="vimqa_all_dense_bkai_current", methods=("es_bm25", "es_dense"), default_method="es_bm25",
        dense_backend="elasticsearch_dense_vector", embedding_model="bkai", vector_dims=768,
        query_file=None, qrels_file=None, benchmark_files=(bm25, dense), readiness="ready", supports_metadata_filters=False,
        primary_metric="recall@10",
    )
    monkeypatch.setattr(main, "get_dataset_profile", lambda dataset_id: profile)

    payload = main.dataset_benchmarks("vimqa")

    assert payload["current"]["config"]["dataset_id"] == "vimqa/all"
    assert [row["method"] for row in payload["current"]["results"]] == ["es_bm25", "es_dense"]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_api_es_config.py::test_datasets_endpoint_lists_profiles tests/test_api_es_config.py::test_dataset_stats_returns_profile_runtime_fields tests/test_api_es_config.py::test_dataset_queries_uses_profile tests/test_api_es_config.py::test_dataset_benchmarks_combines_vimqa_result_files -q
```

Expected: fail because new endpoint functions do not exist.

- [ ] **Step 3: Implement endpoint helpers and routes**

In `src/api/main.py`, add:

```python
@app.get("/datasets")
def datasets() -> dict[str, Any]:
    return {
        "default_dataset_id": "hotpotqa",
        "datasets": [profile.to_public_dict() for profile in list_dataset_profiles()],
    }


def resolve_dataset_profile(dataset_id: str) -> DatasetProfile:
    try:
        return get_dataset_profile(dataset_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_id}") from None


@app.get("/datasets/{dataset_id}/stats")
def dataset_stats(dataset_id: str) -> dict[str, Any]:
    profile = resolve_dataset_profile(dataset_id)
    return {
        "backend": "elasticsearch",
        "index": profile.index,
        "methods": list(profile.methods),
        "dataset_id": profile.dataset_id,
        "dataset_profile": profile.to_public_dict(),
        "default_search_method": profile.default_method,
        "embedding_model": profile.embedding_model,
        "embedding_service_url": settings.embedding_service_url if profile.dense_backend == "turbovec" else "",
        "num_candidates": settings.elasticsearch_num_candidates,
        "search_cache_ttl_seconds": settings.search_cache_ttl_seconds,
        "history_db_path": str(settings.history_db_path),
        "turbovec_index_path": str(settings.turbovec_index_path) if profile.dense_backend == "turbovec" else None,
        "turbovec_dim": settings.turbovec_dim if profile.dense_backend == "turbovec" else None,
        "turbovec_bit_width": settings.turbovec_bit_width if profile.dense_backend == "turbovec" else None,
        "runtime_profile": profile.id,
        "corpus_doc_count": infer_corpus_doc_count(profile.index) or (3623 if profile.id == "vimqa" else None),
        "primary_metric": profile.primary_metric,
    }


@app.get("/datasets/{dataset_id}/queries")
def dataset_queries(
    dataset_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str = "",
) -> dict[str, Any]:
    profile = resolve_dataset_profile(dataset_id)
    payload = paginate_query_examples(get_dataset_query_examples(profile.id), limit=limit, offset=offset, search=search)
    payload["dataset_id"] = profile.id
    return payload


def build_dataset_benchmark_dashboard(profile: DatasetProfile) -> dict[str, Any]:
    loaded = [load_benchmark_result(path) for path in profile.benchmark_files if path.exists()]
    rows = []
    config: dict[str, Any] = {"dataset_id": profile.dataset_id, "index": profile.index, "primary_metric": profile.primary_metric}
    for result in loaded:
        config.update(result.get("config", {}))
        rows.extend(result.get("results", []))
    return {
        "current": {
            "title": f"{profile.label} Benchmark",
            "subtitle": "Dataset-scoped project evidence; not a leaderboard claim.",
            "config": config,
            "results": rows,
        },
        "legacy": {"title": "Legacy Benchmarks", "subtitle": "No legacy section for this dataset.", "config": {}, "results": []},
        "results": rows,
    }


@app.get("/datasets/{dataset_id}/benchmarks")
def dataset_benchmarks(dataset_id: str) -> dict[str, Any]:
    profile = resolve_dataset_profile(dataset_id)
    if profile.id == "hotpotqa":
        return get_benchmark_result()
    return build_dataset_benchmark_dashboard(profile)
```

Update legacy wrappers:

```python
@app.get("/stats")
def stats() -> dict[str, Any]:
    return dataset_stats("hotpotqa")


@app.get("/queries")
def queries(limit: int = Query(default=10, ge=1, le=100), offset: int = Query(default=0, ge=0), search: str = "") -> dict[str, Any]:
    return dataset_queries("hotpotqa", limit=limit, offset=offset, search=search)


@app.get("/benchmark")
def benchmark() -> dict[str, Any]:
    return dataset_benchmarks("hotpotqa")
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_api_es_config.py::test_datasets_endpoint_lists_profiles tests/test_api_es_config.py::test_dataset_stats_returns_profile_runtime_fields tests/test_api_es_config.py::test_dataset_queries_uses_profile tests/test_api_es_config.py::test_dataset_benchmarks_combines_vimqa_result_files -q
```

Expected: `4 passed`.

---

## Task 5: Add Dataset-Scoped Search Routing

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api_es_config.py`

- [ ] **Step 1: Write failing dataset search tests**

Append to `tests/test_api_es_config.py`:

```python
def test_dataset_search_routes_vimqa_bm25_to_profile_index(monkeypatch):
    from src.api import main

    captured = {}

    class FakeESRetriever:
        def __init__(self, index):
            self.index = index

        def search(self, query, method, top_k, candidate_k=100, metadata_filters=None):
            captured["search"] = (self.index, query, method, top_k, metadata_filters)
            return [{"doc_id": "vimqa_ctx_1", "title": "VimQA context", "text": "body", "url": "", "score": 1.0, "source": "bm25"}]

    class FakeHistoryStore:
        def record_search(self, **kwargs):
            captured["history"] = kwargs
            return 987

    monkeypatch.setattr(main, "read_search_cache", lambda cache_key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda cache_key, payload: captured.setdefault("cache_payload", payload))
    monkeypatch.setattr(main, "get_history_store", lambda: FakeHistoryStore())
    monkeypatch.setattr(main, "find_support_doc_ids_for_profile", lambda profile, query, query_id=None: ["vimqa_ctx_1"])
    monkeypatch.setattr(main, "get_es_retriever_for_profile", lambda profile_id: FakeESRetriever(main.get_dataset_profile(profile_id).index))

    response = main.dataset_search("vimqa", main.SearchRequest(query="Hà Nội là gì?", query_id="vimqa_test_000001", method="es_bm25", top_k=1))

    assert captured["search"] == ("vimqa_all_dense_bkai_current", "Hà Nội là gì?", "bm25", 1, None)
    assert captured["history"]["dataset_id"] == "vimqa"
    assert response["dataset_id"] == "vimqa"
    assert response["support"]["matched_doc_ids"] == ["vimqa_ctx_1"]


def test_dataset_search_rejects_turbovec_method_for_vimqa():
    from fastapi import HTTPException
    from src.api import main

    with pytest.raises(HTTPException) as exc_info:
        main.dataset_search("vimqa", main.SearchRequest(query="Hà Nội là gì?", method="tv_hybrid", top_k=1))

    assert exc_info.value.status_code == 400
    assert "Unknown method for dataset vimqa" in exc_info.value.detail


def test_legacy_search_delegates_to_hotpotqa(monkeypatch):
    from src.api import main

    captured = {}

    def fake_dataset_search(dataset_id, request):
        captured["dataset_id"] = dataset_id
        return {"dataset_id": dataset_id, "query": request.query, "results": []}

    monkeypatch.setattr(main, "dataset_search", fake_dataset_search)

    response = main.search(main.SearchRequest(query="Who connects Alpha and Beta?", method="es_bm25"))

    assert captured["dataset_id"] == "hotpotqa"
    assert response["dataset_id"] == "hotpotqa"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_api_es_config.py::test_dataset_search_routes_vimqa_bm25_to_profile_index tests/test_api_es_config.py::test_dataset_search_rejects_turbovec_method_for_vimqa tests/test_api_es_config.py::test_legacy_search_delegates_to_hotpotqa -q
```

Expected: fail because `dataset_search` or profile retrievers do not exist.

- [ ] **Step 3: Add profile-specific retriever builders**

In `src/api/main.py`, add:

```python
@lru_cache(maxsize=8)
def get_es_retriever_for_profile(profile_id: str) -> ElasticsearchRetriever:
    from elasticsearch import Elasticsearch

    profile = get_dataset_profile(profile_id)
    return ElasticsearchRetriever(
        es=Elasticsearch(settings.elasticsearch_url, request_timeout=120),
        index=profile.index,
        model_name=profile.embedding_model,
        num_candidates=settings.elasticsearch_num_candidates,
        embedding_service_url=settings.embedding_service_url if profile.dense_backend == "turbovec" else "",
        embedding_timeout_seconds=settings.embedding_timeout_seconds,
    )


@lru_cache(maxsize=2)
def get_tv_retriever_for_profile(profile_id: str) -> TurboVecHybridRetriever:
    if profile_id != "hotpotqa":
        raise HTTPException(status_code=400, detail=f"TurboVec is not configured for dataset {profile_id}")
    from elasticsearch import Elasticsearch

    es = Elasticsearch(settings.elasticsearch_url, request_timeout=120)
    return TurboVecHybridRetriever.from_paths(
        bm25_retriever=get_es_retriever_for_profile("hotpotqa"),
        es=es,
        index=get_dataset_profile("hotpotqa").index,
        tv_index_path=str(settings.turbovec_index_path),
        model_name=get_dataset_profile("hotpotqa").embedding_model,
        embedding_service_url=settings.embedding_service_url,
        embedding_timeout_seconds=settings.embedding_timeout_seconds,
    )
```

Keep legacy wrappers:

```python
def get_es_retriever() -> ElasticsearchRetriever:
    return get_es_retriever_for_profile("hotpotqa")


def get_tv_retriever() -> TurboVecHybridRetriever:
    return get_tv_retriever_for_profile("hotpotqa")
```

- [ ] **Step 4: Extract shared search implementation**

Replace current `search()` body with dataset-aware implementation and remove unreachable duplicate tail:

```python
@app.post("/datasets/{dataset_id}/search")
def dataset_search(dataset_id: str, request: SearchRequest) -> dict[str, Any]:
    profile = resolve_dataset_profile(dataset_id)
    method = request.method.strip().lower()
    metadata_filters = build_metadata_filters(request)
    if method not in profile.methods:
        raise HTTPException(status_code=400, detail=f"Unknown method for dataset {profile.id}: {request.method}")
    if metadata_filters and not profile.supports_metadata_filters:
        raise HTTPException(status_code=400, detail=f"Dataset {profile.id} does not support metadata filters")
    if metadata_filters and method == "tv_dense":
        raise HTTPException(status_code=400, detail="tv_dense does not support metadata filters")

    effective_method = effective_search_method(method, metadata_filters)
    cache_key = build_search_cache_key(
        dataset_id=profile.id,
        index=profile.index,
        model=profile.embedding_model,
        query=request.query,
        method=method,
        top_k=request.top_k,
        query_id=request.query_id,
        metadata_filters=metadata_filters,
    )
    cached = read_search_cache(cache_key)
    if cached is not None:
        support_doc_ids = cached.get("support", {}).get("support_doc_ids") or find_support_doc_ids_for_profile(profile, cached["query"], cached.get("query_id"))
        cached["history_id"] = get_history_store().record_search(
            dataset_id=profile.id,
            query=cached["query"],
            method=cached["method"],
            top_k=int(cached["top_k"]),
            latency_ms=float(cached["latency_ms"]),
            cache_hit=True,
            results=cached["results"],
            support_doc_ids=support_doc_ids,
        )
        return cached

    hits, latency_breakdown_ms, latency_ms = run_profile_search(profile, request, effective_method, metadata_filters)
    support_doc_ids = find_support_doc_ids_for_profile(profile, request.query, request.query_id)
    response = build_search_response(profile, request, method, effective_method, hits, support_doc_ids, latency_ms, latency_breakdown_ms, metadata_filters)
    write_search_cache(cache_key, response)
    response["history_id"] = get_history_store().record_search(
        dataset_id=profile.id,
        query=response["query"],
        method=response["method"],
        top_k=int(response["top_k"]),
        latency_ms=float(response["latency_ms"]),
        cache_hit=False,
        results=response["results"],
        support_doc_ids=support_doc_ids,
    )
    return response


@app.post("/search")
def search(request: SearchRequest) -> dict[str, Any]:
    return dataset_search("hotpotqa", request)
```

Add helper functions:

```python
def run_profile_search(
    profile: DatasetProfile,
    request: SearchRequest,
    effective_method: str,
    metadata_filters: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, float] | None, float]:
    start = time.perf_counter()
    latency_breakdown_ms: dict[str, float] | None = None
    if effective_method in TV_METHODS:
        tv_retriever = get_tv_retriever_for_profile(profile.id)
        kwargs = {"bm25_k": settings.hybrid_bm25_k, "dense_k": settings.hybrid_dense_k, "rrf_k": settings.rrf_k}
        if metadata_filters:
            kwargs["metadata_filters"] = metadata_filters
        hits = tv_retriever.search(request.query, effective_method, request.top_k, **kwargs)
        latency_breakdown_ms = {key: round(float(value), 4) for key, value in tv_retriever.last_timing_ms.items()}
    else:
        es_method = ES_METHOD_MAP.get(effective_method, effective_method.removeprefix("es_"))
        hits = get_es_retriever_for_profile(profile.id).search(
            request.query,
            es_method,
            request.top_k,
            metadata_filters=metadata_filters or None,
        )
    return hits, latency_breakdown_ms, round((time.perf_counter() - start) * 1000, 4)


def build_search_response(
    profile: DatasetProfile,
    request: SearchRequest,
    requested_method: str,
    effective_method: str,
    hits: list[dict[str, Any]],
    support_doc_ids: list[str],
    latency_ms: float,
    latency_breakdown_ms: dict[str, float] | None,
    metadata_filters: dict[str, str],
) -> dict[str, Any]:
    support_set = set(support_doc_ids)
    results = []
    for rank, hit in enumerate(hits, start=1):
        result = {
            "doc_id": str(hit.get("doc_id", "")),
            "title": hit.get("title", ""),
            "text": str(hit.get("text", ""))[:800],
            "url": hit.get("url", ""),
            "score": float(hit.get("score", 0.0)),
            "rank": rank,
            "source": hit.get("source", ES_METHOD_MAP.get(effective_method, effective_method)),
            "hop": int(hit.get("hop", 1)),
            "is_support": str(hit.get("doc_id", "")) in support_set,
        }
        for field in ("author", "created_at", "modified_at", "source_split", "answer"):
            if field in hit and hit[field] is not None:
                result[field] = hit[field]
        results.append(result)
    response = {
        "dataset_id": profile.id,
        "query_id": request.query_id,
        "query": request.query,
        "method": effective_method,
        "top_k": request.top_k,
        "latency_ms": latency_ms,
        "cache_hit": False,
        "support": build_support_summary(support_doc_ids, [result["doc_id"] for result in results]),
        "results": results,
    }
    if effective_method != requested_method:
        response["requested_method"] = requested_method
    if metadata_filters:
        response["metadata_filters"] = metadata_filters
        response["metadata_filter_scope"] = "hard_prefilter"
    if latency_breakdown_ms is not None:
        response["latency_breakdown_ms"] = latency_breakdown_ms
    return response
```

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q
```

Expected: selected API/cache/history tests pass.

---

## Task 6: Frontend Types And Dataset-Scoped API Client

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add dataset types**

Modify `frontend/src/types.ts`:

```typescript
export type ViewType = 'search' | 'queries' | 'benchmark' | 'indexes' | 'metadata' | 'history' | 'status';

export type DatasetReadiness = 'ready' | 'partial' | 'missing';

export interface DatasetProfile {
  id: string;
  label: string;
  language: string;
  task_type: string;
  dataset_id: string;
  index: string;
  methods: string[];
  default_method: string;
  dense_backend: string;
  embedding_model: string;
  vector_dims: number | null;
  query_file: string | null;
  qrels_file: string | null;
  benchmark_files: string[];
  readiness: DatasetReadiness;
  supports_metadata_filters: boolean;
  primary_metric: string;
}

export interface DatasetListResponse {
  default_dataset_id: string;
  datasets: DatasetProfile[];
}

export interface SearchPreset {
  id: number;
  datasetId?: string;
  queryId?: string;
  query: string;
  method: string;
  topK: number;
  autoRun?: boolean;
}
```

- [ ] **Step 2: Add API client functions**

Modify imports in `frontend/src/lib/api.ts`:

```typescript
import type { BenchmarkResult, DatasetListResponse, DatasetProfile, Query } from '@/src/types';
```

Add dataset id to response types:

```typescript
export interface SearchResponse {
  dataset_id?: string;
  query_id?: string | null;
  query: string;
  method: string;
  requested_method?: string;
  top_k: number;
  latency_ms: number;
  metadata_filters?: SearchFilters;
  metadata_filter_scope?: 'hard_prefilter';
  support?: SearchSupportSummary;
  results: SearchResult[];
}

export interface StatsResponse {
  backend: string;
  index: string;
  methods: string[];
  dataset_id?: string;
  dataset_profile?: DatasetProfile;
  primary_metric?: string;
  embedding_model?: string;
  embedding_service_url?: string;
  num_candidates?: number;
  search_cache_ttl_seconds?: number;
  history_db_path?: string;
  default_search_method?: string;
  turbovec_index_path?: string | null;
  turbovec_dim?: number | null;
  turbovec_bit_width?: number | null;
  runtime_profile?: string;
  corpus_doc_count?: number | null;
}
```

Add functions:

```typescript
export async function getDatasets(): Promise<DatasetListResponse> {
  return apiFetch('/datasets');
}

export async function getDatasetStats(datasetId: string): Promise<StatsResponse> {
  return apiFetch(`/datasets/${encodeURIComponent(datasetId)}/stats`);
}

export async function getDatasetQueries(datasetId: string, { limit = 10, offset = 0, search = '' }: { limit?: number; offset?: number; search?: string } = {}): Promise<QueryPage> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const trimmedSearch = search.trim();
  if (trimmedSearch) params.set('search', trimmedSearch);
  const payload = await apiFetch<{ count: number; total: number; limit: number; offset: number; queries: ApiQuery[] }>(`/datasets/${encodeURIComponent(datasetId)}/queries?${params.toString()}`);
  return mapQueryPage(payload);
}

export async function getDatasetBenchmark(datasetId: string): Promise<BenchmarkDashboard> {
  const payload = await apiFetch<ApiBenchmarkPayload>(`/datasets/${encodeURIComponent(datasetId)}/benchmarks`);
  return mapBenchmarkDashboard(payload, datasetId);
}

export async function searchDataset(datasetId: string, query: string, method: string, topK: number, queryId?: string, filters: SearchFilters = {}): Promise<SearchResponse> {
  return apiFetch(`/datasets/${encodeURIComponent(datasetId)}/search`, {
    method: 'POST',
    body: JSON.stringify({ query_id: queryId, query, method, top_k: topK, ...filters }),
  });
}
```

Refactor existing functions to call dataset-scoped variants:

```typescript
export async function getStats(): Promise<StatsResponse> {
  return getDatasetStats('hotpotqa');
}

export async function getQueries(params = {}): Promise<QueryPage> {
  return getDatasetQueries('hotpotqa', params);
}

export async function getBenchmark(): Promise<BenchmarkDashboard> {
  return getDatasetBenchmark('hotpotqa');
}

export async function searchHotpotQA(query: string, method: string, topK: number, queryId?: string, filters: SearchFilters = {}): Promise<SearchResponse> {
  return searchDataset('hotpotqa', query, method, topK, queryId, filters);
}
```

Create helper mappings:

```typescript
function mapQueryPage(payload: { count: number; total: number; limit: number; offset: number; queries: ApiQuery[] }): QueryPage {
  return {
    count: payload.count,
    total: payload.total,
    limit: payload.limit,
    offset: payload.offset,
    queries: payload.queries.map((row) => ({
      id: row.query_id,
      text: row.query,
      docs: row.support_doc_ids,
      status: 'processed',
    })),
  };
}

function mapBenchmarkDashboard(payload: ApiBenchmarkPayload, datasetId: string): BenchmarkDashboard {
  const current = payload.current ?? { title: 'Current Benchmark', subtitle: '', config: {}, results: payload.results ?? [] };
  const legacy = payload.legacy ?? { title: 'Legacy Benchmark', subtitle: '', config: {}, results: [] };
  return {
    current: mapBenchmarkSection(current, datasetId === 'vimqa' ? 'VimQA Retrieval Benchmark' : 'Current Full-Corpus Benchmark'),
    legacy: mapBenchmarkSection(legacy, 'Legacy Nano / Elasticsearch Benchmarks'),
  };
}
```

- [ ] **Step 3: Run frontend typecheck to catch RED/GREEN together**

Run:

```powershell
cd frontend
npm run lint
```

Expected before later view updates: TypeScript may fail because new props are not used yet. Complete Tasks 7-10 before treating frontend lint as final.

---

## Task 7: Add Dataset State And Selector Shell

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/components/TopBar.tsx`

- [ ] **Step 1: Update `App.tsx` to load dataset profiles**

Replace `App.tsx` state setup with:

```tsx
import { useEffect, useMemo, useState } from 'react';
import type { DatasetProfile, SearchPreset, ViewType } from './types';
import { getDatasets } from './lib/api';

export default function App() {
  const [activeView, setActiveView] = useState<ViewType>('status');
  const [searchPreset, setSearchPreset] = useState<SearchPreset | null>(null);
  const [datasets, setDatasets] = useState<DatasetProfile[]>([]);
  const [activeDatasetId, setActiveDatasetId] = useState('hotpotqa');
  const [datasetError, setDatasetError] = useState<string | null>(null);

  useEffect(() => {
    getDatasets()
      .then((payload) => {
        setDatasets(payload.datasets);
        setActiveDatasetId(payload.default_dataset_id);
      })
      .catch((err) => setDatasetError(err instanceof Error ? err.message : 'Could not load datasets'));
  }, []);

  const activeDataset = useMemo(
    () => datasets.find((dataset) => dataset.id === activeDatasetId) ?? datasets[0] ?? null,
    [datasets, activeDatasetId],
  );
```

Update `renderView()` calls:

```tsx
case 'search': return <SearchView dataset={activeDataset} preset={searchPreset} />;
case 'queries': return <QueriesView dataset={activeDataset} onSearchQuery={(preset) => { setSearchPreset({ ...preset, datasetId: activeDataset?.id }); setActiveView('search'); }} />;
case 'benchmark': return <BenchmarkView dataset={activeDataset} />;
case 'indexes': return <IndexesView dataset={activeDataset} />;
case 'metadata': return <MetadataView dataset={activeDataset} />;
case 'history': return <HistoryView onRunAgain={(preset) => { setSearchPreset(preset); setActiveDatasetId(preset.datasetId ?? activeDatasetId); setActiveView('search'); }} />;
case 'status': return <StatusView dataset={activeDataset} datasetError={datasetError} />;
```

Add imports beside the existing view imports:

```tsx
import { IndexesView } from './components/IndexesView';
import { MetadataView } from './components/MetadataView';
```

Pass selector props:

```tsx
<Sidebar
  activeView={activeView}
  onViewChange={setActiveView}
  datasets={datasets}
  activeDatasetId={activeDatasetId}
  onDatasetChange={(datasetId) => {
    setActiveDatasetId(datasetId);
    setSearchPreset(null);
  }}
/>
<TopBar activeView={activeView} dataset={activeDataset} />
```

- [ ] **Step 2: Update `Sidebar.tsx` props and selector**

Use existing button styles; add a native select under the app title:

```tsx
import { Braces, Database, FolderTree } from 'lucide-react';
import type { DatasetProfile, ViewType } from '@/src/types';

interface SidebarProps {
  activeView: ViewType;
  onViewChange: (view: ViewType) => void;
  datasets: DatasetProfile[];
  activeDatasetId: string;
  onDatasetChange: (datasetId: string) => void;
}
```

Add the new nav items between Benchmark and History:

```tsx
const navItems = [
  { id: 'search' as ViewType, label: 'Search', Icon: Search },
  { id: 'queries' as ViewType, label: 'Queries', Icon: Terminal },
  { id: 'benchmark' as ViewType, label: 'Benchmark', Icon: Leaderboard },
  { id: 'indexes' as ViewType, label: 'Indexes', Icon: FolderTree },
  { id: 'metadata' as ViewType, label: 'Metadata', Icon: Braces },
  { id: 'history' as ViewType, label: 'History', Icon: Clock },
  { id: 'status' as ViewType, label: 'System Status', Icon: SettingsInputComponent },
];
```

Change title:

```tsx
<h1 className="font-headline text-xl leading-tight text-on-surface">
  Dataset <span className="text-primary font-extrabold">RETRIEVAL</span>
</h1>
```

Add selector:

```tsx
<div className="px-2 space-y-2">
  <label className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">Dataset</label>
  <div className="relative">
    <Database className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" size={14} />
    <select
      value={activeDatasetId}
      onChange={(event) => onDatasetChange(event.target.value)}
      className="w-full pl-9 pr-3 py-2 bg-white border border-outline-variant rounded-lg font-mono text-xs font-bold focus:ring-2 focus:ring-primary outline-none"
    >
      {datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.label}</option>)}
    </select>
  </div>
</div>
```

- [ ] **Step 3: Update `TopBar.tsx` dataset badge**

Change props:

```tsx
import type { DatasetProfile, ViewType } from '@/src/types';

interface TopBarProps {
  activeView: ViewType;
  dataset: DatasetProfile | null;
}
```

Add dataset badge:

```tsx
{dataset && (
  <div className="hidden md:flex items-center space-x-2 px-3 py-1 bg-primary/10 rounded-full border border-primary/20">
    <span className="font-label text-[10px] text-primary uppercase font-bold tracking-widest">
      {dataset.id} / {dataset.language} / {dataset.readiness}
    </span>
  </div>
)}
```

- [ ] **Step 4: Run typecheck after shell changes**

Run:

```powershell
cd frontend
npm run lint
```

Expected: failures identify views still missing `dataset` props. Continue with Tasks 8-11.

---

## Task 8: Make Search And Queries Views Dataset-Aware

**Files:**
- Modify: `frontend/src/components/SearchView.tsx`
- Modify: `frontend/src/components/QueriesView.tsx`

- [ ] **Step 1: Update `SearchView` props and API call**

Change imports:

```tsx
import { searchDataset, type SearchResult, type SearchResponse, type SearchSupportSummary } from '@/src/lib/api';
import type { DatasetProfile, SearchPreset } from '@/src/types';
```

Change component signature:

```tsx
export function SearchView({ dataset, preset }: { dataset: DatasetProfile | null; preset?: SearchPreset | null }) {
```

Replace stats loading effect with profile-driven method setup:

```tsx
useEffect(() => {
  const methods = dataset?.methods?.length ? dataset.methods : FALLBACK_METHODS;
  setAvailableMethods(methods);
  setMethod(methods.includes(dataset?.default_method ?? '') ? dataset!.default_method : methods[0] ?? 'es_bm25');
  setResponse(null);
  setError(null);
}, [dataset?.id]);
```

Update suggestions:

```tsx
const HOTPOTQA_SUGGESTIONS = [
  'What occupations do both Ian Hunter and Rob Thomas have?',
  'The Death of Cook depicts the death of James Cook at a bay on what coast?',
];

const VIMQA_SUGGESTIONS = [
  'Hà Nội là thủ đô của nước nào?',
  'Việt Nam có thủ đô nào?',
];

const suggestions = dataset?.id === 'vimqa' ? VIMQA_SUGGESTIONS : HOTPOTQA_SUGGESTIONS;
```

Update `runSearch`:

```tsx
if (!dataset) {
  setError('Dataset profile is not loaded yet');
  return;
}
const payload = await searchDataset(dataset.id, trimmed, nextMethod, nextTopK, nextQueryId);
```

Update empty-state copy:

```tsx
Run a search to retrieve ranked evidence from the active dataset workspace.
```

- [ ] **Step 2: Update `QueriesView` props and API call**

Change imports:

```tsx
import type { DatasetProfile, Query, SearchPreset } from '@/src/types';
import { getDatasetQueries } from '@/src/lib/api';
```

Change signature:

```tsx
export function QueriesView({ dataset, onSearchQuery }: QueriesViewProps & { dataset: DatasetProfile | null }) {
```

Change load effect:

```tsx
if (!dataset) {
  setIsLoading(false);
  setQueries([]);
  setSelectedQuery(null);
  return;
}
getDatasetQueries(dataset.id, { limit: PAGE_SIZE, offset, search: filter })
```

Update effect dependencies:

```tsx
}, [dataset?.id, filter, offset]);
```

Change filter chip labels:

```tsx
<FilterChip label={dataset?.id === 'vimqa' ? 'VIMQA ALL' : 'FULL DEV'} active />
```

Change selected metadata badge:

```tsx
<span className="...">{dataset?.id?.toUpperCase() ?? 'DATASET'}</span>
```

Change gold docs description:

```tsx
<p className="text-xs text-on-surface-variant mt-1 leading-relaxed line-clamp-2">
  {dataset?.id === 'vimqa' ? 'Gold context from VimQA qrels.' : 'Gold support document from HotpotQA qrels.'}
</p>
```

Change action methods:

```tsx
const primaryMethod = dataset?.default_method ?? 'es_bm25';
<CompactActionButton Icon={Bolt} label="Run Default" primary onClick={() => handoffSelectedSearch(primaryMethod)} />
<CompactActionButton Icon={Route} label="BM25" onClick={() => handoffSelectedSearch('es_bm25')} />
```

- [ ] **Step 3: Run frontend typecheck**

Run:

```powershell
cd frontend
npm run lint
```

Expected: remaining failures point to Benchmark/Status/History dataset props. Continue.

---

## Task 9: Make Benchmark And Status Views Dataset-Aware

**Files:**
- Modify: `frontend/src/components/BenchmarkView.tsx`
- Modify: `frontend/src/components/StatusView.tsx`

- [ ] **Step 1: Update `BenchmarkView`**

Change imports:

```tsx
import type { BenchmarkResult, DatasetProfile } from '@/src/types';
import { getDatasetBenchmark, type BenchmarkDashboard, type BenchmarkSection } from '@/src/lib/api';
```

Change signature:

```tsx
export function BenchmarkView({ dataset }: { dataset: DatasetProfile | null }) {
```

Change effect:

```tsx
useEffect(() => {
  if (!dataset) return;
  setDashboard(null);
  setError(null);
  getDatasetBenchmark(dataset.id)
    .then(setDashboard)
    .catch((err) => setError(err instanceof Error ? err.message : 'Could not load benchmark data'));
}, [dataset?.id]);
```

Compute dataset-specific primary metric:

```tsx
const isVimQA = dataset?.id === 'vimqa';
const primaryMetricLabel = isVimQA ? 'Best Recall@10' : 'Best Full-Support@10';
const primaryMetricValue = isVimQA ? bestRecall : bestFullSupport;
```

Change summary card:

```tsx
<SummaryCard label={primaryMetricLabel} value={primaryMetricValue.toFixed(3)} Icon={FactCheck} badge={dataset?.primary_metric ?? 'Primary Metric'} />
```

Change subtitle paragraph:

```tsx
{isVimQA
  ? 'VimQA is a single-context retrieval proxy, so recall, MRR, and nDCG are emphasized over HotpotQA full-support metrics.'
  : 'HotpotQA is multi-hop, so full-support recall remains the project metric for retrieving all evidence documents.'}
```

- [ ] **Step 2: Update `StatusView`**

Change imports:

```tsx
import type { DatasetProfile } from '@/src/types';
import { getDatasetStats, getHealth, type StatsResponse } from '@/src/lib/api';
```

Change signature:

```tsx
export function StatusView({ dataset, datasetError }: { dataset: DatasetProfile | null; datasetError?: string | null }) {
```

Change stats effect:

```tsx
useEffect(() => {
  getHealth().then((payload) => setHealth(payload.status)).catch(() => setHealth('down'));
}, []);

useEffect(() => {
  if (!dataset) return;
  getDatasetStats(dataset.id).then(setStats).catch(() => setStats(null));
}, [dataset?.id]);
```

Change intro copy:

```tsx
Live infrastructure and runtime configuration for the active dataset workspace.
```

Change dataflow nodes:

```tsx
<FlowNode Icon={Dataset} label={dataset?.label ?? 'Dataset'} sub={dataset?.language?.toUpperCase() ?? 'UNKNOWN'} />
<FlowConnector />
<FlowNode Icon={DescriptionIcon} label="ES Search" sub={stats?.index ?? 'INDEX'} isPrimary />
<FlowConnector />
<FlowNode Icon={Hub} label={dataset?.dense_backend === 'turbovec' ? 'TurboVec' : 'ES Dense'} sub={dataset?.embedding_model ?? 'MODEL'} isAlt />
<FlowConnector />
<FlowNode Icon={Lan} label="Ranked Evidence" sub={dataset?.primary_metric ?? 'METRIC'} />
```

Show dataset error:

```tsx
{datasetError && <div className="bg-white border border-primary text-primary rounded-xl p-4 font-bold">{datasetError}</div>}
```

- [ ] **Step 3: Run frontend typecheck**

Run:

```powershell
cd frontend
npm run lint
```

Expected: remaining errors are small prop/type mismatches. Fix exact messages without changing behavior.

---

## Task 10: Add Indexes And Metadata Workspace Views

**Files:**
- Create: `frontend/src/components/IndexesView.tsx`
- Create: `frontend/src/components/MetadataView.tsx`

- [ ] **Step 1: Create `IndexesView.tsx`**

Create `frontend/src/components/IndexesView.tsx`:

```tsx
import { Database, FolderTree, Gauge, Layers3 } from 'lucide-react';
import type { DatasetProfile } from '@/src/types';

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="border border-outline-variant rounded-lg p-3 bg-white">
      <div className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">{label}</div>
      <div className="mt-1 font-mono text-sm text-on-surface break-words">{value ?? 'Not configured'}</div>
    </div>
  );
}

export function IndexesView({ dataset }: { dataset: DatasetProfile | null }) {
  if (!dataset) {
    return <div className="p-6 font-label text-sm text-on-surface-variant">Dataset profile is loading.</div>;
  }

  return (
    <section className="p-6 space-y-5">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-headline text-2xl text-on-surface">Indexes</h2>
          <p className="mt-1 text-sm text-on-surface-variant">Runtime index configuration for {dataset.label}.</p>
        </div>
        <span className="px-3 py-1 rounded-full bg-primary/10 text-primary font-mono text-xs font-bold uppercase">{dataset.readiness}</span>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <Field label="Search index" value={dataset.index} />
        <Field label="Dense backend" value={dataset.dense_backend} />
        <Field label="Embedding model" value={dataset.embedding_model} />
        <Field label="Vector dims" value={dataset.vector_dims} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Field label="Dataset source" value={dataset.dataset_id} />
        <Field label="Query file" value={dataset.query_file} />
        <Field label="Qrels file" value={dataset.qrels_file} />
      </div>

      <div className="border border-outline-variant rounded-lg bg-white p-4">
        <div className="flex items-center gap-2 text-on-surface font-bold"><FolderTree size={18} /> Benchmark artifacts</div>
        <ul className="mt-3 space-y-2">
          {dataset.benchmark_files.map((path) => <li key={path} className="font-mono text-xs text-on-surface-variant break-all">{path}</li>)}
        </ul>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Create `MetadataView.tsx`**

Create `frontend/src/components/MetadataView.tsx`:

```tsx
import { Braces, CheckCircle2, XCircle } from 'lucide-react';
import type { DatasetProfile } from '@/src/types';

const HOTPOTQA_METADATA_FIELDS = ['author', 'created_at', 'modified_at', 'source_split'];

export function MetadataView({ dataset }: { dataset: DatasetProfile | null }) {
  if (!dataset) {
    return <div className="p-6 font-label text-sm text-on-surface-variant">Dataset profile is loading.</div>;
  }

  const supported = dataset.supports_metadata_filters;
  const fields = dataset.id === 'hotpotqa' ? HOTPOTQA_METADATA_FIELDS : [];

  return (
    <section className="p-6 space-y-5">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-headline text-2xl text-on-surface">Metadata</h2>
          <p className="mt-1 text-sm text-on-surface-variant">Metadata filter capability for {dataset.label}.</p>
        </div>
        <span className={`px-3 py-1 rounded-full font-mono text-xs font-bold uppercase ${supported ? 'bg-primary/10 text-primary' : 'bg-surface-container-high text-on-surface-variant'}`}>
          {supported ? 'filters enabled' : 'filters unavailable'}
        </span>
      </header>

      <div className="border border-outline-variant rounded-lg bg-white p-4 flex items-start gap-3">
        {supported ? <CheckCircle2 className="text-primary mt-0.5" size={20} /> : <XCircle className="text-on-surface-variant mt-0.5" size={20} />}
        <div>
          <div className="font-bold text-on-surface">{supported ? 'Search requests can include metadata filters.' : 'This dataset does not expose metadata filters in Sprint 4.'}</div>
          <p className="mt-1 text-sm text-on-surface-variant">
            {supported ? 'Filters are applied as hard prefilters before ranked evidence is returned.' : 'Search, queries, benchmarks, and index status remain available for this dataset.'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {(fields.length ? fields : ['No metadata fields configured']).map((field) => (
          <div key={field} className="border border-outline-variant rounded-lg p-3 bg-white flex items-center gap-2">
            <Braces size={16} className="text-on-surface-variant" />
            <span className="font-mono text-sm text-on-surface">{field}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Run frontend typecheck**

Run:

```powershell
cd frontend
npm run lint
```

Expected: remaining failures are limited to history/run-again wiring if Task 11 has not been applied yet.

---

## Task 11: History Dataset Id UI And Run Again

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/HistoryView.tsx`

- [ ] **Step 1: Add dataset id to history types**

Modify `HistoryEntry` in `frontend/src/lib/api.ts`:

```typescript
export interface HistoryEntry {
  id: number;
  dataset_id?: string;
  created_at: string;
  query: string;
  method: string;
  top_k: number;
  latency_ms: number;
  cache_hit: boolean;
  result_count: number;
  top_docs: HistoryDoc[];
  support_doc_ids: string[];
}
```

- [ ] **Step 2: Update `HistoryView` run-again preset**

Find the `onRunAgain` preset creation and include:

```tsx
datasetId: entry.dataset_id ?? 'hotpotqa',
```

Display a compact dataset badge near query/method:

```tsx
<span className="px-2 py-0.5 bg-surface-container-high text-on-surface-variant font-mono text-[9px] rounded font-bold uppercase">
  {(entry.dataset_id ?? 'hotpotqa').toUpperCase()}
</span>
```

- [ ] **Step 3: Run frontend typecheck**

Run:

```powershell
cd frontend
npm run lint
```

Expected: frontend typecheck passes.

---

## Task 12: Backend Full Test Pass And API Smoke

**Files:**
- No new files.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
python -m pytest tests/test_api_dataset_profiles.py tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run adjacent retrieval tests**

Run:

```powershell
python -m pytest tests/test_elasticsearch_retriever.py tests/test_turbovec_retriever.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Start API locally for smoke if dependencies are available**

Discover service runtime:

```powershell
.\scripts\bin\harness-cli.exe query tools --capability service-runtime --status present
```

If Docker is present and Elasticsearch indexes exist, run:

```powershell
docker compose up -d elasticsearch redis
uvicorn src.api.main:app --host 0.0.0.0 --port 8001
```

In a second shell, smoke:

```powershell
Invoke-RestMethod http://localhost:8001/datasets
Invoke-RestMethod http://localhost:8001/datasets/vimqa/stats
Invoke-RestMethod 'http://localhost:8001/datasets/vimqa/queries?limit=1'
Invoke-RestMethod http://localhost:8001/datasets/vimqa/benchmarks
```

Expected: endpoints return JSON payloads with `vimqa` profile/stat/query/benchmark data. If runtime indexes are absent, skip search smoke and record platform proof as docs/API tests only.

---

## Task 13: Frontend Verification And Optional Browser Smoke

**Files:**
- No new files.

- [ ] **Step 1: Run frontend typecheck**

Run:

```powershell
cd frontend
npm run lint
```

Expected: TypeScript passes.

- [ ] **Step 2: Run frontend dev smoke if browser tooling is equipped**

Discover test/tooling:

```powershell
.\scripts\bin\harness-cli.exe query tools --capability service-runtime --status present
```

If Docker is present:

```powershell
docker compose up -d frontend api elasticsearch redis
```

Open:

```text
http://localhost:3001
```

Manual smoke checklist:

```text
Dataset selector shows HotpotQA and VimQA.
Switching to VimQA changes Status dataset/index/model labels.
Indexes view shows the active dataset index alias, dense backend, vector dimensions, query/qrels files, and benchmark artifacts.
Metadata view shows HotpotQA metadata filters as enabled and VimQA metadata filters as unavailable.
VimQA Queries loads query ids from vimqa_queries.tsv.
Run Default from a VimQA query sends user to Search and uses es_bm25.
VimQA Benchmark table emphasizes Recall/MRR/nDCG.
Switching back to HotpotQA keeps legacy methods and full-support metrics visible.
```

Expected: UI remains usable on desktop; no overlapping critical controls; text fits in dataset selector/top bar.

---

## Task 14: Documentation And Harness Closeout

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/current-architecture.md`
- Modify: `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-011-dataset-first-api-ui-refactor.md`

- [ ] **Step 1: Update README runtime section**

Add a section after Docker Development Stack:

```markdown
## Dataset-First Runtime

The dashboard exposes HotpotQA and VimQA as dataset workspaces from one API/frontend runtime.

- `GET /datasets` lists available dataset profiles.
- Dataset-scoped endpoints live under `/datasets/{dataset_id}/...`, for example `/datasets/hotpotqa/search` and `/datasets/vimqa/search`.
- The React UI uses a dataset selector, then routes Search, Queries, Benchmarks, Indexes, Metadata, History, and Status through the active dataset profile.
- Legacy endpoints `/stats`, `/queries`, `/benchmark`, and `/search` remain HotpotQA-compatible during migration.
- The UI is a query and inspection surface only. It does not create, delete, rebuild, or edit Elasticsearch indexes or metadata schemas.

Dataset flow:

```text
Select VimQA
-> Queries calls GET /datasets/vimqa/queries
-> Run Default sends POST /datasets/vimqa/search with method es_bm25
-> Benchmark calls GET /datasets/vimqa/benchmarks and emphasizes recall/MRR/nDCG
-> Metadata displays filters unsupported
```

```text
Select HotpotQA
-> Queries calls GET /datasets/hotpotqa/queries
-> Search calls POST /datasets/hotpotqa/search with HotpotQA methods
-> Benchmark calls GET /datasets/hotpotqa/benchmarks and emphasizes full-support recall
-> Metadata displays supported filter fields
```

Runtime modes:

| Mode | Services | Use |
| --- | --- | --- |
| UI/API lightweight | frontend + api | Inspect profiles and static benchmark/query artifacts; search may fail without indexes. |
| Search runtime | frontend + api + elasticsearch + redis + embedding service when dense/TurboVec is used | Run interactive search. |
| Index/benchmark runtime | elasticsearch + scripts | Build indexes and benchmark artifacts. |
| Full demo runtime | frontend + api + elasticsearch + redis + embedding service + prepared HotpotQA/VimQA indexes | Side-by-side HotpotQA/VimQA workspace demo. |
```

- [ ] **Step 2: Update current architecture**

Add a `Dataset Profiles` section to `docs/architecture/current-architecture.md`:

```markdown
## Dataset Profiles

The API now treats datasets as runtime profiles. `src/api/dataset_profiles.py` declares `hotpotqa` and `vimqa` profiles with index aliases, methods, default method, language, dense backend, embedding model, query/qrels files, benchmark files, readiness, metadata support, and primary metric.

Legacy endpoints delegate to the `hotpotqa` profile. New dataset-scoped endpoints are available under `/datasets/{dataset_id}`. HotpotQA keeps TurboVec methods; VimQA uses Elasticsearch BM25/dense/hybrid over the BKAI dense index and defaults to `es_bm25`. The UI remains a query/read-only inspection surface; Indexes and Metadata views expose profile/runtime information without managing indexes or metadata schemas.
```

- [ ] **Step 3: Update story evidence**

Append to `US-S4-011` evidence:

```markdown
- 2026-06-21: Implemented dataset-first API/UI runtime refactor. API proof: `python -m pytest tests/test_api_dataset_profiles.py tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q` -> pass. Frontend proof: `cd frontend && npm run lint` -> pass. Dataset profiles: `GET /datasets` exposes `hotpotqa` and `vimqa`; legacy endpoints remain HotpotQA-compatible; frontend selector switches Search, Queries, Benchmark, Indexes, Metadata, History, and Status by dataset.
```

- [ ] **Step 4: Update durable Harness row after verification**

Run only after tests and docs are complete:

```powershell
.\scripts\bin\harness-cli.exe story update --id US-S4-011 --status implemented --unit 1 --integration 1 --e2e 1 --platform 1 --evidence "Dataset-first API/UI refactor complete: GET /datasets plus dataset-scoped stats/queries/search/benchmarks; legacy HotpotQA endpoints preserved; frontend dataset selector drives Search, Queries, Benchmarks, Indexes, Metadata, History, and Status. Proof: backend dataset/API/cache/history tests pass; frontend npm run lint passes; Docker/API smoke completed or documented if runtime indexes unavailable."
```

- [ ] **Step 5: Record final trace**

Run:

```powershell
.\scripts\bin\harness-cli.exe trace --summary "Completed dataset-first API and UI runtime refactor" --intake 91 --story US-S4-011 --agent codex --outcome completed --actions "implemented dataset profile registry,dataset-scoped API endpoints,dataset-aware cache/history,frontend dataset selector,dataset-aware views,docs updates,verification" --read "docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-011-dataset-first-api-ui-refactor.md,docs/architecture/current-architecture.md,src/api/main.py,frontend/src/App.tsx" --changed "src/api/dataset_profiles.py,src/api/main.py,src/api/history.py,tests/test_api_dataset_profiles.py,tests/test_api_es_config.py,tests/test_api_cache.py,tests/test_search_history.py,frontend/src/types.ts,frontend/src/lib/api.ts,frontend/src/App.tsx,frontend/src/components/Sidebar.tsx,frontend/src/components/TopBar.tsx,frontend/src/components/SearchView.tsx,frontend/src/components/QueriesView.tsx,frontend/src/components/BenchmarkView.tsx,frontend/src/components/IndexesView.tsx,frontend/src/components/MetadataView.tsx,frontend/src/components/StatusView.tsx,frontend/src/components/HistoryView.tsx,README.md,docs/architecture/current-architecture.md,docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-011-dataset-first-api-ui-refactor.md" --errors "none" --friction "none"
```

Expected: trace tier is Standard or Detailed and meets normal/high-risk closeout expectations. If Docker smoke was skipped, set `--friction` to a concrete reason and keep `e2e`/`platform` proof aligned with actual evidence.

---

## Final Verification Commands

Run these before claiming completion:

```powershell
python -m pytest tests/test_api_dataset_profiles.py tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q
python -m pytest tests/test_elasticsearch_retriever.py tests/test_turbovec_retriever.py -q
cd frontend
npm run lint
```

If Docker/runtime smoke is claimed, also run:

```powershell
docker compose up -d elasticsearch redis api frontend
Invoke-RestMethod http://localhost:8001/datasets
Invoke-RestMethod http://localhost:8001/datasets/vimqa/stats
Invoke-RestMethod 'http://localhost:8001/datasets/vimqa/queries?limit=1'
Invoke-RestMethod http://localhost:8001/datasets/vimqa/benchmarks
```

Search smoke is optional unless prepared VimQA/HotpotQA indexes are present in the local Elasticsearch volume. If search smoke is skipped, do not claim E2E search proof.

## Self-Review Notes

- Spec coverage: The plan covers `GET /datasets`, dataset-scoped stats/queries/search/benchmarks, profile declarations, legacy endpoint compatibility, cache key scope, frontend dataset-first workspace including Search, Queries, Benchmarks, Indexes, Metadata, History, and Status, VimQA metric emphasis, Docker/runtime docs, and Harness closeout.
- Placeholder scan: No forbidden placeholder markers or unsupported vague implementation steps were found. Every code-facing task includes concrete test and implementation snippets.
- Type consistency: Backend uses `dataset_id` for public dataset id where payloads need the workspace id, `profile.dataset_id` for source dataset ids such as `beir/hotpotqa/dev` and `vimqa/all`, and `profile.id` for registry lookup. Frontend uses `DatasetProfile.id` as the workspace selector value.
- Risk control: Legacy endpoints remain wrappers around `hotpotqa`; VimQA avoids TurboVec; metadata filters are disabled for VimQA in v1; history migration is additive and backfills `hotpotqa`.
