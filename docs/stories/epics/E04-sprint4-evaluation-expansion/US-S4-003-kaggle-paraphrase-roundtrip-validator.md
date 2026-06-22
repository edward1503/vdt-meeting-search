# US-S4-003 OpenAI Paraphrase Roundtrip Validator

## Status

implemented

## Lane

normal

## Product Contract

Imported paraphrases are validated before they enter benchmark runs. Invalid paraphrases are rejected rather than scored with stale qrels when wording changes the meaning of the source question.

## Relevant Product Docs

- `docs/sprint4/plan.md`
- `docs/sprint4/paraphrase-protocol.md`

## Acceptance Criteria

- Validator accepts rows with `variant_query_id`, `source_query_id`, `paraphrased_query`, `paraphrase_profile`, and preserved qrels linkage.
- Validator rejects empty paraphrases.
- Validator rejects duplicate accidental collapse within the same profile/source query.
- Validator checks that named entities and numbers are mostly preserved.
- Validator verifies every `source_query_id` maps to exported qrels.
- Validator writes accepted and rejected artifacts separately with rejection reasons.
- Benchmark input is built only from accepted paraphrases.

## Design Notes

- Commands: likely validator CLI over Kaggle-returned TSV/JSONL artifacts.
- Queries: paraphrase variants become benchmark query ids; qrels remain source-query qrels.
- API: no API changes.
- Tables: no durable schema change.
- Domain rules: if the paraphrase clearly changes the meaning, exclude it from benchmark.
- UI surfaces: no UI changes.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-003 --unit 1 --integration 0 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Validator tests for accepted rows, empty rows, duplicate variants, missing qrels, and entity/number drift. |
| Integration | Optional artifact-level validation against sample returned file. |
| E2E | Not required. |
| Platform | Accepted and rejected artifact files exist with counts. |
| Release | Not required. |

## Harness Delta

No Harness policy change is planned.

## Evidence

- Implemented local validator module `src/evaluation/openai_paraphrase_validation.py` and CLI `scripts/validate_openai_paraphrases.py`.
- Unit proof: `python -m pytest tests/test_openai_paraphrase_validation.py tests/test_kaggle_paraphrase_notebook.py tests/test_query_paraphrase.py tests/test_benchmark_es.py -q` => 20 passed.
- Artifact proof: `python scripts/validate_openai_paraphrases.py --input artifacts/hotpotqa_full/paraphrase/openai_generation/openai_paraphrase_candidates.tsv --output-dir artifacts/hotpotqa_full/paraphrase/validated --expected-per-profile 200` wrote `accepted.tsv`, `rejected.tsv`, `summary.json`, `mild_200.tsv`, `strong_200.tsv`, and `regeneration_needed.tsv`.
- Validation result for the first 400 generated candidates: 389 accepted, 11 rejected. Rejection reasons: 10 `same_as_original`, 1 `number_drift`.
- Final selection result after regeneration: `mild_200.tsv` has 200 rows and `strong_200.tsv` has 200 rows. `regeneration_needed.tsv` is empty.
- Retry workflow added: when `regeneration_needed.tsv` exists, `notebooks/kaggle_hotpotqa_paraphrase_generation.ipynb` writes retry-safe `openai_paraphrase_regeneration_candidates.tsv` with `__regen` variant ids, and `scripts/merge_openai_paraphrases.py` merges original plus regeneration candidates before revalidation.

- Regeneration proof: notebook retry mode generated 11 first-round candidates and 5 second-round candidates; merged artifact `openai_paraphrase_candidates_merged.tsv` has 416 rows, validator selected 400 accepted rows and rejected 16 invalid/duplicate attempts.
