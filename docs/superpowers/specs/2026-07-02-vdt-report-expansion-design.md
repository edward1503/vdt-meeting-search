# VDT Report Expansion Design

Date: 2026-07-02

## Goal

Expand `submission/bao-cao-vdt-2026.docx` by editing its Markdown source
`submission/bao-cao-vdt-2026.md` and regenerating the DOCX. The expanded report
must better reflect the desired project result: a full-corpus HotpotQA retrieval
workspace centered on hybrid retrieval and bridge-aware multi-hop retrieval,
with enough pipeline, architecture, ablation, benchmark, paper comparison, and
reference detail to support technical review.

## Scope

Keep the VDT report's existing six-section shape:

1. Gioi thieu chung
2. Noi dung va phuong phap
3. Ket qua thuc hien
4. Danh gia hieu qua
5. Ket luan
6. Tai lieu tham khao

The report may become longer, but it should still read as one coherent
submission report, not as a raw dump of sprint notes.

## Required Content Changes

### Pipeline And Architecture

Add a clearer offline/online pipeline description:

- Offline ingest: load BEIR HotpotQA, normalize documents, assign stable
  `numeric_id`, write staging shards, build Elasticsearch BM25 index, generate
  BGE embeddings, build the TurboVec 4-bit `.tvim` index, and validate counts.
- Online retrieval: parse optional metadata, run BM25 and/or TurboVec dense
  retrieval, hydrate dense hits through Elasticsearch by `numeric_id`, fuse
  rankings with RRF, optionally run bridge-aware second-hop retrieval, then
  return API/UI results with support overlay and highlighting.

Describe core components:

- Elasticsearch: BM25 lexical retrieval, structured filters, document store,
  and hydration layer.
- TurboVec: compressed dense vector search over the full HotpotQA corpus.
- Host embedding service: BGE-small query embeddings for HotpotQA.
- FastAPI/React: dataset-first search, query browser, benchmarks, metadata,
  history, and inspection UI.
- Redis/SQLite: cache and local search history.

### TurboVec Versus Elasticsearch

Add a dedicated explanation that avoids an overbroad claim:

- TurboVec is not "better than Elasticsearch" in general.
- Elasticsearch remains the right tool for BM25, filtering, document storage,
  and result hydration.
- TurboVec is the better fit for this project's local full-corpus dense
  retrieval path because Elasticsearch `dense_vector`/HNSW on 5.23M documents
  has high memory and index overhead risk on the target laptop environment.
- TurboVec provides a compact 4-bit dense index artifact
  (`hotpotqa_bge_small_4bit.tvim`, about 1.07 GB) with stable `numeric_id`
  joins back to Elasticsearch.
- The quality argument should be benchmark-based: BM25 alone reaches
  `full_support@10=36.50%` on the 200-query pilot, while one-shot hybrid
  BM25 + TurboVec reaches `54.50%`. TurboVec contributes the semantic half of
  the hybrid system; Elasticsearch remains essential for the lexical and
  document-store half.

### Main Methods

Make the main narrative focus on two methods:

- `tv_hybrid`: BM25 + TurboVec dense retrieval fused by Reciprocal Rank Fusion.
  This is the practical baseline and interactive default.
- `tv_bridge_title_entities_rrf`: bridge-aware retrieval that starts with
  `tv_hybrid`, builds second-hop bridge queries from first-hop title/entity
  signals, and improves complete evidence coverage for HotpotQA.

Other methods should appear as ablations rather than as equal headline methods:
`es_bm25`, `tv_dense`, `tv_filtered_hybrid`, `es_bm25_title`,
`tv_hybrid_rerank`, `tv_two_hop_bridge_rrf`, and bridge tuning variants.

### Full-Test Results

Retain the full `beir/hotpotqa/test` result with 7,405 queries and present both
absolute and percentage differences:

- `tv_hybrid`: `full_support@10=51.75%`, `recall@10=73.05%`,
  `MRR@10=84.13%`, `nDCG@10=70.01%`, p95 `0.76s`.
- `tv_bridge_title_entities_rrf`: `full_support@10=60.08%`,
  `recall@10=75.85%`, `MRR@10=82.51%`, `nDCG@10=71.20%`, p95 `1.60s`.
