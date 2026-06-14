# Sprint 3 HotpotQA 5M TurboVec Hybrid Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and evaluate full-scale HotpotQA retrieval over 5,233,329 documents with Elasticsearch BM25, TurboVec dense search, and RRF hybrid fusion.

**Architecture:** Keep Elasticsearch as the BM25 lexical index and document store. Move full-scale dense retrieval out of Elasticsearch `dense_vector` into TurboVec `IdMapIndex` with 4-bit quantization, then fuse BM25 and dense rankings in the application layer with Reciprocal Rank Fusion. Preserve the existing Elasticsearch-only code path for nano/legacy experiments, but make the full-scale path `es_bm25`, `tv_dense`, and `tv_hybrid`.

**Tech Stack:** Python 3.12, Elasticsearch 8.x, SentenceTransformers `BAAI/bge-small-en-v1.5`, TurboVec 0.8.x, NumPy, FastAPI, pytest, existing HotpotQA staging/evaluation code.

---

## Scope Lock

Sprint 3 focuses only on full-scale HotpotQA retrieval.

In scope:

- Full HotpotQA corpus staging with stable `numeric_id`.
- Elasticsearch BM25-only full index.
- Resumable BGE-small embedding shard generation.
- TurboVec dense index build and load/search smoke tests.
- `tv_dense` and `tv_hybrid` retrieval methods.
- Benchmark accuracy and latency on at least 200 HotpotQA queries.
- API method exposure after offline benchmark path works.
- Final sprint report with commands, hardware, metrics, latency, and limitations.

Out of scope:

- VimQA integration.
- Answer generation or reader model.
- LLM reasoning agent.
- Fine-tuning embedding models.
- Reranker training.
- Frontend redesign.
- Making iterative multihop the default retrieval mode.

## Success Criteria

- `artifacts/hotpotqa_full/staging/manifest.json` reports exactly `5,233,329` documents.
- Elasticsearch index `hotpotqa_full_bm25_v1` validates exactly `5,233,329` documents.
- TurboVec full index loads from disk and returns `numeric_id` results for BGE-small query embeddings.
- `tv_dense` returns hydrated HotpotQA documents from full corpus.
- `tv_hybrid` fuses Elasticsearch BM25 and TurboVec dense rankings with RRF.
- Benchmark output exists for `es_bm25`, `tv_dense`, and `tv_hybrid` on at least 200 queries.
- Benchmark reports `precision@10`, `recall@10`, `mrr@10`, `ndcg@10`, `full_support_recall@10`, p50/p95/p99 latency, and QPS.
- API `/search` accepts `tv_hybrid` after offline retrieval and benchmark are stable.
- `docs/sprint3/sprint3-report.md` summarizes the final result.

## Design Decisions

### Dense Backend

Do not use Elasticsearch `dense_vector` for the full 5M index in Sprint 3. Local RAM is around 16 GB, and Elasticsearch dense vector/HNSW overhead is too risky for full-scale experiments. TurboVec is compatible with the current Windows/Python 3.12 environment and supports `IdMapIndex`, `add_with_ids`, `search`, `allowlist`, `write`, and `load`.

Use:

```text
Elasticsearch: BM25 + document store
TurboVec: compressed dense vector search
App layer: RRF fusion
```

### Numeric IDs

TurboVec external ids are `uint64`, while HotpotQA `doc_id` values are strings. Add a stable sequential `numeric_id` during staging and carry it through Elasticsearch, embedding shards, and TurboVec.

Rules:

- `numeric_id` starts at `0`.
- `numeric_id` increments by one in staging order.
- `numeric_id` is stored in each staged JSONL row.
- `numeric_id` is stored in Elasticsearch as `long`.
- Embedding shard ids are saved as `uint64` NumPy arrays.
- Retrieval hydrates final results from Elasticsearch by `numeric_id` or `doc_id` while preserving ranking order.

### Accuracy Defaults

Initial full-scale retrieval config:

```yaml
top_k: 10
bm25_k: 100
dense_k: 100
rrf_k: 30
embedding_model: BAAI/bge-small-en-v1.5
normalize_embeddings: true
turbovec_bit_width: 4
```

