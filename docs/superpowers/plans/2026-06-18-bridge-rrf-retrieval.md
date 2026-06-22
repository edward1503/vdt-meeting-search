# Bridge-RRF Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Sprint 4 Workstream 2 evidence-chain metrics and a benchmark-only TurboVec two-hop Bridge-RRF retrieval method named `tv_two_hop_bridge_rrf`.

**Architecture:** Keep the first slice in the evaluation/retrieval layer only. `TurboVecHybridRetriever` owns the two-hop retrieval algorithm, `benchmark_es` dispatches the new method and records hyperparameters, and `metrics` computes full-support cutoffs plus chain metrics from optional chain metadata on `SearchHit` results. API/dashboard defaults remain unchanged.

**Tech Stack:** Python, pytest, existing Elasticsearch BM25 retriever, TurboVec index, BEIR/HotpotQA benchmark runner, Harness story `US-S4-009`.

---

## File Structure

- Modify `src/retrieval/base.py`: add optional chain metadata fields to `SearchHit` without breaking existing callers.
- Modify `src/evaluation/metrics.py`: report `full_support_recall@2`, `full_support_recall@5`, and `full_support_recall@10` when `k=10`; report chain metrics only when chain metadata exists.
- Modify `src/retrieval/turbovec_retriever.py`: add bridge-query helpers and `search_two_hop_bridge_rrf`.
- Modify `src/evaluation/benchmark_es.py`: register `tv_two_hop_bridge_rrf`, pass hop/beam hyperparameters, preserve chain metadata when converting raw hits to `SearchHit`.
- Add `tests/test_metrics.py`: focused metric tests.
- Modify `tests/test_turbovec_retriever.py`: Bridge-RRF unit tests.
- Modify `tests/test_benchmark_es.py`: method dispatch and config tests.
- Create `docs/sprint4/retrieval-improvement-report.md`: report template after smoke validation exists.

## Task 1: Metrics Cutoffs And Chain Metadata

**Files:**
- Modify: `src/retrieval/base.py`
- Modify: `src/evaluation/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write failing tests for full-support cutoffs and chain metrics**

Create `tests/test_metrics.py` with:

```python
from __future__ import annotations

from src.evaluation.metrics import evaluate_rankings
from src.retrieval.base import SearchHit


def test_evaluate_rankings_reports_full_support_at_2_5_and_10():
    qrels = {"q1": {"d1": 1.0, "d2": 1.0}, "q2": {"d3": 1.0, "d4": 1.0}}
    runs = {
        "q1": [
            SearchHit(doc_id="d1", score=1.0, rank=1, method="m"),
            SearchHit(doc_id="d2", score=0.9, rank=2, method="m"),
        ],
        "q2": [
            SearchHit(doc_id="x1", score=1.0, rank=1, method="m"),
            SearchHit(doc_id="x2", score=0.9, rank=2, method="m"),
            SearchHit(doc_id="d3", score=0.8, rank=3, method="m"),
            SearchHit(doc_id="x3", score=0.7, rank=4, method="m"),
            SearchHit(doc_id="d4", score=0.6, rank=5, method="m"),
        ],
    }

    metrics = evaluate_rankings(qrels, runs, {"q1": 10.0, "q2": 20.0}, k=10)

    assert metrics["full_support_recall@2"] == 0.5
    assert metrics["full_support_recall@5"] == 1.0
    assert metrics["full_support_recall@10"] == 1.0


