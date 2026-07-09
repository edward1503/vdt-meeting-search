# Semantic Metadata Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build opt-in natural-language metadata search over the existing HotpotQA metadata fields without changing document metadata schema.

**Architecture:** Keep standard HotpotQA/VimQA search untouched by default. Add a rule-based query understanding layer that only runs when `semantic_metadata=true`, producing an execution plan with `original_query`, `effective_query`, parsed metadata filters, and UI/debug chips. Route the effective query and final filters through the existing BM25/TurboVec metadata-aware retrieval path, then evaluate parsed search against manual-filter and content-only baselines.

**Tech Stack:** Python/FastAPI/Pydantic backend, existing Elasticsearch/TurboVec retrievers, React/Vite frontend, pytest validation, Harness story/matrix records.

---

## Decisions

- Do not add metadata fields. Only use `author`, `created_at`, and `modified_at`.
- Do not add `metadata_text` or append metadata to dense embeddings.
- Do not auto-parse original HotpotQA/VimQA queries. Parser runs only when `semantic_metadata=true`.
- Manual metadata filter fields override parsed filters.
- If parsing is uncertain, keep `effective_query = original_query` and apply no parsed filters.
- `tv_dense` still rejects metadata filters.
- `tv_hybrid` with metadata filters still routes to `tv_filtered_hybrid`.
- UI highlights should use `effective_query` when semantic metadata mode is enabled.

## File Structure

- Create `src/retrieval/metadata_query_parser.py`: deterministic parser and dataclasses for parsed query output.
- Create `tests/test_metadata_query_parser.py`: parser unit tests for positive patterns and HotpotQA false-positive protection.
- Modify `src/api/main.py`: request/response contract, search execution planning, cache key isolation, support lookup using original query.
- Create `tests/test_semantic_metadata_api.py`: API-level unit tests for opt-in parsing, filter merge/override, method routing, and fallback behavior.
- Modify `frontend/src/lib/api.ts`: API types and `searchDataset` option for `semantic_metadata`.
- Modify `frontend/src/components/SearchView.tsx`: search mode control, semantic flag submission, parsed chips, effective-query highlighting.
- Modify or extend `tests/test_search_ui_metadata.py`: source-level frontend regression for mode flag and chips.
- Create `scripts/semantic_metadata_eval.py`: semantic metadata query-set builder and offline comparison artifact writer.
- Create `tests/test_semantic_metadata_eval.py`: toy-data test for query generation and comparison payload shape.
- Create `docs/sprint5/semantic-metadata-search-report.md`: report generated from evaluation output.
- Update `docs/stories/epics/E05-sprint5-explainable-retrieval/README.md`: add Sprint 5 semantic metadata stories.
- Create or update story files:
  - `docs/stories/epics/E05-sprint5-explainable-retrieval/US-S5-003-semantic-metadata-parser.md`
  - `docs/stories/epics/E05-sprint5-explainable-retrieval/US-S5-004-semantic-metadata-api-ui.md`
  - `docs/stories/epics/E05-sprint5-explainable-retrieval/US-S5-005-semantic-metadata-evaluation.md`

---

## Task 1: Parser Core

**Files:**
- Create: `src/retrieval/metadata_query_parser.py`
- Create: `tests/test_metadata_query_parser.py`
- Read: `src/data/synthetic_metadata.py`

- [ ] **Step 1: Write parser tests first**

Add `tests/test_metadata_query_parser.py` with tests covering:

