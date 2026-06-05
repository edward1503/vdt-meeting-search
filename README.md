# VDT Meeting Search

Minimal FAISS-based semantic search MVP for meeting minutes. The first target is an end-to-end path over AMI Meeting Corpus transcripts: parse raw meetings, chunk transcripts, embed chunks, search with FAISS, expose a FastAPI endpoint, and show results in a small UI.

## Data

Raw data belongs in `data/raw`. For AMI, place the extracted corpus so one of these paths exists:

```text
data/raw/corpusResources/meetings.xml
data/raw/<ami-folder>/corpusResources/meetings.xml
```

The parser expects AMI `words/`, `segments/`, and `corpusResources/meetings.xml`. A tiny `data/raw/sample_meetings.json` is included so the pipeline can be smoke-tested before the full AMI download is added.

## Quick Start

```bash
pip install -r requirements.txt
python -m src.indexing.build_faiss
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The Nexus Intelligence UI is a Vite app under `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

Then open `http://127.0.0.1:5173`. The UI calls the FastAPI backend at `http://127.0.0.1:8000`.

For a dependency-light smoke test that avoids downloading a transformer model:

```bash
python -m src.indexing.build_faiss --model hashing
python -m evaluation.run_eval --top-k 5
```

## API

```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"meetings about battery life","top_k":5}'
```

## Evaluation

```bash
python -m evaluation.run_eval --top-k 5
python -m evaluation.run_eval --qrels data/eval/ami_qrels.json --top-k 5
```

## Sprint 2 Retrieval Benchmark

Sprint 2 keeps the Sprint 1 parser, chunking, embedding model, and qrels fixed, then compares three retrieval backends over the same chunk vectors:

```bash
python -m evaluation.benchmark_retrieval --model hashing --rebuild-shared --qrels data/eval/sample_qrels.json --top-k 5
python -m evaluation.benchmark_retrieval --qrels data/eval/ami_qrels.json --top-k 5
```

The benchmark tries `faiss`, `elasticsearch`, and `turbovec` by default. FAISS and TurboVec run locally. Elasticsearch requires a reachable server at `ELASTICSEARCH_URL` / `http://localhost:9200`; if it is unavailable, the benchmark records that backend as skipped instead of failing the whole run.

The API can also target a backend after the corresponding index has been built:

```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"meetings about battery life","top_k":5,"backend":"turbovec"}'
```

The sample qrels are only a smoke test. Once AMI raw data is added, replace `data/eval/sample_qrels.json` with AMI-derived queries and relevant meeting ids.

Current AMI MVP stats after indexing `ami_public_manual_1.6.2`:

```text
meetings: 171
chunks: 5347
embedding dim: 384
index backend: faiss
```

Initial AMI judged-set results over `data/eval/ami_qrels.json`:

```text
queries: 10
precision@5: 0.60
recall@5: 1.00
mrr@5: 1.00
```

The AMI qrels are an initial MVP evaluation set created from inspected top snippets. Expand this set before treating the numbers as final benchmark results.
