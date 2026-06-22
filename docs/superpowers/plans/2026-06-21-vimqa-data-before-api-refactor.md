# VimQA Data Before Dataset-First API Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate VimQA as a real Elasticsearch retrieval dataset first, then refactor the API/frontend into a dataset-first workspace that can run HotpotQA and VimQA side by side.

**Architecture:** Phase 1 creates first-class VimQA artifacts, indexes, retrieval benchmarks, and report evidence without changing the current API contract. Phase 2 adds a dataset registry and dataset-scoped endpoints, then updates the dashboard to select a dataset workspace before entering Search, Queries, Benchmarks, Indexes, or Metadata.

**Tech Stack:** Python, pytest, Elasticsearch 8.15, SentenceTransformers, FastAPI, React/Vite, Docker Compose, Harness CLI.

---

## Scope Order

1. `US-S4-008`: VimQA data/retrieval activation.
2. `US-S4-011`: Dataset-first API/frontend runtime refactor.

Do not start `US-S4-011` until `US-S4-008` has runnable evidence: staged corpus, query/qrels TSVs, at least one Elasticsearch index, at least one retrieval benchmark result JSON/TREC run, and a report.

## File Structure

### VimQA Data And Retrieval Activation

- Create `src/data/vimqa.py`: load local VimQA JSON, normalize text, deduplicate contexts, emit documents, queries, qrels, and metadata.
- Create `scripts/stage_vimqa.py`: write staging JSONL, manifest, benchmark-compatible query TSV, qrels TSV, and dataset stats.
- Modify `src/retrieval/elasticsearch_retriever.py`: preserve optional metadata fields such as `source_split`, `answer`, and future synthetic fields in mappings, bulk actions, and result payloads.
- Modify `src/evaluation/benchmark_es.py`: support VimQA query TSVs without pretending they are paraphrase variants, or make `stage_vimqa.py` emit compatible TSV columns if a smaller change is safer.
- Create `tests/test_vimqa_dataset.py`: loader/dedupe/qrels tests.
- Create `tests/test_stage_vimqa.py`: staging artifact tests.
- Modify `tests/test_elasticsearch_retriever.py`: metadata mapping/action/source tests.
- Create `docs/sprint4/vimqa-benchmark-design.md`: dataset conversion protocol and caveats.
- Create `docs/sprint4/vimqa-pipeline-report.md`: commands, artifacts, metrics, and model/index notes.

### Dataset-First API And Frontend Refactor

- Create `src/api/dataset_profiles.py`: registry for `hotpotqa` and `vimqa` runtime profiles.
- Modify `src/api/main.py`: add dataset-scoped endpoints while keeping legacy endpoints temporarily.
- Modify `src/api/history.py`: store or return dataset id for new searches if schema migration is accepted; otherwise include dataset in query metadata until migration is planned.
- Modify `tests/test_api_es_config.py`: dataset endpoint and profile tests.
- Modify `tests/test_api_cache.py`: cache key includes dataset/profile/model/index.
- Modify `frontend/src/types.ts`: dataset/profile/search types.
- Modify `frontend/src/lib/api.ts`: dataset-scoped API client methods.
- Modify `frontend/src/App.tsx`, `frontend/src/components/Sidebar.tsx`, `SearchView.tsx`, `QueriesView.tsx`, `BenchmarkView.tsx`, `StatusView.tsx`: dataset-first navigation and dataset-aware views.
- Modify `docker-compose.yml` and/or helper scripts only if runtime env needs explicit dataset profile configuration.
- Update `docs/architecture/current-architecture.md` after behavior changes.

---

## Phase 1: VimQA Data And Retrieval Activation

### Task 1: Add VimQA Dataset Adapter

**Files:**
- Create: `src/data/vimqa.py`
- Test: `tests/test_vimqa_dataset.py`

- [ ] **Step 1: Write failing loader/dedupe tests**

Create `tests/test_vimqa_dataset.py` with tests shaped like this:

