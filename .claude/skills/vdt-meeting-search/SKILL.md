```markdown
# vdt-meeting-search Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches you the core development patterns, coding conventions, and workflows used in the `vdt-meeting-search` Python repository. The project focuses on implementing and benchmarking retrieval pipelines (such as BM25 and turbovec) for datasets like HotpotQA, with a strong emphasis on modular code, reproducible experiments, and thorough documentation. You'll learn how to add new retrieval methods, benchmark results, document features, and maintain comprehensive test coverage.

---

## Coding Conventions

### File Naming

- Use **snake_case** for all Python files and scripts.
  - Example: `elasticsearch_retriever.py`, `build_turbovec.py`

### Import Style

- Use **alias imports** for external libraries and internal modules.
  - Example:
    ```python
    import numpy as np
    import src.retrieval.elasticsearch_retriever as es_retriever
    ```

### Export Style

- Use **named exports** (explicitly define what is exported from a module).
  - Example:
    ```python
    # In src/retrieval/turbovec_retriever.py
    class TurbovecRetriever:
        ...

    __all__ = ["TurbovecRetriever"]
    ```

### Commit Messages

- Follow **conventional commit** style with these prefixes: `chore`, `docs`, `feat`, `fix`.
  - Example: `feat: add turbovec retriever for HotpotQA`

---

## Workflows

### Add or Update Retrieval Pipeline

**Trigger:** When you want to add a new retrieval method or update an existing one.  
**Command:** `/add-retrieval-pipeline`

1. Implement or update retrieval logic in `src/retrieval/*.py`.
    - Example:
      ```python
      # src/retrieval/turbovec_retriever.py
      class TurbovecRetriever:
          def retrieve(self, query):
              # Retrieval logic here
              pass
      ```
2. Update or add configuration in `src/core/config.py`.
    - Example:
      ```python
      # src/core/config.py
      RETRIEVER_CONFIG = {
          "turbovec": {...}
      }
      ```
3. Update or add API integration in `src/api/main.py` (if needed).
4. Add or update scripts for data processing or pipeline in `scripts/*.py`.
5. Write or update tests in `tests/test_*retriever.py` and related test files.

---

### Benchmark or Evaluate Retrieval Results

**Trigger:** When you want to benchmark retrieval performance or compare methods.  
**Command:** `/benchmark-retrieval`

1. Run evaluation scripts to produce results in `evaluation/results/*` and `evaluation/runs/*`.
    - Example:
      ```bash
      python src/evaluation/benchmark_es.py
      ```
2. Update or create benchmark scripts in `src/evaluation/*.py` or `scripts/verify_*.py`.
3. Update sprint or project report in `docs/sprint*/sprint*-report.md`.

---

### Feature or Experiment Documentation and Planning

**Trigger:** When you want to plan, document, or track a new feature, experiment, or sprint.  
**Command:** `/new-feature-docs`

1. Create or update plan/spec files in `docs/superpowers/plans/*` or `docs/decisions/*`.
2. Update or create epic/story tracking in `docs/stories/epics/*`.
3. Update sprint or experiment report in `docs/sprint*/sprint*-report.md`.

---

### Add or Update Tests for New Pipeline or Feature

**Trigger:** When you add a new retrieval pipeline or feature and need test coverage.  
**Command:** `/add-tests`

1. Implement or update test files in `tests/test_*.py` corresponding to new or changed code.
    - Example:
      ```python
      # tests/test_turbovec_retriever.py
      import unittest
      from src.retrieval.turbovec_retriever import TurbovecRetriever

      class TestTurbovecRetriever(unittest.TestCase):
          def test_retrieve(self):
              retriever = TurbovecRetriever()
              results = retriever.retrieve("example query")
              self.assertIsNotNone(results)
      ```
2. Run tests to ensure correctness.
    - Example:
      ```bash
      python -m unittest discover tests/
      ```

---

## Testing Patterns

- **Framework:** Not explicitly specified, but Python's `unittest` or similar is likely.
- **Test File Naming:** All test files use the pattern `test_*.py` and are located in the `tests/` directory.
- **Test Coverage:** Each new feature or retrieval pipeline should have corresponding test files.
- **JavaScript Note:** There are also `*.spec.js` files, but the main codebase is Python.

---

## Commands

| Command                  | Purpose                                                      |
|--------------------------|--------------------------------------------------------------|
| /add-retrieval-pipeline  | Add or update a retrieval pipeline and its configuration     |
| /benchmark-retrieval     | Run benchmarks and update evaluation results and reports     |
| /new-feature-docs        | Plan, document, or track new features, experiments, or sprints|
| /add-tests               | Add or update tests for new pipelines or features            |
```