Use 4-bit TurboVec first. Do not start with 2-bit because BGE-small has 384 dimensions, and lower-dimensional embeddings may lose more quality under heavier quantization.

### Latency Defaults

- Load TurboVec index once per process.
- Load SentenceTransformer once per process or use the existing embedding service.
- Cache query embeddings in process for repeated benchmark/API queries.
- Fetch only final top-k documents from Elasticsearch after fusion.
- Keep iterative retrieval experimental because it multiplies BM25, dense, and embedding calls per query.

## File Structure

Create or modify these files:

- Modify `requirements.txt`: add `turbovec`.
- Modify `src/data/staging.py`: add `numeric_id` staging support and manifest validation helpers.
- Modify `scripts/stage_hotpotqa.py`: pass through numeric ids for full corpus staging.
- Create `scripts/embed_hotpotqa.py`: encode staging shards to NumPy embedding and id shards.
- Create `scripts/build_turbovec.py`: build and persist TurboVec `IdMapIndex` from embedding shards.
- Modify `src/retrieval/elasticsearch_retriever.py`: add BM25-only index body/action helpers and numeric-id source fields without breaking legacy vector helpers.
- Create `src/retrieval/turbovec_retriever.py`: load TurboVec, embed queries, dense search, hydrate docs, and hybrid RRF search.
- Modify `src/evaluation/benchmark_es.py`: support `tv_dense`, `tv_hybrid`, and custom query/qrels mode without mandatory `ir_datasets` load when files are provided.
- Modify `src/core/config.py`: add TurboVec and full-scale retrieval env vars.
- Modify `src/api/main.py`: add `tv_dense` and `tv_hybrid` methods after retrieval tests pass.
- Create `docs/sprint3/sprint3-report.md`: final report after benchmarks are complete.

## Artifact Layout

```text
artifacts/hotpotqa_full/
  staging/
    docs-00000.jsonl
    docs-00001.jsonl
    manifest.json
  embeddings/
    docs-00000.float16.npy
    docs-00000.ids.npy
    docs-00000.meta.json
  turbovec/
    hotpotqa_bge_small_4bit.tvim
    config.json
  progress/
    bm25/
    embed/
    turbovec/

evaluation/results/hotpotqa_full/
evaluation/runs/hotpotqa_full/
```

---

## Task 1: Add TurboVec Dependency And Smoke Test

**Files:**

- Modify: `requirements.txt`
- Create: `tests/test_turbovec_smoke.py`

- [ ] **Step 1: Write a failing import/search/load test**

Create `tests/test_turbovec_smoke.py`:

```python
from __future__ import annotations

import numpy as np


def test_turbovec_id_map_add_search_and_load(tmp_path):
    from turbovec import IdMapIndex

    rng = np.random.default_rng(13)
    vectors = rng.normal(size=(100, 384)).astype("float32")
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    ids = np.arange(1000, 1100, dtype=np.uint64)

    index = IdMapIndex(dim=384, bit_width=4)
    index.add_with_ids(vectors, ids)

    scores, result_ids = index.search(vectors[7:8], k=3)
    assert scores.shape == (1, 3)
    assert result_ids[0, 0] == 1007

    path = tmp_path / "smoke.tvim"
    index.write(str(path))
    loaded = IdMapIndex.load(str(path))
    loaded_scores, loaded_ids = loaded.search(vectors[7:8], k=3)
    assert loaded_ids[0, 0] == 1007
    assert loaded_scores.shape == (1, 3)
```

- [ ] **Step 2: Run the test and verify it fails before dependency is installed**

Run:

```powershell
pytest tests/test_turbovec_smoke.py -q
```

Expected before dependency: FAIL with `ModuleNotFoundError: No module named 'turbovec'`.

- [ ] **Step 3: Add dependency**

Add to `requirements.txt`:

```text
turbovec==0.8.0
```

- [ ] **Step 4: Install and verify**

Run:

```powershell
python -m pip install -r requirements.txt
pytest tests/test_turbovec_smoke.py -q
```

Expected: PASS.

---

## Task 2: Add Numeric IDs To Staging

**Files:**

- Modify: `src/data/staging.py`
- Modify: `tests/test_staging.py`
- Modify: `scripts/stage_hotpotqa.py`

- [ ] **Step 1: Write failing staging tests**

