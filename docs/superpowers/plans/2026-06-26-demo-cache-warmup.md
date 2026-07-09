# Demo Cache Warmup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small demo-safe cache warmup command that pre-runs the first 50 queries for each active dataset, plus selected semantic metadata demo queries, through the existing API so Redis contains the exact responses the UI will request.

**Architecture:** Keep Redis as an optional runtime optimization already owned by `src/api/main.py`. The warmup tool will call public dataset endpoints (`/datasets/{id}/queries` and `/datasets/{id}/search`) instead of writing Redis keys directly, so it reuses the existing cache key, metadata, history, default-method, and error behavior. The implementation is a standalone script plus focused unit tests for dataset selection, payload construction, and warmup summary handling.

**Tech Stack:** Python 3 standard library (`argparse`, `json`, `urllib.request`), existing FastAPI runtime, Redis via current API cache layer, pytest.

---

## Scope

This plan intentionally does not change retrieval ranking, model loading, Elasticsearch mappings, Redis cache key construction, or frontend behavior. It adds one operator script and documentation for demo use. The runtime must already be up with API, Redis, Elasticsearch, and the embedding service when warming HotpotQA `tv_hybrid`. Metadata demo warmup uses `semantic_metadata: true` and curated natural-language metadata queries that the existing rule-based parser already supports.

## File Structure

- Create `scripts/warm_demo_cache.py`: CLI script and small testable helpers for reading queries and calling dataset search endpoints.
- Create `tests/test_warm_demo_cache.py`: unit tests for method override parsing, query limiting, payload shape, metadata-demo payloads, cache-hit verification, and failure accounting without network access.
- Modify `README.md`: add a short demo cache warmup command and TTL note under Docker/demo runtime docs.
- Optional during execution: update Harness story evidence only if an existing cache/runtime story is selected for this bounded script. If no matching story is appropriate, use Harness intake + trace only.

## CLI Contract

Default command for demo:

```powershell
python scripts/warm_demo_cache.py --api-url http://localhost:8001 --datasets hotpotqa,vimqa --limit 50 --top-k 10 --metadata-demo --verify-cache-hit
```

Expected behavior:

- HotpotQA uses profile `default_method`, currently `tv_hybrid`.
- VimQA uses profile `default_method`, currently `es_bm25`.
- The script requests the first 50 queries from each dataset profile.
- Each query is posted to `/datasets/{dataset_id}/search` with `query_id`, `query`, `method`, and `top_k`.
- `--verify-cache-hit` immediately posts the same request again and counts whether the second response returns `cache_hit: true`.
- `--metadata-demo` additionally warms curated semantic metadata queries for supported datasets using `semantic_metadata: true`.
- Metadata demo payloads intentionally omit `query_id` so they match the cache key produced when a presenter types the same query in the Search tab.
- `--metadata-query dataset_id::query text` can add more metadata-mode queries without editing code.
- The process exits `0` if all warmup requests succeed and, when verification is enabled, all verification requests are cache hits.
- The process exits `1` if any dataset cannot be loaded, any warmup request fails, or any verification request is not a cache hit.

## Task 1: Add Unit Tests For Warmup Helpers

**Files:**
- Create: `tests/test_warm_demo_cache.py`

- [ ] **Step 1: Write tests for method override parsing and payload construction**

Create `tests/test_warm_demo_cache.py` with these tests:

```python
from scripts.warm_demo_cache import (
    DatasetWarmupConfig,
    build_search_payload,
    parse_method_overrides,
    select_dataset_method,
)


def test_parse_method_overrides_accepts_dataset_equals_method() -> None:
    assert parse_method_overrides(["hotpotqa=tv_hybrid", "vimqa=es_bm25"]) == {
        "hotpotqa": "tv_hybrid",
        "vimqa": "es_bm25",
    }


def test_select_dataset_method_prefers_override_then_profile_default() -> None:
    profile = {"id": "hotpotqa", "default_method": "tv_hybrid"}

    assert select_dataset_method(profile, {"hotpotqa": "es_bm25"}) == "es_bm25"
    assert select_dataset_method(profile, {}) == "tv_hybrid"


def test_build_search_payload_uses_query_id_text_method_and_top_k() -> None:
    query = {"query_id": "q1", "query": "Who connects Alpha and Beta?"}
    payload = build_search_payload(query, method="tv_hybrid", top_k=10)

    assert payload == {
        "query_id": "q1",
        "query": "Who connects Alpha and Beta?",
        "method": "tv_hybrid",
        "top_k": 10,
    }


def test_dataset_warmup_config_normalizes_url_and_dataset_list() -> None:
    config = DatasetWarmupConfig(
        api_url="http://localhost:8001/",
        datasets=[" hotpotqa ", "vimqa"],
        limit=50,
        top_k=10,
        verify_cache_hit=True,
        method_overrides={},
    )

    assert config.base_url == "http://localhost:8001"
    assert config.dataset_ids == ["hotpotqa", "vimqa"]
```

