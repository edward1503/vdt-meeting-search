# Kaggle Paraphrase Notebook Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Kaggle paraphrase notebook with a robust subprocess-per-GPU workflow that reads TSV input efficiently and generates higher-quality paraphrase candidates.

**Architecture:** Keep the notebook as an orchestrator only. It prepares profile-specific request TSVs, writes a real `paraphrase_worker.py` script into `/kaggle/working`, launches one Python subprocess per GPU/profile, then merges checkpoint outputs. Worker code owns model loading, CUDA initialization, generation, parsing, and checkpointing.

**Tech Stack:** Jupyter notebook JSON, Python 3.12, pandas, Hugging Face Transformers, PyTorch, bitsandbytes 4-bit loading, subprocess, pytest contract tests.

---

### Task 1: Lock the New Notebook Contract

**Files:**
- Modify: `tests/test_kaggle_paraphrase_notebook.py`
- Test: `tests/test_kaggle_paraphrase_notebook.py`

- [ ] **Step 1: Add failing assertions**

Assert the notebook uses `subprocess.Popen`, writes `paraphrase_worker.py`, avoids `multiprocessing`, uses optimized TSV reads with `usecols`, `nrows`, `dtype=str`, and documents `Qwen/Qwen3-4B-Instruct-2507` plus `Qwen/Qwen2.5-3B-Instruct` fallback.

- [ ] **Step 2: Run focused test**

Run: `python -m pytest tests/test_kaggle_paraphrase_notebook.py -q`

Expected: FAIL because the current notebook still uses multiprocessing and lacks the new worker/orchestrator contract.

### Task 2: Rewrite the Notebook

**Files:**
- Modify: `notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb`
- Test: `tests/test_kaggle_paraphrase_notebook.py`

- [ ] **Step 1: Replace notebook content**

Create a fresh notebook with markdown sections for purpose, model choice, run configuration, worker script generation, input preparation, subprocess launch, merge, and handoff.

- [ ] **Step 2: Implement optimized input preparation**

Use pandas `read_csv` with `sep=TAB`, `dtype=str`, `keep_default_na=False`, schema-specific `usecols`, and `nrows=SOURCE_QUERY_LIMIT` for base query TSVs.

- [ ] **Step 3: Implement worker script text**

Write `/kaggle/working/paraphrase_worker.py` with importable top-level functions, argparse, model loading, JSON-array-first parsing, duplicate filtering, checkpoint writes, and profile-specific generation parameters.

- [ ] **Step 4: Implement subprocess orchestration**

Launch `natural_mild` on `cuda:0` and `natural_strong` on `cuda:1` with `subprocess.Popen`; fall back to sequential subprocesses when parallel is unavailable.

- [ ] **Step 5: Merge outputs**

Read profile output files, concatenate, sort, write TSV and JSONL final artifacts plus shortage artifacts.

### Task 3: Update Docs and Verify

**Files:**
- Modify: `docs/sprint4/paraphrase-protocol.md`
- Modify: `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-002-hotpotqa-paraphrase-export-protocol.md`
- Test: `tests/test_kaggle_paraphrase_notebook.py`

- [ ] **Step 1: Document subprocess worker strategy**

Add a concise protocol note that Kaggle generation uses subprocess workers rather than notebook multiprocessing.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_kaggle_paraphrase_notebook.py -q`

Expected: PASS with the existing pytest-asyncio warning allowed.
