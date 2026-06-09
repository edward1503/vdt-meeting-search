# Elasticsearch Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest production-demo baseline that stages HotpotQA docs, embeds them, ingests them into Elasticsearch, searches with BM25/dense/hybrid, and benchmarks against BEIR qrels.

**Architecture:** Elasticsearch is the only search backend. Python owns staging, embedding, bulk ingest, RRF fusion, API orchestration, and evaluation. The baseline is single-process with file-level resume; distributed execution is intentionally limited to rerunning independent staging shards after the single-node path works.

**Tech Stack:** `ir_datasets`, `sentence-transformers`, `elasticsearch` Python client, Elasticsearch Docker, FastAPI, pytest.

---

## Simplicity Decisions

- No Redis in the baseline. Cache is filesystem staging JSONL, `.done` markers, and the Elasticsearch Docker volume.
- No FAISS, Pyserini, DuckDB, Celery, queue, or multi-node cluster in the baseline.
- No default chunking. One HotpotQA doc becomes one Elasticsearch doc and one embedding vector.
- No separate distributed scheduler. Staging shards make manual parallel ingest possible after the single worker is proven.
- No custom docstore. Elasticsearch stores `doc_id`, `title`, `text`, `url`, `content`, and `embedding`.
- No Elasticsearch-native RRF first. Python RRF is simpler to inspect and shares the existing baseline logic.
- API integration happens only after index ingest and CLI search smoke work.

## File Boundaries

- Create `docker-compose.yml`: single-node Elasticsearch with persistent volume.
- Create `.env.example`: minimal config knobs.
- Modify `requirements.txt`: add `elasticsearch` only.
- Create `src/data/staging.py`: normalize docs and write/read staging JSONL shards.
- Create `scripts/stage_hotpotqa.py`: stream `ir_datasets` into staging shards.
- Create `src/retrieval/elasticsearch_retriever.py`: ES mapping, bulk action builder, query builders, BM25/dense/hybrid search.
- Create `scripts/es_hotpotqa.py`: one CLI with `create-index`, `ingest`, `validate`, and `search` subcommands.
- Create `src/evaluation/benchmark_es.py`: benchmark ES search modes and write metrics/run files.
- Modify `src/core/config.py`: add ES/model env fields using existing dataclass style.
- Modify `src/api/main.py`: add `es_bm25`, `es_dense`, `es_hybrid` methods.
- Create/update docs in `docs/baseline/elasticsearch-baseline.md` and `README.md`.

## Build Phases

### Phase 0: Runtime And Config

**Goal:** Start a local Elasticsearch instance and make Python able to talk to it.

**Builds:**
- `docker-compose.yml`
- `.env.example`
- `requirements.txt` dependency update

**Gate:** `curl http://localhost:9200/_cluster/health?pretty` returns cluster health JSON.

### Phase 1: Data Staging Cache

**Goal:** Convert `ir_datasets` docs into deterministic JSONL shard files before any embedding or ES ingest.

**Builds:**
- `src/data/staging.py`
- `scripts/stage_hotpotqa.py`
- `tests/test_staging.py`
- `artifacts/nano/staging/*.jsonl` for smoke tests

**Gate:** staging nano writes 5,090 docs into 3 shard files when `docs_per_file=2000`.

### Phase 2: Elasticsearch Index And Ingest

**Goal:** Create the ES index, embed staged docs, bulk index them, and validate document count.

**Builds:**
- ES mapping and bulk helpers in `src/retrieval/elasticsearch_retriever.py`
- `scripts/es_hotpotqa.py create-index`
- `scripts/es_hotpotqa.py ingest`
- `scripts/es_hotpotqa.py validate`
- `.done` progress markers under `artifacts/*/progress/`

**Gate:** one nano staging shard ingests exactly 2,000 docs into `hotpotqa_nano_current`.

### Phase 3: Retrieval Modes

**Goal:** Prove BM25, dense kNN, and hybrid RRF all work against the same ES index.

**Builds:**
- `build_bm25_query`
- `build_knn_query`
- `ElasticsearchRetriever.search(method="bm25|dense|hybrid")`
- `scripts/es_hotpotqa.py search`