- [ ] **Step 2: Run tests and verify expected failure**

Run:

```powershell
python -m pytest tests/test_warm_demo_cache.py -q
```

Expected: FAIL with `ModuleNotFoundError` or import errors because `scripts/warm_demo_cache.py` does not exist yet.

## Task 2: Implement Pure Helpers And CLI Data Types

**Files:**
- Create: `scripts/warm_demo_cache.py`
- Test: `tests/test_warm_demo_cache.py`

- [ ] **Step 1: Create script with helper functions**

Create `scripts/warm_demo_cache.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError


@dataclass(frozen=True)
class DatasetWarmupConfig:
    api_url: str
    datasets: list[str]
    limit: int
    top_k: int
    verify_cache_hit: bool
    method_overrides: dict[str, str]
    sleep_seconds: float = 0.0
    timeout_seconds: float = 120.0

    @property
    def base_url(self) -> str:
        return self.api_url.rstrip("/")

    @property
    def dataset_ids(self) -> list[str]:
        return [item.strip() for item in self.datasets if item.strip()]


def parse_method_overrides(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Method override must use dataset=method format: {value}")
        dataset_id, method = value.split("=", 1)
        dataset_id = dataset_id.strip()
        method = method.strip()
        if not dataset_id or not method:
            raise ValueError(f"Method override must include dataset and method: {value}")
        overrides[dataset_id] = method
    return overrides


def select_dataset_method(profile: dict[str, Any], overrides: dict[str, str]) -> str:
    dataset_id = str(profile.get("id", "")).strip()
    if dataset_id in overrides:
        return overrides[dataset_id]
    method = str(profile.get("default_method", "")).strip()
    if not method:
        raise ValueError(f"Dataset {dataset_id or '<unknown>'} has no default_method")
    return method


def build_search_payload(query: dict[str, Any], *, method: str, top_k: int) -> dict[str, Any]:
    query_id = str(query.get("query_id") or query.get("id") or "").strip()
    text = str(query.get("query") or query.get("text") or "").strip()
    if not text:
        raise ValueError(f"Query {query_id or '<unknown>'} has empty text")
    return {
        "query_id": query_id or None,
        "query": text,
        "method": method,
        "top_k": int(top_k),
    }
```

- [ ] **Step 2: Run helper tests**

Run:

```powershell
python -m pytest tests/test_warm_demo_cache.py -q
```

Expected: PASS for helper tests in Task 1.

## Task 3: Add API Client And Warmup Loop Tests

**Files:**
- Modify: `tests/test_warm_demo_cache.py`
- Modify: `scripts/warm_demo_cache.py`

- [ ] **Step 1: Add fake-client tests for successful warmup and cache-hit verification**

Append to `tests/test_warm_demo_cache.py`:

```python
from scripts.warm_demo_cache import WarmupSummary, warm_dataset


class FakeClient:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []

    def get_json(self, path: str) -> dict:
        if path == "/datasets/hotpotqa/queries?limit=2&offset=0":
            return {
                "queries": [
                    {"query_id": "q1", "query": "Question one?"},
                    {"query_id": "q2", "query": "Question two?"},
                ]
            }
        raise AssertionError(path)

    def post_json(self, path: str, payload: dict) -> dict:
        self.posts.append((path, payload))
        cache_hit = len(self.posts) > 2
        return {"cache_hit": cache_hit, "results": [{"doc_id": "d1"}]}


def test_warm_dataset_posts_queries_and_verifies_cache_hits() -> None:
    client = FakeClient()
    summary = warm_dataset(
        client=client,
        dataset_id="hotpotqa",
        method="tv_hybrid",
        limit=2,
        top_k=10,
        verify_cache_hit=True,
        sleep_seconds=0.0,
    )

    assert summary == WarmupSummary(dataset_id="hotpotqa", method="tv_hybrid", requested=2, warmed=2, failed=0, verified_hits=2)
    assert client.posts[0] == (
        "/datasets/hotpotqa/search",
        {"query_id": "q1", "query": "Question one?", "method": "tv_hybrid", "top_k": 10},
    )
    assert len(client.posts) == 4


class FailingClient(FakeClient):
    def post_json(self, path: str, payload: dict) -> dict:
        self.posts.append((path, payload))
        if payload["query_id"] == "q2":
            raise RuntimeError("search failed")
        return {"cache_hit": False, "results": [{"doc_id": "d1"}]}


def test_warm_dataset_counts_failures_without_stopping() -> None:
    summary = warm_dataset(
        client=FailingClient(),
        dataset_id="hotpotqa",
        method="tv_hybrid",
        limit=2,
        top_k=10,
        verify_cache_hit=False,
        sleep_seconds=0.0,
    )

    assert summary == WarmupSummary(dataset_id="hotpotqa", method="tv_hybrid", requested=2, warmed=1, failed=1, verified_hits=0)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_warm_demo_cache.py -q
```