```python
from src.retrieval.metadata_query_parser import parse_metadata_query


def test_parse_author_and_created_before_query():
    parsed = parse_metadata_query("find documents about anarchism by Nguyen An before 01/31/2024")

    assert parsed.parsed is True
    assert parsed.original_query == "find documents about anarchism by Nguyen An before 01/31/2024"
    assert parsed.content_query == "anarchism"
    assert parsed.metadata_filters == {"author": "Nguyen An", "created_at_to": "2024-01-31"}
    assert "Content: anarchism" in parsed.parsed_chips
    assert "Author: Nguyen An" in parsed.parsed_chips
    assert "Created before: 2024-01-31" in parsed.parsed_chips


def test_parse_modified_after_query():
    parsed = parse_metadata_query("documents about ozone modified after 2024-02-03")

    assert parsed.parsed is True
    assert parsed.content_query == "ozone"
    assert parsed.metadata_filters == {"modified_at_from": "2024-02-03"}
    assert "Modified after: 2024-02-03" in parsed.parsed_chips


def test_does_not_parse_original_hotpotqa_question_with_written_by():
    query = "Scarface Nation was a book written by an arts critic of what nationality?"
    parsed = parse_metadata_query(query)

    assert parsed.parsed is False
    assert parsed.content_query == query
    assert parsed.metadata_filters == {}
    assert parsed.warnings


def test_manual_author_must_match_known_synthetic_author():
    parsed = parse_metadata_query("find documents about anarchism by Not A Real Author before 01/31/2024")

    assert parsed.parsed is True
    assert parsed.content_query == "anarchism"
    assert parsed.metadata_filters == {"created_at_to": "2024-01-31"}
    assert any("author" in warning.lower() for warning in parsed.warnings)
```

- [ ] **Step 2: Run parser tests and verify RED**

Run:

```powershell
python -m pytest tests/test_metadata_query_parser.py -q
```

Expected: FAIL because `src.retrieval.metadata_query_parser` does not exist.

- [ ] **Step 3: Implement parser dataclasses and minimal rule parser**

Create `src/retrieval/metadata_query_parser.py` with:

```python
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from src.data.synthetic_metadata import DISPLAY_AUTHORS


@dataclass(frozen=True)
class ParsedMetadataQuery:
    original_query: str
    content_query: str
    metadata_filters: dict[str, str] = field(default_factory=dict)
    parsed_chips: list[str] = field(default_factory=list)
    parsed: bool = False
    parser: str = "rule_based"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SEMANTIC_PREFIX_RE = re.compile(r"^\s*(?:find|search|get|show)?\s*(?:all\s+)?(?:documents?|docs?)\s+(?:related\s+to|about)\s+", re.IGNORECASE)
DATE_RE = r"(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})"


def parse_metadata_query(query: str) -> ParsedMetadataQuery:
    original = query.strip()
    if not SEMANTIC_PREFIX_RE.search(original):
        return ParsedMetadataQuery(
            original_query=original,
            content_query=original,
            warnings=["No explicit semantic metadata search pattern found."],
        )

    body = SEMANTIC_PREFIX_RE.sub("", original, count=1).strip()
    filters: dict[str, str] = {}
    warnings: list[str] = []
    chips: list[str] = []

    body, date_chips = _extract_dates(body, filters)
    chips.extend(date_chips)
    body, author = _extract_author(body)
    if author:
        filters["author"] = author
        chips.append(f"Author: {author}")
    elif re.search(r"\b(?:by|written by|authored by)\b", body, re.IGNORECASE):
        warnings.append("Author phrase was present but did not match known synthetic authors.")

    content_query = _clean_content_query(body)
    if content_query:
        chips.insert(0, f"Content: {content_query}")
    else:
        content_query = original
        warnings.append("Parsed metadata but could not extract a stable content query; using original query.")

    return ParsedMetadataQuery(
        original_query=original,
        content_query=content_query,
        metadata_filters=filters,
        parsed_chips=chips,
        parsed=bool(filters or content_query != original),
        warnings=warnings,
    )


def _extract_dates(body: str, filters: dict[str, str]) -> tuple[str, list[str]]:
    chips: list[str] = []

    patterns = [
        (rf"\bcreated\s+before\s+{DATE_RE}", "created_at_to", "Created before"),
        (rf"\bcreated\s+after\s+{DATE_RE}", "created_at_from", "Created after"),
        (rf"\bmodified\s+before\s+{DATE_RE}", "modified_at_to", "Modified before"),
        (rf"\bmodified\s+after\s+{DATE_RE}", "modified_at_from", "Modified after"),
        (rf"\bbefore\s+{DATE_RE}", "created_at_to", "Created before"),
        (rf"\bafter\s+{DATE_RE}", "created_at_from", "Created after"),
    ]
    for pattern, field, label in patterns:
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if not match:
            continue
        value = _normalize_date(match.group(1))
        filters[field] = value
        chips.append(f"{label}: {value}")
        body = body[:match.start()] + " " + body[match.end():]
    return body, chips


def _extract_author(body: str) -> tuple[str, str | None]:
    lowered = body.lower()
    cue_positions = [position for cue in ("written by", "authored by", "by") if (position := lowered.find(cue)) >= 0]
    if not cue_positions:
        return body, None
    cue_start = min(cue_positions)
    candidate_region = body[cue_start:]
    for author in sorted(DISPLAY_AUTHORS, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(author)}\b", candidate_region, flags=re.IGNORECASE)
        if match:
            absolute_start = cue_start + match.start()
            absolute_end = cue_start + match.end()
            return (body[:cue_start] + " " + body[absolute_end:]).strip(), author
    return body, None


def _normalize_date(value: str) -> str:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def _clean_content_query(value: str) -> str:
    return " ".join(value.replace("?", " ").split()).strip(" ,.;:")
```