**Gate:** CLI search returns non-empty results for `bm25`, `dense`, and `hybrid` on the nano index.

### Phase 4: Evaluation

**Goal:** Measure retrieval quality against BEIR qrels before doing any tuning or full-corpus claims.

**Builds:**
- `src/evaluation/benchmark_es.py`
- TREC run files under `evaluation/runs/`
- JSON metrics under `evaluation/results/`

**Gate:** nano benchmark with 10 queries writes metrics and run files for `es_bm25`, `es_dense`, and `es_hybrid`.

### Phase 5: API And Docs

**Goal:** Expose the proven ES retrieval modes through the existing FastAPI demo and document the operational commands.

**Builds:**
- `src/core/config.py` ES settings
- `src/api/main.py` ES method routing
- `docs/baseline/elasticsearch-baseline.md`
- `README.md` link

**Gate:** `POST /search` works with `method=es_bm25` against the nano ES index.

## Data Contracts

### Staged JSONL Row

Each line in `artifacts/*/staging/docs-xxxxx.jsonl` must have this shape:

```json
{
  "doc_id": "49892372",
  "title": "",
  "text": "Raw document text after whitespace collapse.",
  "url": "",
  "content": "title\ntext used by BM25/display",
  "embedding_text": "title\ntext used by the embedding model"
}
```

Baseline policy: `content` and `embedding_text` are identical. Later truncation can change `embedding_text`, but chunking must stay out of this baseline.

### Elasticsearch Document

The indexed ES source stores only fields needed for search/display:

```json
{
  "doc_id": "49892372",
  "title": "",
  "text": "Raw document text after whitespace collapse.",
  "url": "",
  "content": "title\ntext used by BM25/display",
  "embedding": [0.01, -0.02]
}
```

`embedding_text` is not indexed. Elasticsearch `_id` is always `doc_id`.

### Search Methods

All search modes use Elasticsearch only:

```text
es_bm25  -> multi_match(title^2, content)
es_dense -> kNN on dense_vector field embedding
es_hybrid -> es_bm25 candidates + es_dense candidates -> Python RRF -> top_k docs
```

### Benchmark Output

The benchmark writes both JSON metrics and TREC rows:

```text
query_id Q0 doc_id rank score method
```

Example:

```text
q1 Q0 d1 3 0.250000 es_hybrid
```

## Logic Ownership

| Logic | Owner File | Notes |
|---|---|---|
| Whitespace normalization and `content` assembly | `src/data/staging.py` | Uses `make_ingest_content` from existing ingest EDA utilities. |
| Staging shard write/read | `src/data/staging.py` | Deterministic filenames `docs-00000.jsonl`, sorted reads. |
| Dataset-to-staging CLI | `scripts/stage_hotpotqa.py` | Thin wrapper around `write_staging_shards`. |
| ES index mapping | `src/retrieval/elasticsearch_retriever.py` | Text fields plus one `dense_vector`. |
| ES bulk action construction | `src/retrieval/elasticsearch_retriever.py` | Uses `_id = doc_id`, excludes `embedding_text`. |
| Embedding and bulk ingest loop | `scripts/es_hotpotqa.py` | CLI orchestration only; calls retriever helpers. |
| BM25/dense query bodies | `src/retrieval/elasticsearch_retriever.py` | Testable pure functions. |
| Hybrid RRF | `src/retrieval/elasticsearch_retriever.py` | Python fusion for transparency. |
| Benchmark loops and run files | `src/evaluation/benchmark_es.py` | Reuses existing qrels/metrics concepts. |
| API method routing | `src/api/main.py` | Adds ES methods without deleting local nano baseline. |

## Full-Corpus Readiness Gates

Do not run full 5.23M ingest until these gates pass on nano:

- `scripts/stage_hotpotqa.py` writes nano staging shards.
- `scripts/es_hotpotqa.py create-index` creates `hotpotqa_nano_current`.
- `scripts/es_hotpotqa.py ingest --max-files 1` indexes exactly 2,000 docs.
- `scripts/es_hotpotqa.py search` works for BM25, dense, and hybrid.
- `benchmark_es` writes metrics for 10 nano queries.
- API returns search results for `es_bm25`.