Expected: FAIL because `WarmupSummary` and `warm_dataset` are not implemented.

## Task 4: Implement API Client And Warmup Loop

**Files:**
- Modify: `scripts/warm_demo_cache.py`
- Test: `tests/test_warm_demo_cache.py`

- [ ] **Step 1: Add summary type, HTTP client, and warmup function**

Append to `scripts/warm_demo_cache.py` after `build_search_payload`:

```python
@dataclass(frozen=True)
class WarmupSummary:
    dataset_id: str
    method: str
    requested: int
    warmed: int
    failed: int
    verified_hits: int

    @property
    def ok(self) -> bool:
        return self.failed == 0


class ApiClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with urlrequest.urlopen(url, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GET {path} failed with HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"GET {path} failed: {exc.reason}") from exc

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        request = urlrequest.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlrequest.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"POST {path} failed with HTTP {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise RuntimeError(f"POST {path} failed: {exc.reason}") from exc


def warm_dataset(
    *,
    client: Any,
    dataset_id: str,
    method: str,
    limit: int,
    top_k: int,
    verify_cache_hit: bool,
    sleep_seconds: float,
) -> WarmupSummary:
    query_payload = client.get_json(f"/datasets/{dataset_id}/queries?limit={int(limit)}&offset=0")
    queries = list(query_payload.get("queries", []))[: int(limit)]
    warmed = 0
    failed = 0
    verified_hits = 0

    for index, query in enumerate(queries, start=1):
        try:
            payload = build_search_payload(query, method=method, top_k=top_k)
            client.post_json(f"/datasets/{dataset_id}/search", payload)
            warmed += 1
            if verify_cache_hit:
                verification = client.post_json(f"/datasets/{dataset_id}/search", payload)
                if verification.get("cache_hit") is True:
                    verified_hits += 1
                else:
                    failed += 1
                    print(f"[{dataset_id}] cache verification miss for query {payload.get('query_id') or index}", file=sys.stderr)
        except Exception as exc:
            failed += 1
            print(f"[{dataset_id}] failed query {index}: {exc}", file=sys.stderr)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return WarmupSummary(
        dataset_id=dataset_id,
        method=method,
        requested=len(queries),
        warmed=warmed,
        failed=failed,
        verified_hits=verified_hits,
    )
```

- [ ] **Step 2: Run tests**

Run:

```powershell
python -m pytest tests/test_warm_demo_cache.py -q
```

Expected: PASS.

## Task 5: Add CLI Main And Dataset Profile Resolution

**Files:**
- Modify: `scripts/warm_demo_cache.py`
- Modify: `tests/test_warm_demo_cache.py`

- [ ] **Step 1: Add tests for profile lookup and exit status**

Append to `tests/test_warm_demo_cache.py`:

```python
from scripts import warm_demo_cache


def test_find_profiles_returns_requested_dataset_profiles() -> None:
    payload = {
        "datasets": [
            {"id": "hotpotqa", "default_method": "tv_hybrid"},
            {"id": "vimqa", "default_method": "es_bm25"},
        ]
    }

    profiles = warm_demo_cache.find_profiles(payload, ["vimqa", "hotpotqa"])

    assert [profile["id"] for profile in profiles] == ["vimqa", "hotpotqa"]


def test_find_profiles_raises_for_missing_dataset() -> None:
    payload = {"datasets": [{"id": "hotpotqa", "default_method": "tv_hybrid"}]}

    try:
        warm_demo_cache.find_profiles(payload, ["vimqa"])
    except ValueError as exc:
        assert "Dataset not found: vimqa" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_warm_demo_cache.py -q
```

