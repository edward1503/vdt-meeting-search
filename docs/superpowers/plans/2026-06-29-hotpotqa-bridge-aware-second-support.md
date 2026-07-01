# HotpotQA Bridge-Aware Second-Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and evaluate a HotpotQA benchmark-only retrieval ablation that improves second-support candidate generation.

**Architecture:** Extend the existing `tv_two_hop_bridge_rrf` path instead of adding a separate retrieval stack. The new variant uses a stronger bridge query builder that prioritizes title phrases, capitalized entity spans, and lead-sentence terms from hop-1 documents, then exposes it through the benchmark runner as a separate method.

**Tech Stack:** Python, pytest, Elasticsearch BM25, TurboVec hybrid retrieval, Harness CLI.

---

### Task 1: Story and Design Record

**Files:**
- Create: `docs/stories/epics/E05-sprint5-explainable-retrieval/US-S5-011-bridge-aware-second-support-retrieval.md`
- Create: `docs/sprint5/bridge-aware-second-support-report.md`

- [ ] **Step 1: Create the story packet**

Add a normal-lane story that states acceptance criteria, validation, and non-goals. The story must say the method is benchmark-only and the default retrieval path does not change.

- [ ] **Step 2: Create a report shell**

Create a report shell with command slots, metrics table, and decision section. Fill runtime numbers only after benchmarks complete.

### Task 2: Bridge Query Extraction TDD

**Files:**
- Modify: `tests/test_turbovec_retriever.py`
- Modify: `src/retrieval/turbovec_retriever.py`

- [ ] **Step 1: Write failing tests**

Add tests that expect a new bridge query mode to keep title terms, entity spans from the lead sentence, dedupe query terms, and cap added terms.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_turbovec_retriever.py -q`

Expected: fail because the new method does not exist yet.

- [ ] **Step 3: Implement minimal extractor**

Add a helper that builds a focused bridge query from the original question and hop-1 hit. Keep token filtering simple and deterministic.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_turbovec_retriever.py -q`

Expected: pass.

### Task 3: Benchmark Method TDD

**Files:**
- Modify: `tests/test_benchmark_es.py`
- Modify: `src/evaluation/benchmark_es.py`

- [ ] **Step 1: Write failing benchmark dispatch test**

Add a test for method `tv_bridge_title_entities_rrf` that dispatches to the new retriever method and records bridge settings.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_benchmark_es.py -q`

Expected: fail because the method is unsupported.

- [ ] **Step 3: Implement benchmark dispatch**

Add `tv_bridge_title_entities_rrf` to `TURBOVEC_METHODS` and `_search_method`.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_benchmark_es.py -q`

Expected: pass.

### Task 4: Diagnostics and Runtime Pilot

**Files:**
- Generate: `evaluation/results/hotpotqa_full/bridge_title_entities/bridge_title_entities_200.json`
- Generate: `evaluation/runs/hotpotqa_full/bridge_title_entities/tv_bridge_title_entities_rrf_beir_hotpotqa_dev_top10.trec`
- Generate: `evaluation/results/hotpotqa_full/bridge_title_entities/second_support_diagnostics.json`

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest tests/test_turbovec_retriever.py tests/test_benchmark_es.py -q`

- [ ] **Step 2: Run benchmark pilot**

Run: `python -m src.evaluation.benchmark_es --dataset beir/hotpotqa/dev --index hotpotqa_full_bm25_current --methods tv_hybrid,tv_two_hop_bridge_rrf,tv_bridge_title_entities_rrf --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --beam-size 3 --max-bridge-terms 8 --output evaluation/results/hotpotqa_full/bridge_title_entities/bridge_title_entities_200.json --run-dir evaluation/runs/hotpotqa_full/bridge_title_entities`

- [ ] **Step 3: Run diagnostics on generated runs**

Use `scripts/ranking_diagnostics.py` against generated TREC files and the HotpotQA qrels/query TSV available in the repo. If no suitable TSV exists, document that diagnostics are limited to benchmark metrics.

### Task 5: Report and Harness Closeout

**Files:**
- Modify: `docs/sprint5/bridge-aware-second-support-report.md`
- Modify: `docs/stories/epics/E05-sprint5-explainable-retrieval/US-S5-011-bridge-aware-second-support-retrieval.md`
- Modify: `harness.db`

- [ ] **Step 1: Fill report**

Record metrics versus `tv_hybrid` and `tv_two_hop_bridge_rrf`. State whether `full_support_recall@10` improved.

- [ ] **Step 2: Update story evidence**

Use Harness proof booleans: unit `1`, integration `1` if benchmark ran, e2e `0`, platform `1` if artifacts/report were generated.

- [ ] **Step 3: Record trace**

Record intake `#174`, story `US-S5-011`, commands run, files changed, and any friction.