After all gates pass, run full in this order:

```bash
python scripts/eda_hotpotqa_ingest.py --dataset beir/hotpotqa --sample-docs 100000
python scripts/stage_hotpotqa.py --dataset beir/hotpotqa --output-dir artifacts/hotpotqa_full/staging
python scripts/es_hotpotqa.py create-index --index hotpotqa_docs_v1 --alias hotpotqa_docs_current --reset
python scripts/es_hotpotqa.py ingest --index hotpotqa_docs_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress
python scripts/es_hotpotqa.py validate --index hotpotqa_docs_current --expected-count 5233329
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_docs_current --methods es_bm25,es_dense,es_hybrid --top-k 100
```

---

### Task 1: Minimal Elasticsearch Runtime

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Modify: `requirements.txt`

- [ ] **Step 1: Add the Python client dependency**

Add this line to `requirements.txt`:

```text
elasticsearch>=8.15.0,<9.0.0
```

- [ ] **Step 2: Create `.env.example`**

```dotenv
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=hotpotqa_docs_current
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMS=384
EMBEDDING_BATCH_SIZE=128
ES_BULK_DOCS=512
```

- [ ] **Step 3: Create single-node Docker Compose**

```yaml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.15.1
    container_name: vdt-hotpotqa-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - ES_JAVA_OPTS=-Xms2g -Xmx2g
    ports:
      - "9200:9200"
    volumes:
      - esdata:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:9200/_cluster/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 30

volumes:
  esdata:
```

- [ ] **Step 4: Verify Elasticsearch boots**

Run:

```bash
docker compose up -d elasticsearch
curl http://localhost:9200/_cluster/health?pretty
```

Expected: curl returns cluster health JSON with `status` equal to `green` or `yellow`.

---

### Task 2: Staging Cache Before Embedding

**Files:**
- Create: `src/data/staging.py`
- Create: `scripts/stage_hotpotqa.py`
- Test: `tests/test_staging.py`

- [ ] **Step 1: Write failing tests for staging behavior**

Create `tests/test_staging.py`:

```python
from __future__ import annotations

import json
from collections import namedtuple

from src.data.staging import iter_staging_files, normalize_document, write_staging_shards


def test_normalize_document_builds_one_doc_one_embedding_text():
    raw_type = namedtuple("RawDoc", ["doc_id", "title", "text", "url"])
    row = normalize_document(raw_type("d1", " Ada ", " First\n programmer. ", "u"))

    assert row == {
        "doc_id": "d1",
        "title": "Ada",
        "text": "First programmer.",
        "url": "u",
        "content": "Ada\nFirst programmer.",
        "embedding_text": "Ada\nFirst programmer.",
    }


def test_write_staging_shards_creates_jsonl_cache(tmp_path):
    raw_type = namedtuple("RawDoc", ["doc_id", "title", "text", "url"])
    docs = [raw_type(str(idx), "T", f"body {idx}", "") for idx in range(5)]

    manifest = write_staging_shards(docs, tmp_path, docs_per_file=2)

    assert manifest == {"docs_written": 5, "files_written": 3, "docs_per_file": 2}
    files = list(iter_staging_files(tmp_path))
    assert [path.name for path in files] == ["docs-00000.jsonl", "docs-00001.jsonl", "docs-00002.jsonl"]
    first_row = json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])
    assert first_row["doc_id"] == "0"
```

- [ ] **Step 2: Run RED test**

Run: `python -m pytest tests/test_staging.py -q`

Expected: fails because `src.data.staging` does not exist.

- [ ] **Step 3: Implement staging utilities**

