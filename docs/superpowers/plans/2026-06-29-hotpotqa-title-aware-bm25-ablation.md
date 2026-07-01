# HotpotQA Title-Aware BM25 Ablation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and benchmark a HotpotQA BM25 title-aware indexing ablation against the existing full-corpus BM25 baseline.

**Architecture:** Keep the existing full HotpotQA staging files unchanged. Add title-aware BM25 index helpers that enrich Elasticsearch documents with `title_exact`, `lead_sentence`, and `title_repeat_content`, then expose a benchmark method `es_bm25_title` that queries boosted title-aware fields. The experiment is isolated in a new Elasticsearch index/alias and produces a small pilot report.

**Tech Stack:** Python, Elasticsearch 8, pytest, Harness CLI, existing HotpotQA staging and benchmark runner.

---

### Task 1: Title-Aware Retriever Helpers

**Files:**
- Modify: `src/retrieval/elasticsearch_retriever.py`
- Test: `tests/test_elasticsearch_retriever.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:

```python
def test_title_aware_bm25_index_body_adds_title_fields():
    body = build_bm25_index_body(shards=2, title_aware=True)
    props = body["mappings"]["properties"]
    assert props["title_exact"] == {"type": "keyword"}
    assert props["lead_sentence"] == {"type": "text"}
    assert props["title_repeat_content"] == {"type": "text"}

def test_title_aware_bm25_bulk_action_adds_enriched_fields():
    action = bm25_bulk_action(
        "idx",
        {
            "numeric_id": 7,
            "doc_id": "d7",
            "title": "Ada Lovelace",
            "text": "First sentence. Second sentence.",
            "url": "",
            "content": "Ada Lovelace\nFirst sentence. Second sentence.",
        },
        title_aware=True,
    )
    assert action["title_exact"] == "Ada Lovelace"
    assert action["lead_sentence"] == "First sentence"
    assert action["title_repeat_content"] == "Ada Lovelace\nAda Lovelace\nFirst sentence. Second sentence."

def test_build_title_aware_bm25_query_boosts_title_fields():
    body = build_title_aware_bm25_query("analytical engine", 10)
    assert body["query"]["multi_match"]["fields"] == [
        "title^3",
        "title_exact^4",
        "title_repeat_content^1.5",
        "lead_sentence^1.2",
        "content",
    ]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_elasticsearch_retriever.py -q
```

Expected: tests fail because `title_aware` and `build_title_aware_bm25_query` do not exist.

- [ ] **Step 3: Implement minimal helpers**

Add optional `title_aware` support to `build_bm25_index_body` and `bm25_bulk_action`, add `build_title_aware_bm25_query`, and route retriever method `bm25_title` to it.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_elasticsearch_retriever.py -q
```

Expected: all Elasticsearch retriever tests pass.

### Task 2: Benchmark Method Dispatch

**Files:**
- Modify: `src/evaluation/benchmark_es.py`
- Test: `tests/test_benchmark_es.py`
- Modify: `scripts/es_hotpotqa.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:

```python
def test_map_es_method_accepts_title_aware_bm25():
    assert map_es_method("es_bm25_title") == "bm25_title"

def test_run_benchmark_dispatches_title_aware_bm25(monkeypatch, tmp_path):
    calls = []
    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id="q1", text="query")
        def qrels_iter(self):
            yield SimpleNamespace(query_id="q1", doc_id="d1", relevance=1)
    class FakeRetriever:
        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            calls.append(method)
            return [{"doc_id": "d1", "score": 1.0}]
    monkeypatch.setattr(benchmark_es, "_load_ir_dataset", lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, "build_retriever", lambda *args, **kwargs: FakeRetriever())
    benchmark_es.run_benchmark(
        dataset_id="dataset",
        index="idx",
        methods=["es_bm25_title"],
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
    )
    assert calls == ["bm25_title"]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_benchmark_es.py -q
```

Expected: mapping test fails because `es_bm25_title` is unsupported.

- [ ] **Step 3: Implement benchmark and CLI dispatch**

Add `es_bm25_title` to `METHOD_MAP`, allow CLI search method `bm25_title`, and add `--title-aware` to `create-bm25-index` and `ingest-bm25`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_benchmark_es.py tests/test_elasticsearch_retriever.py -q
```

Expected: all focused tests pass.

### Task 3: Build Index and Benchmark Pilot

**Files:**
- Create: `evaluation/results/hotpotqa_full/title_aware_bm25_200.json`
- Create: `evaluation/runs/hotpotqa_full/title_aware_bm25/es_bm25_title_beir_hotpotqa_dev_top10.trec`
- Create: `docs/sprint5/title-aware-bm25-ablation-report.md`

- [ ] **Step 1: Build title-aware BM25 index**

Run:

```powershell
python scripts/es_hotpotqa.py create-bm25-index --index hotpotqa_full_titleaware_bm25_v1 --alias hotpotqa_full_titleaware_bm25_current --reset --title-aware
python scripts/es_hotpotqa.py ingest-bm25 --index hotpotqa_full_titleaware_bm25_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress/titleaware_bm25 --batch-size 1000 --title-aware
python scripts/es_hotpotqa.py validate --index hotpotqa_full_titleaware_bm25_current --expected-count 5233329
```

- [ ] **Step 2: Run 200-query benchmark**

Run:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_titleaware_bm25_current --methods es_bm25_title --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 30 --output evaluation/results/hotpotqa_full/title_aware_bm25_200.json --run-dir evaluation/runs/hotpotqa_full/title_aware_bm25
```

- [ ] **Step 3: Write report**

Compare `title_aware_bm25_200.json` against `evaluation/results/hotpotqa_full/tv_full_200.json`, especially `es_bm25` full-support@10, recall@10, nDCG@10, p95 latency, and QPS.

- [ ] **Step 4: Update story evidence**

Create or update `US-S5-010` with commands, metrics, and whether the ablation beats baseline.