- [ ] **Step 4: Run parser tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_metadata_query_parser.py -q
```

Expected: PASS.

---

## Task 2: API Opt-In Search Execution Plan

**Files:**
- Modify: `src/api/main.py`
- Create: `tests/test_semantic_metadata_api.py`
- Read: `tests/test_api_es_config.py`

- [ ] **Step 1: Write API tests first**

Create `tests/test_semantic_metadata_api.py` with focused tests:

```python
from __future__ import annotations

from typing import Any

from src.api import main


def test_semantic_metadata_search_uses_effective_query_and_parsed_filters(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_run_profile_search(profile, request, effective_method, metadata_filters):
        captured["query"] = request.query
        captured["effective_method"] = effective_method
        captured["metadata_filters"] = metadata_filters
        return ([{"doc_id": "d1", "title": "Anarchism", "text": "anarchism text", "url": "", "score": 1.0, "source": "bm25+dense", "author": "Nguyen An", "created_at": "2024-01-01"}], None, 12.0)

    monkeypatch.setattr(main, "run_profile_search", fake_run_profile_search)
    monkeypatch.setattr(main, "read_search_cache", lambda key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda key, payload: None)
    monkeypatch.setattr(main, "find_support_doc_ids", lambda query, query_id=None: [])
    monkeypatch.setattr(main.get_history_store(), "record_search", lambda **kwargs: 1)

    response = main.search(
        main.SearchRequest(
            query="find documents about anarchism by Nguyen An before 01/31/2024",
            method="tv_hybrid",
            top_k=1,
            semantic_metadata=True,
        )
    )

    assert captured["query"] == "anarchism"
    assert captured["effective_method"] == "tv_filtered_hybrid"
    assert captured["metadata_filters"] == {"author": "Nguyen An", "created_at_to": "2024-01-31"}
    assert response["query"] == "find documents about anarchism by Nguyen An before 01/31/2024"
    assert response["effective_query"] == "anarchism"
    assert response["semantic_metadata"] is True
    assert response["parsed_query"]["parsed"] is True


def test_standard_search_does_not_parse_hotpotqa_question(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_run_profile_search(profile, request, effective_method, metadata_filters):
        captured["query"] = request.query
        captured["metadata_filters"] = metadata_filters
        return ([], None, 1.0)

    monkeypatch.setattr(main, "run_profile_search", fake_run_profile_search)
    monkeypatch.setattr(main, "read_search_cache", lambda key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda key, payload: None)
    monkeypatch.setattr(main, "find_support_doc_ids", lambda query, query_id=None: [])
    monkeypatch.setattr(main.get_history_store(), "record_search", lambda **kwargs: 1)

    query = "Scarface Nation was a book written by an arts critic of what nationality?"
    response = main.search(main.SearchRequest(query=query, method="es_bm25", top_k=1))

    assert captured["query"] == query
    assert captured["metadata_filters"] == {}
    assert response["query"] == query
    assert response.get("parsed_query") is None


def test_manual_filters_override_parsed_filters(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_run_profile_search(profile, request, effective_method, metadata_filters):
        captured["metadata_filters"] = metadata_filters
        return ([], None, 1.0)

    monkeypatch.setattr(main, "run_profile_search", fake_run_profile_search)
    monkeypatch.setattr(main, "read_search_cache", lambda key: None)
    monkeypatch.setattr(main, "write_search_cache", lambda key, payload: None)
    monkeypatch.setattr(main, "find_support_doc_ids", lambda query, query_id=None: [])
    monkeypatch.setattr(main.get_history_store(), "record_search", lambda **kwargs: 1)

    main.search(
        main.SearchRequest(
            query="find documents about anarchism by Nguyen An before 01/31/2024",
            method="es_bm25",
            top_k=1,
            semantic_metadata=True,
            author="Tran Minh",
        )
    )

    assert captured["metadata_filters"]["author"] == "Tran Minh"
    assert captured["metadata_filters"]["created_at_to"] == "2024-01-31"
```

- [ ] **Step 2: Run API semantic tests and verify RED**

Run:

```powershell
python -m pytest tests/test_semantic_metadata_api.py -q
```

Expected: FAIL because `SearchRequest.semantic_metadata`, effective query planning, and `parsed_query` response fields do not exist.

- [ ] **Step 3: Add request/response execution planning in `src/api/main.py`**

Make these changes:

1. Import parser near retrieval imports:

```python
from dataclasses import dataclass
from src.retrieval.metadata_query_parser import ParsedMetadataQuery, parse_metadata_query
```

2. Add request flag:

```python
class SearchRequest(BaseModel):
    ...
    semantic_metadata: bool = False
```

3. Add an internal execution-plan dataclass after `build_metadata_filters`:

```python
@dataclass(frozen=True)
class SearchExecutionPlan:
    original_query: str
    effective_query: str
    metadata_filters: dict[str, str]
    parsed_query: ParsedMetadataQuery | None = None


def build_search_execution_plan(request: SearchRequest) -> SearchExecutionPlan:
    manual_filters = build_metadata_filters(request)
    if not request.semantic_metadata:
        return SearchExecutionPlan(
            original_query=request.query,
            effective_query=request.query,
            metadata_filters=manual_filters,
        )

    parsed = parse_metadata_query(request.query)
    final_filters = {**parsed.metadata_filters, **manual_filters}
    effective_query = parsed.content_query.strip() or request.query
    return SearchExecutionPlan(
        original_query=request.query,
        effective_query=effective_query,
        metadata_filters=final_filters,
        parsed_query=parsed,
    )
```

4. Add a helper to run search with the effective query without mutating original request state:

```python
def request_with_query(request: SearchRequest, query: str) -> SearchRequest:
    return request.model_copy(update={"query": query})
```

5. In `dataset_search`, replace direct `metadata_filters = build_metadata_filters(request)` with:

```python
execution_plan = build_search_execution_plan(request)
metadata_filters = execution_plan.metadata_filters
search_request = request_with_query(request, execution_plan.effective_query)
```

Then pass `search_request` to `run_profile_search`, but use the original `request` plus `execution_plan` in response building.

6. Extend `build_search_cache_key` with `effective_query` and `semantic_metadata` so standard and semantic searches do not collide:

```python
effective_query: str | None = None,
semantic_metadata: bool = False,
```

Payload additions:

```python
'effective_query': (effective_query or query).strip(),
'semantic_metadata': semantic_metadata,
```

7. Extend `build_search_response` signature with `execution_plan: SearchExecutionPlan`, and add fields:

```python
"query": execution_plan.original_query,
"effective_query": execution_plan.effective_query,
"semantic_metadata": request.semantic_metadata,
```

If `execution_plan.parsed_query is not None`, add:

```python
response["parsed_query"] = execution_plan.parsed_query.to_dict()
```

8. Keep support lookup on the original query/query id:

```python
support_doc_ids = find_support_doc_ids(request.query, request.query_id)
```

- [ ] **Step 4: Run API tests and existing metadata API tests**

Run:

```powershell
python -m pytest tests/test_semantic_metadata_api.py tests/test_api_es_config.py -q
```

Expected: PASS. If existing tests fail because mocks do not accept the new signature, update the tests or preserve backward-compatible function signatures by adding defaulted parameters.

---

## Task 3: Frontend Semantic Metadata Mode

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/SearchView.tsx`
- Modify: `tests/test_search_ui_metadata.py`
- Read: `frontend/src/lib/highlight.ts`

- [ ] **Step 1: Write frontend source-level regression test first**

Extend `tests/test_search_ui_metadata.py` with:

```python
def test_search_view_has_opt_in_semantic_metadata_mode_and_chips() -> None:
    source = _search_view_source()

    assert "semanticMetadata" in source
    assert "Semantic Metadata" in source
    assert "parsed_query" in source
    assert "parsed_chips" in source
    assert "response?.effective_query" in source
    assert "semanticMetadata" in Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run frontend source tests and verify RED**

Run:

```powershell
python -m pytest tests/test_search_ui_metadata.py -q
```

Expected: FAIL because frontend API types and SearchView mode are not implemented.

- [ ] **Step 3: Update frontend API types**

Modify `frontend/src/lib/api.ts`:

1. Add parsed-query interface:

```ts
export interface ParsedMetadataQuery {
  original_query: string;
  content_query: string;
  metadata_filters: SearchFilters;
  parsed_chips: string[];
  parsed: boolean;
  parser: string;
  warnings: string[];
}
```

2. Extend `SearchResponse`:

```ts
effective_query?: string;
semantic_metadata?: boolean;
parsed_query?: ParsedMetadataQuery | null;
```

3. Extend `searchDataset` signature:

```ts
export async function searchDataset(
  datasetId: string,
  query: string,
  method: string,
  topK: number,
  queryId?: string,
  filters: SearchFilters = {},
  semanticMetadata = false
): Promise<SearchResponse> {
  return apiFetch(`/datasets/${encodeURIComponent(datasetId)}/search`, {
    method: 'POST',
    body: JSON.stringify({ query_id: queryId, query, method, top_k: topK, semantic_metadata: semanticMetadata, ...filters }),
  });
}
```

- [ ] **Step 4: Update SearchView state, request payload, chips, and highlight input**

Modify `frontend/src/components/SearchView.tsx`:

1. Add state:

```ts
const [semanticMetadata, setSemanticMetadata] = useState(false);
```

2. Reset it when dataset changes or preset changes only if needed. Keep default `false`.

3. Use effective query for highlighting:

```ts
const highlightTerms = buildHighlightTerms(response?.effective_query ?? response?.query ?? query);
```

4. Submit flag:

```ts
const payload = await searchDataset(dataset.id, trimmed, nextMethod, nextTopK, nextQueryId, activeFilters, semanticMetadata);
```

5. Add a compact segmented control near existing retrieval controls:

```tsx
<ControlItem label="Search Mode">
  <div className="grid grid-cols-2 gap-2">
    <button type="button" onClick={() => setSemanticMetadata(false)} className={cn(...)}>Standard</button>
    <button type="button" onClick={() => setSemanticMetadata(true)} className={cn(...)}>Semantic Metadata</button>
  </div>
</ControlItem>
```

6. Add parsed chips above results, after `SupportCoverage`:

```tsx
{response?.parsed_query && <ParsedQueryChips parsed={response.parsed_query} />}
```

7. Add component:

```tsx
function ParsedQueryChips({ parsed }: { parsed: ParsedMetadataQuery }) {
  return (
    <div className="bg-white border border-outline-variant rounded-xl p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest font-black">Parsed Query</span>
        {parsed.parsed_chips.map((chip) => (
          <span key={chip} className="px-3 py-1 rounded border border-primary/20 bg-primary/10 text-primary font-mono text-[10px] font-black uppercase tracking-widest">
            {chip}
          </span>
        ))}
      </div>
      {parsed.warnings.length > 0 && (
        <div className="mt-3 text-xs text-on-surface-variant font-medium">{parsed.warnings.join(' ')}</div>
      )}
    </div>
  );
}
```

8. Import the type:

```ts
type ParsedMetadataQuery
```

- [ ] **Step 5: Run UI tests**

Run:

```powershell
python -m pytest tests/test_search_ui_metadata.py tests/test_search_highlighting.py tests/test_frontend_dataset_state.py -q
```

Expected: PASS.

- [ ] **Step 6: Run frontend typecheck if capability is equipped**

First query Harness tool registry:

```powershell
.\scripts\bin\harness-cli.exe query tools --capability frontend-lint --status present
```

If present, run:

```powershell
cd frontend
npm run lint
```

If absent, skip cleanly and keep backlog `#10` as the known missing capability.

---

## Task 4: Semantic Metadata Evaluation

**Files:**
- Create: `scripts/semantic_metadata_eval.py`
- Create: `tests/test_semantic_metadata_eval.py`
- Create: `docs/sprint5/semantic-metadata-search-report.md`
- Create output directory: `evaluation/results/hotpotqa_full/semantic_metadata/`

- [ ] **Step 1: Write evaluation tests first**

Create `tests/test_semantic_metadata_eval.py` with toy metadata rows and assertions:

```python
from __future__ import annotations

import json
from pathlib import Path

from scripts.semantic_metadata_eval import build_semantic_queries, compare_semantic_runs


def test_build_semantic_queries_from_metadata_rows(tmp_path: Path) -> None:
    rows = [
        {"doc_id": "d1", "title": "Anarchism", "text": "Anarchism history", "author": "Nguyen An", "created_at": "2024-01-10", "modified_at": "2024-01-12"},
        {"doc_id": "d2", "title": "Ozone", "text": "Ozone chemistry", "author": "Tran Binh", "created_at": "2024-02-10", "modified_at": "2024-02-20"},
    ]
    queries = build_semantic_queries(rows, limit=2)

    assert queries[0]["query"].startswith("find documents about Anarchism by Nguyen An")
    assert queries[0]["content_query"] == "Anarchism"
    assert queries[0]["metadata_filters"]["author"] == "Nguyen An"
    assert queries[0]["relevant_doc_ids"] == ["d1"]


def test_compare_semantic_runs_reports_expected_settings(tmp_path: Path) -> None:
    queries = [{"query_id": "smq1", "relevant_doc_ids": ["d1"]}]
    runs = {
        "content_only_original": {"smq1": ["d2"]},
        "manual_filter": {"smq1": ["d1"]},
        "parsed_metadata": {"smq1": ["d1"]},
    }

    summary = compare_semantic_runs(queries, runs, top_k=1)

    assert summary["content_only_original"]["recall@1"] == 0.0
    assert summary["manual_filter"]["recall@1"] == 1.0
    assert summary["parsed_metadata"]["recall@1"] == 1.0
```

- [ ] **Step 2: Run eval tests and verify RED**

Run:

```powershell
python -m pytest tests/test_semantic_metadata_eval.py -q
```

Expected: FAIL because `scripts.semantic_metadata_eval` does not exist.

- [ ] **Step 3: Implement evaluation helpers**

Create `scripts/semantic_metadata_eval.py` with:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_semantic_queries(rows: list[dict[str, Any]], limit: int = 200) -> list[dict[str, Any]]:
    queries = []
    for row in rows[:limit]:
        title = str(row.get("title") or row.get("doc_id") or "document").strip()
        author = str(row.get("author", "")).strip()
        created_at = str(row.get("created_at", "")).strip()
        if not author or not created_at:
            continue
        query_id = f"smq_{len(queries):06d}"
        queries.append(
            {
                "query_id": query_id,
                "query": f"find documents about {title} by {author} before {created_at}",
                "content_query": title,
                "metadata_filters": {"author": author, "created_at_to": created_at},
                "relevant_doc_ids": [str(row["doc_id"])],
            }
        )
    return queries


def compare_semantic_runs(queries: list[dict[str, Any]], runs: dict[str, dict[str, list[str]]], top_k: int = 10) -> dict[str, dict[str, float]]:
    summary = {}
    for setting, run in runs.items():
        recalls = []
        for query in queries:
            relevant = set(str(doc_id) for doc_id in query["relevant_doc_ids"])
            returned = set(run.get(str(query["query_id"]), [])[:top_k])
            recalls.append(len(relevant & returned) / max(1, len(relevant)))
        summary[setting] = {f"recall@{top_k}": round(sum(recalls) / len(recalls), 4) if recalls else 0.0}
    return summary
```

Then add CLI incrementally. The first CLI can generate a query JSON from a small metadata JSONL file; full online retrieval can be added after the parser/API path is stable.

- [ ] **Step 4: Run eval tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_semantic_metadata_eval.py -q
```

Expected: PASS.

- [ ] **Step 5: Generate a small evaluation artifact**

Use existing metadata smoke/full shards if available. For a smoke artifact, use a small JSONL subset and write:

```text
evaluation/results/hotpotqa_full/semantic_metadata/semantic_queries_smoke.json
```

Report should include the comparison design even if full online retrieval is deferred:

```text
content_only_original vs manual_filter vs parsed_metadata
```

---

## Task 5: Harness Stories, Docs, and Final Validation

**Files:**
- Modify: `docs/stories/epics/E05-sprint5-explainable-retrieval/README.md`
- Create/update: `US-S5-003`, `US-S5-004`, `US-S5-005`
- Modify: `docs/sprint5/plan.md` if scope wording changes

- [ ] **Step 1: Add stories to Harness and story docs**

Commands:

```powershell
.\scripts\bin\harness-cli.exe story add --id US-S5-003 --title "Semantic metadata parser" --lane normal --verify "python -m pytest tests/test_metadata_query_parser.py -q"
.\scripts\bin\harness-cli.exe story add --id US-S5-004 --title "Semantic metadata API and UI mode" --lane normal --verify "python -m pytest tests/test_semantic_metadata_api.py tests/test_search_ui_metadata.py tests/test_search_highlighting.py tests/test_frontend_dataset_state.py -q"
.\scripts\bin\harness-cli.exe story add --id US-S5-005 --title "Semantic metadata evaluation" --lane normal --verify "python -m pytest tests/test_semantic_metadata_eval.py -q"
```

If a story already exists, use `story update` instead of `story add`.

- [ ] **Step 2: Run combined validation**

Run:

```powershell
python -m pytest tests/test_metadata_query_parser.py tests/test_semantic_metadata_api.py tests/test_semantic_metadata_eval.py tests/test_search_ui_metadata.py tests/test_search_highlighting.py tests/test_frontend_dataset_state.py -q
```

Expected: PASS.

- [ ] **Step 3: Run story verification**

Run:

```powershell
.\scripts\bin\harness-cli.exe story verify US-S5-003
.\scripts\bin\harness-cli.exe story verify US-S5-004
.\scripts\bin\harness-cli.exe story verify US-S5-005
```

Expected: all pass.

- [ ] **Step 4: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: exit 0.

- [ ] **Step 5: Record final trace**

Record a Harness trace with intake id, story ids, changed files, validation commands, and any skipped checks. Use `docs/TRACE_SPEC.md` for field depth.

---

## End-to-End Acceptance Criteria

- Standard HotpotQA/VimQA queries run unchanged unless `semantic_metadata=true`.
- Semantic metadata mode parses explicit document-search queries into `effective_query` and metadata filters.
- Original query is preserved in response/history/debug surfaces.
- Effective query is used for retrieval and UI highlighting.
- Parsed chips are visible in UI only when parsed-query data exists.
- Manual filters override parsed filters.
- Existing metadata validation and method routing behavior remains intact.
- Evaluation artifacts compare content-only, manual-filter, and parsed-metadata settings.
- Reports clearly state that this is natural-language metadata search over synthetic HotpotQA metadata, not production meeting-search metadata.