Create `src/data/staging.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from src.data.ingest_eda import make_ingest_content


def normalize_document(raw_doc: Any) -> dict[str, str]:
    doc_id = str(getattr(raw_doc, "doc_id"))
    title = _collapse(getattr(raw_doc, "title", "") or "")
    text = _collapse(getattr(raw_doc, "text", "") or "")
    url = str(getattr(raw_doc, "url", "") or "")
    content = make_ingest_content(title, text)
    return {
        "doc_id": doc_id,
        "title": title,
        "text": text,
        "url": url,
        "content": content,
        "embedding_text": content,
    }


def write_staging_shards(raw_docs: Iterable[Any], output_dir: Path, docs_per_file: int = 50_000) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_written = 0
    files_written = 0
    current = None
    try:
        for raw_doc in raw_docs:
            if docs_written % docs_per_file == 0:
                if current is not None:
                    current.close()
                current = (output_dir / f"docs-{files_written:05d}.jsonl").open("w", encoding="utf-8")
                files_written += 1
            current.write(json.dumps(normalize_document(raw_doc), ensure_ascii=False) + "\n")
            docs_written += 1
    finally:
        if current is not None:
            current.close()
    manifest = {"docs_written": docs_written, "files_written": files_written, "docs_per_file": docs_per_file}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def iter_staging_files(staging_dir: Path):
    yield from sorted(staging_dir.glob("docs-*.jsonl"))


def _collapse(value: str) -> str:
    return " ".join(str(value or "").split())
```

- [ ] **Step 4: Create staging CLI**

Create `scripts/stage_hotpotqa.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.staging import write_staging_shards


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage HotpotQA docs into JSONL shards")
    parser.add_argument("--dataset", default="beir/hotpotqa")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/hotpotqa_full/staging"))
    parser.add_argument("--docs-per-file", type=int, default=50_000)
    parser.add_argument("--max-docs", type=int, default=None)
    args = parser.parse_args()

    import ir_datasets

    docs = ir_datasets.load(args.dataset).docs_iter()
    if args.max_docs is not None:
        docs = _take(docs, args.max_docs)
    print(json.dumps({"dataset": args.dataset, **write_staging_shards(docs, args.output_dir, args.docs_per_file)}, indent=2))


def _take(items, limit: int):
    for idx, item in enumerate(items):
        if idx >= limit:
            break
        yield item


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Verify staging**

Run:

```bash
python -m pytest tests/test_staging.py -q
python scripts/stage_hotpotqa.py --dataset nano-beir/hotpotqa --output-dir artifacts/nano/staging --docs-per-file 2000
```

Expected: tests pass; staging command reports `docs_written` as `5090` and `files_written` as `3`.

---

### Task 3: Elasticsearch Index, Ingest, And Smoke Search In One CLI

**Files:**
- Create: `src/retrieval/elasticsearch_retriever.py`
- Create: `scripts/es_hotpotqa.py`
- Test: `tests/test_elasticsearch_retriever.py`

- [ ] **Step 1: Write failing tests for ES mapping, bulk action, query bodies, and RRF**

Create `tests/test_elasticsearch_retriever.py`:

```python
from __future__ import annotations

from src.retrieval.elasticsearch_retriever import build_bm25_query, build_index_body, build_knn_query, bulk_action, fuse_rrf


def test_build_index_body_has_text_and_vector_fields():
    body = build_index_body(dims=384)

    assert body["settings"]["refresh_interval"] == "-1"
    assert body["mappings"]["properties"]["doc_id"]["type"] == "keyword"
    assert body["mappings"]["properties"]["content"]["type"] == "text"
    assert body["mappings"]["properties"]["embedding"] == {"type": "dense_vector", "dims": 384, "similarity": "cosine"}


def test_bulk_action_uses_doc_id_as_id_and_excludes_embedding_text():
    row = {"doc_id": "d1", "title": "T", "text": "X", "url": "", "content": "T\nX", "embedding_text": "T\nX"}
    action = bulk_action("idx", row, [0.1, 0.2])

    assert action["_index"] == "idx"
    assert action["_id"] == "d1"
    assert action["doc_id"] == "d1"
    assert action["embedding"] == [0.1, 0.2]
    assert "embedding_text" not in action


def test_query_builders_and_rrf_are_stable():
    assert build_bm25_query("ada", 5)["query"]["multi_match"]["fields"] == ["title^2", "content"]
    assert build_knn_query([0.1, 0.2], 5, 50)["knn"]["num_candidates"] == 50

    fused = fuse_rrf([[{"doc_id": "a"}, {"doc_id": "b"}], [{"doc_id": "b"}, {"doc_id": "c"}]], top_k=3)
    assert [hit["doc_id"] for hit in fused] == ["b", "a", "c"]
