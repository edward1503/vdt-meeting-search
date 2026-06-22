# Sprint 4 Paraphrase Protocol

## Goal

Create a reproducible paraphrase benchmark path for 200 HotpotQA source queries that keeps local benchmark truth tied to the original qrels while using the OpenAI API for local paraphrase generation.

## Fixed Query Sets

- `original_200`: the 200 source queries used for the Sprint 3-style pilot baseline
- `mild_200`: one accepted `natural_mild` paraphrase per source query
- `strong_200`: one accepted `natural_strong` paraphrase per source query
- `lexical_strong_200`: one accepted `lexical_strong` paraphrase per source query

The paraphrase benchmark is complete only when `mild_200`, `strong_200`, and `lexical_strong_200` have all 200 rows. The `lexical_strong_200` set is the required stress set for testing whether BM25 drops more than dense retrieval under lexical substitution.

## OpenAI Generation Contract

For each `source_query_id`, the local OpenAI notebook must generate:

- 1 paraphrase per profile for `natural_mild`
- 1 paraphrase per profile for `natural_strong`
- 1 paraphrase per profile for `lexical_strong`

Each candidate must follow these rules:

- keep the main entities unchanged
- keep numbers, years, and dates unchanged
- keep the relation being asked unchanged
- do not return empty text
- do not return duplicates
- keep the sentence natural and answerable by the original qrels

Additional `lexical_strong` rules:

- replace 2-3 non-entity content words with equivalent terms or short phrases
- do not only reorder the original words
- satisfy local lexical gates: `content_change_ratio >= 0.15`, at least 2 new non-entity content terms, and `content_jaccard <= 0.80`

## Input Schema

The local export or base query TSV should contain these columns:

- `source_query_id`
- `original_query`
- `support_doc_ids`
- `qrels`
- `paraphrase_profile`
- `constraints`

`paraphrase_profile` is expected to be `natural_mild`, `natural_strong`, or `lexical_strong`.

For local convenience, the notebook may also accept a base query TSV such as `hotpotqa_full_dev_queries.tsv` with columns `query_id`, `query`, and `support_doc_ids`. In that mode the notebook expands each source query into both paraphrase profiles and applies a default pilot limit of 200 source queries unless the notebook configuration is changed.

The notebook should read TSV input with schema-specific columns and a row limit when possible. For base query TSVs, use `usecols`, `dtype=str`, `keep_default_na=False`, and `nrows=SOURCE_QUERY_LIMIT` so the pilot does not load the full dev query table just to keep the first 200 rows.

## Local OpenAI Runtime Strategy

The notebook is intentionally sequential for local reliability. It uses
`OPENAI_API_KEY`, optionally uses `OPENAI_BASE_URL` for an OpenAI-compatible
router endpoint, calls the API from the local machine, generates all
`natural_mild` rows first, writes checkpoint and final artifacts, then runs
`natural_strong`, then runs `lexical_strong`. This avoids GPU setup entirely
and keeps failures easy to inspect.

Default model for the local 9router-compatible endpoint:

- `combo`

Set `OPENAI_MODEL` in `.env` when the router should use a different model slug
or a provider-specific model id.

The configured model must keep the same output schema. The notebook calls the
Chat Completions API for broad OpenAI-compatible endpoint support, asks for a
single JSON object with one `paraphrase` string, parses JSON first, falls back to
plain text parsing, deduplicates candidates, and records shortages when no valid
paraphrase is produced.

## OpenAI Raw Output Schema

The notebook should write one row per generated candidate with these columns:

- `variant_query_id`
- `source_query_id`
- `paraphrase_profile`
- `candidate_index`
- `paraphrased_query`
- `model_id`
- `prompt_version`
- `generation_notes`

Expected raw artifact names:

- `openai_paraphrase_candidates.tsv`
- `openai_paraphrase_candidates.jsonl`
- `openai_paraphrase_shortages.tsv`
- `openai_paraphrase_shortages.jsonl`

During long local runs, the notebook may also write profile-specific checkpoint
files under `artifacts/hotpotqa_full/paraphrase/openai_generation/paraphrase_checkpoints/`
so interrupted sessions can be inspected before rerun.

## Local Validation And Selection

After OpenAI generation, the local repo remains the source of truth.

The local validator should:

1. reject rows that break schema or the hard rules
2. group rows by `source_query_id` and `paraphrase_profile`
3. choose one accepted candidate for `natural_mild`
4. choose one accepted candidate for `natural_strong`
5. choose one accepted candidate for `lexical_strong`
6. reject `lexical_strong` rows with `insufficient_lexical_change`, `no_new_content_terms`, or `high_content_overlap` when the lexical gates fail
7. write accepted and rejected artifacts with reasons
8. write `lexical_diversity_summary.json` and `lexical_diversity_examples.tsv` so the set quality can be audited before benchmarking
9. write `regeneration_needed.tsv` for source/profile pairs that still need a valid candidate

If a source query does not have at least one acceptable candidate for a profile, it must be regenerated. Missing rows are not allowed in the final benchmark sets.

## Final Benchmark Inputs

The local benchmark stage should consume:

- `original_200`
- `mild_200`
- `strong_200`
- `lexical_strong_200`

`mild_200`, `strong_200`, and `lexical_strong_200` should keep `source_query_id` so qrels can still be mapped from the original HotpotQA dev queries.

## Notes

This protocol keeps OpenAI focused on generation only. Accepted and rejected decisions stay local so the benchmark can be reproduced and audited from the repository.