def test_evaluate_rankings_reports_chain_metrics_when_chain_output_exists():
    qrels = {"q1": {"bridge": 1.0, "answer": 1.0}, "q2": {"a": 1.0, "b": 1.0}}
    runs = {
        "q1": [
            SearchHit(
                doc_id="bridge",
                score=2.0,
                rank=1,
                method="tv_two_hop_bridge_rrf",
                chain_rank=1,
                chain_doc_ids=("bridge", "answer"),
            ),
            SearchHit(
                doc_id="answer",
                score=1.9,
                rank=2,
                method="tv_two_hop_bridge_rrf",
                chain_rank=1,
                chain_doc_ids=("bridge", "answer"),
            ),
        ],
        "q2": [
            SearchHit(
                doc_id="a",
                score=1.0,
                rank=1,
                method="tv_two_hop_bridge_rrf",
                chain_rank=1,
                chain_doc_ids=("a", "x"),
            ),
            SearchHit(
                doc_id="b",
                score=0.9,
                rank=2,
                method="tv_two_hop_bridge_rrf",
                chain_rank=2,
                chain_doc_ids=("a", "b"),
            ),
        ],
    }

    metrics = evaluate_rankings(qrels, runs, {"q1": 10.0, "q2": 20.0}, k=10)

    assert metrics["chain_recall@1"] == 0.5
    assert metrics["chain_recall@5"] == 1.0
    assert metrics["chain_mrr"] == 0.75
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_metrics.py -q`

Expected: FAIL because `SearchHit` does not accept `chain_rank` or `chain_doc_ids`, and metrics do not include the new keys.

- [ ] **Step 3: Implement minimal metadata and metrics support**

In `src/retrieval/base.py`, extend `SearchHit`:

```python
@dataclass(frozen=True)
class SearchHit:
    doc_id: str
    score: float
    rank: int
    method: str
    hop: int = 1
    chain_rank: int | None = None
    chain_doc_ids: tuple[str, ...] = ()
```

In `src/evaluation/metrics.py`, compute full-support for cutoffs and chain metrics. Keep the existing top-k metrics unchanged, and add helpers equivalent to:

```python
def _full_support_at(returned: list[str], relevant: set[str], cutoff: int) -> float:
    if not relevant:
        return 0.0
    return 1.0 if relevant.issubset(set(returned[:cutoff])) else 0.0


def _extract_ranked_chains(hits: list[SearchHit]) -> list[tuple[str, ...]]:
    chains: dict[tuple[str, ...], int] = {}
    for hit in hits:
        if not hit.chain_doc_ids:
            continue
        chain = tuple(str(doc_id) for doc_id in hit.chain_doc_ids if str(doc_id))
        if not chain:
            continue
        rank = hit.chain_rank if hit.chain_rank is not None else hit.rank
        chains[chain] = min(chains.get(chain, rank), rank)
    return [chain for chain, _ in sorted(chains.items(), key=lambda item: item[1])]
```

- [ ] **Step 4: Run metrics tests and verify GREEN**

Run: `python -m pytest tests/test_metrics.py -q`

Expected: PASS.

- [ ] **Step 5: Commit metrics slice**

```bash
git add src/retrieval/base.py src/evaluation/metrics.py tests/test_metrics.py
git commit -m "feat: add evidence chain metrics"
```

## Task 2: TurboVec Two-Hop Bridge-RRF Retriever

**Files:**
- Modify: `src/retrieval/turbovec_retriever.py`
- Modify: `tests/test_turbovec_retriever.py`

- [ ] **Step 1: Write failing Bridge-RRF retriever tests**

Append to `tests/test_turbovec_retriever.py`:

```python
def test_tv_two_hop_bridge_rrf_builds_bridge_queries_and_returns_chain_metadata(monkeypatch):
    class FakeBM25:
        pass

    class FakeTVIndex:
        pass

    class FakeEmbedder:
        pass

    class FakeDocStore:
        pass

    retriever = TurboVecHybridRetriever(
        bm25_retriever=FakeBM25(),
        tv_index=FakeTVIndex(),
        embedder=FakeEmbedder(),
        docstore=FakeDocStore(),
    )
    calls = []

    def fake_search(query, method, top_k, bm25_k=100, dense_k=100, rrf_k=60, candidate_k=None, **kwargs):
        calls.append({"query": query, "method": method, "top_k": top_k, "candidate_k": candidate_k, "rrf_k": rrf_k})
        if len(calls) == 1:
            return [
                {"doc_id": "bridge", "numeric_id": 1, "title": "Bridge Title", "text": "alpha beta gamma", "score": 0.9, "source": "bm25+dense"},
                {"doc_id": "other", "numeric_id": 2, "title": "Other", "text": "delta", "score": 0.8, "source": "bm25+dense"},
            ]
        return [
            {"doc_id": "answer", "numeric_id": 3, "title": "Answer", "text": "answer text", "score": 0.7, "source": "bm25+dense"},
            {"doc_id": "bridge", "numeric_id": 1, "title": "Bridge Title", "text": "duplicate", "score": 0.6, "source": "bm25+dense"},
        ]

    monkeypatch.setattr(retriever, "search", fake_search)

    hits = retriever.search_two_hop_bridge_rrf(
        "original question",
        top_k=3,
        hop1_top_k=2,
        hop2_top_k=2,
        beam_size=1,
        max_bridge_terms=2,
        candidate_k=20,
        rrf_k=30,
    )

    assert calls[0] == {"query": "original question", "method": "tv_hybrid", "top_k": 2, "candidate_k": 20, "rrf_k": 30}
    assert calls[1]["query"] == "original question Bridge Title alpha beta"
    assert [hit["doc_id"] for hit in hits[:2]] == ["bridge", "answer"]
    assert hits[0]["chain_rank"] == 1
    assert hits[0]["chain_doc_ids"] == ["bridge", "answer"]
    assert hits[1]["hop"] == 2


