# Sprint 5 Plan: Explainable Retrieval, Ranking Diagnostics, and Semantic Metadata Search

## Status

Draft plan for Sprint 5 discussion. This document records the three tasks selected
after the Sprint 4 presentation feedback. It is not yet a detailed implementation
checklist.

Update 2026-06-29: HotpotQA retrieval follow-up results are consolidated in
`docs/sprint5/hotpotqa-retrieval-results-summary.md`. The strongest current
pilot method is `tv_bridge_title_entities_rrf` with `beam_size=1` and
`max_bridge_terms=6`, which reached `full_support_recall@10=0.6200` on the
200-query `beir/hotpotqa/dev` pilot while keeping p95 latency at `1224.9911 ms`.

## Goal

Sprint 5 should make the retrieval demo easier to explain, easier to evaluate,
and closer to the mentor's semantic metadata search expectation.

The sprint focuses on three tasks:

1. Highlight query-relevant terms in retrieval results.
2. Analyze document ranking quality before deciding whether a reranker is needed.
3. Support semantic metadata search where metadata constraints appear inside the
   natural-language query, not only in separate filter fields.

## Current Context

Sprint 4 already delivered full-corpus HotpotQA retrieval, dataset-first API/UI,
metadata filter controls, paraphrase robustness evidence, VimQA benchmarking,
and a first iterative retrieval experiment. The active default remains
`tv_hybrid` because the Sprint 4 `tv_two_hop_bridge_rrf` pilot did not beat the
default quality target.

HotpotQA has synthetic metadata suitable for Sprint 5 experiments:

- `author`
- `created_at`
- `modified_at`

The current metadata behavior is mostly explicit filtering: users provide a
content query and fill separate author/date fields. Sprint 5 should add a path
for queries that include both content intent and metadata constraints in one
natural-language string.

## Task 1: Retrieval Result Highlighting

### Purpose

Help users and reviewers see why a document was retrieved. The search results
should make the relation between the query and each result visible without
requiring someone to manually scan the entire snippet.

### Scope

- Highlight query-relevant terms in result titles and text snippets.
- Prefer content-bearing terms over stopwords.
- Keep the first version lexical and deterministic; semantic highlighting is out
  of scope for the first slice.
- For parsed semantic metadata queries, distinguish content highlights from
  metadata constraint matches.

### Expected UI Behavior

For a regular query, the result card should highlight matching content terms in
the title and snippet.

For a semantic metadata query such as:

```text
Find documents about anarchism by Nguyen An before 01/31/2024
```

the UI should show:

- content term highlight: `anarchism`
- metadata match chip: `author = Nguyen An`
- metadata constraint chip: `created_at <= 2024-01-31`

### Output

- Search result cards expose content matches more clearly.
- Metadata constraints parsed from the query are visible as explanation chips.
- The demo can answer: "Why is this result relevant to the query?"

## Task 2: Ranking Diagnostics Before Reranker

### Purpose

Decide whether a reranker is actually needed using ranking evidence instead of
guesswork.

### Scope

- Analyze where relevant documents appear in each method's ranked list.
- Compare candidate recall and final top-k ranking quality.
- Separate candidate-generation failures from ranking failures.
- Produce a report that recommends whether Sprint 6 should try a reranker,
  tune fusion, or improve candidate generation first.

### Diagnostic Questions

- Are gold/support documents missing from the candidate pool entirely?
- Are gold/support documents present in top-50 or top-100 but ranked below
  top-10?
- Which queries are better served by BM25 than dense retrieval?
- Which queries are better served by dense retrieval than BM25?
- Does hybrid fusion improve or hurt ranking for difficult queries?
- Do metadata constraints ever exclude expected gold/support documents?

### Failure Buckets

Ranking diagnostics should classify failures into buckets such as:

- `missing_candidate`
- `candidate_ranked_low`
- `bm25_wins_dense_fails`
- `dense_wins_bm25_fails`
- `hybrid_fusion_regression`
- `metadata_filter_excluded_gold`

### Decision Rule

- If many relevant documents appear in candidates but rank below top-k, a
  reranker is justified.
- If many relevant documents never enter the candidate pool, reranking is not
  the first fix.
- If hybrid underperforms one of its inputs, tune fusion before adding a heavier
  reranker.

### Output

- `docs/sprint5/ranking-diagnostics-report.md`
- Evidence-backed recommendation: try reranker, tune fusion, or improve
  candidate generation.

## Task 3: Semantic Metadata Search

### Purpose

Address the mentor feedback that metadata search should understand natural
queries containing metadata meaning, not only form-based filters.

The target behavior is:

```text
User query:
Find documents about anarchism by Nguyen An before 01/31/2024

Parsed search intent:
content_query = "anarchism"
author = "Nguyen An"
created_at_to = "2024-01-31"
```

### Scope

- Use HotpotQA synthetic metadata as the primary Sprint 5 evaluation surface.
- Start with a deterministic rule-based parser for natural-language metadata
  queries.
- Extract content intent and metadata constraints from a single query string.
- Route parsed constraints through the existing metadata-aware retrieval path.
- Return parse/explanation metadata so the UI can display what the system
  understood.

### Initial Query Patterns

The first slice should support simple, demoable patterns such as:

```text
documents about <topic> by <author>
documents about <topic> before <date>
documents about <topic> after <date>
documents about <topic> by <author> before <date>
documents about <topic> between <date> and <date>
```

### Ground Truth Direction

The semantic metadata evaluation should use HotpotQA qrels plus synthetic
metadata:

- Start from HotpotQA queries with known support documents.
- Read synthetic metadata for the support documents.
- Generate semantic metadata query variants that include author/date constraints.
- Treat relevant documents as support documents that satisfy the parsed metadata
  constraints.
- Record when a metadata constraint reduces the original support set.

This should be described as a synthetic-metadata retrieval evaluation, not a
BEIR leaderboard claim.

### Output

- Semantic metadata query examples and evaluation artifacts under
  `evaluation/results/hotpotqa_full/semantic_metadata/`.
- Parser output returned in API responses for UI explanation.
- Reported metrics for semantic metadata retrieval quality.

## Recommended Work Order

1. Define semantic metadata query format and parser expectations.
2. Build or generate the semantic metadata evaluation set.
3. Add ranking diagnostics over existing and semantic-metadata query runs.
4. Add UI highlight and explanation chips using parser output.

This order keeps the UI aligned with the retrieval behavior that Sprint 5 needs
to demonstrate.

## Explicit Non-Goals

- Do not train a reranker in Sprint 5 before diagnostics justify it.
- Do not claim production meeting-search quality while metadata is synthetic.
- Do not replace the dashboard default retrieval method without benchmark
  evidence.
- Do not use VimQA as the primary semantic metadata benchmark unless a later
  audit finds comparable metadata fields.
- Do not add an LLM parser before a deterministic parser proves the query shape.

## Exit Criteria

Sprint 5 is ready to close when:

- Retrieval results visually explain content and metadata matches.
- Ranking diagnostics identify whether reranking is justified.
- Semantic metadata queries can be parsed, executed, evaluated, and explained.
- Reports clearly separate synthetic metadata evidence from benchmark claims.