```python
import json
from pathlib import Path

from src.data.vimqa import build_vimqa_dataset


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def test_build_vimqa_dataset_deduplicates_contexts_and_preserves_qrels(tmp_path):
    train_path = tmp_path / "train_vimqa.json"
    test_path = tmp_path / "test_vimqa.json"
    shared_context = "Hà Nội là thủ đô của Việt Nam. Thành phố nằm ở miền Bắc."
    write_rows(
        train_path,
        [
            {"question": "Hà Nội là thủ đô của nước nào?", "context": shared_context, "answer": "Việt Nam"},
            {"question": "Hà Nội nằm ở miền nào?", "context": shared_context, "answer": "miền Bắc"},
        ],
    )
    write_rows(
        test_path,
        [{"question": "Thủ đô Việt Nam là gì?", "context": shared_context, "answer": "Hà Nội"}],
    )

    dataset = build_vimqa_dataset(train_path=train_path, test_path=test_path)

    assert len(dataset.documents) == 1
    assert dataset.documents[0].doc_id.startswith("vimqa_ctx_")
    assert dataset.documents[0].content == shared_context
    assert dataset.documents[0].numeric_id == 0
    assert [query.query_id for query in dataset.queries] == [
        "vimqa_train_000000",
        "vimqa_train_000001",
        "vimqa_test_000000",
    ]
    assert set(dataset.qrels) == {"vimqa_train_000000", "vimqa_train_000001", "vimqa_test_000000"}
    assert dataset.qrels["vimqa_test_000000"] == dataset.documents[0].doc_id


def test_build_vimqa_dataset_keeps_split_and_answer_metadata(tmp_path):
    train_path = tmp_path / "train_vimqa.json"
    test_path = tmp_path / "test_vimqa.json"
    write_rows(train_path, [{"question": "Ai?", "context": "Nguyễn Du viết Truyện Kiều.", "answer": "Nguyễn Du"}])
    write_rows(test_path, [])

    dataset = build_vimqa_dataset(train_path=train_path, test_path=test_path)

    assert dataset.documents[0].source_splits == ["train"]
    assert dataset.queries[0].answer == "Nguyễn Du"
    assert dataset.queries[0].split == "train"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_vimqa_dataset.py -q
```

Expected: fail because `src.data.vimqa` does not exist.

- [ ] **Step 3: Implement the minimal adapter**

Create `src/data/vimqa.py` with dataclasses and functions equivalent to:

```python
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VimQADocument:
    numeric_id: int
    doc_id: str
    title: str
    text: str
    content: str
    embedding_text: str
    source_splits: list[str]


@dataclass(frozen=True)
class VimQAQuery:
    query_id: str
    query: str
    doc_id: str
    split: str
    answer: str


@dataclass(frozen=True)
class VimQADataset:
    documents: list[VimQADocument]
    queries: list[VimQAQuery]
    qrels: dict[str, str]


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", str(value)).strip().split())


def context_doc_id(context: str) -> str:
    digest = hashlib.sha1(normalize_text(context).lower().encode("utf-8")).hexdigest()[:16]
    return f"vimqa_ctx_{digest}"


def load_rows(path: Path) -> list[dict[str, str]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"VimQA file must contain a JSON list: {path}")
    return rows


def build_vimqa_dataset(*, train_path: Path, test_path: Path) -> VimQADataset:
    docs_by_id: dict[str, VimQADocument] = {}
    split_sets: dict[str, set[str]] = {}
    queries: list[VimQAQuery] = []

    for split, path in (("train", train_path), ("test", test_path)):
        for index, row in enumerate(load_rows(path)):
            question = normalize_text(row.get("question", ""))
            context = normalize_text(row.get("context", ""))
            answer = normalize_text(row.get("answer", ""))
            if not question or not context:
                raise ValueError(f"VimQA row is missing question/context: {path}:{index}")
            doc_id = context_doc_id(context)
            split_sets.setdefault(doc_id, set()).add(split)
            if doc_id not in docs_by_id:
                docs_by_id[doc_id] = VimQADocument(
                    numeric_id=len(docs_by_id),
                    doc_id=doc_id,
                    title="VimQA context",
                    text=context,
                    content=context,
                    embedding_text=context,
                    source_splits=[],
                )
            query_id = f"vimqa_{split}_{index:06d}"
            queries.append(VimQAQuery(query_id=query_id, query=question, doc_id=doc_id, split=split, answer=answer))

    documents = [
        VimQADocument(
            numeric_id=doc.numeric_id,
            doc_id=doc.doc_id,
            title=doc.title,
            text=doc.text,
            content=doc.content,
            embedding_text=doc.embedding_text,
            source_splits=sorted(split_sets[doc.doc_id]),
        )
        for doc in sorted(docs_by_id.values(), key=lambda item: item.numeric_id)
    ]
    return VimQADataset(documents=documents, queries=queries, qrels={query.query_id: query.doc_id for query in queries})
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_vimqa_dataset.py -q
```

