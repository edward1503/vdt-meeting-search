# Kaggle Paraphrase Generation Design

Date: 2026-06-19
Story: US-S4-002, US-S4-003, US-S4-004
Lane: normal

## Goal

Add a Kaggle-ready notebook that generates LLM paraphrase candidates for the Sprint 4 200-query HotpotQA benchmark, using separate `natural_mild` and `natural_strong` profiles while preserving local benchmark traceability through `source_query_id`.

## Current State

The benchmark runner in `src/evaluation/benchmark_es.py` already supports custom query TSV files with `variant_query_id`, `source_query_id`, and `query`, then remaps qrels from the original query ids. The repo does not yet have a Sprint 4 notebook or protocol for exporting 200 source queries to Kaggle, generating multiple paraphrase candidates per profile, and bringing them back for local validation.

## Design

### Notebook Scope

The new notebook will live under `notebooks/` and act as a Kaggle execution surface only. It should not own the final benchmark truth. Its job is to:

1. Read a TSV export of 200 source queries.
2. Generate three `natural_mild` and three `natural_strong` candidates per source query.
3. Apply only light notebook-side checks such as non-empty output, duplicate collapse, and basic schema sanity.
4. Write raw candidate artifacts for download back into the local repository.

### Profiles

Each source query must produce both profiles:

- `natural_mild`: minimal but noticeable rewriting.
- `natural_strong`: larger surface-form rewriting while preserving meaning.

The final benchmark target is fixed at 200 accepted `natural_mild` queries and 200 accepted `natural_strong` queries. Missing or invalid rows should be regenerated rather than dropped.

### Candidate Rules

The notebook prompt and post-generation checks should preserve these rules:

- do not change the main named entities
- do not change numbers, years, or dates
- do not change the relation being asked
- do not return empty text
- do not return exact duplicates
- keep the sentence natural and answerable by the original qrels

### Input And Output Contracts

Notebook input TSV should include:

- `source_query_id`
- `original_query`
- `support_doc_ids`
- `qrels`
- `paraphrase_profile`
- `constraints`

Notebook raw output TSV should include one row per candidate with:

- `variant_query_id`
- `source_query_id`
- `paraphrase_profile`
- `candidate_index`
- `paraphrased_query`
- `model_id`
- `prompt_version`
- `generation_notes`

The local repository remains responsible for validating candidates, selecting one best candidate per source/profile, producing accepted and rejected artifacts, and running the benchmark.

### Model Strategy

The notebook should default to a configurable open instruct model that can run on Kaggle GPU, but the workflow must keep `MODEL_ID` configurable in one place. The notebook should document that the model can be swapped without changing the artifact schema.

### Validation And Reporting

Because notebook execution is external to the repo, local tests should validate the notebook contract rather than execute the model. The repository should also include a short Sprint 4 protocol doc explaining:

- what to upload to Kaggle
- what the notebook returns
- what the local validator is expected to do next

## Non-Goals

- No full local validator implementation in this change.
- No benchmark execution in this change.
- No semantic-similarity scoring in the notebook gate.
- No dashboard or API changes.