Add tests to `tests/test_staging.py`:

```python
def test_write_staging_shards_assigns_stable_numeric_ids(tmp_path):
    raw_type = namedtuple("RawDoc", ["doc_id", "title", "text", "url"])
    docs = [raw_type(f"d{idx}", "T", f"body {idx}", "") for idx in range(3)]

    manifest = write_staging_shards(docs, tmp_path, docs_per_file=2)

    rows = []
    for path in iter_staging_files(tmp_path):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    assert [row["numeric_id"] for row in rows] == [0, 1, 2]
    assert manifest["docs_written"] == 3
    assert manifest["numeric_id_start"] == 0
    assert manifest["numeric_id_end"] == 2


def test_validate_staging_manifest_rejects_missing_shards(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"docs_written": 4, "files_written": 2, "docs_per_file": 2}),
        encoding="utf-8",
    )
    (tmp_path / "docs-00000.jsonl").write_text("{}\n{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="files_written=2 but found 1 staging files"):
        validate_staging_manifest(tmp_path)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
pytest tests/test_staging.py -q
```

Expected: FAIL because `numeric_id` and `validate_staging_manifest` are not implemented yet.

- [ ] **Step 3: Implement staging support**

In `src/data/staging.py`, update `write_staging_shards` so each normalized row gets `numeric_id = docs_written` before writing. Add `load_staging_manifest` and `validate_staging_manifest` helpers.

Implementation behavior:

```text
manifest fields:
  docs_written
  files_written
  docs_per_file
  numeric_id_start
  numeric_id_end

validate_staging_manifest checks:
  manifest exists
  actual docs-*.jsonl count equals files_written
  optional expected_docs equals docs_written
```

- [ ] **Step 4: Verify**

Run:

```powershell
pytest tests/test_staging.py -q
```

Expected: PASS.

---

## Task 3: Build BM25-Only Elasticsearch Index Path

**Files:**

- Modify: `src/retrieval/elasticsearch_retriever.py`
- Modify: `scripts/es_hotpotqa.py`
- Modify: `tests/test_elasticsearch_retriever.py`
- Modify: `tests/test_es_hotpotqa_cli.py`

- [ ] **Step 1: Write failing mapping/action tests**

Add to `tests/test_elasticsearch_retriever.py`:

```python
from src.retrieval.elasticsearch_retriever import build_bm25_index_body, bm25_bulk_action


def test_build_bm25_index_body_excludes_dense_vector_and_keeps_numeric_id():
    body = build_bm25_index_body(shards=3)

    props = body["mappings"]["properties"]
    assert props["numeric_id"] == {"type": "long"}
    assert props["doc_id"] == {"type": "keyword"}
    assert props["content"] == {"type": "text"}
    assert "embedding" not in props
    assert body["settings"]["number_of_shards"] == 3


def test_bm25_bulk_action_uses_numeric_id_and_excludes_embedding_text():
    row = {
        "numeric_id": 7,
        "doc_id": "d7",
        "title": "T",
        "text": "X",
        "url": "",
        "content": "T\nX",
        "embedding_text": "T\nX",
    }

    action = bm25_bulk_action("idx", row)

    assert action["_index"] == "idx"
    assert action["_id"] == "d7"
    assert action["numeric_id"] == 7
    assert "embedding" not in action
    assert "embedding_text" not in action
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
pytest tests/test_elasticsearch_retriever.py -q
```

Expected: FAIL because BM25-only helpers do not exist.

- [ ] **Step 3: Implement helpers**

Add `build_bm25_index_body(shards: int = 1)` and `bm25_bulk_action(index, row)` to `src/retrieval/elasticsearch_retriever.py`. Keep existing `build_index_body` and `bulk_action` for legacy ES dense path.

- [ ] **Step 4: Add CLI support**

In `scripts/es_hotpotqa.py`, add:

```text
create-bm25-index
ingest-bm25
```

Behavior:

- `create-bm25-index` calls `build_bm25_index_body`.
- `ingest-bm25` reads staging rows and bulk indexes text fields only.
- `ingest-bm25` uses the existing file-level done marker pattern under a configurable progress directory.

- [ ] **Step 5: Verify focused tests**

Run:

```powershell
pytest tests/test_elasticsearch_retriever.py tests/test_es_hotpotqa_cli.py -q
```

Expected: PASS.

---

## Task 4: Stage Full HotpotQA Corpus

**Files:**

- Uses: `scripts/stage_hotpotqa.py` or `scripts/stage_hotpotqa_hf.py`
- Creates: `artifacts/hotpotqa_full/staging/`

- [ ] **Step 1: Stage a one-file smoke subset**

Run:

```powershell
python scripts/stage_hotpotqa.py --dataset beir/hotpotqa --output-dir artifacts/hotpotqa_smoke/staging --docs-per-file 1000 --max-docs 1000
```

Expected:

```text
manifest docs_written=1000
first row numeric_id=0
last row numeric_id=999
```

- [ ] **Step 2: Stage full corpus**

Run:

```powershell
python scripts/stage_hotpotqa.py --dataset beir/hotpotqa --output-dir artifacts/hotpotqa_full/staging --docs-per-file 50000
```

If `ir_datasets` download is too slow or unreliable, use the existing Hugging Face staging script and preserve the same output schema:

```powershell
python scripts/stage_hotpotqa_hf.py --output-dir artifacts/hotpotqa_full/staging --docs-per-file 50000
```

- [ ] **Step 3: Validate manifest**

Run:

```powershell
python - <<'PY'
from pathlib import Path
from src.data.staging import validate_staging_manifest
print(validate_staging_manifest(Path('artifacts/hotpotqa_full/staging'), expected_docs=5233329))
PY
```

Expected: manifest prints with `docs_written=5233329`.

---

## Task 5: Build And Benchmark Full BM25 Index

**Files:**

- Uses: `scripts/es_hotpotqa.py`
- Uses: `src/evaluation/benchmark_es.py`
- Creates: `evaluation/results/hotpotqa_full/bm25_full_200.json`

- [ ] **Step 1: Start Elasticsearch only**

Run:

```powershell
docker compose up -d elasticsearch
```

Recommended local heap for 16 GB RAM:

```text
ES_JAVA_OPTS=-Xms6g -Xmx6g
```

- [ ] **Step 2: Create BM25 index**

Run:

```powershell
python scripts/es_hotpotqa.py create-bm25-index --index hotpotqa_full_bm25_v1 --alias hotpotqa_full_bm25_current --shards 3 --reset
```

Expected: index created with no `embedding` field.

- [ ] **Step 3: Ingest full BM25 index**

Run:

```powershell
python scripts/es_hotpotqa.py ingest-bm25 --index hotpotqa_full_bm25_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress/bm25 --batch-size 1000
```

Expected: file-level progress markers under `progress/bm25`.

- [ ] **Step 4: Validate count**

Run:

```powershell
python scripts/es_hotpotqa.py validate --index hotpotqa_full_bm25_v1 --expected-count 5233329
```

Expected: `count_matches=true`.

- [ ] **Step 5: Benchmark BM25**

Run:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa --index hotpotqa_full_bm25_v1 --methods es_bm25 --top-k 10 --max-queries 200 --candidate-k 100 --output evaluation/results/hotpotqa_full/bm25_full_200.json --run-dir evaluation/runs/hotpotqa_full
```

Expected: result JSON and TREC run file are written.

---

## Task 6: Generate Resumable Embedding Shards

**Files:**

- Create: `scripts/embed_hotpotqa.py`
- Create: `tests/test_embed_hotpotqa.py`

- [ ] **Step 1: Write failing shard writer test**

Create `tests/test_embed_hotpotqa.py`:

```python
from __future__ import annotations

import json
import numpy as np

from scripts import embed_hotpotqa


def test_write_embedding_shard_saves_vectors_ids_and_meta(tmp_path):
    staging_file = tmp_path / "docs-00000.jsonl"
    staging_file.write_text(
        "\n".join(
            [
                json.dumps({"numeric_id": 10, "embedding_text": "alpha"}),
                json.dumps({"numeric_id": 11, "embedding_text": "beta"}),
            ]
        ) + "\n",
        encoding="utf-8",
    )

    class FakeModel:
        def encode(self, texts, normalize_embeddings, convert_to_numpy, batch_size):
            assert texts == ["alpha", "beta"]
            return np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    out_dir = tmp_path / "embeddings"
    embed_hotpotqa.write_embedding_shard(staging_file, out_dir, FakeModel(), batch_size=2, model_name="fake")

    assert np.load(out_dir / "docs-00000.float16.npy").dtype == np.float16
    assert np.load(out_dir / "docs-00000.ids.npy").tolist() == [10, 11]
    meta = json.loads((out_dir / "docs-00000.meta.json").read_text(encoding="utf-8"))
    assert meta["docs"] == 2
    assert meta["dims"] == 2
    assert meta["model"] == "fake"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
