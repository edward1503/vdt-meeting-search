# Query Paraphrase Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây một experiment tạo paraphrase cho 50 HotpotQA queries theo tỷ lệ thay thế từ có kiểm soát, rồi benchmark lại retrieval quality của `es_bm25`, `es_dense`, `es_hybrid`, và `es_iterative_hybrid`.

**Architecture:** Thêm một module tạo query variants deterministic dựa trên synonym substitution có seed cố định, giữ nguyên `query_id` gốc và qrels gốc. Benchmark runner hiện tại được mở rộng để nhận query file override, chạy retrieval trên query paraphrase, sau đó report metric theo từng tỷ lệ paraphrase và so sánh degradation với original queries.

**Tech Stack:** Python 3.12, pytest, ir_datasets, Elasticsearch retriever hiện có, JSON/TSV artifacts, metrics hiện có trong `src/evaluation/metrics.py`.

---

## Review ý tưởng

Ý tưởng paraphrase 50 query là đáng làm vì nó đo được độ robust của retriever trước lexical variation. Đây là điểm BM25 thường yếu hơn dense/hybrid, còn iterative retrieval có thể vừa được lợi vừa bị hại nếu paraphrase làm mất bridge entity.

Rủi ro chính:

1. Paraphrase đổi nghĩa câu hỏi, làm qrels gốc không còn đúng.
2. Thay named entities sẽ phá benchmark, vì HotpotQA phụ thuộc entity rất mạnh.
3. Nếu chỉ thay stopwords hoặc từ ít quan trọng, benchmark sẽ quá dễ.
4. Nếu dùng LLM paraphrase không seed hoặc không lưu artifacts, kết quả khó tái lập.
5. Nếu dùng cùng 50 query để tune và report, kết quả sẽ bị optimistic.

Quyết định thiết kế:

1. Không thay named entities, số, ngày tháng, title-like spans, hoặc token viết hoa giữa câu.
2. Tạo nhiều mức paraphrase: `0.2`, `0.4`, `0.6`, tương ứng tỷ lệ token đủ điều kiện bị thay bằng synonym.
3. Giữ `source_query_id`, tạo `variant_query_id = {query_id}::syn{ratio}::v{n}`.
4. Dùng cùng qrels của query gốc cho variants.
5. Report cả absolute metrics và delta so với original.

## File Structure

Create:

- `src/evaluation/query_paraphrase.py`: tạo synonym variants deterministic, giữ entity tokens, xuất TSV/JSONL.
- `scripts/paraphrase_queries.py`: CLI tạo 50 query paraphrases từ dataset hoặc từ TSV hiện có.
- `tests/test_query_paraphrase.py`: unit tests cho tỷ lệ thay thế, entity preservation, deterministic seed.
- `docs/superpowers/plans/2026-06-11-query-paraphrase-benchmark.md`: plan này.

Modify:

- `src/evaluation/benchmark_es.py`: thêm tùy chọn `query_file` để benchmark bằng custom queries thay vì query iterator mặc định.
- `tests/test_benchmark_es.py`: test benchmark runner nhận query override và map qrels theo `source_query_id`.
- `README.md`: thêm command chạy paraphrase benchmark.

Artifacts to produce during execution:

- `evaluation/results/query_paraphrases_50.tsv`
- `evaluation/results/query_paraphrases_50.jsonl`
- `evaluation/results/es_nano_paraphrase_syn020.json`
- `evaluation/results/es_nano_paraphrase_syn040.json`
- `evaluation/results/es_nano_paraphrase_syn060.json`
- `evaluation/runs/paraphrase/syn020/*.trec`
- `evaluation/runs/paraphrase/syn040/*.trec`
- `evaluation/runs/paraphrase/syn060/*.trec`

---

### Task 1: Add deterministic query paraphraser

**Files:**

- Create: `src/evaluation/query_paraphrase.py`
- Test: `tests/test_query_paraphrase.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_query_paraphrase.py`:

```python
from __future__ import annotations

from src.evaluation.query_paraphrase import ParaphraseConfig, make_query_variants


def test_make_query_variants_is_deterministic():
    query = "What occupations do both Ian Hunter and Rob Thomas have?"
    config = ParaphraseConfig(ratios=[0.4], variants_per_ratio=2, seed=7)

    first = make_query_variants("q1", query, config)
    second = make_query_variants("q1", query, config)

    assert first == second
    assert [item.variant_query_id for item in first] == ["q1::syn040::v1", "q1::syn040::v2"]


def test_make_query_variants_preserves_named_entities():
    query = "What occupations do both Ian Hunter and Rob Thomas have?"
    config = ParaphraseConfig(ratios=[0.6], variants_per_ratio=1, seed=3)

    [variant] = make_query_variants("q1", query, config)

    assert "Ian Hunter" in variant.query
    assert "Rob Thomas" in variant.query
    assert variant.source_query_id == "q1"
    assert variant.ratio == 0.6


def test_make_query_variants_changes_some_eligible_words():
    query = "What city did the famous scientist visit after the important conference?"
    config = ParaphraseConfig(ratios=[0.5], variants_per_ratio=1, seed=11)

    [variant] = make_query_variants("q2", query, config)

    assert variant.query != query
    assert variant.changed_terms
    assert 0.0 < variant.actual_change_ratio <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_query_paraphrase.py -q
```

Expected: FAIL because `src.evaluation.query_paraphrase` does not exist.

- [ ] **Step 3: Implement minimal paraphraser**

Create `src/evaluation/query_paraphrase.py`:

```python
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*|\d+|[^A-Za-z\d\s]+")

SYNONYMS: dict[str, list[str]] = {
    "occupation": ["profession", "job", "vocation"],
    "occupations": ["professions", "jobs", "vocations"],
    "famous": ["well-known", "notable", "renowned"],
    "important": ["major", "significant", "notable"],
    "conference": ["symposium", "meeting", "event"],
    "city": ["municipality", "urban area"],
    "visit": ["travel to", "go to"],
    "visited": ["traveled to", "went to"],
    "after": ["following", "subsequent to"],
    "before": ["prior to", "ahead of"],
    "both": ["the two", "both of"],
    "wrote": ["authored", "composed"],
    "written": ["authored", "composed"],
    "starred": ["appeared", "featured"],
    "features": ["includes", "presents"],
    "located": ["situated", "based"],
    "founded": ["established", "created"],
    "launched": ["started", "introduced"],
    "released": ["published", "issued"],
    "hosted": ["held", "organized"],
    "defeated": ["beat", "overcame"],
    "depicts": ["portrays", "shows"],
    "title": ["name", "heading"],
    "memoir": ["autobiography", "personal account"],
    "scientist": ["researcher", "scholar"],
    "university": ["college", "institution"],
    "annual": ["yearly", "once-a-year"],
    "actor": ["performer", "cast member"],
    "actress": ["performer", "female actor"],
}

STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "from", "with", "and", "or",
    "what", "which", "who", "where", "when", "why", "how", "do", "does", "did", "is", "are", "was", "were",
}


@dataclass(frozen=True)
class ParaphraseConfig:
    ratios: list[float] = field(default_factory=lambda: [0.2, 0.4, 0.6])
    variants_per_ratio: int = 1
    seed: int = 13


@dataclass(frozen=True)
class QueryVariant:
    variant_query_id: str
    source_query_id: str
    query: str
    ratio: float
    variant_index: int
    changed_terms: list[tuple[str, str]]
    actual_change_ratio: float


def make_query_variants(query_id: str, query: str, config: ParaphraseConfig) -> list[QueryVariant]:
    variants: list[QueryVariant] = []
    for ratio in config.ratios:
        for variant_index in range(1, config.variants_per_ratio + 1):
            rng = random.Random(f"{config.seed}:{query_id}:{ratio}:{variant_index}")
            variant_query, changed_terms, actual_ratio = _paraphrase_once(query, ratio, rng)
            variants.append(
                QueryVariant(
                    variant_query_id=f"{query_id}::syn{int(ratio * 100):03d}::v{variant_index}",
                    source_query_id=query_id,
                    query=variant_query,
                    ratio=ratio,
                    variant_index=variant_index,
                    changed_terms=changed_terms,
                    actual_change_ratio=actual_ratio,
                )
            )
    return variants


def _paraphrase_once(query: str, ratio: float, rng: random.Random) -> tuple[str, list[tuple[str, str]], float]:
    tokens = TOKEN_RE.findall(query)
    eligible = [idx for idx, token in enumerate(tokens) if _is_eligible(tokens, idx)]
    if not eligible:
        return query, [], 0.0

    target = max(1, round(len(eligible) * ratio))
    chosen = set(rng.sample(eligible, min(target, len(eligible))))
    changed: list[tuple[str, str]] = []
    output = tokens[:]

    for idx in sorted(chosen):
        original = tokens[idx]
        options = SYNONYMS.get(original.lower())
        if not options:
            continue
        replacement = rng.choice(options)
        output[idx] = _match_case(original, replacement)
        changed.append((original, output[idx]))

    return _join_tokens(output), changed, len(changed) / max(1, len(eligible))


def _is_eligible(tokens: list[str], idx: int) -> bool:
    token = tokens[idx]
    lower = token.lower()
    if lower in STOPWORDS or lower not in SYNONYMS:
        return False
    if token.isdigit():
        return False
    if token[:1].isupper() and idx > 0:
        return False
    return True


def _match_case(original: str, replacement: str) -> str:
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _join_tokens(tokens: list[str]) -> str:
    text = ""
    for token in tokens:
        if not text:
            text = token
        elif re.fullmatch(r"[^A-Za-z\d\s]+", token):
            text += token
        else:
            text += " " + token
    return text
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_query_paraphrase.py -q
```

