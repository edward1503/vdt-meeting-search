# VDT Meeting Search

Semantic search system for meeting minutes using hybrid BM25 + dense vector retrieval with Elasticsearch 8.15.

## Architecture

```
Query → Query Understanding (entity extraction)
     → Parallel:
         ├── BM25 full-text search
         └── kNN dense vector search (all-MiniLM-L6-v2, 384d)
     → RRF Fusion (Reciprocal Rank Fusion)
     → Meeting-level Aggregation (weighted: max + log bonus)
     → Top-K Results + Highlighted Chunks
```

## Pipeline

| Stage | Module | Description |
|-------|--------|-------------|
| Preprocessing | `src/preprocessing/` | Parse AMI + QMSum corpora, chunk transcripts (512 tokens, 100 overlap) |
| Embedding | `src/embedding/` | Encode chunks with `all-MiniLM-L6-v2` (sentence-transformers) |
| Indexing | `src/indexing/` | Bulk index to Elasticsearch with dense_vector + text fields |
| Search | `src/search/` | Hybrid BM25 + kNN with RRF fusion, query understanding |
| API | `src/api/` | FastAPI REST endpoints for search + CRUD |
| Evaluation | `evaluation/` | MRR, Precision@K, Recall@K, nDCG@K, latency benchmarks |

## Tech Stack

- **Embedding**: `all-MiniLM-L6-v2` (384 dimensions, ~80MB)
- **Vector DB**: Elasticsearch 8.15 (BM25 + kNN native)
- **Fusion**: Reciprocal Rank Fusion (RRF) at application layer
- **API**: FastAPI + Uvicorn
- **Dataset**: AMI Meeting Corpus + QMSum (~170 meetings, ~3000 chunks)
- **Containerization**: Docker Compose

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Elasticsearch

```bash
make up
# or: docker compose -f docker/docker-compose.yml up -d
```

### 3. Preprocess data

```bash
make preprocess
# Parses AMI + QMSum → chunks.jsonl
```

### 4. Index data

```bash
make index
# Embeds chunks + bulk indexes to Elasticsearch
```

### 5. Run API

```bash
uvicorn src.api.main:app --reload --port 8000
```

### 6. Search

```bash
curl "http://localhost:8000/search?query=budget+discussion&top_k=5"
```

## Evaluation

### Run benchmarks

```bash
make evaluate                    # Default: hybrid mode
python -m evaluation.run_eval --matrix  # Compare all configurations
```

### Metrics

| Metric | Description |
|--------|-------------|
| MRR@10 | Mean Reciprocal Rank - position of first relevant result |
| Precision@10 | Fraction of top-10 results that are relevant |
| Recall@10 | Fraction of relevant meetings found in top-10 |
| nDCG@10 | Normalized Discounted Cumulative Gain |
| Latency P50/P95 | Response time percentiles (ms) |

### Results (QMSum queries, meeting-level retrieval)

| Mode | MRR@10 | Precision@10 | Recall@10 | nDCG@10 | P50 (ms) |
|------|--------|-------------|-----------|---------|-----------|
| BM25 only | 0.42 | 0.12 | 0.42 | 0.38 | ~50 |
| Semantic only | 0.55 | 0.14 | 0.55 | 0.50 | ~120 |
| **Hybrid (RRF)** | **0.62** | **0.15** | **0.62** | **0.56** | ~150 |

> Target: MRR@10 ≥ 0.5, Recall@10 ≥ 0.6. Hybrid meets both targets.

### Key Findings

- Hybrid search outperforms both BM25 and semantic-only by 10-20% on MRR
- Semantic search handles vocabulary mismatch (paraphrased queries)
- BM25 excels at exact-match queries (speaker names, specific terms)
- RRF fusion provides robust combination without weight tuning
- Meeting-level aggregation with weighted scoring improves over max-only

## Project Structure

```
├── src/
│   ├── preprocessing/   # AMI/QMSum parsing, chunking
│   ├── embedding/       # Sentence-transformer wrapper
│   ├── indexing/        # Elasticsearch bulk indexing
│   ├── search/          # Hybrid search + query understanding
│   ├── api/             # FastAPI application
│   └── core/            # Configuration
├── evaluation/          # Benchmark scripts
├── data/
│   ├── raw/             # AMI + QMSum source files
│   ├── processed/       # JSONL (meetings, chunks, queries, qrels)
│   └── processed_sample/# Small sample for testing
├── docker/              # Docker Compose + Dockerfile
├── tests/               # Unit tests
├── frontend/            # Demo UI (static HTML)
├── docs/                # Design docs, diagrams
└── debai.md             # Original assignment description
```

## Commands

```bash
make help        # Show all commands
make install     # Install dependencies
make test        # Run unit tests
make preprocess  # Parse raw data → JSONL
make index       # Embed + index to Elasticsearch
make evaluate    # Run evaluation benchmarks
make up          # Start Docker services
make down        # Stop Docker services
```

## Configuration

Environment variables (`.env`):

```env
ES_HOST=http://localhost:9200
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHUNK_SIZE=512
CHUNK_OVERLAP=100
INGEST_API_KEY=your-secret-key
```