pytest tests/test_embed_hotpotqa.py -q
```

Expected: FAIL because script/helper does not exist.

- [ ] **Step 3: Implement `scripts/embed_hotpotqa.py`**

Implement CLI arguments:

```text
--staging-dir
--embedding-dir
--progress-dir
--model
--batch-size
--max-files
```

Behavior:

- Iterate staging files in order.
- Skip files with `.done` marker in `progress/embed`.
- Encode `embedding_text` with `normalize_embeddings=True`.
- Save vectors as `.float16.npy` to reduce disk.
- Save ids as `.ids.npy` with `uint64` dtype.
- Save metadata JSON per shard.
- Write done marker only after all three files are successfully written.

- [ ] **Step 4: Verify test**

Run:

```powershell
pytest tests/test_embed_hotpotqa.py -q
```

Expected: PASS.

- [ ] **Step 5: Encode one smoke shard**

Run:

```powershell
python scripts/embed_hotpotqa.py --staging-dir artifacts/hotpotqa_full/staging --embedding-dir artifacts/hotpotqa_full/embeddings --progress-dir artifacts/hotpotqa_full/progress/embed --batch-size 64 --max-files 1
```

Expected: one `.float16.npy`, one `.ids.npy`, one `.meta.json`, and one `.done` marker.

- [ ] **Step 6: Encode full corpus**

Run after smoke passes:

```powershell
python scripts/embed_hotpotqa.py --staging-dir artifacts/hotpotqa_full/staging --embedding-dir artifacts/hotpotqa_full/embeddings --progress-dir artifacts/hotpotqa_full/progress/embed --batch-size 64
```

If GPU VRAM OOM occurs, retry with `--batch-size 32`.

---

## Task 7: Build TurboVec Index

**Files:**

- Create: `scripts/build_turbovec.py`
- Create: `tests/test_build_turbovec.py`

- [ ] **Step 1: Write failing build helper test**

Create `tests/test_build_turbovec.py`:

```python
from __future__ import annotations

import numpy as np

from scripts import build_turbovec


def test_embedding_shards_are_loaded_as_float32_and_uint64(tmp_path):
    emb_dir = tmp_path / "embeddings"
    emb_dir.mkdir()
    np.save(emb_dir / "docs-00000.float16.npy", np.array([[1, 0], [0, 1]], dtype=np.float16))
    np.save(emb_dir / "docs-00000.ids.npy", np.array([5, 6], dtype=np.uint64))

    shards = list(build_turbovec.iter_embedding_shards(emb_dir))
    vectors, ids = build_turbovec.load_embedding_shard(shards[0])

    assert vectors.dtype == np.float32
    assert ids.dtype == np.uint64
    assert ids.tolist() == [5, 6]
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
pytest tests/test_build_turbovec.py -q
```

Expected: FAIL because script/helper does not exist.

- [ ] **Step 3: Implement `scripts/build_turbovec.py`**

Implement CLI arguments:

```text
--embedding-dir
--output
--config-output
--dim
--bit-width
--max-shards
```

Behavior:

- Load `.float16.npy` as `float32`.
- Load ids as `uint64`.
- Create `IdMapIndex(dim=384, bit_width=4)`.
- Add each shard with `add_with_ids`.
- Write `.tvim` output.
- Write config JSON with dim, bit width, shard count, model, and build timestamp.

- [ ] **Step 4: Verify test**

Run:

```powershell
pytest tests/test_build_turbovec.py -q
```

Expected: PASS.

- [ ] **Step 5: Build smoke TurboVec index**

Run:

```powershell
python scripts/build_turbovec.py --embedding-dir artifacts/hotpotqa_full/embeddings --output artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit_smoke.tvim --config-output artifacts/hotpotqa_full/turbovec/config_smoke.json --dim 384 --bit-width 4 --max-shards 1
```

Expected: `.tvim` and config JSON are written.

- [ ] **Step 6: Build full TurboVec index**

Run:

```powershell
python scripts/build_turbovec.py --embedding-dir artifacts/hotpotqa_full/embeddings --output artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim --config-output artifacts/hotpotqa_full/turbovec/config.json --dim 384 --bit-width 4
```

Expected: full `.tvim` index is written and can be loaded.

---

## Task 8: Implement TurboVec Dense And Hybrid Retriever

**Files:**

- Create: `src/retrieval/turbovec_retriever.py`
- Create: `tests/test_turbovec_retriever.py`

- [ ] **Step 1: Write failing RRF/hydration test**

Create `tests/test_turbovec_retriever.py`:

```python
from __future__ import annotations