Expected: PASS.

---

### Task 2: Add paraphrase generation CLI

**Files:**

- Create: `scripts/paraphrase_queries.py`
- Test: `tests/test_query_paraphrase.py`

- [ ] **Step 1: Add TSV/JSONL serialization tests**

Append to `tests/test_query_paraphrase.py`:

```python
import json

from src.evaluation.query_paraphrase import write_variants_jsonl, write_variants_tsv


def test_write_variants_outputs_tsv_and_jsonl(tmp_path):
    config = ParaphraseConfig(ratios=[0.2], variants_per_ratio=1, seed=5)
    variants = make_query_variants("q1", "What famous city did the scientist visit?", config)
    tsv_path = tmp_path / "variants.tsv"
    jsonl_path = tmp_path / "variants.jsonl"

    write_variants_tsv(variants, tsv_path)
    write_variants_jsonl(variants, jsonl_path)

    assert tsv_path.read_text(encoding="utf-8").splitlines()[0] == "variant_query_id\tsource_query_id\tratio\tvariant_index\tquery\tchanged_terms\tactual_change_ratio"
    record = json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["source_query_id"] == "q1"
    assert record["variant_query_id"].startswith("q1::syn020::v")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_query_paraphrase.py -q
```

Expected: FAIL because writer functions do not exist.

- [ ] **Step 3: Add writer functions**

Append to `src/evaluation/query_paraphrase.py`:

```python
import json
from pathlib import Path


def write_variants_tsv(variants: list[QueryVariant], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["variant_query_id\tsource_query_id\tratio\tvariant_index\tquery\tchanged_terms\tactual_change_ratio"]
    for item in variants:
        changed = ";".join(f"{src}->{dst}" for src, dst in item.changed_terms)
        lines.append(
            "\t".join(
                [
                    item.variant_query_id,
                    item.source_query_id,
                    f"{item.ratio:.2f}",
                    str(item.variant_index),
                    item.query.replace("\t", " "),
                    changed.replace("\t", " "),
                    f"{item.actual_change_ratio:.4f}",
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_variants_jsonl(variants: list[QueryVariant], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(item.__dict__, ensure_ascii=False) for item in variants]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
```

