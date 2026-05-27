# Research — Semantic Search for Meeting Minutes

## 1. Semantic Search & Dense Retrieval

**Sparse Retrieval (BM25):** Tìm kiếm dựa trên term frequency — tốt cho exact match, tên riêng, mã số.

**Dense Retrieval (Bi-encoder):** Encode query và document thành vectors, tìm nearest neighbors — tốt cho semantic similarity, paraphrase, intent matching.

**Hybrid:** Kết hợp cả hai qua Reciprocal Rank Fusion (RRF) — cho recall cao hơn 15-30% so với dùng riêng lẻ.

**Retrieve & Re-rank Pipeline (2-stage):**

```
Stage 1: Retrieval (fast, broad)
  - BM25 → top 100 keyword matches
  - kNN → top 100 semantic matches
  - RRF fusion → top 50 combined

Stage 2: Re-ranking (slow, precise)
  - Cross-encoder scores (query, doc) pairs
  - Re-sort top 50 → final top 10
```

## 2. Embedding Models

| Model | Type | Dim | Speed | Accuracy | Use case |
|-------|------|-----|-------|----------|----------|
| **all-MiniLM-L6-v2** | Bi-encoder (sentence) | 384 | ~5ms/text CPU | Good | Production, low resource |
| all-mpnet-base-v2 | Bi-encoder (sentence) | 768 | ~12ms/text | Better | Higher accuracy needs |
| intfloat/e5-large-v2 | Bi-encoder (asymmetric) | 1024 | ~25ms/text | Best | SOTA retrieval |
| ColBERT | Late interaction (contextual) | 128/token | Slower index | Excellent | Fine-grained matching |

**Chosen: `all-MiniLM-L6-v2`** — runs well on CPU, 384-dim saves storage, sufficient for benchmarking.

**Sentence Embedding vs Contextual Embedding:**

- **Sentence embedding (Bi-encoder):** Encode full text into 1 vector. Fast, scalable, but loses fine-grained token interactions.
- **Contextual embedding (ColBERT/Late interaction):** 1 vector per token, relevance via MaxSim. More accurate but 100x storage.
- **Decision:** Sentence embedding (bi-encoder) for retrieval + cross-encoder for reranking = best balance.

## 3. Embedding Input Strategy

**Decision: (A) Raw chunk text only — no metadata prefix.**

We considered:
- **(A) Raw text only:** Embed the chunk content as-is.
- **(B) Metadata-enriched:** Prepend structured metadata (e.g., `"Speakers: X, Y | {text}"`) before encoding.

Rationale for choosing (A):

1. **Separation of concerns in hybrid architecture.** Our system handles metadata through dedicated mechanisms: ES structured fields for filtering (speaker, date, meeting_id) and BM25 for keyword matching. The dense vector's role is purely semantic similarity on *content meaning*. Mixing responsibilities into a single 384-dim vector creates coupling that is harder to evaluate and debug.

2. **Embedding capacity constraint.** At 384 dimensions, the vector space has limited capacity. Metadata tokens like speaker IDs (e.g., "MEO069") carry no semantic meaning — they consume model attention and embedding capacity without contributing to content similarity. This dilutes the signal for queries that require semantic understanding (e.g., "discussions about budget constraints").

3. **Evaluation isolation.** The project requires evaluating content search and metadata search independently. Embedding raw text keeps the semantic retrieval channel pure, allowing clean ablation studies: BM25-only vs kNN-only vs hybrid.

4. **RRF handles the fusion.** Reciprocal Rank Fusion merges results from BM25 (captures metadata matches) and kNN (semantic content) without requiring either to be aware of the other. This is the designed integration point — not the embedding itself.

## 4. Hybrid Search Architecture (Elasticsearch 8.x)

```
┌─────────────────────────────────────────────────────────┐
│                    User Query (prompt)                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Embedding Service (FastAPI)                  │
│         sentence-transformers: all-MiniLM-L6-v2          │
└─────────────────────┬───────────────────────────────────┘
                      │ query vector (384-dim)
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Elasticsearch 8.x                            │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  BM25 Search │  │  kNN Search  │  │Metadata Filter│  │
│  │  (inverted   │  │  (HNSW index │  │  (structured  │  │
│  │   index)     │  │   dense_vec) │  │   fields)     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │          │
│         └──────────┬───────┘──────────────────┘          │
│                    │                                     │
│         ┌──────────▼──────────┐                          │
│         │   RRF (k=60)        │                          │
│         │   Rank Fusion       │                          │
│         └──────────┬──────────┘                          │
│                    │                                     │
└────────────────────┼────────────────────────────────────┘
                     │ top-50 candidates
                     ▼
┌─────────────────────────────────────────────────────────┐
│           Cross-Encoder Re-ranker                        │
│     cross-encoder/ms-marco-MiniLM-L6-v2                  │
│     Score each (query, passage) pair                     │
└─────────────────────┬───────────────────────────────────┘
                      │ top-10 ranked results
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Response (ranked meetings + highlights)      │
└─────────────────────────────────────────────────────────┘
```

**RRF Formula:** `score = Σ 1/(k + rank_i)` where k=60 (standard).

## 5. Reranking Strategy

Reranking is the second stage that refines the top-N candidates from hybrid retrieval by scoring each (query, document) pair with full cross-attention.