Expected: FAIL because `find_profiles` is not implemented.

- [ ] **Step 3: Implement profile lookup and CLI entrypoint**

Append to `scripts/warm_demo_cache.py`:

```python
def find_profiles(datasets_payload: dict[str, Any], dataset_ids: list[str]) -> list[dict[str, Any]]:
    profiles_by_id = {str(profile.get("id", "")): profile for profile in datasets_payload.get("datasets", [])}
    profiles: list[dict[str, Any]] = []
    for dataset_id in dataset_ids:
        profile = profiles_by_id.get(dataset_id)
        if profile is None:
            raise ValueError(f"Dataset not found: {dataset_id}")
        profiles.append(profile)
    return profiles


def parse_args(argv: list[str] | None = None) -> DatasetWarmupConfig:
    parser = argparse.ArgumentParser(description="Warm Redis search cache through the public dataset search API.")
    parser.add_argument("--api-url", default="http://localhost:8001", help="Base URL for the FastAPI service.")
    parser.add_argument("--datasets", default="hotpotqa,vimqa", help="Comma-separated dataset profile ids.")
    parser.add_argument("--limit", type=int, default=50, help="Number of first queries to warm per dataset.")
    parser.add_argument("--top-k", type=int, default=10, help="Search top_k used by the demo UI.")
    parser.add_argument("--method", action="append", default=[], help="Override a dataset method with dataset=method. Can be repeated.")
    parser.add_argument("--verify-cache-hit", action="store_true", help="Immediately re-run each query and require cache_hit=true.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Optional pause between queries.")
    parser.add_argument("--timeout-seconds", type=float, default=120.0, help="HTTP timeout per API request.")
    args = parser.parse_args(argv)
    return DatasetWarmupConfig(
        api_url=args.api_url,
        datasets=args.datasets.split(","),
        limit=args.limit,
        top_k=args.top_k,
        verify_cache_hit=args.verify_cache_hit,
        method_overrides=parse_method_overrides(args.method),
        sleep_seconds=args.sleep_seconds,
        timeout_seconds=args.timeout_seconds,
    )


def run(config: DatasetWarmupConfig) -> int:
    client = ApiClient(config.base_url, timeout_seconds=config.timeout_seconds)
    datasets_payload = client.get_json("/datasets")
    profiles = find_profiles(datasets_payload, config.dataset_ids)
    summaries: list[WarmupSummary] = []

    for profile in profiles:
        dataset_id = str(profile["id"])
        method = select_dataset_method(profile, config.method_overrides)
        print(f"Warming {dataset_id}: method={method}, limit={config.limit}, top_k={config.top_k}")
        summary = warm_dataset(
            client=client,
            dataset_id=dataset_id,
            method=method,
            limit=config.limit,
            top_k=config.top_k,
            verify_cache_hit=config.verify_cache_hit,
            sleep_seconds=config.sleep_seconds,
        )
        summaries.append(summary)
        print(
            f"{summary.dataset_id}: warmed={summary.warmed}/{summary.requested}, "
            f"failed={summary.failed}, verified_hits={summary.verified_hits}"
        )

    if config.verify_cache_hit:
        verification_failed = any(summary.verified_hits != summary.requested for summary in summaries)
    else:
        verification_failed = False
    return 1 if any(not summary.ok for summary in summaries) or verification_failed else 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except Exception as exc:
        print(f"warm_demo_cache failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run all warmup script tests**

Run:

```powershell
python -m pytest tests/test_warm_demo_cache.py -q
```

Expected: PASS.

## Task 6: Document Demo Cache Warmup

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README section under Docker Development Stack**

Add this section after the existing Redis cache paragraph in `README.md`:

````markdown
### Demo Cache Warmup

For a low-latency demo, start the full demo runtime with a longer search cache TTL, then warm the first 50 queries for each dataset through the public API:

```powershell
$env:SEARCH_CACHE_TTL_SECONDS = "86400"
.\start.sh
python scripts/warm_demo_cache.py --api-url http://localhost:8001 --datasets hotpotqa,vimqa --limit 50 --top-k 10 --metadata-demo --verify-cache-hit
```

The warmup command does not write Redis keys directly. It calls `/datasets/{dataset_id}/search`, so it uses the same cache key and default retrieval method as the dashboard. HotpotQA warms with the profile default `tv_hybrid`; VimQA warms with the profile default `es_bm25`. `--metadata-demo` also warms curated semantic metadata queries with `semantic_metadata=true` and no `query_id`, matching the way a presenter types those queries in the Search tab. If a demo needs a cheaper HotpotQA path, override the method explicitly:

```powershell
python scripts/warm_demo_cache.py --api-url http://localhost:8001 --datasets hotpotqa --method hotpotqa=es_bm25 --limit 50 --top-k 10 --metadata-demo --verify-cache-hit
```

To add one-off metadata-mode queries without editing the script, pass `--metadata-query` as `dataset::query`:

```powershell
python scripts/warm_demo_cache.py --api-url http://localhost:8001 --datasets hotpotqa --limit 0 --metadata-query "hotpotqa::find documents about ozone modified after 2024-02-03" --verify-cache-hit
```
````

- [ ] **Step 2: Review README command for Windows shell correctness**

Confirm the command uses PowerShell-compatible environment assignment and the API port from the repo docs, `http://localhost:8001`.

