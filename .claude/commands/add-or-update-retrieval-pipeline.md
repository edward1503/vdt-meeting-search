---
name: add-or-update-retrieval-pipeline
description: Workflow command scaffold for add-or-update-retrieval-pipeline in vdt-meeting-search.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /add-or-update-retrieval-pipeline

Use this workflow when working on **add-or-update-retrieval-pipeline** in `vdt-meeting-search`.

## Goal

Implements or updates a retrieval pipeline (e.g., BM25, turbovec) for HotpotQA, including backend logic, configuration, and tests.

## Common Files

- `src/retrieval/elasticsearch_retriever.py`
- `src/retrieval/turbovec_retriever.py`
- `src/core/config.py`
- `src/api/main.py`
- `scripts/es_hotpotqa.py`
- `scripts/build_turbovec.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Implement or update retrieval logic in src/retrieval/*.py
- Update or add configuration in src/core/config.py
- Update or add API integration in src/api/main.py (if needed)
- Add or update scripts for data processing or pipeline (scripts/*.py)
- Write or update tests in tests/test_*retriever.py and related test files

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.