def test_bridge_query_terms_skip_query_terms_and_dedupe():
    retriever = TurboVecHybridRetriever(bm25_retriever=None, tv_index=None, embedder=None, docstore=None)
    hit = {"title": "Bridge Bridge Title", "text": "original alpha alpha beta gamma"}

    query = retriever._build_bridge_query("original question", hit, max_bridge_terms=3)

    assert query == "original question Bridge Bridge Title alpha beta"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_turbovec_retriever.py -q`

Expected: FAIL because `search_two_hop_bridge_rrf` and `_build_bridge_query` do not exist.

- [ ] **Step 3: Implement minimal Bridge-RRF method**

In `src/retrieval/turbovec_retriever.py`:

- Add `import re` and `TOKEN_RE = re.compile(r"[A-Za-z0-9]+")` near the imports.
- Add helper methods to `TurboVecHybridRetriever`:

```python
def _build_bridge_query(self, query: str, hit: dict[str, Any], max_bridge_terms: int) -> str:
    title = str(hit.get("title", "") or "").strip()
    query_terms = {token.lower() for token in TOKEN_RE.findall(query)}
    bridge_terms: list[str] = []
    seen: set[str] = set()
    text = f"{hit.get('text', '') or ''}"
    for token in TOKEN_RE.findall(text):
        token_key = token.lower()
        if token_key in query_terms or token_key in seen or len(token_key) < 3:
            continue
        seen.add(token_key)
        bridge_terms.append(token)
        if len(bridge_terms) >= max_bridge_terms:
            break
    return " ".join(part for part in [query, title, " ".join(bridge_terms)] if part)