Expected: 2 passed.

### Task 2: Add VimQA Staging Script And Artifact Contract

**Files:**
- Create: `scripts/stage_vimqa.py`
- Test: `tests/test_stage_vimqa.py`

- [ ] **Step 1: Write failing staging tests**

Create `tests/test_stage_vimqa.py`:

```python
import json
from pathlib import Path

from scripts.stage_vimqa import stage_vimqa


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def test_stage_vimqa_writes_staging_queries_qrels_and_manifest(tmp_path):
    train_path = tmp_path / "train_vimqa.json"
    test_path = tmp_path / "test_vimqa.json"
    output_dir = tmp_path / "artifacts"
    result_dir = tmp_path / "results"
    write_rows(train_path, [{"question": "Thủ đô Việt Nam?", "context": "Hà Nội là thủ đô Việt Nam.", "answer": "Hà Nội"}])
    write_rows(test_path, [{"question": "Việt Nam có thủ đô nào?", "context": "Hà Nội là thủ đô Việt Nam.", "answer": "Hà Nội"}])

    summary = stage_vimqa(
        train_path=train_path,
        test_path=test_path,
        staging_dir=output_dir / "staging",
        results_dir=result_dir,
        docs_per_file=100,
    )

    assert summary["documents"] == 1
    assert summary["queries"] == 2
    manifest = json.loads((output_dir / "staging" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset"] == "vimqa"
    first_doc = json.loads((output_dir / "staging" / "docs-00000.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert first_doc["numeric_id"] == 0
    assert first_doc["content"] == "Hà Nội là thủ đô Việt Nam."
    assert first_doc["source_split"] == "train,test"
    query_header = (result_dir / "vimqa_queries.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert query_header == "query_id\tsource_query_id\tquery\tsplit\tanswer"
    qrels_header = (result_dir / "vimqa_qrels.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert qrels_header == "query_id\tdoc_id\trelevance"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_stage_vimqa.py -q
```

Expected: fail because `scripts.stage_vimqa` does not exist.

- [ ] **Step 3: Implement staging script**

Create `scripts/stage_vimqa.py` with:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.vimqa import build_vimqa_dataset