```

- [ ] **Step 2: Run RED test**

Run: `python -m pytest tests/test_elasticsearch_retriever.py -q`

Expected: fails because `src.retrieval.elasticsearch_retriever` does not exist.

- [ ] **Step 3: Implement `src/retrieval/elasticsearch_retriever.py`**

```python
from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer


def build_index_body(dims: int, shards: int = 1) -> dict[str, Any]:
    return {
        "settings": {"number_of_shards": shards, "number_of_replicas": 0, "refresh_interval": "-1"},
        "mappings": {"properties": {
            "doc_id": {"type": "keyword"},
            "title": {"type": "text"},
            "text": {"type": "text"},
            "url": {"type": "keyword"},
            "content": {"type": "text"},
            "embedding": {"type": "dense_vector", "dims": dims, "similarity": "cosine"},
        }},
    }


def bulk_action(index: str, row: dict[str, Any], embedding: list[float]) -> dict[str, Any]:
    return {
        "_index": index,
        "_id": row["doc_id"],
        "doc_id": row["doc_id"],
        "title": row.get("title", ""),
        "text": row.get("text", ""),
        "url": row.get("url", ""),
        "content": row.get("content", ""),
        "embedding": embedding,
    }


def build_bm25_query(query: str, top_k: int) -> dict[str, Any]:
    return {"size": top_k, "track_total_hits": False, "_source": ["doc_id", "title", "text", "url"], "query": {"multi_match": {"query": query, "fields": ["title^2", "content"]}}}


def build_knn_query(vector: list[float], top_k: int, num_candidates: int) -> dict[str, Any]:
    return {"_source": ["doc_id", "title", "text", "url"], "knn": {"field": "embedding", "query_vector": vector, "k": top_k, "num_candidates": num_candidates}}


def fuse_rrf(rankings: list[list[dict[str, Any]]], top_k: int, rrf_k: int = 60) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    docs: dict[str, dict[str, Any]] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            doc_id = hit["doc_id"]
            docs.setdefault(doc_id, hit)
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)
    return [{**docs[doc_id], "score": score} for doc_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]]


class ElasticsearchRetriever:
    def __init__(self, es: Elasticsearch, index: str, model_name: str, num_candidates: int = 1000) -> None:
        self.es = es
        self.index = index
        self.model = SentenceTransformer(model_name)
        self.num_candidates = num_candidates

    def search(self, query: str, method: str, top_k: int, candidate_k: int = 100) -> list[dict[str, Any]]:
        if method == "bm25":
            return self._search_body(build_bm25_query(query, top_k), "bm25")
        if method == "dense":
            return self._search_dense(query, top_k, self.num_candidates)
        if method == "hybrid":
            return fuse_rrf([self.search(query, "bm25", candidate_k), self._search_dense(query, candidate_k, max(candidate_k, self.num_candidates))], top_k)
        raise ValueError(f"Unknown method: {method}")

    def _search_dense(self, query: str, top_k: int, num_candidates: int) -> list[dict[str, Any]]:
        vector = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0].astype(float).tolist()
        return self._search_body(build_knn_query(vector, top_k, num_candidates), "dense")

    def _search_body(self, body: dict[str, Any], source: str) -> list[dict[str, Any]]:
        response = self.es.search(index=self.index, body=body)
        hits = []
        for hit in response.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            hits.append({"doc_id": src.get("doc_id", hit.get("_id", "")), "title": src.get("title", ""), "text": src.get("text", ""), "url": src.get("url", ""), "score": float(hit.get("_score", 0.0)), "source": source})
        return hits
