# US-S4-010 Lexical-Strong Paraphrase Profile

## Status

implemented

## Lane

normal

## Product Contract

The paraphrase pipeline supports a `lexical_strong` profile that is accepted only when the rewritten query changes enough non-entity content terms to act as a lexical-substitution stress test while preserving the original HotpotQA qrels meaning.

## Relevant Product Docs

- `docs/sprint4/paraphrase-protocol.md`
- `docs/sprint4/paraphrase-robustness-report.md`
- `notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb`

## Acceptance Criteria

- The generation notebook includes `lexical_strong` after `natural_mild` and `natural_strong`.
- The `lexical_strong` prompt explicitly requires replacing 2-3 non-entity content words and forbids reorder-only paraphrases.
- The local validator rejects weak `lexical_strong` rows with lexical-change reasons.
- The validator writes `lexical_strong_200.tsv` when valid candidates exist.
- The validator writes lexical audit artifacts before benchmark use.
- Existing `natural_mild` and `natural_strong` validation behavior remains covered by tests.

## Design Notes

- Commands: reuse `scripts/validate_openai_paraphrases.py` and `notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb`.
- Queries: `lexical_strong` keeps `source_query_id` so qrels still map to the original HotpotQA query.
- API: no runtime API surface changes.
- Tables: no database schema changes.
- Domain rules: lexical strength is a local validation gate, not just a generation prompt.
- UI surfaces: no dashboard changes in this story.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-010 --unit 1 --integration 0 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Validator and notebook contract tests pass. |
| Integration | Synthetic validator smoke writes `lexical_strong_200.tsv` and lexical audit artifacts. |
| E2E | Not required until actual generation and benchmark rerun. |
| Platform | Notebook JSON/protocol contract remains valid. |
| Release | Final report must not claim lexical robustness until `lexical_strong_200` has been generated and benchmarked. |

## Harness Delta

No Harness policy change. The story records a stricter benchmark-validity gate discovered from user review.

## Evidence

- Added `lexical_strong` to the validator profile list and notebook generation profiles.
- Added lexical gates: `content_change_ratio >= 0.15`, at least 2 new non-entity content terms, and `content_jaccard <= 0.80`.
- Added rejection reasons: `insufficient_lexical_change`, `no_new_content_terms`, and `high_content_overlap`.
- Added outputs: `lexical_strong_200.tsv`, `lexical_diversity_summary.json`, and `lexical_diversity_examples.tsv`.
- Focused tests: `python -m pytest tests/test_openai_paraphrase_validation.py tests/test_kaggle_paraphrase_notebook.py -q`.