- [ ] **Step 4: Create CLI**

Create `scripts/paraphrase_queries.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from src.evaluation.query_paraphrase import ParaphraseConfig, make_query_variants, write_variants_jsonl, write_variants_tsv


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic query paraphrase variants")
    parser.add_argument("--input", type=Path, default=Path("evaluation/results/nano_test_queries.tsv"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--ratios", default="0.2,0.4,0.6")
    parser.add_argument("--variants-per-ratio", type=int, default=1)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--output-tsv", type=Path, default=Path("evaluation/results/query_paraphrases_50.tsv"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("evaluation/results/query_paraphrases_50.jsonl"))
    args = parser.parse_args()

    ratios = [float(item.strip()) for item in args.ratios.split(",") if item.strip()]
    config = ParaphraseConfig(ratios=ratios, variants_per_ratio=args.variants_per_ratio, seed=args.seed)
    variants = []

    lines = args.input.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    query_id_idx = header.index("query_id")
    query_idx = header.index("query")

    for line in lines[1 : args.limit + 1]:
        cols = line.split("\t")
        variants.extend(make_query_variants(cols[query_id_idx], cols[query_idx], config))

    write_variants_tsv(variants, args.output_tsv)
    write_variants_jsonl(variants, args.output_jsonl)
    print(f"wrote {len(variants)} variants to {args.output_tsv} and {args.output_jsonl}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests and CLI smoke**

Run:

```powershell
pytest tests/test_query_paraphrase.py -q
python scripts/paraphrase_queries.py --limit 2 --ratios 0.2 --output-tsv evaluation/results/query_paraphrases_smoke.tsv --output-jsonl evaluation/results/query_paraphrases_smoke.jsonl
```

Expected: tests pass and CLI prints `wrote 2 variants ...`.

---

### Task 3: Let benchmark use paraphrased query files

**Files:**

- Modify: `src/evaluation/benchmark_es.py`
- Modify: `tests/test_benchmark_es.py`

- [ ] **Step 1: Add failing benchmark override test**

Append to `tests/test_benchmark_es.py`:

```python

def test_run_benchmark_uses_query_file_override(monkeypatch, tmp_path):
    calls = []
    query_file = tmp_path / "queries.tsv"
    query_file.write_text(
        "variant_query_id\tsource_query_id\tratio\tvariant_index\tquery\tchanged_terms\tactual_change_ratio\n"
        "q1::syn020::v1\tq1\t0.20\t1\tparaphrased query\tfamous->notable\t0.2500\n",
        encoding="utf-8",
    )

    class FakeDataset:
        def queries_iter(self):
            yield SimpleNamespace(query_id='q1', text='original query')

        def qrels_iter(self):
            yield SimpleNamespace(query_id='q1', doc_id='d1', relevance=1)

    class FakeRetriever:
        def __init__(self, **kwargs):
            pass

        def search(self, query, method, top_k, candidate_k=100, rrf_k=60):
            calls.append(query)
            return [{'doc_id': 'd1', 'score': 1.0}]

    monkeypatch.setattr(benchmark_es, '_load_ir_dataset', lambda dataset_id: FakeDataset())
    monkeypatch.setattr(benchmark_es, '_client', lambda url: object())
    monkeypatch.setattr(benchmark_es, 'ElasticsearchRetriever', FakeRetriever)

    result = benchmark_es.run_benchmark(
        dataset_id='dataset',
        index='idx',
        methods=['es_bm25'],
        top_k=10,
        max_queries=None,
        url='http://localhost:9200',
        model_name='model',
        num_candidates=100,
        candidate_k=20,
        rrf_k=7,
        first_hop_k=5,
        second_hop_k=10,
        context_chars=256,
        run_dir=tmp_path,
        query_file=query_file,
    )

    assert calls == ['paraphrased query']
    assert result['config']['queries'] == 1
    assert result['config']['query_file'] == str(query_file)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_benchmark_es.py::test_run_benchmark_uses_query_file_override -q
