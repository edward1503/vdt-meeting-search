---
name: benchmark-or-evaluate-retrieval-results
description: Workflow command scaffold for benchmark-or-evaluate-retrieval-results in vdt-meeting-search.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /benchmark-or-evaluate-retrieval-results

Use this workflow when working on **benchmark-or-evaluate-retrieval-results** in `vdt-meeting-search`.

## Goal

Runs benchmarks or evaluations on retrieval pipelines, recording outputs and updating reports.

## Common Files

- `evaluation/results/*`
- `evaluation/runs/*`
- `src/evaluation/benchmark_es.py`
- `src/evaluation/query_paraphrase.py`
- `scripts/verify_sprint3_benchmark.py`
- `docs/sprint3/sprint3-report.md`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Run evaluation scripts to produce results in evaluation/results/* and evaluation/runs/*
- Update or create benchmark scripts in src/evaluation/*.py or scripts/verify_*.py
- Update sprint or project report in docs/sprint*/sprint*-report.md

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.