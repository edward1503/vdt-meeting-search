# Sprint 4 Metadata Demo Report

## Summary

This report closes `US-S4-007`: synthetic HotpotQA author/date metadata now has a separate demo evidence artifact and report. The goal is narrow and product-facing: show how metadata filters reduce the candidate space for search/debug demos without treating synthetic metadata as real HotpotQA truth or as a BEIR benchmark claim.

The metadata fields are synthetic only:

- `author`
- `created_at`
- `modified_at`

The full metadata artifact covers 5,233,329 HotpotQA documents. The manifest marks it as synthetic and states that dense `embedding_text` remains content-only.

## Evidence Artifacts

| Artifact | Path |
| --- | --- |
| Full metadata manifest | `artifacts/hotpotqa_full/metadata/manifest.json` |
| Metadata demo scenario summary | `evaluation/results/hotpotqa_full/metadata/scenario_summary.json` |
| Metadata retrieval story proof | `docs/stories/epics/E04-sprint4-evaluation-expansion/US-S4-006-metadata-aware-retrieval-path.md` |

Scenario artifact command:

```powershell
python scripts/metadata_demo_scenarios.py --metadata-dir artifacts/hotpotqa_full/metadata --output evaluation/results/hotpotqa_full/metadata/scenario_summary.json
```

Unit proof for the scenario artifact builder:

```powershell
python -m pytest tests/test_metadata_demo_scenarios.py -q
```

Result: 2 passed.

## Dataset And Metadata Scope

| Field | Value |
| --- | ---: |
| Documents counted | 5,233,329 |
| Metadata shard files | 105 |
| Synthetic authors | 128 |
| Modified documents | 1,831,684 |
| Unchanged documents | 3,401,645 |
| Created date range | 2024-01-01 to 2025-12-30 |
| Modified date range | 2024-01-01 to 2026-02-12 |

Metadata is deterministic from document identity. It is useful for demo filtering and result display, but it is not an attribute of the original HotpotQA corpus.

## Scenario Results

The table reports candidate-space narrowing from the full 5,233,329-document corpus. The artifact builder performs an offline one-pass count over the metadata shards; this is not an online search SLA. Online filtered-search behavior is covered by `US-S4-006`, where Elasticsearch indexed metadata fields, API payloads returned metadata, and `tv_hybrid` with metadata filters routed through the BM25-prefiltered path.

| Scenario | Mode | Effective method | Filters | Matching docs | Narrowing |
| --- | --- | --- | --- | ---: | ---: |
| `content_only_anarchism` | content-only | `es_bm25` | none | 5,233,329 | 0.0000% |
| `author_nguyen_an` | metadata-filtered | `es_bm25` | `author=Nguyen An` | 40,886 | 99.2187% |
| `created_january_2024` | metadata-filtered | `es_bm25` | `created_at=2024-01-01..2024-01-31` | 222,239 | 95.7534% |
| `modified_mid_january_2024` | metadata-filtered | `es_bm25` | `modified_at=2024-01-10..2024-01-20` | 60,589 | 98.8422% |
| `hybrid_author_created_january` | metadata + content hybrid | `tv_filtered_hybrid` | `author=Nguyen An`, `created_at=2024-01-01..2024-01-31` | 1,793 | 99.9657% |

The full one-pass scenario count took 94,131.8344 ms on this local workspace while parsing all 5.23M JSONL rows. Because all five scenarios were counted in the same pass, the same offline count duration is recorded for each scenario in the artifact.

## Result Examples

| Scenario | Example document | Metadata |
| --- | --- | --- |
| content-only | `doc_id=12`, `title=Anarchism` | `author=Nguyen An`, `created_at=2024-01-01`, `modified_at=2024-01-02` |
| author filter | `doc_id=844`, `title=Amsterdam` | `author=Nguyen An`, `created_at=2024-05-08`, `modified_at=2024-05-10` |
| created-date filter | `doc_id=25`, `title=Autism` | `author=Nguyen Binh`, `created_at=2024-01-02`, `modified_at=2024-01-03` |
| modified-date filter | `doc_id=309`, `title=An American in Paris` | `author=Nguyen Huy`, `created_at=2024-01-09`, `modified_at=2024-01-10` |
| metadata + content hybrid | `doc_id=6780`, `title=CD-R` | `author=Nguyen An`, `created_at=2024-01-25`, `modified_at=2024-01-25` |

## Retrieval Behavior Notes

- `es_bm25` applies metadata filters in Elasticsearch filter context.
- `tv_hybrid` with metadata filters routes to `tv_filtered_hybrid`, using BM25 as the metadata-aware hard prefilter before TurboVec reranking.
- `tv_dense` rejects metadata filters because dense-only search cannot enforce author/date constraints in this v1 path.
- Dense embedding input remains content-only; synthetic metadata is not appended to embeddings.
- Dashboard controls were intentionally out of the Sprint 4 MVP; API/backend evidence is the active proof.

## Interpretation

The demo evidence shows that even simple synthetic fields can make result sets much more inspectable. An author filter narrows the full corpus by about 99.22%, a January 2024 created-date filter narrows it by about 95.75%, and combining author plus date narrows it by about 99.97% before content ranking.

This should be presented as a metadata-filter demo only. It should not be used to claim HotpotQA benchmark quality, BEIR comparability, real document authorship, or production meeting-search metadata validity.

## Follow-Up

The next natural step is to expose these filters through the dataset-first API/UI refactor from `US-S4-011`, after HotpotQA and VimQA are represented as dataset workspaces.
