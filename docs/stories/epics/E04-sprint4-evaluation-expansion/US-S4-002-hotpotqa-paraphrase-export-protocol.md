# US-S4-002 HotpotQA Paraphrase Export Protocol

## Status

implemented

## Lane

normal

## Product Contract

The system can build a deterministic 200-query HotpotQA paraphrase request path through the local notebook/base-TSV workflow documented in `docs/sprint4/paraphrase-protocol.md`, while preserving qrels traceability back to the original `beir/hotpotqa/dev` source queries.

## Relevant Product Docs

- `docs/sprint4/plan.md`
- `docs/sprint4/paraphrase-protocol.md`
- `docs/architecture/current-architecture.md`

## Acceptance Criteria

- The active protocol uses the base TSV path described in `docs/sprint4/paraphrase-protocol.md` instead of a separate export-request artifact.
- The notebook reads the deterministic first 200 `beir/hotpotqa/dev` source queries from `evaluation/results/hotpotqa_full_dev_queries.tsv` and expands them into paraphrase profiles.
- Generated candidate rows preserve `source_query_id`, `original_query`, `support_doc_ids`, `qrels`, `paraphrase_profile`, and generation metadata.
- Profiles include `natural_mild`, `natural_strong`, and the later Sprint 4 `lexical_strong` stress profile.
- Prompt and validator constraints require preserving named entities, numbers, dates, and relation meaning.
- Canonical artifacts are documented under `artifacts/hotpotqa_full/paraphrase/`.
- Local validation catches missing source ids, empty paraphrases, duplicate source/profile variants, qrels linkage gaps, number drift, same-as-original rows, and insufficient lexical change before benchmark selection.

## Design Notes

- Commands: no standalone export CLI is used for the accepted Sprint 4 path; the local OpenAI-compatible notebook consumes the base query TSV and writes canonical artifacts.
- Queries: source split is `beir/hotpotqa/dev`; source count is 200.
- API: no API changes.
- Tables: no SQLite or Elasticsearch changes.
- Domain rules: qrels are owned by the source query and must not be regenerated from paraphrased text.
- UI surfaces: no UI changes.

## Validation

When updating durable proof status, use numeric booleans:
`scripts/bin/harness-cli story update --id US-S4-002 --unit 1 --integration 0 --e2e 0 --platform 1`.

| Layer | Expected proof |
| --- | --- |
| Unit | Notebook/static validation and local paraphrase validation tests. |
| Integration | Not required unless export directly loads `ir_datasets`. |
| E2E | Not required. |
| Platform | Canonical paraphrase artifacts exist with 200 source queries and complete selected profile sets. |
| Release | Not required. |

## Harness Delta

No Harness policy change is planned.

## Evidence

