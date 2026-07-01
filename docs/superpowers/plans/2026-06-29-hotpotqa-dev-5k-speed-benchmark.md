# HotpotQA Dev 5k Speed Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a laptop-safe HotpotQA dev speed benchmark at 100, 500, 1000, and 5000 queries, then summarize latency, QPS, and quality trade-offs.

**Architecture:** Use the existing `src.evaluation.benchmark_es` runner against the full HotpotQA Elasticsearch index and TurboVec artifact. Treat `es_bm25` as the fastest lexical baseline, `tv_filtered_hybrid` as the optimized semantic pipeline, and `tv_hybrid` as a smaller quality comparison only.

**Tech Stack:** Python benchmark runner, Elasticsearch, TurboVec, Docker Compose runtime, Harness CLI.

---

## File Map

- Read: `README.md` for benchmark command shape and runtime expectations.
- Read: `src/evaluation/benchmark_es.py` only if a command fails or a CLI option is unclear.
- Create: `evaluation/results/hotpotqa_full/dev_speed/dev_speed_100.json`
- Create: `evaluation/results/hotpotqa_full/dev_speed/dev_speed_500.json`
- Create: `evaluation/results/hotpotqa_full/dev_speed/dev_speed_1000.json`
- Create: `evaluation/results/hotpotqa_full/dev_speed/dev_speed_5000.json`
- Create: `evaluation/results/hotpotqa_full/dev_quality/dev_quality_100.json`
- Create: `evaluation/results/hotpotqa_full/dev_quality/dev_quality_500.json`
- Create: `evaluation/results/hotpotqa_full/dev_quality/dev_quality_1000.json`
- Create: `evaluation/results/hotpotqa_full/dev_speed/summary.csv`
- Optional create: `docs/sprint5/hotpotqa-dev-speed-benchmark-report.md`

## Task 1: Runtime Preflight

**Files:**
- Read: `README.md`
- No source files changed.

- [ ] **Step 1: Confirm tools are registered**

Run:

```powershell
.\scripts\bin\harness-cli.exe query tools --capability service-runtime --status present
.\scripts\bin\harness-cli.exe query tools --capability benchmark --status present
```

Expected: `docker` and `python` are present.

- [ ] **Step 2: Start or reuse the full demo runtime**

Run:

```powershell
sh ./start.sh
```

Expected: output ends with `Startup complete`, `tv_hybrid results=3`, frontend URL, and FastAPI URL.

- [ ] **Step 3: Confirm HotpotQA dev query count**

Run:

```powershell
python -c "import csv; from pathlib import Path; p=Path('evaluation/results/hotpotqa_full_dev_queries.tsv'); print(sum(1 for _ in csv.DictReader(p.open(encoding='utf-8'), delimiter='\t')))"
```

Expected: `5447`. The 5000-query run is therefore valid and still leaves a small holdout.

## Task 2: Main Speed Benchmark

**Files:**
- Create: `evaluation/results/hotpotqa_full/dev_speed/*.json`
- Create: `evaluation/runs/hotpotqa_full/dev_speed_*/*.trec`

- [ ] **Step 1: Run speed methods at 100, 500, 1000, and 5000 queries**

Run:

```powershell
New-Item -ItemType Directory -Force evaluation/results/hotpotqa_full/dev_speed | Out-Null

foreach ($n in 100,500,1000,5000) {
  python -m src.evaluation.benchmark_es `
    --dataset beir/hotpotqa/dev `
    --index hotpotqa_full_bm25_current `
    --methods es_bm25,tv_filtered_hybrid `
    --top-k 10 `
    --max-queries $n `
    --candidate-k 100 `
    --num-candidates 100 `
    --rrf-k 30 `
    --output "evaluation/results/hotpotqa_full/dev_speed/dev_speed_$n.json" `
    --run-dir "evaluation/runs/hotpotqa_full/dev_speed_$n"
}
```

Expected: four JSON files. Each file has results for `es_bm25` and `tv_filtered_hybrid`, with `metrics.queries` matching the requested count.

- [ ] **Step 2: If the 5000 run is too slow, keep partial evidence honestly**

If runtime becomes impractical, stop after `1000` and record that `5000` was not attempted or was interrupted. Do not extrapolate 5000 as measured.

## Task 3: Quality Comparison Benchmark

**Files:**
- Create: `evaluation/results/hotpotqa_full/dev_quality/*.json`
- Create: `evaluation/runs/hotpotqa_full/dev_quality_*/*.trec`

- [ ] **Step 1: Run `tv_hybrid` only up to 1000 queries**

Run:

```powershell
New-Item -ItemType Directory -Force evaluation/results/hotpotqa_full/dev_quality | Out-Null

foreach ($n in 100,500,1000) {
  python -m src.evaluation.benchmark_es `
    --dataset beir/hotpotqa/dev `
    --index hotpotqa_full_bm25_current `
    --methods tv_hybrid `
    --top-k 10 `
    --max-queries $n `
    --candidate-k 100 `
    --num-candidates 100 `
    --rrf-k 30 `
    --output "evaluation/results/hotpotqa_full/dev_quality/dev_quality_$n.json" `
    --run-dir "evaluation/runs/hotpotqa_full/dev_quality_$n"
}
```

Expected: three JSON files with `tv_hybrid` quality and latency evidence. Do not run `tv_hybrid` at 5000 unless there is spare time.

## Task 4: Summarize Results

**Files:**
- Create: `evaluation/results/hotpotqa_full/dev_speed/summary.csv`

- [ ] **Step 1: Generate a compact CSV summary**

Run:

```powershell
python -c "import csv,json; from pathlib import Path; files=list(Path('evaluation/results/hotpotqa_full/dev_speed').glob('dev_speed_*.json'))+list(Path('evaluation/results/hotpotqa_full/dev_quality').glob('dev_quality_*.json')); rows=[]; \
[rows.append({'file':str(p),'method':r['method'],'queries':r['metrics'].get('queries'),'full_support_recall@10':r['metrics'].get('full_support_recall@10'),'recall@10':r['metrics'].get('recall@10'),'ndcg@10':r['metrics'].get('ndcg@10'),'latency_p50_ms':r['metrics'].get('latency_p50_ms'),'latency_p95_ms':r['metrics'].get('latency_p95_ms'),'latency_p99_ms':r['metrics'].get('latency_p99_ms'),'qps':r['metrics'].get('qps')}) for p in files for r in json.loads(p.read_text(encoding='utf-8'))['results']]; \
out=Path('evaluation/results/hotpotqa_full/dev_speed/summary.csv'); out.parent.mkdir(parents=True, exist_ok=True); w=csv.DictWriter(out.open('w',encoding='utf-8',newline=''), fieldnames=['file','method','queries','full_support_recall@10','recall@10','ndcg@10','latency_p50_ms','latency_p95_ms','latency_p99_ms','qps']); w.writeheader(); w.writerows(sorted(rows, key=lambda x:(int(x['queries']), x['method']))); print(out)"
```

Expected: `evaluation/results/hotpotqa_full/dev_speed/summary.csv`.

- [ ] **Step 2: Inspect the summary**

Run:

```powershell
Import-Csv evaluation/results/hotpotqa_full/dev_speed/summary.csv | Format-Table method,queries,'full_support_recall@10','latency_p95_ms',qps -AutoSize
```

Expected: a readable table for the report.

## Task 5: Report Interpretation

**Files:**
- Optional create: `docs/sprint5/hotpotqa-dev-speed-benchmark-report.md`

- [ ] **Step 1: Write the conclusion using this framing**

Use this wording if the numbers support the existing pattern:

```text
BM25 is the fastest lexical baseline on the full HotpotQA corpus. Filtered hybrid adds a semantic TurboVec stage while keeping latency lower than broad hybrid by constraining dense search with BM25 candidates. Broad hybrid remains the quality-oriented comparison and is intentionally measured only up to 1000 dev queries on the laptop run.
```

- [ ] **Step 2: Include the caveat**

Use this caveat:

```text
This is a HotpotQA dev laptop benchmark, not a BEIR leaderboard claim. The dev TSV has 5,447 labeled queries; this run measures up to 5,000 queries to show scaling behavior while staying practical on local hardware.
```

## Task 6: Harness Trace

**Files:**
- Durable Harness trace only.

- [ ] **Step 1: Record the task trace**

Run:

```powershell
.\scripts\bin\harness-cli.exe trace `
  --summary "Planned or ran HotpotQA dev 5k speed benchmark" `
  --agent codex `
  --outcome completed `
  --actions "checked runtime,ran benchmark milestones,summarized latency qps and quality metrics" `
  --read "README.md,docs/superpowers/plans/2026-06-29-hotpotqa-dev-5k-speed-benchmark.md" `
  --changed "evaluation/results/hotpotqa_full/dev_speed artifacts,evaluation/results/hotpotqa_full/dev_quality artifacts" `
  --friction "none"
```

Expected: trace recorded and tier meets tiny-lane requirement.

## Self-Review

- Spec coverage: covers the requested HotpotQA dev 5k benchmark plan with mốc 100, 500, 1000, and 5000.
- Placeholder scan: no `TBD`, no unfilled TODOs, no unspecified validation.
- Type consistency: paths and method names match the existing benchmark CLI and dataset profile.
