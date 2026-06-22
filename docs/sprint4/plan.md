# Sprint 4 Plan: Retrieval Quality, Robustness, Metadata Search, and VimQA

## Status

Finalized execution plan for completion by Sunday, 2026-06-21. This replaces
the earlier brainstorm with four required workstreams, explicit MVP outputs,
and a fixed priority order. Redis cache hardening is intentionally out of scope
for Sprint 4.

## Harness Classification

- Type: new initiative
- Initiative lane: high-risk
- Story lane default: normal
- Intake: #39 and #40
- Reason: Sprint 4 touches benchmark validity, qrels preservation, retrieval
  ranking behavior, metadata indexing/filtering, and a new VimQA evaluation
  pipeline.

## Goal

By Sunday, Sprint 4 must produce runnable evidence for four tasks:

1. Test HotpotQA paraphrase robustness.
2. Improve iterative retrieval with evidence-chain metrics and Bridge-RRF.
3. Add lightweight synthetic metadata and searchable filters.
4. Build a minimal VimQA retrieval pipeline.

## Priority Order

1. Retrieval improvement: directly targets result quality.
2. Paraphrase robustness: proves whether retrieval survives rewritten queries.
3. Synthetic metadata search: supports the meeting-search demo path.
4. VimQA pipeline: opens Vietnamese retrieval evaluation, with MVP scope only.

## Workstream 1: Paraphrase Robustness Test

### Scope

- Export 200 `beir/hotpotqa/dev` source queries for paraphrase generation.
- Preserve qrels through `source_query_id`.
- Support two paraphrase profiles: `natural_mild` and `natural_strong`.
- Validate returned paraphrases before benchmarking.
- Benchmark original vs paraphrased queries.

### Required Export Fields

```text
source_query_id
original_query
support_doc_ids
qrels
paraphrase_profile
constraints
```

### Validation Rules

- Reject empty paraphrases.
- Reject duplicate variants for the same source/profile.
- Reject rows without qrels linkage.
- Check named entities, numbers, and dates for obvious drift.
- Count accepted and rejected paraphrases separately with reasons.

### Methods To Compare

```text
es_bm25
tv_dense
tv_hybrid
tv_two_hop_bridge_rrf, if Workstream 2 lands first
```

### Outputs

```text
docs/sprint4/paraphrase-protocol.md
docs/sprint4/paraphrase-robustness-report.md
artifacts/hotpotqa_full/paraphrase/
evaluation/results/hotpotqa_full/paraphrase/
evaluation/runs/hotpotqa_full/paraphrase/
```

### MVP Cut

If runtime or paraphrase generation is blocked, complete the validator and a
50-query smoke run first, then extend to the 200-query pilot.

## Workstream 2: Iterative Retrieval Improvement

### Scope

- Add evidence-chain metrics before claiming quality improvement.
- Audit existing Elasticsearch iterative methods.
- Implement a TurboVec-backed two-hop method named `tv_two_hop_bridge_rrf`.
- Add lightweight chain reranking.
- Report quality/latency tradeoffs against `tv_hybrid`.

### Metrics

```text
full_support_recall@2
full_support_recall@5
full_support_recall@10
chain_recall@1
chain_recall@5
chain_mrr
latency_p95_ms
qps
```

### Existing Baselines To Audit

```text
es_bm25
tv_dense
tv_hybrid
tv_filtered_hybrid
es_iterative_hybrid
es_iterative_title
es_iterative_sentence
es_iterative_fast
```

### New Method

```text
question
  -> tv_hybrid hop 1
  -> top beam p1
  -> q2 = question + title(p1) + bridge terms
  -> tv_hybrid hop 2
  -> candidate chains (p1, p2)
  -> lightweight chain reranking
  -> ranked chains + flattened ranked documents
```

### Hyperparameters

```text
hop1_top_k
hop2_top_k
beam_size
max_bridge_terms
candidate_k
rrf_k
```

### Success Rule

Treat the new method as successful if it improves `full_support_recall@10` by
at least `+0.05` over `tv_hybrid` on the Sprint 4 pilot while keeping p95
latency within `2.5x` of `tv_hybrid`. If quality improves but latency exceeds
that threshold, report it as a quality-first experimental method and do not
change the dashboard default.

### Outputs

```text
docs/sprint4/retrieval-improvement-report.md
evaluation/results/hotpotqa_full/bridge_rrf/
evaluation/runs/hotpotqa_full/bridge_rrf/
```