```

Expected: FAIL because `run_benchmark` has no `query_file` parameter.

- [ ] **Step 3: Modify benchmark loader**

In `src/evaluation/benchmark_es.py`:

1. Add `query_file: Path | None = None` to `run_benchmark` parameters.
2. Replace query/qrels loading with:

```python
    dataset = _load_ir_dataset(dataset_id)
    if query_file is None:
        queries = _load_queries(dataset, max_queries=max_queries)
        qrels = _load_qrels(dataset, set(queries))
    else:
        queries, source_query_ids = _load_query_file(query_file, max_queries=max_queries)
        source_qrels = _load_qrels(dataset, set(source_query_ids.values()))
        qrels = {
            variant_id: source_qrels[source_id]
            for variant_id, source_id in source_query_ids.items()
            if source_id in source_qrels
        }
```

3. Add `query_file` to the returned config:

```python
            "query_file": str(query_file) if query_file else None,
```

4. Add helper:

```python
def _load_query_file(path: Path, max_queries: int | None) -> tuple[dict[str, str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return {}, {}
    header = lines[0].split("\t")
    variant_idx = header.index("variant_query_id")
    source_idx = header.index("source_query_id")
    query_idx = header.index("query")
    queries: dict[str, str] = {}
    source_query_ids: dict[str, str] = {}
    for idx, line in enumerate(lines[1:]):
        if max_queries is not None and idx >= max_queries:
            break
        cols = line.split("\t")
        variant_id = cols[variant_idx]
        queries[variant_id] = cols[query_idx]
        source_query_ids[variant_id] = cols[source_idx]
    return queries, source_query_ids
```

5. Add CLI argument:

```python
    parser.add_argument("--query-file", type=Path, default=None)
```

6. Pass `query_file=args.query_file` into `run_benchmark`.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
pytest tests/test_benchmark_es.py -q
```

Expected: PASS.

---

### Task 4: Add result comparison report

**Files:**

- Create: `src/evaluation/compare_paraphrase.py`
- Create: `scripts/compare_paraphrase_results.py`
- Test: `tests/test_query_paraphrase.py`

- [ ] **Step 1: Add comparison test**

Append to `tests/test_query_paraphrase.py`:

```python
from src.evaluation.compare_paraphrase import summarize_metric_deltas


def test_summarize_metric_deltas():
    baseline = {"results": [{"method": "es_bm25", "metrics": {"recall@10": 0.5, "full_support_recall@10": 0.2}}]}
    variant = {"results": [{"method": "es_bm25", "metrics": {"recall@10": 0.4, "full_support_recall@10": 0.1}}]}

    rows = summarize_metric_deltas(baseline, {"syn020": variant}, metrics=["recall@10", "full_support_recall@10"])

    assert rows == [
        {"condition": "syn020", "method": "es_bm25", "metric": "recall@10", "baseline": 0.5, "variant": 0.4, "delta": -0.1},
        {"condition": "syn020", "method": "es_bm25", "metric": "full_support_recall@10", "baseline": 0.2, "variant": 0.1, "delta": -0.1},
    ]
```

- [ ] **Step 2: Implement comparison helper**

Create `src/evaluation/compare_paraphrase.py`:

```python
from __future__ import annotations

from typing import Any


def summarize_metric_deltas(
    baseline: dict[str, Any],
    variants: dict[str, dict[str, Any]],
    metrics: list[str],
) -> list[dict[str, Any]]:
    baseline_by_method = {item["method"]: item["metrics"] for item in baseline.get("results", [])}
    rows: list[dict[str, Any]] = []
    for condition, result in variants.items():
        for item in result.get("results", []):
            method = item["method"]
            variant_metrics = item["metrics"]
            base_metrics = baseline_by_method.get(method, {})
            for metric in metrics:
                base_value = float(base_metrics.get(metric, 0.0))
                variant_value = float(variant_metrics.get(metric, 0.0))
                rows.append(
                    {
                        "condition": condition,
                        "method": method,
                        "metric": metric,
                        "baseline": base_value,
                        "variant": variant_value,
                        "delta": round(variant_value - base_value, 4),
                    }
                )
    return rows
```

- [ ] **Step 3: Create comparison CLI**

Create `scripts/compare_paraphrase_results.py`:

```python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.evaluation.compare_paraphrase import summarize_metric_deltas


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare paraphrase benchmark results against baseline")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--variant", action="append", default=[], help="condition=path.json")
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/paraphrase_summary.csv"))
    parser.add_argument("--metrics", default="recall@10,ndcg@10,full_support_recall@10,mrr@10,latency_p95_ms")
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    variants = {}
    for item in args.variant:
        condition, path = item.split("=", 1)
        variants[condition] = json.loads(Path(path).read_text(encoding="utf-8"))

    rows = summarize_metric_deltas(baseline, variants, [m.strip() for m in args.metrics.split(",") if m.strip()])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["condition", "method", "metric", "baseline", "variant", "delta"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run:

```powershell
pytest tests/test_query_paraphrase.py -q
```

Expected: PASS.

---

### Task 5: Run the 50-query paraphrase benchmark

**Files:**

- Generate: `evaluation/results/query_paraphrases_50.tsv`
- Generate: `evaluation/results/query_paraphrases_50.jsonl`
- Generate: `evaluation/results/es_nano_paraphrase_syn020.json`
- Generate: `evaluation/results/es_nano_paraphrase_syn040.json`
- Generate: `evaluation/results/es_nano_paraphrase_syn060.json`
- Generate: `evaluation/results/paraphrase_summary.csv`

- [ ] **Step 1: Generate paraphrases**

Run:

```powershell
python scripts/paraphrase_queries.py --input evaluation/results/nano_test_queries.tsv --limit 50 --ratios 0.2,0.4,0.6 --variants-per-ratio 1 --seed 13 --output-tsv evaluation/results/query_paraphrases_50.tsv --output-jsonl evaluation/results/query_paraphrases_50.jsonl
```

Expected: `wrote 150 variants ...`.

- [ ] **Step 2: Manually inspect sampled paraphrases**

Run:

```powershell
Get-Content evaluation/results/query_paraphrases_50.tsv -TotalCount 12
```

Expected: named entities remain unchanged; changed terms are normal synonyms; query meaning is still answerable by the original HotpotQA support docs.

- [ ] **Step 3: Run original baseline for the same 50 queries**

Run:

```powershell
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_current --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --max-queries 50 --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_original_50.json --run-dir evaluation/runs/paraphrase/original
```

Expected: JSON result with 50 queries and TREC files under `evaluation/runs/paraphrase/original`.

- [ ] **Step 4: Split paraphrase TSV by ratio**

Run:

```powershell
Import-Csv evaluation/results/query_paraphrases_50.tsv -Delimiter "`t" | Where-Object { $_.ratio -eq "0.20" } | Export-Csv evaluation/results/query_paraphrases_50_syn020.tsv -Delimiter "`t" -NoTypeInformation
Import-Csv evaluation/results/query_paraphrases_50.tsv -Delimiter "`t" | Where-Object { $_.ratio -eq "0.40" } | Export-Csv evaluation/results/query_paraphrases_50_syn040.tsv -Delimiter "`t" -NoTypeInformation
Import-Csv evaluation/results/query_paraphrases_50.tsv -Delimiter "`t" | Where-Object { $_.ratio -eq "0.60" } | Export-Csv evaluation/results/query_paraphrases_50_syn060.tsv -Delimiter "`t" -NoTypeInformation
```

Expected: three TSV files, each with 50 variant queries.

- [ ] **Step 5: Benchmark each paraphrase ratio**

Run:

```powershell
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_current --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --query-file evaluation/results/query_paraphrases_50_syn020.tsv --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_paraphrase_syn020.json --run-dir evaluation/runs/paraphrase/syn020
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_current --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --query-file evaluation/results/query_paraphrases_50_syn040.tsv --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_paraphrase_syn040.json --run-dir evaluation/runs/paraphrase/syn040
python -m src.evaluation.benchmark_es --dataset nano-beir/hotpotqa --index hotpotqa_nano_current --methods es_bm25,es_dense,es_hybrid,es_iterative_hybrid --top-k 10 --query-file evaluation/results/query_paraphrases_50_syn060.tsv --candidate-k 100 --num-candidates 100 --rrf-k 30 --first-hop-k 5 --second-hop-k 10 --context-chars 256 --output evaluation/results/es_nano_paraphrase_syn060.json --run-dir evaluation/runs/paraphrase/syn060
```

Expected: three JSON result files, each with 50 queries per method.

- [ ] **Step 6: Compare against original**

Run:

```powershell
python scripts/compare_paraphrase_results.py --baseline evaluation/results/es_nano_original_50.json --variant syn020=evaluation/results/es_nano_paraphrase_syn020.json --variant syn040=evaluation/results/es_nano_paraphrase_syn040.json --variant syn060=evaluation/results/es_nano_paraphrase_syn060.json --output evaluation/results/paraphrase_summary.csv
```

Expected: CSV with metric deltas by condition, method, and metric.

---

### Task 6: Document experiment outcome

**Files:**

- Modify: `sprint2/research.md`
- Modify: `README.md`

- [ ] **Step 1: Add command docs to README**

Append a `Paraphrase Robustness Benchmark` section to `README.md` with:

```markdown
## Paraphrase Robustness Benchmark

Generate deterministic synonym paraphrases for 50 HotpotQA queries:

```bash
python scripts/paraphrase_queries.py --input evaluation/results/nano_test_queries.tsv --limit 50 --ratios 0.2,0.4,0.6 --variants-per-ratio 1 --seed 13
```

Benchmark each ratio with `--query-file`, then compare against the original 50-query baseline:

```bash
python scripts/compare_paraphrase_results.py --baseline evaluation/results/es_nano_original_50.json --variant syn020=evaluation/results/es_nano_paraphrase_syn020.json --variant syn040=evaluation/results/es_nano_paraphrase_syn040.json --variant syn060=evaluation/results/es_nano_paraphrase_syn060.json --output evaluation/results/paraphrase_summary.csv
```
```

- [ ] **Step 2: Add Sprint 2 note**

Append to `sprint2/research.md`:

```markdown
## Paraphrase robustness experiment

Sprint 2 should include a 50-query robustness benchmark. The experiment creates synonym-based paraphrases at 20%, 40%, and 60% eligible-token replacement rates while preserving named entities and qrels. It then reruns `es_bm25`, `es_dense`, `es_hybrid`, and `es_iterative_hybrid` to measure metric degradation against the original queries.

Primary metrics:

- `recall@10`
- `full_support_recall@10`
- `ndcg@10`
- `mrr@10`
- `latency_p95_ms`

Expected finding: BM25 should degrade more under lexical paraphrase; dense and hybrid should be more stable; iterative hybrid may be sensitive if paraphrase weakens bridge terms.
```

- [ ] **Step 3: Run final tests**

Run:

```powershell
pytest tests/test_query_paraphrase.py tests/test_benchmark_es.py -q
```

Expected: PASS.

---

## Success Criteria

The experiment is successful when:

1. 50 source queries produce 150 paraphrased variants across 3 ratios.
2. Named entities and support qrels are preserved.
3. Benchmark can run original and paraphrased query sets through all four retrieval methods.
4. Output includes per-ratio metric deltas versus original.
5. The report clearly answers which retriever is most robust to paraphrase noise.

## Recommendation

Do this experiment. It is small, cheap, and directly useful. Keep the first version deterministic and synonym-based for reproducibility. After this baseline, add LLM paraphrases as a second experiment with manual validation, because LLM paraphrases are more natural but easier to accidentally change the question semantics.