import numpy as np

from src.retrieval.turbovec_retriever import TurboVecHybridRetriever


def test_tv_hybrid_fuses_bm25_and_dense_and_preserves_hydrated_order():
    class FakeESRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            assert method == "bm25"
            return [
                {"doc_id": "d1", "numeric_id": 1, "title": "A", "source": "bm25"},
                {"doc_id": "d2", "numeric_id": 2, "title": "B", "source": "bm25"},
            ]

    class FakeTVIndex:
        def search(self, queries, k, allowlist=None):
            assert queries.shape == (1, 2)
            return np.array([[0.9, 0.8]], dtype=np.float32), np.array([[2, 3]], dtype=np.uint64)

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            return np.array([[1.0, 0.0]], dtype=np.float32)

    class FakeDocStore:
        def hydrate_by_numeric_ids(self, numeric_ids):
            docs = {
                2: {"doc_id": "d2", "numeric_id": 2, "title": "B"},
                3: {"doc_id": "d3", "numeric_id": 3, "title": "C"},
                1: {"doc_id": "d1", "numeric_id": 1, "title": "A"},
            }
            return [docs[int(numeric_id)] for numeric_id in numeric_ids]

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeESRetriever(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )

    hits = retriever.search("query", method="tv_hybrid", top_k=2, bm25_k=2, dense_k=2, rrf_k=30)

    assert [hit["doc_id"] for hit in hits] == ["d2", "d1"]
    assert hits[0]["source"] == "bm25+dense"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
pytest tests/test_turbovec_retriever.py -q
```

Expected: FAIL because retriever does not exist.

- [ ] **Step 3: Implement retriever**

`TurboVecHybridRetriever` responsibilities:

- Embed query once with normalized BGE-small vector.
- `tv_dense`: TurboVec full-index search, hydrate top-k docs, mark source `dense`.
- `tv_hybrid`: BM25 ranking + TurboVec ranking + existing `fuse_rrf`.
- `tv_filtered_hybrid`: BM25 candidate set + TurboVec `allowlist`; catch/filter missing ids before calling allowlist.
- Preserve final ranking order after hydration.
- Add timing breakdown fields internally for benchmark/API use.

- [ ] **Step 4: Verify test**

Run:

```powershell
pytest tests/test_turbovec_retriever.py -q
```

Expected: PASS.

---

## Task 9: Extend Benchmark For TurboVec Methods

**Files:**

- Modify: `src/evaluation/benchmark_es.py`
- Modify: `tests/test_benchmark_es.py`

- [ ] **Step 1: Write failing method mapping tests**

Add tests:

```python
def test_method_mapping_accepts_turbovec_methods():
    assert benchmark_es.classify_method("es_bm25") == "es"
    assert benchmark_es.classify_method("tv_dense") == "turbovec"
    assert benchmark_es.classify_method("tv_hybrid") == "turbovec"