## Task 7: Validation And Harness Trace

**Files:**
- Read: `docs/TRACE_SPEC.md`
- Read: `git status --short`
- Changed: `scripts/warm_demo_cache.py`, `tests/test_warm_demo_cache.py`, `README.md`, this plan file

- [ ] **Step 1: Run focused unit tests**

Run:

```powershell
python -m pytest tests/test_warm_demo_cache.py tests/test_api_cache.py -q
```

Expected: PASS. `tests/test_api_cache.py` proves existing cache key behavior still holds; `tests/test_warm_demo_cache.py` proves the new script behavior without network access.

- [ ] **Step 2: Optional runtime smoke when services are up**

Run only after `start.sh` or Docker runtime is healthy:

```powershell
python scripts/warm_demo_cache.py --api-url http://localhost:8001 --datasets vimqa --limit 2 --top-k 10 --verify-cache-hit
```

Expected: exit `0` and output like:

```text
Warming vimqa: method=es_bm25, limit=2, top_k=10
vimqa: warmed=2/2, failed=0, verified_hits=2
```

Use VimQA first because it avoids TurboVec/embedding-service warmup risk. For full demo proof, run:

```powershell
python scripts/warm_demo_cache.py --api-url http://localhost:8001 --datasets hotpotqa,vimqa --limit 50 --top-k 10 --metadata-demo --verify-cache-hit
```

Expected: exit `0`; both datasets report `warmed=53/53`, `failed=0`, and `verified_hits=53` when the curated metadata set has 3 queries per dataset.

- [ ] **Step 3: Read trace spec and inspect working tree**

Run:

```powershell
Get-Content docs/TRACE_SPEC.md
git status --short
```

Expected: trace guidance is available and working tree shows only the intended files for this task plus pre-existing unrelated changes.

- [ ] **Step 4: Record Harness trace**

Run:

```powershell
.\scripts\bin\harness-cli.exe trace --summary "Planned and implemented demo cache warmup script" --outcome completed --actions "added API-based warmup script,added warmup unit tests,documented demo TTL and warmup command,ran focused pytest validation" --read "README.md,docs/HARNESS.md,docs/FEATURE_INTAKE.md,docs/ARCHITECTURE.md,docs/CONTEXT_RULES.md,docs/TOOL_REGISTRY.md,src/api/main.py,src/api/dataset_profiles.py,tests/test_api_cache.py,docs/TRACE_SPEC.md" --changed "scripts/warm_demo_cache.py,tests/test_warm_demo_cache.py,README.md,docs/superpowers/plans/2026-06-26-demo-cache-warmup.md" --friction "none"
```

Expected: trace records successfully. If runtime smoke was skipped because services were not running, include that in the final response and omit any claim that Redis was warmed in the live container.

## Rollback

- Delete `scripts/warm_demo_cache.py` and `tests/test_warm_demo_cache.py`.
- Remove the `Demo Cache Warmup` section from `README.md`.
- No Redis data migration or Elasticsearch change is involved. If demo cache contents are unwanted, restart Redis or run `docker compose exec redis redis-cli FLUSHDB` after confirming no other demo state matters.

## Self-Review

- Spec coverage: The plan covers prewarming the first 50 queries for HotpotQA and VimQA, uses Redis indirectly through current API cache behavior, supports method overrides, includes cache-hit verification, and documents longer TTL for demo.
- Placeholder scan: The plan does not rely on undefined future decisions; all code-facing steps include concrete commands and expected results.
- Type consistency: `DatasetWarmupConfig`, `WarmupSummary`, `ApiClient`, `warm_dataset`, `find_profiles`, and helper function names are used consistently across tests and implementation steps.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-26-demo-cache-warmup.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.