```

Add `search_two_hop_bridge_rrf` that:

- Calls `self.search(query, "tv_hybrid", hop1_top_k, candidate_k=candidate_k, rrf_k=rrf_k)`.
- For each first-hop hit within `beam_size`, builds a bridge query.
- Calls `self.search(bridge_query, "tv_hybrid", hop2_top_k, candidate_k=candidate_k, rrf_k=rrf_k)`.
- Skips same-doc pairs.
- Scores chains with `1 / (rrf_k + hop1_rank) + 1 / (rrf_k + hop2_rank)`.
- Flattens sorted chains into unique document hits with `hop`, `chain_rank`, `chain_doc_ids`, `source="bridge_rrf"`, and score.
- Fills remaining slots from first-hop hits if fewer than `top_k` unique docs exist.

- [ ] **Step 4: Run retriever tests and verify GREEN**

Run: `python -m pytest tests/test_turbovec_retriever.py -q`

Expected: PASS.

- [ ] **Step 5: Commit retriever slice**

```bash
git add src/retrieval/turbovec_retriever.py tests/test_turbovec_retriever.py
git commit -m "feat: add TurboVec Bridge-RRF retrieval"
```

## Task 3: Benchmark Dispatch And Config

**Files:**
- Modify: `src/evaluation/benchmark_es.py`
- Modify: `tests/test_benchmark_es.py`

- [ ] **Step 1: Write failing benchmark dispatch test**

Append to `tests/test_benchmark_es.py`:

```python
def test_run_benchmark_dispatches_tv_two_hop_bridge_rrf(monkeypatch, tmp_path):
    calls = []

    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id="q1", text="query")

        def qrels_iter(self):
            yield SimpleNamespace(query_id="q1", doc_id="d1", relevance=1)

    class FakeRetriever:
        def search_two_hop_bridge_rrf(self, query, top_k, hop1_top_k, hop2_top_k, beam_size, max_bridge_terms, candidate_k, rrf_k):
            calls.append(
                {
                    "query": query,
                    "top_k": top_k,
                    "hop1_top_k": hop1_top_k,
                    "hop2_top_k": hop2_top_k,
                    "beam_size": beam_size,
                    "max_bridge_terms": max_bridge_terms,
                    "candidate_k": candidate_k,
                    "rrf_k": rrf_k,
                }
            )
            return [{"doc_id": "d1", "score": 1.0, "chain_rank": 1, "chain_doc_ids": ["d1"], "hop": 1}]

    monkeypatch.setattr(benchmark_es, "_load_ir_dataset", lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, "build_retriever", lambda *args, **kwargs: FakeRetriever())

    result = benchmark_es.run_benchmark(
        dataset_id="dataset",
        index="idx",
        methods=["tv_two_hop_bridge_rrf"],
        top_k=10,
        max_queries=None,
        url="http://localhost:9200",
        model_name="model",
        num_candidates=100,
        candidate_k=20,
        rrf_k=7,
        first_hop_k=3,
        second_hop_k=4,
        context_chars=128,
        run_dir=tmp_path,
        beam_size=2,
        max_bridge_terms=6,
    )

    assert calls == [
        {
            "query": "query",
            "top_k": 10,
            "hop1_top_k": 3,
            "hop2_top_k": 4,
            "beam_size": 2,
            "max_bridge_terms": 6,
            "candidate_k": 20,
            "rrf_k": 7,
        }
    ]
    assert result["config"]["beam_size"] == 2
    assert result["config"]["max_bridge_terms"] == 6
    assert result["results"][0]["metrics"]["chain_recall@1"] == 1.0
```

- [ ] **Step 2: Run test and verify RED**

Run: `python -m pytest tests/test_benchmark_es.py::test_run_benchmark_dispatches_tv_two_hop_bridge_rrf -q`

Expected: FAIL because the method is unsupported and `run_benchmark` does not accept `beam_size`/`max_bridge_terms`.

- [ ] **Step 3: Implement benchmark registration**

In `src/evaluation/benchmark_es.py`:

- Add `"tv_two_hop_bridge_rrf"` to `TURBOVEC_METHODS`.
- Add optional `beam_size: int = 3` and `max_bridge_terms: int = 8` to `run_benchmark` and `_search_method`.
- Include `beam_size`, `max_bridge_terms`, `hop1_top_k`, and `hop2_top_k` in `result["config"]` while keeping existing `first_hop_k` and `second_hop_k` for backward compatibility.
- Preserve raw hit chain metadata when converting to `SearchHit`:

```python
SearchHit(
    doc_id=str(hit["doc_id"]),
    score=float(hit.get("score", 0.0)),
    rank=rank,
    method=method,
    hop=int(hit.get("hop", 1) or 1),
    chain_rank=int(hit["chain_rank"]) if hit.get("chain_rank") is not None else None,
    chain_doc_ids=tuple(str(doc_id) for doc_id in hit.get("chain_doc_ids", []) if str(doc_id)),
)
```

- Add CLI args:

```python
parser.add_argument("--beam-size", type=int, default=3)
parser.add_argument("--max-bridge-terms", type=int, default=8)
```

- [ ] **Step 4: Run benchmark tests and verify GREEN**

Run: `python -m pytest tests/test_benchmark_es.py -q`

Expected: PASS.

- [ ] **Step 5: Commit benchmark dispatch slice**

```bash
git add src/evaluation/benchmark_es.py tests/test_benchmark_es.py
git commit -m "feat: benchmark Bridge-RRF retrieval"
```

## Task 4: Focused Verification And Sprint 4 Report

**Files:**
- Create: `docs/sprint4/retrieval-improvement-report.md`
- Modify: `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-009-iterative-retrieval-improvement.md`

- [ ] **Step 1: Run focused unit verification**

Run:

```bash
python -m pytest tests/test_metrics.py tests/test_turbovec_retriever.py tests/test_benchmark_es.py -q
```

Expected: PASS.

- [ ] **Step 2: Run a smoke benchmark when Elasticsearch, embedding server, and TurboVec artifact are available**

Run:

```bash
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_current --methods tv_hybrid,tv_two_hop_bridge_rrf --top-k 10 --max-queries 50 --candidate-k 50 --num-candidates 50 --rrf-k 30 --first-hop-k 3 --second-hop-k 5 --beam-size 2 --max-bridge-terms 6 --output evaluation/results/hotpotqa_full/bridge_rrf/bridge_rrf_smoke_50.json --run-dir evaluation/runs/hotpotqa_full/bridge_rrf
```

Expected: JSON output contains both methods, `full_support_recall@2`, `full_support_recall@5`, `full_support_recall@10`, and chain metrics for `tv_two_hop_bridge_rrf`.

- [ ] **Step 3: Write the initial report**

Create `docs/sprint4/retrieval-improvement-report.md` with:

```markdown
# Sprint 4 Retrieval Improvement Report