- Delta: `full_support@10 +8.33 percentage points` and about `+16.1%`
  relative; `recall@10 +2.80 points` and about `+3.8%` relative;
  `nDCG@10 +1.19 points` and about `+1.7%` relative; p95 latency about
  `+110.1%` relative.

### 200-Query Ablation Section

Add a separate ablation section based on the 200-query HotpotQA dev/qrels runs.
It should include all important ablations, grouped for readability:

- Retrieval ladder: `es_bm25`, `tv_dense` if available in the artifact,
  `tv_filtered_hybrid`, `tv_hybrid`.
- Title-aware BM25: `es_bm25` versus `es_bm25_title`.
- Reranker ablation: `tv_hybrid` versus `tv_hybrid_rerank`; explain that
  reranking did not create a net win because the bottleneck was candidate
  generation.
- Bridge ablation: `tv_hybrid`, `tv_two_hop_bridge_rrf`, and
  `tv_bridge_title_entities_rrf`.
- Bridge tuning grid: `beam1_terms6`, `beam2_terms4`, `beam2_terms6`,
  `beam2_terms8`, and `beam3_terms8`.
- Paraphrase/robustness and metadata/VimQA results may be summarized briefly
  if space allows, but the core ablation section should stay centered on the
  200-query HotpotQA retrieval comparison.

Every table should state whether it is a 200-query dev pilot or a 7,405-query
full test, so the reader does not confuse pilot ablations with paper-style full
test results.

### Paper And Benchmark Comparison

Add a compact comparison section:

- Direct-ish BEIR/Pyserini comparison by `nDCG@10`, with caveats about
  implementation differences.
- HotpotQA original paper: compare task motivation, not metrics, because it
  reports answer/supporting-fact/joint QA metrics rather than pure retrieval
  evidence coverage.
- MDR: compare the goal of retrieving complete multi-hop evidence chains, but
  caveat dataset/process differences.
- Beam Retrieval: compare the idea of beam/sequence evidence retrieval, but
  caveat candidate-set versus full-corpus retrieval.
- IRCoT: compare iterative retrieval motivation, but caveat LLM reasoning loop
  versus this project's heuristic bridge state.

Use cautious wording. Do not claim the system beats HotpotQA QA papers.

### References

Replace placeholder references with concrete references, including at least:

- HotpotQA paper and/or homepage.
- BEIR paper.
- Pyserini BEIR regression table.
- Reciprocal Rank Fusion paper.
- BGE embedding model reference or model page.
- Elasticsearch documentation.
- TurboVec project or local artifact/decision reference.
- MDR paper/repository.
- Beam Retrieval paper.
- IRCoT paper.
- Project sprint reports and benchmark artifacts.

## Source Files And Artifacts

Primary files to edit/regenerate:

- `submission/bao-cao-vdt-2026.md`
- `submission/bao-cao-vdt-2026.docx`
- `submission/bao-cao-vdt-2026-theo-mau.docx`

Likely supporting sources:

- `submission/generate_vdt_report.py`
- `docs/sprint5/hotpotqa-test-benchmark-paper-comparison.md`
- `docs/sprint5/hotpotqa-retrieval-results-summary.md`
- `docs/sprint5/bridge-aware-second-support-report.md`
- `docs/sprint5/bridge-aware-tuning-report.md`
- `docs/sprint5/reranker-rrf-ablation-report.md`
- `docs/sprint5/title-aware-bm25-ablation-report.md`
- `docs/sprint3/full-corpus-retrieval-pipeline-vi.md`
- `docs/decisions/0006-sprint3-dense-backend.md`
- `evaluation/results/hotpotqa_full/**`

## Validation

After implementation:

- Run `python submission/generate_vdt_report.py`.
- Run `python -m pytest tests/test_generate_vdt_report.py -q`.
- Use `python-docx` or the existing test pattern to confirm the regenerated
  DOCX contains the new tables and key method names:
  `tv_hybrid`, `tv_bridge_title_entities_rrf`, `TurboVec`, `Elasticsearch`,
  and at least one paper-comparison/reference section.
- If the DOCX is locked by Word, ask the user to close it and rerun generation.

## Non-Goals

- Do not rerun expensive HotpotQA benchmarks unless an existing artifact is
  missing.
- Do not change retrieval code, API behavior, or frontend behavior.
- Do not claim production latency or paper leaderboard ranking.
- Do not compare `full_support@10` directly to answer EM/F1 or supporting-fact
  F1.