def stage_vimqa(*, train_path: Path, test_path: Path, staging_dir: Path, results_dir: Path, docs_per_file: int) -> dict[str, int]:
    dataset = build_vimqa_dataset(train_path=train_path, test_path=test_path)
    staging_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for shard_index in range(0, len(dataset.documents), docs_per_file):
        shard_docs = dataset.documents[shard_index : shard_index + docs_per_file]
        path = staging_dir / f"docs-{len(files):05d}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for doc in shard_docs:
                handle.write(json.dumps({
                    "numeric_id": doc.numeric_id,
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "text": doc.text,
                    "url": "",
                    "content": doc.content,
                    "embedding_text": doc.embedding_text,
                    "source_split": ",".join(doc.source_splits),
                }, ensure_ascii=False) + "\n")
        files.append({"file": path.name, "docs": len(shard_docs)})

    (results_dir / "vimqa_queries.tsv").write_text(
        "query_id\tsource_query_id\tquery\tsplit\tanswer\n" +
        "".join(f"{q.query_id}\t{q.query_id}\t{q.query}\t{q.split}\t{q.answer}\n" for q in dataset.queries),
        encoding="utf-8",
    )
    (results_dir / "vimqa_qrels.tsv").write_text(
        "query_id\tdoc_id\trelevance\n" +
        "".join(f"{query_id}\t{doc_id}\t1\n" for query_id, doc_id in dataset.qrels.items()),
        encoding="utf-8",
    )
    manifest = {"dataset": "vimqa", "documents": len(dataset.documents), "queries": len(dataset.queries), "qrels": len(dataset.qrels), "files": files}
    (staging_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"documents": len(dataset.documents), "queries": len(dataset.queries), "qrels": len(dataset.qrels), "files": len(files)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage local VimQA JSON files for Elasticsearch retrieval")
    parser.add_argument("--train", type=Path, default=Path("docs/data/vimqa/train_vimqa.json"))
    parser.add_argument("--test", type=Path, default=Path("docs/data/vimqa/test_vimqa.json"))
    parser.add_argument("--staging-dir", type=Path, default=Path("artifacts/vimqa/all/staging"))
    parser.add_argument("--results-dir", type=Path, default=Path("evaluation/results/vimqa"))
    parser.add_argument("--docs-per-file", type=int, default=5000)
    args = parser.parse_args()
    print(json.dumps(stage_vimqa(train_path=args.train, test_path=args.test, staging_dir=args.staging_dir, results_dir=args.results_dir, docs_per_file=args.docs_per_file), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_stage_vimqa.py tests/test_vimqa_dataset.py -q
```

Expected: all tests pass.

### Task 3: Preserve VimQA Metadata In Elasticsearch Documents

**Files:**
- Modify: `src/retrieval/elasticsearch_retriever.py`
- Test: `tests/test_elasticsearch_retriever.py`

- [ ] **Step 1: Add failing metadata mapping/action tests**

Append tests equivalent to:

```python
def test_build_index_body_supports_optional_vimqa_metadata_fields():
    body = build_index_body(dims=768)
    properties = body["mappings"]["properties"]
    assert properties["source_split"] == {"type": "keyword"}
    assert properties["answer"] == {"type": "keyword"}


def test_bulk_action_preserves_optional_metadata_fields():
    action = bulk_action(
        "idx",
        {
            "doc_id": "vimqa_ctx_1",
            "title": "VimQA context",
            "text": "Hà Nội là thủ đô Việt Nam.",
            "content": "Hà Nội là thủ đô Việt Nam.",
            "source_split": "train,test",
            "answer": "Hà Nội",
        },
        [0.1, 0.2],
    )
    assert action["source_split"] == "train,test"
    assert action["answer"] == "Hà Nội"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_elasticsearch_retriever.py -q
```

Expected: new assertions fail because metadata fields are not mapped/preserved.

- [ ] **Step 3: Implement minimal metadata preservation**

Modify `build_index_body`, `build_bm25_index_body`, `bulk_action`, `bm25_bulk_action`, `build_bm25_query`, `build_knn_query`, and `_search_body` so optional fields are stored and returned:

```python
OPTIONAL_METADATA_FIELDS = ("source_split", "answer", "author", "created_at", "modified_at")


def _copy_optional_metadata(row: dict[str, Any], target: dict[str, Any]) -> None:
    for field in OPTIONAL_METADATA_FIELDS:
        value = row.get(field)
        if value not in (None, ""):
            target[field] = value
```

Use `_source`: `['numeric_id', 'doc_id', 'title', 'text', 'url', *OPTIONAL_METADATA_FIELDS]` in search queries.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_elasticsearch_retriever.py tests/test_stage_vimqa.py -q
```

Expected: all selected tests pass.

### Task 4: Stage Full VimQA Artifacts

**Files:**
- Generated: `artifacts/vimqa/all/staging/`
- Generated: `evaluation/results/vimqa/vimqa_queries.tsv`
- Generated: `evaluation/results/vimqa/vimqa_qrels.tsv`

- [ ] **Step 1: Discover benchmark tooling**

Run:

```powershell
.\scripts\bin\harness-cli.exe query tools --capability benchmark --status present
```

Expected: `python` is present. If absent, skip staging and record Harness friction.

- [ ] **Step 2: Generate VimQA staging artifacts**

Run:

```powershell
python scripts/stage_vimqa.py --docs-per-file 5000
```

Expected summary approximately:

```json
{
  "documents": 3623,
  "queries": 9044,
  "qrels": 9044,
  "files": 1
}
```

- [ ] **Step 3: Inspect manifest**

Run:

```powershell
Get-Content artifacts/vimqa/all/staging/manifest.json
```

Expected: dataset is `vimqa`, document count is around `3623`, query count is `9044`.

### Task 5: Run Elasticsearch BM25 VimQA Retrieval Benchmark

**Files:**
- Generated: Elasticsearch index `vimqa_all_bm25_v1` with alias `vimqa_all_bm25_current`
- Generated: `evaluation/results/vimqa/bm25_vimqa_all.json`
- Generated: `evaluation/runs/vimqa/es_bm25_vimqa_top10.trec`

- [ ] **Step 1: Discover service runtime and test tooling**

Run:

```powershell
.\scripts\bin\harness-cli.exe query tools --capability service-runtime --status present
.\scripts\bin\harness-cli.exe query tools --capability test --status present
```

Expected: Docker and pytest are present.

- [ ] **Step 2: Start Elasticsearch if needed**

Run:

```powershell
docker compose up -d elasticsearch
```

Expected: Elasticsearch service becomes healthy at `http://localhost:9200`.

- [ ] **Step 3: Create BM25 index**

Run:

```powershell
python scripts/es_hotpotqa.py create-bm25-index --index vimqa_all_bm25_v1 --alias vimqa_all_bm25_current --reset
```

Expected: JSON reports index and alias created with mode `bm25`.

- [ ] **Step 4: Ingest VimQA BM25 docs**

Run:

```powershell
python scripts/es_hotpotqa.py ingest-bm25 --index vimqa_all_bm25_v1 --staging-dir artifacts/vimqa/all/staging --progress-dir artifacts/vimqa/all/progress/bm25 --batch-size 1000
```

Expected: one staging file ingested.

- [ ] **Step 5: Validate count**

Run:

```powershell
python scripts/es_hotpotqa.py validate --index vimqa_all_bm25_current --expected-count 3623
```

Expected: `count_matches` is true. If count differs, use manifest count instead of guessing.

- [ ] **Step 6: Run BM25 benchmark**

Run:

```powershell
python -m src.evaluation.benchmark_es --dataset vimqa/all --index vimqa_all_bm25_current --methods es_bm25 --top-k 10 --query-file evaluation/results/vimqa/vimqa_queries.tsv --qrels-file evaluation/results/vimqa/vimqa_qrels.tsv --output evaluation/results/vimqa/bm25_vimqa_all.json --run-dir evaluation/runs/vimqa
```

Expected: JSON result and TREC run are written. If `benchmark_es` rejects the query TSV shape, implement the minimal TSV loader adjustment in Task 6.

### Task 6: Make Benchmark Query Loading Dataset-Neutral If Needed

**Files:**
- Modify: `src/evaluation/benchmark_es.py`
- Test: `tests/test_benchmark_es.py`

- [ ] **Step 1: Add failing query TSV compatibility test**

Add a test that writes `query_id`, `source_query_id`, and `query` columns and asserts `run_benchmark` uses `query_id` as the query id.

```python
def test_run_benchmark_accepts_dataset_query_file_with_query_id_header(tmp_path, monkeypatch):
    query_file = tmp_path / "queries.tsv"
    qrels_file = tmp_path / "qrels.tsv"
    query_file.write_text("query_id\tsource_query_id\tquery\nq1\tq1\tHà Nội là gì?\n", encoding="utf-8")
    qrels_file.write_text("query_id\tdoc_id\trelevance\nq1\td1\t1\n", encoding="utf-8")

    class FakeRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            return [{"doc_id": "d1", "score": 1.0}]

    monkeypatch.setattr("src.evaluation.benchmark_es.build_retriever", lambda *args, **kwargs: FakeRetriever())
    result = run_benchmark(
        dataset_id="vimqa/all",
        index="idx",
        methods=["es_bm25"],
        top_k=10,
        max_queries=None,
        url="http://example.invalid",
        model_name="model",
        num_candidates=100,
        candidate_k=10,
        rrf_k=60,
        first_hop_k=5,
        second_hop_k=10,
        context_chars=256,
        run_dir=tmp_path,
        query_file=query_file,
        qrels_file=qrels_file,
    )
    assert result["config"]["queries"] == 1
    assert result["results"][0]["metrics"]["recall@10"] == 1.0
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_benchmark_es.py -q
```

Expected: fail if `_load_query_file` only accepts `variant_query_id`.

- [ ] **Step 3: Implement dataset-neutral query file loader**

Modify `_load_query_file` to accept either `variant_query_id` or `query_id`:

```python
query_id = str(row.get("variant_query_id") or row.get("query_id") or "").strip()
if not query_id:
    raise ValueError(f"Query file row is missing query id: {path}")
queries[query_id] = str(row["query"])
source_query_ids[query_id] = str(row.get("source_query_id") or query_id)
```

- [ ] **Step 4: Run tests and re-run BM25 benchmark**

Run:

```powershell
python -m pytest tests/test_benchmark_es.py -q
python -m src.evaluation.benchmark_es --dataset vimqa/all --index vimqa_all_bm25_current --methods es_bm25 --top-k 10 --query-file evaluation/results/vimqa/vimqa_queries.tsv --qrels-file evaluation/results/vimqa/vimqa_qrels.tsv --output evaluation/results/vimqa/bm25_vimqa_all.json --run-dir evaluation/runs/vimqa
```

Expected: tests pass and BM25 benchmark writes artifacts.

### Task 7: Run Dense/Hybrid VimQA Benchmark In Elasticsearch

**Files:**
- Generated: one or more dense ES indexes, for example `vimqa_all_dense_halong_v1` or `vimqa_all_dense_aiteam_v1`
- Generated: `evaluation/results/vimqa/dense_<model_slug>_vimqa_all.json`
- Generated: `evaluation/runs/vimqa/*.trec`

- [ ] **Step 1: Use the paper-backed primary dense model**

Use only the paper-backed primary model first:

```text
Primary: bkai-foundation-models/vietnamese-bi-encoder, dims=768
Fallback only if segmentation/runtime blocks progress: AITeamVN/Vietnamese_Embedding, dims=1024
```

Rationale: VIMQA's original paper uses BM25 for distractor retrieval rather than dense embeddings. For dense retrieval, the closest Vietnamese IR paper evidence favors `bkai-foundation-models/vietnamese-bi-encoder` on Vietnamese retrieval tasks. Do not spend Sprint time trying many embedding models.

- [ ] **Step 2: Create dense index for BKAI**

Run:

```powershell
python scripts/es_hotpotqa.py create-index --index vimqa_all_dense_bkai_v1 --alias vimqa_all_dense_bkai_current --dims 768 --reset
```

If BKAI is blocked and the user approves fallback, run:

```powershell
python scripts/es_hotpotqa.py create-index --index vimqa_all_dense_aiteam_v1 --alias vimqa_all_dense_aiteam_current --dims 1024 --reset
```

- [ ] **Step 3: Ingest dense vectors**

For BKAI:

```powershell
python scripts/es_hotpotqa.py ingest --index vimqa_all_dense_bkai_v1 --staging-dir artifacts/vimqa/all/staging --progress-dir artifacts/vimqa/all/progress/dense_bkai --model bkai-foundation-models/vietnamese-bi-encoder --batch-size 64
```

If fallback is needed:

```powershell
python scripts/es_hotpotqa.py ingest --index vimqa_all_dense_aiteam_v1 --staging-dir artifacts/vimqa/all/staging --progress-dir artifacts/vimqa/all/progress/dense_aiteam --model AITeamVN/Vietnamese_Embedding --batch-size 64
```

- [ ] **Step 4: Validate dense index count**

Run the matching command:

```powershell
python scripts/es_hotpotqa.py validate --index vimqa_all_dense_bkai_current --expected-count 3623
python scripts/es_hotpotqa.py validate --index vimqa_all_dense_aiteam_current --expected-count 3623
```

Expected: count matches manifest document count.

- [ ] **Step 5: Run dense and hybrid benchmark**

For BKAI:

```powershell
python -m src.evaluation.benchmark_es --dataset vimqa/all --index vimqa_all_dense_bkai_current --methods es_bm25,es_dense,es_hybrid --top-k 10 --query-file evaluation/results/vimqa/vimqa_queries.tsv --qrels-file evaluation/results/vimqa/vimqa_qrels.tsv --model bkai-foundation-models/vietnamese-bi-encoder --num-candidates 500 --candidate-k 50 --rrf-k 30 --output evaluation/results/vimqa/dense_bkai_vimqa_all.json --run-dir evaluation/runs/vimqa
```

For AITeamVN:

```powershell
python -m src.evaluation.benchmark_es --dataset vimqa/all --index vimqa_all_dense_aiteam_current --methods es_bm25,es_dense,es_hybrid --top-k 10 --query-file evaluation/results/vimqa/vimqa_queries.tsv --qrels-file evaluation/results/vimqa/vimqa_qrels.tsv --model AITeamVN/Vietnamese_Embedding --num-candidates 500 --candidate-k 50 --rrf-k 30 --output evaluation/results/vimqa/dense_aiteam_vimqa_all.json --run-dir evaluation/runs/vimqa
```

Expected: metrics include `recall@1`, `recall@5`, `recall@10`, `mrr@10`, `ndcg@10`, latency percentiles, and QPS.

### Task 8: Write VimQA Design And Pipeline Report

**Files:**
- Create: `docs/sprint4/vimqa-benchmark-design.md`
- Create: `docs/sprint4/vimqa-pipeline-report.md`
- Modify: `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-008-vimqa-benchmark-pipeline-research.md`

- [ ] **Step 1: Write the design document**

Include these sections:

```markdown
# VimQA Benchmark Design

## Dataset Contract
VimQA is converted from QA rows into a context retrieval proxy: question -> query, unique context -> document, question-context relation -> qrel.

## Corpus Shape
- Input files: docs/data/vimqa/train_vimqa.json and docs/data/vimqa/test_vimqa.json.
- Fields: question, context, answer.
- Corpus: union of unique normalized contexts from train and test.

## Retrieval Semantics
Each query has one gold context. Recall@k means retrieving that context, not full multi-support evidence as in HotpotQA.

## Index Strategy
Use Elasticsearch BM25 and dense_vector first. TurboVec is out of scope for VimQA MVP because the corpus is small and future metadata filters are easier in Elasticsearch.

## Model Strategy
Primary dense model: bkai-foundation-models/vietnamese-bi-encoder, based on Vietnamese IR paper evidence. Fallback only if segmentation/runtime blocks progress: AITeamVN/Vietnamese_Embedding. VIMQA's original paper-backed retrieval baseline is BM25.
```

- [ ] **Step 2: Write pipeline report from actual artifacts**

Include exact commands, result paths, metrics table, index names, model names, dimensions, and caveats. Do not claim paper-comparable VimQA benchmark results.

- [ ] **Step 3: Update story evidence**

Run, replacing evidence text with actual commands/results:

```powershell
.\scripts\bin\harness-cli.exe story update --id US-S4-008 --status implemented
.\scripts\bin\harness-cli.exe story update --id US-S4-008 --unit 1 --integration 1 --e2e 0 --platform 1
```

Expected: Harness matrix shows US-S4-008 implemented with unit/integration/platform proof.

---

## Phase 2: Dataset-First API And Frontend Refactor

Start this phase only after Phase 1 has produced VimQA retrieval artifacts.

### Task 9: Add Dataset Profile Registry

**Files:**
- Create: `src/api/dataset_profiles.py`
- Test: `tests/test_api_dataset_profiles.py`

- [ ] **Step 1: Write failing profile tests**

Test that `hotpotqa` and `vimqa` profiles exist and expose index, methods, default method, language, dense backend, and readiness fields.

- [ ] **Step 2: Implement `DatasetProfile`**

Use a frozen dataclass with explicit fields:

```python
@dataclass(frozen=True)
class DatasetProfile:
    id: str
    label: str
    language: str
    index: str
    methods: tuple[str, ...]
    default_method: str
    dense_backend: str
    embedding_model: str
    vector_dims: int | None
    query_file: Path | None
    qrels_file: Path | None
    benchmark_files: tuple[Path, ...]
```

### Task 10: Add Dataset-Scoped API Endpoints

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api_es_config.py`
- Modify: `tests/test_api_cache.py`

- [ ] **Step 1: Add endpoint tests**

Cover:

```text
GET /datasets
GET /datasets/vimqa/stats
GET /datasets/vimqa/queries
POST /datasets/vimqa/search
GET /datasets/vimqa/benchmarks
```

- [ ] **Step 2: Implement endpoints by delegating to existing search/query/benchmark helpers**

Legacy endpoints stay in place and delegate to the `hotpotqa` profile until frontend migration is complete.

- [ ] **Step 3: Fix cache keys**

Cache key payload must include:

```json
{
  "dataset_id": "vimqa",
  "index": "vimqa_all_dense_halong_current",
  "method": "es_hybrid",
  "model": "contextboxai/halong_embedding",
  "top_k": 10,
  "query": "..."
}
```

### Task 11: Refactor Frontend To Dataset-First Workspace

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/components/SearchView.tsx`
- Modify: `frontend/src/components/QueriesView.tsx`
- Modify: `frontend/src/components/BenchmarkView.tsx`
- Modify: `frontend/src/components/StatusView.tsx`

- [ ] **Step 1: Add dataset types and API client methods**

Add `DatasetProfile`, `DatasetStats`, and dataset-scoped functions:

```typescript
getDatasets()
getDatasetStats(datasetId)
getDatasetQueries(datasetId, params)
searchDataset(datasetId, request)
getDatasetBenchmark(datasetId)
```

- [ ] **Step 2: Add dataset-first navigation state**

Keep `activeDatasetId` at app level. Dataset selector changes workspace content but keeps the selected child view when possible.

- [ ] **Step 3: Update labels and metrics by dataset**

HotpotQA benchmark keeps `full_support_recall@10`. VimQA benchmark emphasizes `recall@1/5/10`, `mrr@10`, and `ndcg@10`.

### Task 12: Update Docker And Architecture Docs

**Files:**
- Modify: `docker-compose.yml` only if env wiring is needed.
- Modify: `README.md`
- Modify: `docs/architecture/current-architecture.md`
- Modify: `docs/stories/epics/E04-sprint4-evaluation-expansion/README.md`
- Modify: `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-011-dataset-first-api-ui-refactor.md`

- [ ] **Step 1: Document runtime modes**

Record these modes:

```text
UI/API lightweight: frontend + api, no search guarantee.
Search runtime: frontend + api + elasticsearch + redis + embedding service when dense is used.
Index/benchmark runtime: elasticsearch + scripts, frontend optional.
Full demo runtime: frontend + api + elasticsearch + redis + embedding service + prepared HotpotQA/VimQA indexes.
```

- [ ] **Step 2: Update Harness proof**

After implementation, update `US-S4-011` proof booleans according to actual validation:

```powershell
.\scripts\bin\harness-cli.exe story update --id US-S4-011 --status implemented
.\scripts\bin\harness-cli.exe story update --id US-S4-011 --unit 1 --integration 1 --e2e 1 --platform 1
```

---

## Final Verification Commands

Run after Phase 1:

```powershell
python -m pytest tests/test_vimqa_dataset.py tests/test_stage_vimqa.py tests/test_elasticsearch_retriever.py tests/test_benchmark_es.py -q
python scripts/stage_vimqa.py --docs-per-file 5000
python scripts/es_hotpotqa.py validate --index vimqa_all_bm25_current --expected-count 3623
python -m src.evaluation.benchmark_es --dataset vimqa/all --index vimqa_all_bm25_current --methods es_bm25 --top-k 10 --query-file evaluation/results/vimqa/vimqa_queries.tsv --qrels-file evaluation/results/vimqa/vimqa_qrels.tsv --output evaluation/results/vimqa/bm25_vimqa_all.json --run-dir evaluation/runs/vimqa
```

Run after Phase 2:

```powershell
python -m pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_api_dataset_profiles.py -q
cd frontend
npm run lint
```

If Docker runtime is part of the completion claim, also run a manual smoke against:

```text
GET http://localhost:8001/datasets
GET http://localhost:8001/datasets/vimqa/stats
POST http://localhost:8001/datasets/vimqa/search
```

## Self-Review Notes

- Spec coverage: The plan implements VimQA corpus/query/qrels conversion, Elasticsearch BM25/dense retrieval, benchmark artifacts, reports, and later dataset-first API/frontend routing.
- Placeholder scan: No open TBD/TODO placeholders remain; model choice is ordered and explicit.
- Type consistency: The plan consistently uses `query_id`, `source_query_id`, `doc_id`, `source_split`, and `answer` across staging, benchmark, and metadata preservation.
- Scope control: TurboVec is deliberately excluded from VimQA MVP; dense retrieval stays in Elasticsearch; dense model exploration is limited to BM25 plus BKAI dense/hybrid, with AITeamVN only as fallback.