```

- [ ] **Step 4: Create one ES CLI**

Create `scripts/es_hotpotqa.py` with subcommands:

```text
create-index --index hotpotqa_docs_v1 --alias hotpotqa_docs_current --dims 384 --reset
ingest --index hotpotqa_docs_v1 --staging-dir artifacts/nano/staging --progress-dir artifacts/nano/progress --max-files 1
validate --index hotpotqa_docs_current --expected-count 2000
search --index hotpotqa_docs_current --method bm25 --query "Ada Lovelace" --top-k 5
```

The CLI must reuse `build_index_body`, `bulk_action`, and `ElasticsearchRetriever`. The ingest subcommand reads staging JSONL files in sorted order, skips files with an existing `.done` marker, embeds each batch, bulk indexes with `_id = doc_id`, and writes `docs-xxxxx.done` after a file completes.

- [ ] **Step 5: Verify ES utilities and nano ingest smoke**

Run:

```bash
python -m pytest tests/test_elasticsearch_retriever.py -q
python scripts/es_hotpotqa.py create-index --index hotpotqa_nano_v1 --alias hotpotqa_nano_current --reset
python scripts/es_hotpotqa.py ingest --index hotpotqa_nano_v1 --staging-dir artifacts/nano/staging --progress-dir artifacts/nano/progress --max-files 1 --batch-size 64
python scripts/es_hotpotqa.py validate --index hotpotqa_nano_current --expected-count 2000
python scripts/es_hotpotqa.py search --index hotpotqa_nano_current --method bm25 --query "Ada Lovelace" --top-k 5
```

Expected: tests pass; validate exits 0; search prints at least one result.

---

### Task 4: Benchmark Elasticsearch Retrieval

**Files:**
- Create: `src/evaluation/benchmark_es.py`
- Test: `tests/test_benchmark_es.py`

- [ ] **Step 1: Write failing test for run file formatting**

Create `tests/test_benchmark_es.py`:

```python
from __future__ import annotations

from src.evaluation.benchmark_es import trec_line


def test_trec_line_is_stable():
    assert trec_line("q1", "d1", 3, 0.25, "es_hybrid") == "q1 Q0 d1 3 0.250000 es_hybrid"
```

- [ ] **Step 2: Run RED test**

Run: `python -m pytest tests/test_benchmark_es.py -q`

Expected: fails because `src.evaluation.benchmark_es` does not exist.

- [ ] **Step 3: Implement benchmark runner**

Create `src/evaluation/benchmark_es.py` with:

```python
def trec_line(query_id: str, doc_id: str, rank: int, score: float, method: str) -> str:
    return f"{query_id} Q0 {doc_id} {rank} {score:.6f} {method}"
```

The CLI must load queries/qrels from `ir_datasets`, call `ElasticsearchRetriever.search`, compute metrics with existing `src.evaluation.metrics`, write JSON metrics, and write TREC run files. Supported methods are `es_bm25`, `es_dense`, and `es_hybrid`, mapped to retriever methods `bm25`, `dense`, and `hybrid`.

- [ ] **Step 4: Verify benchmark on nano smoke index**

Run:

```bash
python -m pytest tests/test_benchmark_es.py -q
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_current --methods es_bm25,es_dense,es_hybrid --top-k 10 --max-queries 10 --output evaluation/results/es_nano_smoke.json --run-dir evaluation/runs
```

Expected: test passes; JSON metrics file exists; run files exist under `evaluation/runs`.

---

### Task 5: Wire ES Search Into Existing API

**Files:**
- Modify: `src/core/config.py`
- Modify: `src/api/main.py`
- Test: `tests/test_api_es_config.py`

- [ ] **Step 1: Write failing config test**

Create `tests/test_api_es_config.py`:

```python
from __future__ import annotations

from src.core.config import Settings


