# Lexical Strong Paraphrase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `lexical_strong` paraphrase profile that can be audited as a real lexical-substitution stress test before benchmark runs.

**Architecture:** Keep generation in the existing sequential OpenAI-compatible notebook, but add local validation gates in `src/evaluation/openai_paraphrase_validation.py` so benchmark inputs cannot accept reorder-only strong paraphrases. The validator computes content-term overlap, writes lexical audit artifacts, and selects `lexical_strong_200.tsv` only when each source query has a candidate that passes the thresholds.

**Tech Stack:** Python validator and tests, Jupyter notebook JSON, Harness story/docs.

---

### Task 1: Validator Lexical Gates

**Files:**
- Modify: `tests/test_openai_paraphrase_validation.py`
- Modify: `src/evaluation/openai_paraphrase_validation.py`

- [ ] Add tests proving `lexical_strong` rejects reorder-only candidates with `insufficient_lexical_change` and accepts candidates with enough non-entity content substitutions.
- [ ] Run the focused validator tests and verify the new test fails before implementation.
- [ ] Add content-term extraction, lexical metrics, profile-specific thresholds, and `lexical_strong_200.tsv` output.
- [ ] Run focused validator tests and verify they pass.

### Task 2: Notebook And Protocol Profile

**Files:**
- Modify: `notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb`
- Modify: `tests/test_kaggle_paraphrase_notebook.py`
- Modify: `docs/sprint4/paraphrase-protocol.md`

- [ ] Add tests that expect `lexical_strong`, `2-3 non-entity content words`, and `lexical_strong_200.tsv` in notebook/protocol text.
- [ ] Run the notebook contract tests and verify they fail before notebook/docs changes.
- [ ] Update notebook generation profiles, prompt text, output copy, and markdown to include `lexical_strong` after `natural_strong`.
- [ ] Update protocol docs to define the lexical gates.
- [ ] Run notebook contract tests and verify they pass.

### Task 3: Story Evidence And Verification

**Files:**
- Create: `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-010-lexical-strong-paraphrase-profile.md`
- Modify: Harness durable story rows

- [ ] Add `US-S4-010` story with acceptance criteria and validation evidence.
- [ ] Run focused tests: `python -m pytest tests/test_openai_paraphrase_validation.py tests/test_kaggle_paraphrase_notebook.py -q`.
- [ ] Run a small synthetic validator smoke for `lexical_strong` and verify lexical audit artifacts are written.
- [ ] Update Harness story/matrix evidence and record a trace.

### Self-Review

- The plan covers validator, notebook, docs, tests, and Harness evidence.
- No benchmark run is included until real `lexical_strong` candidates are generated.
- No API calls are required for this implementation pass.