## Workstream 3: Synthetic Metadata Search

### Scope

Generate and search only three lightweight synthetic metadata fields:

```text
author
created_at
modified_at
```

### Rules

- Generate deterministic values from `doc_id` or `numeric_id`.
- Keep HotpotQA `title`, `text`, `content`, `doc_id`, and `numeric_id`
  unchanged.
- Index `author` as keyword and `created_at`/`modified_at` as dates.
- Support filters for `author`, `created_at` range, and `modified_at` range.
- Return the metadata in API/search result payloads.
- Do not append synthetic metadata into dense embedding text in v1.
- Clearly label metadata as synthetic in artifacts and reports.

### Outputs

```text
artifacts/hotpotqa_full/metadata/
evaluation/results/hotpotqa_full/metadata/
docs/sprint4/metadata-demo-report.md
```

### MVP Cut

API and benchmark-filtered search come first. Dashboard controls are optional
unless the API/filter path is already complete.

## Workstream 4: VimQA Retrieval Pipeline

### Scope

Build a minimal retrieval pipeline over local VimQA JSON files. Sprint 4 should
produce a runnable evaluation artifact, not only a design note.

### Pipeline

```text
load train_vimqa.json + test_vimqa.json
  -> deduplicate contexts
  -> corpus = unique contexts
  -> queries = questions
  -> qrels = question_id -> context_doc_id
  -> run retrieval
  -> report metrics
```

### Metrics

```text
recall@1
recall@5
recall@10
mrr@10
ndcg@10
latency
```

### Model And Index Direction

```text
primary model = paraphrase-multilingual-MiniLM-L12-v2
secondary model = BAAI/bge-m3, optional
index alias = vimqa_all_current
```

### Required Caveats

- VimQA is a QA dataset, not a native BEIR retrieval benchmark.
- Unioning train/test contexts can create leakage for benchmark claims.
- Sprint 4 results are pipeline-readiness evidence, not paper-comparable
  retrieval claims.

### Outputs

```text
docs/sprint4/vimqa-benchmark-design.md
docs/sprint4/vimqa-pipeline-report.md
evaluation/results/vimqa/
evaluation/runs/vimqa/
```

### MVP Cut

If Elasticsearch indexing is too slow, produce a local JSONL/TREC/evaluation
pipeline first and record Elasticsearch indexing as the next step.

## Deadline Schedule

### Thursday, 2026-06-18

- Finalize Sprint 4 docs and Harness records around the four workstreams.
- Start Workstream 2: metrics and iterative baseline audit.
- Begin `tv_two_hop_bridge_rrf` smoke tests.

### Friday, 2026-06-19

- Finish Workstream 2 50-query and 200-query benchmark evidence.
- Start Workstream 1 export and validator.
- Run paraphrase robustness smoke if paraphrase artifacts are available.

### Saturday, 2026-06-20

- Finish Workstream 1 report.
- Build Workstream 3 metadata generator, mapping, and filtered search.
- Run API/search smoke for author/date filters.

### Sunday, 2026-06-21

- Build Workstream 4 minimal VimQA retrieval pipeline.
- Write final Sprint 4 evidence reports.
- Run available verification commands and update Harness story evidence.

## Explicit Non-Goals

- Redis retrieval cache hardening.
- LLM query rewrite.
- Cross-encoder reranking.
- Full MDR training.
- Beam Retrieval training.
- Dashboard metadata UI unless API/filter work is already complete.
- Paper-comparable BEIR claims.
- Production VimQA benchmark claims.
- Replacing `tv_hybrid` default before benchmark evidence supports it.

## Story Mapping

| Workstream | Stories |
| --- | --- |
| Sprint setup | `US-S4-001` |
| Paraphrase robustness | `US-S4-002`, `US-S4-003`, `US-S4-004` |
| Iterative retrieval improvement | `US-S4-009` |
| Synthetic metadata search | `US-S4-005`, `US-S4-006`, `US-S4-007` |
| VimQA pipeline | `US-S4-008` |

## Exit Criteria

Sprint 4 is successful when all four workstreams have at least MVP evidence:

1. Paraphrase export/validation and robustness report exist.
2. Iterative retrieval improvement report compares `tv_two_hop_bridge_rrf`
   against current baselines.
3. Synthetic `author`/`created_at`/`modified_at` metadata can be generated,
   indexed, filtered, and reported.
4. VimQA has a runnable retrieval pipeline report with caveats.