- 2026-06-19: Kaggle paraphrase notebook CUDA multiprocessing hotfix. Parallel profile workers now use the `spawn` multiprocessing context instead of `fork` so each GPU worker initializes CUDA in its own process. Focused proof: `python -m pytest tests/test_kaggle_paraphrase_notebook.py -q` -> 2 passed.
- 2026-06-19: Rewrote the Kaggle paraphrase notebook as a subprocess-per-profile orchestrator. The notebook now writes `/kaggle/working/paraphrase_run/paraphrase_worker.py`, reads base TSVs with schema-specific `usecols`, `dtype=str`, `keep_default_na=False`, and `nrows=SOURCE_QUERY_LIMIT`, defaults to `Qwen/Qwen3-4B-Instruct-2507` with `Qwen/Qwen2.5-3B-Instruct` fallback, and avoids notebook process targets entirely. Focused proof: `python -m pytest tests/test_kaggle_paraphrase_notebook.py -q` -> 2 passed.
- 2026-06-20: Simplified the Kaggle paraphrase notebook to a sequential Kaggle-stability path. Current notebook generates `natural_mild` first, writes checkpoints and aggregate artifacts, then generates `natural_strong`; the older parallel worker design is no longer the active notebook design. The optional Kaggle install now requires `transformers>=4.51.0` because Qwen3 model loading can fail with older Transformers. Focused proof: `python -m pytest tests/test_kaggle_paraphrase_notebook.py -q` -> 2 passed. Related proof: `python -m pytest tests/test_query_paraphrase.py -q` -> 5 passed; notebook JSON/nbformat validation passed with 9 cells and 6 code cells.
- 2026-06-20: Converted the active paraphrase generation notebook from Kaggle/Qwen to local OpenAI API generation. Current notebook uses `OPENAI_API_KEY`, defaults to `gpt-4.1-mini`, generates 1 paraphrase per profile for 200 source queries, runs `natural_mild` before `natural_strong`, and writes `openai_paraphrase_candidates.*` plus shortages/checkpoints under `artifacts/hotpotqa_full/paraphrase/openai_generation/`. Focused proof: `python -m pytest tests/test_kaggle_paraphrase_notebook.py tests/test_query_paraphrase.py -q` -> 7 passed; notebook static validation passed with 7 cells, 5 code cells, and no saved output errors.
- 2026-06-20: Added local OpenAI-compatible router support. The notebook reads `.env`, accepts `OPENAI_BASE_URL` such as `http://localhost:20128/v1`, initializes `OpenAI(base_url=openai_base_url)`, and uses Chat Completions instead of Responses API for broader `/v1` compatibility. Focused proof: `python -m pytest tests/test_kaggle_paraphrase_notebook.py tests/test_query_paraphrase.py -q` -> 7 passed; notebook static validation passed with 7 cells, 5 code cells, and no saved output errors.
- 2026-06-20: Smoke-tested the local 9router-compatible endpoint at `http://localhost:20128/v1`: `/models` returned 19 models and `/chat/completions` with `combo` returned `ok`. The notebook now allows `.env` to override `OPENAI_MODEL` for router-specific model slugs. Focused proof: `python -m pytest tests/test_kaggle_paraphrase_notebook.py tests/test_query_paraphrase.py -q` -> 7 passed; notebook static validation passed with 7 cells, 5 code cells, and no saved output errors.
- 2026-06-20: Changed the visible notebook default model from `gpt-4.1-mini` to `combo` so the local 9router path works without requiring `OPENAI_MODEL` override. `OPENAI_MODEL` remains configurable through `.env`.
- 2026-06-20: Fixed local notebook TSV discovery when Jupyter starts from `notebooks/`. The input-loading cell now finds the repo root before looking for `evaluation/results/hotpotqa_full_dev_queries.tsv`, preventing a false `Visible TSVs: (none)` error. Focused proof: `python -m pytest tests/test_kaggle_paraphrase_notebook.py tests/test_query_paraphrase.py -q` -> 8 passed; notebook static validation passed with 7 cells, 5 code cells, and no saved output errors.
- 2026-06-20: Copied the generated OpenAI paraphrase artifacts from the accidental `notebooks/artifacts/...` path to the canonical `artifacts/hotpotqa_full/paraphrase/openai_generation/` path after fixing notebook output-root discovery. Artifact proof: 400 rows, 200 `natural_mild`, 200 `natural_strong`, 200 source ids, 0 empty paraphrases, 0 duplicate source/profile rows, 0 duplicate variant ids, 400 parseable JSONL rows, and 0 shortages; 4 rows exactly match the original query after normalization and should be handled by validator/selection.
- 2026-06-21: Closed this story around the accepted notebook/base-TSV protocol rather than a separate export-request artifact. Final local validation artifacts confirm 603 accepted candidates and complete selected sets: `mild_200.tsv` = 200 rows, `strong_200.tsv` = 200 rows, `lexical_strong_200.tsv` = 200 rows, and `regeneration_needed.tsv` = 0 data rows. The protocol is documented in `docs/sprint4/paraphrase-protocol.md`, and the end-to-end benchmark evidence is reported in `docs/sprint4/paraphrase-robustness-report.md`.