## Scope

This report covers `US-S4-009`: evidence-chain metrics and the benchmark-only `tv_two_hop_bridge_rrf` retrieval method. Redis cache hardening, dashboard defaults, LLM rewriting, cross-encoder reranking, MDR training, and Beam Retrieval training are out of scope.

## Methods

- `tv_hybrid`: Sprint 3 default quality baseline.
- `tv_two_hop_bridge_rrf`: first-hop `tv_hybrid`, bridge query expansion from first-hop evidence titles and terms, second-hop `tv_hybrid`, chain reranking, and flattened document output.

## Metrics

- `full_support_recall@2`
- `full_support_recall@5`
- `full_support_recall@10`
- `chain_recall@1`
- `chain_recall@5`
- `chain_mrr`
- `latency_p95_ms`
- `qps`

## Smoke Evidence

Add the smoke benchmark command, artifact paths, metric table, and blockers after the command runs.

## Decision

Do not change the dashboard/default method unless `tv_two_hop_bridge_rrf` improves `full_support_recall@10` by at least `+0.05` over `tv_hybrid` while keeping p95 latency within `2.5x` of `tv_hybrid` on the Sprint 4 pilot.
```

- [ ] **Step 4: Update story evidence**

Update `US-S4-009` with validation commands, artifacts, and whether the smoke benchmark ran or was blocked by missing local services/artifacts.

- [ ] **Step 5: Update Harness story row**

If focused tests pass and smoke benchmark runs:

```bash
scripts/bin/harness-cli story update --id US-S4-009 --status implemented --unit 1 --integration 1 --e2e 0 --platform 1 --evidence "Bridge-RRF unit tests and benchmark smoke passed; report at docs/sprint4/retrieval-improvement-report.md."
```

If only unit tests pass and benchmark smoke is blocked by services/artifacts:

```bash
scripts/bin/harness-cli story update --id US-S4-009 --status implemented --unit 1 --integration 0 --e2e 0 --platform 1 --evidence "Bridge-RRF code and unit tests passed; benchmark smoke blocked by missing local service/artifact; report documents blocker."
```

- [ ] **Step 6: Commit report and story evidence**

```bash
git add docs/sprint4/retrieval-improvement-report.md docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-009-iterative-retrieval-improvement.md
git commit -m "docs: report Bridge-RRF retrieval evidence"
```

## Self-Review

- Spec coverage: Covers metrics, existing baseline audit path, `tv_two_hop_bridge_rrf`, hyperparameters, smoke benchmark, report, and no default-method change.
- Placeholder scan: No placeholder markers are required for implementation. The report intentionally says to add smoke evidence only after the command runs.
- Type consistency: `chain_rank` is `int | None`; `chain_doc_ids` is `tuple[str, ...]` in `SearchHit` and list-like raw dict metadata from retrievers.
- Scope: Benchmark/retrieval layer only; no Redis, API, dashboard, cross-encoder, LLM rewrite, or training work.