def test_settings_exposes_elasticsearch_defaults():
    settings = Settings()

    assert settings.elasticsearch_url == "http://localhost:9200"
    assert settings.elasticsearch_index == "hotpotqa_docs_current"
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
```

- [ ] **Step 2: Run RED test**

Run: `python -m pytest tests/test_api_es_config.py -q`

Expected: fails because settings do not expose these fields.

- [ ] **Step 3: Extend dataclass config only**

In `src/core/config.py`, add these fields to the existing `Settings` dataclass:

```python
search_backend: str = os.getenv("SEARCH_BACKEND", "local")
elasticsearch_url: str = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
elasticsearch_index: str = os.getenv("ELASTICSEARCH_INDEX", "hotpotqa_docs_current")
elasticsearch_num_candidates: int = int(os.getenv("ELASTICSEARCH_NUM_CANDIDATES", "1000"))
embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
```

- [ ] **Step 4: Add ES methods to `src/api/main.py`**

Keep current local methods. Add `es_bm25`, `es_dense`, and `es_hybrid`. Lazily initialize one `ElasticsearchRetriever` using settings. Map API methods as:

```python
{"es_bm25": "bm25", "es_dense": "dense", "es_hybrid": "hybrid"}
```

- [ ] **Step 5: Verify API config and manual search**

Run:

```bash
python -m pytest tests/test_api_es_config.py -q
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
curl -X POST http://127.0.0.1:8000/search -H "Content-Type: application/json" -d "{\"query\":\"Ada Lovelace\",\"method\":\"es_bm25\",\"top_k\":5}"
```

Expected: test passes; API returns JSON with `results` and `latency_ms`.

---

### Task 6: Docs And Final Verification

**Files:**
- Create: `docs/baseline/elasticsearch-baseline.md`
- Modify: `README.md`

- [ ] **Step 1: Write the baseline doc**

Create `docs/baseline/elasticsearch-baseline.md`:

````markdown
# Elasticsearch Baseline

## Pipeline

```text
ir_datasets
  -> EDA/preflight
  -> staging JSONL cache
  -> embed + bulk ingest into Elasticsearch
  -> validate index
  -> BM25/dense/hybrid search
  -> benchmark qrels
```

## Baseline Policy

- Elasticsearch is the only search backend.
- One HotpotQA doc maps to one ES doc and one vector.
- Staging JSONL and `.done` markers are the only ingest cache.
- Redis, FAISS, queues, and multi-node cluster setup are outside the baseline.

## Commands

```bash
docker compose up -d elasticsearch
python scripts/eda_hotpotqa_ingest.py --dataset beir/hotpotqa --sample-docs 100000
python scripts/stage_hotpotqa.py --dataset beir/hotpotqa --output-dir artifacts/hotpotqa_full/staging
python scripts/es_hotpotqa.py create-index --index hotpotqa_docs_v1 --alias hotpotqa_docs_current --reset
python scripts/es_hotpotqa.py ingest --index hotpotqa_docs_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress
python scripts/es_hotpotqa.py validate --index hotpotqa_docs_current --expected-count 5233329
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_docs_current --methods es_bm25,es_dense,es_hybrid --top-k 100
```
````

- [ ] **Step 2: Update README**

Add:

```markdown
## Elasticsearch Production-Demo Baseline

See `docs/baseline/elasticsearch-baseline.md` for the lean Elasticsearch ingest, search, and benchmark pipeline.
```

- [ ] **Step 3: Run final unit tests**

Run:

```bash
python -m pytest tests/test_ingest_eda.py tests/test_staging.py tests/test_elasticsearch_retriever.py tests/test_benchmark_es.py tests/test_api_es_config.py tests/test_eda_hotpotqa.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Run final nano smoke**

Run:

```bash
docker compose up -d elasticsearch
python scripts/stage_hotpotqa.py --dataset nano-beir/hotpotqa --output-dir artifacts/nano/staging --docs-per-file 2000
python scripts/es_hotpotqa.py create-index --index hotpotqa_nano_v1 --alias hotpotqa_nano_current --reset
python scripts/es_hotpotqa.py ingest --index hotpotqa_nano_v1 --staging-dir artifacts/nano/staging --progress-dir artifacts/nano/progress --max-files 1 --batch-size 64
python scripts/es_hotpotqa.py validate --index hotpotqa_nano_current --expected-count 2000
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_current --methods es_bm25,es_dense,es_hybrid --top-k 10 --max-queries 10 --output evaluation/results/es_nano_smoke.json --run-dir evaluation/runs
```

Expected: validate exits 0; benchmark writes `evaluation/results/es_nano_smoke.json` and TREC run files.

## Review Checklist

- The baseline has one search backend: Elasticsearch.
- The baseline has one mandatory cache layer: staging JSONL plus `.done` markers.
- The baseline has one ingest CLI: `scripts/es_hotpotqa.py`.
- The baseline does not implement Redis, queues, FAISS, Pyserini, DuckDB, or multi-node ES.
- The baseline keeps no-chunking as the default.
- The baseline proves value through dev benchmark before adding reranking or multi-hop expansion.
