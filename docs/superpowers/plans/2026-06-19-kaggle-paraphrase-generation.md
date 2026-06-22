# Kaggle Paraphrase Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Kaggle notebook and repo docs for generating 3 `natural_mild` and 3 `natural_strong` paraphrase candidates per HotpotQA source query for the Sprint 4 200-query benchmark.

**Architecture:** Keep Kaggle responsible for candidate generation only and keep local benchmark truth in the repo. The notebook reads a fixed TSV schema, generates raw candidates for both profiles, performs only light sanity checks, and writes deterministic artifact files that the later local validator can consume.

**Tech Stack:** Jupyter notebook JSON, Python 3, Hugging Face Transformers, pytest, repo markdown docs.

---

## File Structure

- Create: `notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb`
- Create: `docs/sprint4/paraphrase-protocol.md`
- Create: `tests/test_kaggle_paraphrase_notebook.py`
- Create: `docs/superpowers/specs/2026-06-19-kaggle-paraphrase-generation-design.md`
- Create: `docs/superpowers/plans/2026-06-19-kaggle-paraphrase-generation.md`

---

### Task 1: Lock the notebook contract with tests

**Files:**
- Create: `tests/test_kaggle_paraphrase_notebook.py`
- Test: `notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb`

- [ ] **Step 1: Write the failing test**

Add a test that loads the notebook JSON and asserts:

- the notebook exists
- it documents `natural_mild` and `natural_strong`
- it requires 3 candidates per profile
- it documents the input columns and output columns
- it writes raw candidate artifacts for local download

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_kaggle_paraphrase_notebook.py -q`

Expected: FAIL because the notebook does not exist yet.

- [ ] **Step 3: Create the notebook**

Build a Kaggle notebook that:

- installs `transformers`, `accelerate`, `bitsandbytes`, and `pandas`
- reads an uploaded/exported TSV from `/kaggle/input` or `/kaggle/working`
- defines one configurable `MODEL_ID`
- builds prompts for `natural_mild` and `natural_strong`
- generates 3 candidates per query/profile
- filters empty and duplicate notebook-side candidates
- writes raw TSV and JSONL outputs under `/kaggle/working`

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_kaggle_paraphrase_notebook.py -q`

Expected: PASS.

### Task 2: Add protocol documentation for local handoff

**Files:**
- Create: `docs/sprint4/paraphrase-protocol.md`
- Test: `tests/test_kaggle_paraphrase_notebook.py`

- [ ] **Step 1: Extend the failing test**

Add assertions that the protocol doc exists and mentions:

- the 200-query source set
- both paraphrase profiles
- 3 candidates per profile
- required export/import columns
- local accepted/rejected selection after Kaggle download

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_kaggle_paraphrase_notebook.py -q`

Expected: FAIL because the protocol doc does not exist yet.

- [ ] **Step 3: Write the protocol doc**

Document the end-to-end flow:

- local export to Kaggle
- Kaggle candidate generation
- local validation and best-candidate selection
- regeneration when a source query/profile has no acceptable candidate
- final benchmark inputs `original_200`, `mild_200`, and `strong_200`

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_kaggle_paraphrase_notebook.py -q`

Expected: PASS.

### Task 3: Verify repository state and handoff

**Files:**
- Review: `notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb`
- Review: `docs/sprint4/paraphrase-protocol.md`

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest tests/test_kaggle_paraphrase_notebook.py -q`

Expected: PASS.

- [ ] **Step 2: Inspect notebook JSON and protocol text**

Run:

```powershell
Get-Content notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb -TotalCount 40
Get-Content docs/sprint4/paraphrase-protocol.md
```

Expected: notebook clearly describes profiles, rules, and output files; protocol doc clearly describes local handoff.

---

## Success Criteria

The change is successful when:

1. The repository contains a Kaggle notebook for raw paraphrase generation.
2. The notebook contract matches the agreed Sprint 4 pipeline.
3. The protocol doc tells the next agent exactly how Kaggle output flows back into local validation and benchmark steps.
4. Focused tests pass without needing to execute a live Kaggle model.