| Model | Params | Latency (50 docs, CPU) | BEIR NDCG@10 | Notes |
|-------|--------|----------------------|-------------|-------|
| ms-marco-MiniLM-L6-v2 | 22M | ~200-400ms | ~52 | Baseline cross-encoder |
| FlashRank (ONNX MiniLM) | 22M | ~36ms | ~52 | Same model, ONNX optimized, 5-10x faster |
| BGE-reranker-v2-m3 | 568M | ~800-1200ms | ~57 | High accuracy, too slow on CPU |
| Jina-reranker-v2 | 137M | ~150-300ms | ~58 | Best accuracy/speed ratio |
| Jina-reranker-v3 | ~400M | ~400-600ms | 61.94 | SOTA but heavier |
| LLM-based (listwise) | >1B | ~2-5s | Highest | Impractical for <500ms budget |

**Decision: Configurable multi-tier approach.** The system supports multiple reranking backends selectable via API parameter. This enables:
- Fair benchmarking across methods in evaluation (Task 9)
- Latency/quality tradeoff at query time
- All options remain within <500ms total latency budget

Candidate configurations for experiments:
- `rerank=none` — RRF scores only (~20ms total)
- `rerank=flash` — FlashRank ONNX (~56ms total)
- `rerank=cross-encoder` — ms-marco-MiniLM-L6-v2 (~300ms total)
- `rerank=jina` — Jina-reranker-v2 (~250ms total)

Final model selection will be determined by Task 9 experiment results on our meeting corpus.

## 6. Data & Chunking Strategy

**Datasets:**
- AMI (`edinburghcstr/ami`, config `ihm`): 137 meetings, ~109K utterances, fields: `meeting_id`, `text`, `speaker_id`, `begin_time`, `end_time`
- ICSI (`StDestiny/icsi_cleaned`): 59 meetings, fields: `src` (dialogue), `tgt` (summary)
- QMSum (`pszemraj/qmsum-cleaned`): 232 meetings, 1,808 query-summary pairs, fields: `input` (query + dialogue), `output` (summary)

**Chunking Strategy: Speaker-turn grouping with sliding window fallback (Method B)**

We evaluated two approaches:

| Criteria | A: Fixed sliding window | B: Speaker-turn + fallback |
|----------|------------------------|---------------------------|
| Semantic coherence | ❌ Cuts mid-sentence/speaker | ✅ Preserves speaker boundaries |
| Speaker attribution | ❌ Mixed speakers per chunk | ✅ Clear speaker metadata |
| Supports "who said X" queries | ❌ No | ✅ Yes |
| Chunk size consistency | ✅ Uniform 512 tokens | ⚠️ Variable, needs min/max bounds |
| Implementation complexity | ✅ Simple | ⚠️ Moderate |
| Embedding quality | ⚠️ Random boundaries dilute signal | ✅ Natural semantic units |

**Why Method B:** Meeting transcripts are dialogue — speaker changes often correlate with topic shifts. Fixed-size chunking blindly cuts across these boundaries, producing chunks with mixed speakers and split sentences. This hurts both retrieval precision (diluted semantic signal) and the highlight feature (can't attribute text to speakers). Method B preserves natural conversation units while maintaining chunk sizes suitable for embedding models.

**Algorithm:**
1. Merge consecutive utterances from same speaker into one block
2. If merged block < 200 tokens → merge with next speaker block (retain both speaker IDs)
3. If merged block > 512 tokens → apply sliding window (512 tokens, 100 token overlap)
4. Each chunk stores: `meeting_id`, `speakers[]`, `time_start`, `time_end`, `text`

**Indexing: Single-level with meeting grouping**
- Index chunks (passage-level) with meeting metadata as fields on each chunk
- Group results by `meeting_id` in response to show per-meeting results
- Simpler than two-level, and passage-level is needed for highlighting anyway

## 7. Vector Database Selection

**Decision: Elasticsearch 8.x** over FAISS and Milvus.

| Capability | Elasticsearch 8.x | FAISS | Milvus |
|-----------|-------------------|-------|--------|
| Vector kNN search | ✅ | ✅ (fastest) | ✅ |
| BM25 keyword search | ✅ (best-in-class) | ❌ | ⚠️ basic |
| Metadata filtering | ✅ native | ❌ must build separately | ✅ |
| RRF fusion | ✅ built-in, single query | ❌ | ✅ |
| Highlight matching text | ✅ native | ❌ | ❌ |
| Near real-time indexing | ✅ (~1s) | ❌ (rebuild index) | ✅ |
| Deployment complexity | 1 container | Library only | 3+ containers |

Rationale: Project requires hybrid search (BM25 + vector + metadata) in one query. Dataset is small (~23K vectors, ~35MB). ES handles this trivially while providing all features natively. FAISS/Milvus would require building BM25, metadata filtering, and highlighting separately.

## 8. TurboVec (TurboQuant, ICLR 2026) — Experimental Comparison

TurboVec is included as an experimental comparison in Task 9, not as the primary search backend.

**Why not primary:** TurboVec only does vector search — no BM25, no metadata filtering, no highlighting. At 23K vectors, compression/speed gains are irrelevant (brute-force is <1ms). At d=384, TurboQuant's theoretical guarantees are weaker (low-dim regime).

**Why include as experiment:** Academic novelty (ICLR 2026), empirical data at d=384 where few benchmarks exist, demonstrates knowledge of cutting-edge algorithms.

## 9. Evaluation Framework

*(To be discussed and finalized)*
