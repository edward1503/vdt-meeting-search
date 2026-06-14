# Scale 5M HotpotQA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scale the current Elasticsearch retrieval pipeline from nano HotpotQA to full `beir/hotpotqa` with 5,233,329 documents.

**Architecture:** Stage full data as JSONL shards, create a versioned Elasticsearch index, bulk ingest with `_id = doc_id`, validate counts, benchmark by gates, then promote the read alias.

**Tech Stack:** Python, `ir_datasets`, `sentence-transformers`, `BAAI/bge-small-en-v1.5`, Elasticsearch BM25 + dense vector, Docker Compose.

---

## Baseline Context

- Full dataset: `beir/hotpotqa`, expected docs: `5,233,329`.
- Staging script: `scripts/stage_hotpotqa.py`.
- Index/ingest/search script: `scripts/es_hotpotqa.py`.
- Mapping/retriever: `src/retrieval/elasticsearch_retriever.py`.
- Benchmark script: `src/evaluation/benchmark_es.py`.
- Current serving alias: `hotpotqa_docs_current`.

## Capacity Targets

- Raw vectors: `5,233,329 * 384 * 4`, about 7.5 GiB before Elasticsearch vector graph and segment overhead.
- Disk: reserve 80-150 GiB free for full hybrid index and merges.
- RAM: 32 GiB minimum for local full run, 64 GiB+ preferred.
- Elasticsearch ingest settings: `number_of_replicas=0`, `refresh_interval=-1`, restore refresh after full validation.
- Main bottleneck: embedding generation. Prefer GPU or a dedicated embedding service for the full run.

## Rollout Gates

- Gate 1: 100k docs staged, indexed, validated, and benchmarked on 50 queries.
- Gate 2: 1M docs indexed and benchmarked on 200 queries.
- Gate 3: all 5,233,329 docs indexed and exact count validated.
- Gate 4: alias `hotpotqa_docs_current` promoted only after smoke search and benchmark pass.

### Task 1: Preflight Elasticsearch

**Files:**
- Modify: `docker-compose.yml`
- Check: Elasticsearch HTTP API

- [ ] **Step 1: Configure heap**

Set Elasticsearch environment in `docker-compose.yml`:

```yaml
- ES_JAVA_OPTS=-Xms8g -Xmx8g
```

Use `-Xms16g -Xmx16g` on a 64 GiB machine.

- [ ] **Step 2: Start Elasticsearch**

Run:

```powershell
docker compose up -d elasticsearch
```

Expected: Elasticsearch container stays running.

- [ ] **Step 3: Check health and disk**

Run:

```powershell
curl http://localhost:9200/_cluster/health?pretty
curl http://localhost:9200/_nodes/stats/jvm,fs?pretty
```

Expected: cluster is `green` or `yellow`, and disk has at least 80 GiB free.

### Task 2: Stage Full HotpotQA

**Files:**
- Uses: `scripts/stage_hotpotqa.py`
- Creates: `artifacts/hotpotqa_full/staging/manifest.json`
- Creates: `artifacts/hotpotqa_full/staging/docs-*.jsonl`

- [ ] **Step 1: Stage 100k smoke subset**

Run:

```powershell
python scripts/stage_hotpotqa.py --dataset beir/hotpotqa --output-dir artifacts/hotpotqa_100k/staging --docs-per-file 50000 --max-docs 100000
```

Expected: manifest has `docs_written=100000`, `files_written=2`.

- [ ] **Step 2: Stage all documents**

Run:

```powershell
python scripts/stage_hotpotqa.py --dataset beir/hotpotqa --output-dir artifacts/hotpotqa_full/staging --docs-per-file 50000
```

Expected: manifest has `docs_written=5233329`, `files_written=105`.

- [ ] **Step 3: Verify manifest**

Run:

```powershell
Get-Content artifacts/hotpotqa_full/staging/manifest.json
```

Expected: `docs_written` equals `5233329`.

### Task 3: Create Versioned Full Index

**Files:**
- Uses: `scripts/es_hotpotqa.py`
- Uses: `src/retrieval/elasticsearch_retriever.py`

- [ ] **Step 1: Create candidate index**

Run:

```powershell
python scripts/es_hotpotqa.py create-index --index hotpotqa_full_v1 --alias hotpotqa_full_candidate --dims 384 --shards 3 --reset
```

Expected: output reports `index=hotpotqa_full_v1`, `alias=hotpotqa_full_candidate`, `created=true`.

- [ ] **Step 2: Confirm settings and mapping**

Run:

```powershell
curl http://localhost:9200/hotpotqa_full_v1/_settings?pretty
curl http://localhost:9200/hotpotqa_full_v1/_mapping?pretty
```

Expected: `number_of_shards=3`, `number_of_replicas=0`, `refresh_interval=-1`, `embedding.dims=384`.

### Task 4: Ingest By Gates

**Files:**
- Uses: `scripts/es_hotpotqa.py`
- Creates: `artifacts/hotpotqa_full/progress/docs-*.done`

- [ ] **Step 1: Ingest first 100k docs**

Run:

```powershell
python scripts/es_hotpotqa.py ingest --index hotpotqa_full_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress --batch-size 256 --max-files 2
python scripts/es_hotpotqa.py validate --index hotpotqa_full_v1 --expected-count 100000
```

Expected: `count_matches=true`.

- [ ] **Step 2: Ingest up to 1M docs**

Run:

```powershell
python scripts/es_hotpotqa.py ingest --index hotpotqa_full_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress --batch-size 256 --max-files 18
python scripts/es_hotpotqa.py validate --index hotpotqa_full_v1 --expected-count 1000000
```

Expected: `count_matches=true`.

- [ ] **Step 3: Ingest remaining docs**

Run:

```powershell
python scripts/es_hotpotqa.py ingest --index hotpotqa_full_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress --batch-size 256
python scripts/es_hotpotqa.py validate --index hotpotqa_full_v1 --expected-count 5233329
```

Expected: `count_matches=true` and all staging files have `.done` markers.

- [ ] **Step 4: If bulk timeouts occur**

Rerun the same command with a smaller batch:

```powershell
python scripts/es_hotpotqa.py ingest --index hotpotqa_full_v1 --staging-dir artifacts/hotpotqa_full/staging --progress-dir artifacts/hotpotqa_full/progress --batch-size 128
```

Expected: previously completed files are skipped because progress markers already exist.

### Task 5: Restore Search Settings

**Files:**
- Uses: Elasticsearch HTTP API

- [ ] **Step 1: Restore refresh interval**

Run:

```powershell
curl -X PUT http://localhost:9200/hotpotqa_full_v1/_settings -H "Content-Type: application/json" -d '{"index":{"refresh_interval":"1s"}}'
curl -X POST http://localhost:9200/hotpotqa_full_v1/_refresh
```

Expected: both requests are acknowledged.

- [ ] **Step 2: Optional force merge**

Only run this if disk has at least 2x current index size free:

```powershell
curl -X POST "http://localhost:9200/hotpotqa_full_v1/_forcemerge?max_num_segments=5"
```

Expected: request completes. Skip on constrained local machines.

### Task 6: Benchmark Full Index

**Files:**
- Uses: `src/evaluation/benchmark_es.py`
- Creates: `evaluation/results/es_full_smoke_50.json`
- Creates: `evaluation/results/es_full_200.json`

- [ ] **Step 1: Run 50-query smoke benchmark**

Run:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa --index hotpotqa_full_v1 --methods es_bm25,es_dense,es_hybrid --top-k 10 --max-queries 50 --candidate-k 100 --num-candidates 1000 --rrf-k 30 --output evaluation/results/es_full_smoke_50.json --run-dir evaluation/runs/full_smoke
```

Expected: output has BM25, dense, and hybrid metrics with no query failures.

- [ ] **Step 2: Run 200-query benchmark**

Run:

```powershell
python -m src.evaluation.benchmark_es --dataset beir/hotpotqa --index hotpotqa_full_v1 --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --max-queries 200 --candidate-k 100 --num-candidates 1000 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_full_200.json --run-dir evaluation/runs/full
```

Expected: output reports `recall@10`, `mrr@10`, `ndcg@10`, `full_support_recall@10`, latency percentiles, and QPS.

### Task 7: Promote Alias And Smoke Search

**Files:**
- Uses: Elasticsearch HTTP API
- Uses: `scripts/es_hotpotqa.py`

- [ ] **Step 1: Move serving alias**

Run:

```powershell
curl -X POST http://localhost:9200/_aliases -H "Content-Type: application/json" -d '{"actions":[{"remove":{"index":"*","alias":"hotpotqa_docs_current"}},{"add":{"index":"hotpotqa_full_v1","alias":"hotpotqa_docs_current"}}]}'
```

Expected: alias update is acknowledged.

- [ ] **Step 2: Validate alias and search**

Run:

```powershell
python scripts/es_hotpotqa.py validate --index hotpotqa_docs_current --expected-count 5233329
python scripts/es_hotpotqa.py search --index hotpotqa_docs_current --method hybrid --query "What country is the creator of Miffy from?" --top-k 5 --candidate-k 100 --num-candidates 1000
```

Expected: count matches and search returns 5 result objects.

## Serving Decision

- Default to `es_hybrid` if its quality is close to `es_iterative_hybrid` and latency is much lower.
- Keep `es_iterative_hybrid` as an optional mode if it materially improves `full_support_recall@10`.
- Keep `es_bm25` as the cheap fallback and debugging mode.
- For API serving under load, test `ELASTICSEARCH_NUM_CANDIDATES=500`; keep `1000` for offline benchmark comparability.

## Acceptance Criteria

- Full staging manifest reports `5233329` docs.
- `hotpotqa_full_v1` validates with exactly `5233329` docs.
- `evaluation/results/es_full_smoke_50.json` exists.
- `evaluation/results/es_full_200.json` exists.
- `hotpotqa_docs_current` points to `hotpotqa_full_v1` after smoke benchmark passes.

## Risks And Mitigations

- CPU embedding may take too long: use GPU embedding or split embedding precompute from Elasticsearch bulk indexing.
- Dense vector index may exceed local resources: fall back to BM25-only for demo, then move dense full index to a larger node.
- Current progress markers are file-level: interruption mid-file reprocesses that file, but `_id = doc_id` keeps writes idempotent.
- Force merge is disk-heavy: skip it unless there is ample free disk.

## Self-Review

- Spec coverage: staging, index creation, ingest, validation, benchmark, and alias promotion are all covered for full HotpotQA.
- Placeholder scan: no placeholder steps remain.
- Type consistency: commands use existing repo methods `es_bm25`, `es_dense`, `es_hybrid`, and `es_iterative_hybrid`.