def test_run_benchmark_with_query_and_qrels_files_does_not_load_ir_dataset(monkeypatch, tmp_path):
    query_file = tmp_path / "queries.tsv"
    qrels_file = tmp_path / "qrels.tsv"
    query_file.write_text("variant_query_id\tsource_query_id\tquery\nq1\tq1\tcustom query\n", encoding="utf-8")
    qrels_file.write_text("query_id\tdoc_id\trelevance\nq1\td1\t1\n", encoding="utf-8")

    monkeypatch.setattr(benchmark_es, "_load_ir_dataset", lambda dataset_id: (_ for _ in ()).throw(AssertionError("should not load ir_datasets")))

    class FakeRetriever:
        def search(self, query, method, top_k, **kwargs):
            return [{"doc_id": "d1", "score": 1.0}]

    monkeypatch.setattr(benchmark_es, "build_retriever", lambda *args, **kwargs: FakeRetriever())

    result = benchmark_es.run_benchmark(
        dataset_id="dataset",
        index="idx",
        methods=["tv_dense"],
        top_k=10,
        max_queries=None,
        url="http://localhost:9200",
        model_name="model",
        num_candidates=100,
        candidate_k=20,
        rrf_k=7,
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

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
pytest tests/test_benchmark_es.py -q
```

Expected: FAIL because TurboVec method classification/building is not implemented.

- [ ] **Step 3: Implement benchmark support**

Add:

```text
tv_dense
tv_hybrid
tv_filtered_hybrid
```

Benchmark rules:

- `es_bm25` uses existing Elasticsearch retriever.
- `tv_*` uses TurboVec retriever.
- If both `query_file` and `qrels_file` are provided, do not load `ir_datasets`.
- TREC run filenames include method and dataset slug.

- [ ] **Step 4: Verify focused benchmark tests**

Run:

```powershell
pytest tests/test_benchmark_es.py -q
```

Expected: PASS.

---

## Task 10: Full Benchmark And Tuning

**Files:**

- Uses: `src/evaluation/benchmark_es.py`
- Creates: `evaluation/results/hotpotqa_full/tv_full_200.json`
- Creates: `evaluation/runs/hotpotqa_full/*.trec`

- [ ] **Step 1: Run primary 200-query benchmark**

Run:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa --index hotpotqa_full_bm25_v1 --methods es_bm25,tv_dense,tv_hybrid --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 30 --output evaluation/results/hotpotqa_full/tv_full_200.json --run-dir evaluation/runs/hotpotqa_full
```

Expected:

- JSON result contains all three methods.
- TREC files exist for all three methods.
- Metrics include quality and latency.

- [ ] **Step 2: Tune accuracy-latency tradeoff**

Run only after the primary benchmark works:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa --index hotpotqa_full_bm25_v1 --methods tv_hybrid --top-k 10 --max-queries 200 --candidate-k 50 --num-candidates 50 --rrf-k 30 --output evaluation/results/hotpotqa_full/tune_k50_rrf30.json --run-dir evaluation/runs/hotpotqa_full/tune_k50_rrf30

python -m src.evaluation.benchmark_es --dataset beir/hotpotqa --index hotpotqa_full_bm25_v1 --methods tv_hybrid --top-k 10 --max-queries 200 --candidate-k 200 --num-candidates 200 --rrf-k 30 --output evaluation/results/hotpotqa_full/tune_k200_rrf30.json --run-dir evaluation/runs/hotpotqa_full/tune_k200_rrf30

python -m src.evaluation.benchmark_es --dataset beir/hotpotqa --index hotpotqa_full_bm25_v1 --methods tv_hybrid --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 60 --output evaluation/results/hotpotqa_full/tune_k100_rrf60.json --run-dir evaluation/runs/hotpotqa_full/tune_k100_rrf60
```

Selection rule:

- Prefer higher `full_support_recall@10` when latency remains usable.
- If quality difference is small, choose lower p95 latency.
- Do not make `tv_filtered_hybrid` default unless it matches `tv_hybrid` quality with materially better latency.

---

## Task 11: API Integration

**Files:**

- Modify: `src/core/config.py`
- Modify: `src/api/main.py`
- Modify: API tests under `tests/`

- [ ] **Step 1: Add config**

Add env vars:

```text
TURBOVEC_INDEX_PATH=artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim
TURBOVEC_BIT_WIDTH=4
TURBOVEC_DIM=384
DEFAULT_SEARCH_METHOD=tv_hybrid
HYBRID_BM25_K=100
HYBRID_DENSE_K=100
```

- [ ] **Step 2: Add methods**

Expose:

```text
es_bm25
tv_dense
tv_hybrid
tv_filtered_hybrid
```

Keep legacy `es_dense`, `es_hybrid`, and `es_iterative_hybrid` only when the configured ES index has vectors. If full index is BM25-only, do not make ES dense the default.

- [ ] **Step 3: Add latency breakdown**

Response shape:

```json
{
  "query": "...",
  "method": "tv_hybrid",
  "top_k": 10,
  "latency_ms": 88.1,
  "latency_breakdown_ms": {
    "embed": 12.0,
    "bm25": 35.0,
    "turbovec": 22.0,
    "fusion": 1.0,
    "hydrate": 18.0
  },
  "results": []
}
```

- [ ] **Step 4: Verify API tests**

Run:

```powershell
pytest tests/test_api_es_config.py tests/test_api_cache.py tests/test_search_history.py -q
```

Expected: PASS.

---

## Task 12: Sprint 3 Report

**Files:**

- Create: `docs/sprint3/sprint3-report.md`

- [ ] **Step 1: Create report with measured results**

Report sections:

```text
1. Goal and scope
2. Hardware
3. Dataset and corpus size
4. Architecture: ES BM25 + TurboVec dense + RRF
5. Index/build artifacts
6. Benchmark configuration
7. Accuracy metrics table
8. Latency/QPS table
9. Tuning results
10. API/demo notes
11. Limitations
12. Next steps
```

- [ ] **Step 2: Include acceptance evidence**

Add concrete paths:

```text
artifacts/hotpotqa_full/staging/manifest.json
artifacts/hotpotqa_full/turbovec/hotpotqa_bge_small_4bit.tvim
evaluation/results/hotpotqa_full/tv_full_200.json
evaluation/runs/hotpotqa_full/*.trec
```

- [ ] **Step 3: Document final default method**

Expected default if benchmark supports it:

```text
tv_hybrid
```

If `tv_hybrid` does not beat BM25 in quality or latency, report the measured result honestly and keep BM25 as fallback.

---

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Full embedding generation takes too long | Delays full benchmark | Resume per shard; start with one-shard smoke; keep BM25 full result as early deliverable |
| TurboVec 4-bit recall is lower than expected | Hybrid quality may not improve over BM25 | Keep BM25 baseline; tune `dense_k`, `rrf_k`; compare dense-only and hybrid failures |
| Windows path/build issues | Blocks local execution | TurboVec smoke already passed on Python 3.12 Windows; pin `turbovec==0.8.0` |
| Elasticsearch BM25 ingest strains 16 GB RAM | Slow or unstable indexing | ES-only during ingest; heap around 6 GB; replicas 0; refresh interval disabled during ingest |
| ID mapping bug | Invalid benchmark results | Store `numeric_id` in staging, ES, embedding ids, and TurboVec; unit-test hydration ordering |
| `tv_filtered_hybrid` allowlist contains missing ids | Runtime `KeyError` | Filter allowlist ids or ensure BM25 full index and TurboVec full index are built from the same staging manifest |

## Final Implementation Order

1. TurboVec dependency and smoke test.
2. Numeric-id staging and manifest validation.
3. BM25-only Elasticsearch index path.
4. Full HotpotQA staging.
5. Full BM25 ingest and BM25 benchmark.
6. Resumable embedding shard generation.
7. TurboVec index build.
8. `tv_dense` and `tv_hybrid` retrieval.
9. Benchmark support for TurboVec methods.
10. Full 200-query benchmark and tuning.
11. API integration.
12. Sprint 3 report.

## Self-Review

- Scope coverage: The plan covers full HotpotQA staging, BM25 indexing, dense indexing with TurboVec, hybrid retrieval, benchmark metrics, API exposure, and report output.
- De-scope clarity: VimQA, reader/generator, reranker, fine-tuning, and UI redesign are explicitly out of scope.
- Accuracy and latency: The plan prioritizes `full_support_recall@10`, ranking metrics, p50/p95/p99 latency, QPS, and timing breakdown.
- Hardware fit: The plan avoids Elasticsearch dense vectors for full 5M and uses TurboVec 4-bit to reduce memory pressure on a 16 GB laptop.
- Placeholder scan: No TBD/TODO placeholders remain; commands, artifact paths, and acceptance criteria are concrete.
