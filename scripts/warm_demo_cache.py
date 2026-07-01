from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError


CURATED_METADATA_QUERIES: dict[str, list[str]] = {
    "hotpotqa": [
        "find documents about anarchism by Nguyen An before 01/31/2024",
        "documents about ozone modified after 2024-02-03",
        "find documents about impossible-demo-no-results by Nguyen An before 2024-01-01",
    ],
    "vimqa": [
        "tài liệu về lịch sử Việt Nam của Nguyen An trước 31/01/2024",
        "văn bản về giáo dục bởi Tran Minh chỉnh sửa sau 2024-02-03",
        "tài liệu về khong-co-ket-qua-demo của Nguyen An trước 2024-01-01",
    ],
}


@dataclass(frozen=True)
class DatasetWarmupConfig:
    api_url: str
    datasets: list[str]
    limit: int
    top_k: int
    verify_cache_hit: bool
    method_overrides: dict[str, str]
    metadata_demo: bool = False
    metadata_queries: dict[str, list[str]] | None = None
    sleep_seconds: float = 0.0
    timeout_seconds: float = 120.0

    @property
    def base_url(self) -> str:
        return self.api_url.rstrip("/")

    @property
    def dataset_ids(self) -> list[str]:
        return [item.strip() for item in self.datasets if item.strip()]


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


def parse_metadata_queries(values: list[str]) -> dict[str, list[str]]:
    queries: dict[str, list[str]] = {}
    for value in values:
        if "::" not in value:
            raise ValueError(f"Metadata query must use dataset::query format: {value}")
        dataset_id, query = value.split("::", 1)
        dataset_id = dataset_id.strip()
        query = query.strip()
        if not dataset_id or not query:
            raise ValueError(f"Metadata query must include dataset and query: {value}")
        queries.setdefault(dataset_id, []).append(query)
    return queries


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


def build_metadata_payloads(
    profile: dict[str, Any],
    *,
    method: str,
    top_k: int,
    include_curated: bool,
    custom_queries: dict[str, list[str]] | None,
) -> list[dict[str, Any]]:
    dataset_id = str(profile.get("id", "")).strip()
    if not bool(profile.get("supports_metadata_filters", True)):
        return []

    queries: list[tuple[str, str]] = []
    if include_curated:
        queries.extend(("metadata_demo", query) for query in CURATED_METADATA_QUERIES.get(dataset_id, []))
    for query in (custom_queries or {}).get(dataset_id, []):
        queries.append(("metadata_custom", query))

    payloads: list[dict[str, Any]] = []
    for _, query in queries:
        payloads.append(
            {
                "query_id": None,
                "query": query,
                "method": method,
                "top_k": int(top_k),
                "semantic_metadata": True,
            }
        )
    return payloads


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
    extra_payloads: list[dict[str, Any]],
) -> WarmupSummary:
    query_limit = int(limit)
    queries: list[dict[str, Any]] = []
    if query_limit > 0:
        query_payload = client.get_json(f"/datasets/{dataset_id}/queries?limit={query_limit}&offset=0")
        queries = list(query_payload.get("queries", []))[:query_limit]
    payloads = [build_search_payload(query, method=method, top_k=top_k) for query in queries]
    payloads.extend(extra_payloads)
    warmed = 0
    failed = 0
    verified_hits = 0

    for index, payload in enumerate(payloads, start=1):
        try:
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
        requested=len(payloads),
        warmed=warmed,
        failed=failed,
        verified_hits=verified_hits,
    )


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
    parser.add_argument("--metadata-demo", action="store_true", help="Warm curated semantic metadata demo queries for selected datasets.")
    parser.add_argument("--metadata-query", action="append", default=[], help="Add a metadata-mode query with dataset::query. Can be repeated.")
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
        metadata_demo=args.metadata_demo,
        metadata_queries=parse_metadata_queries(args.metadata_query),
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
        extra_payloads = build_metadata_payloads(
            profile,
            method=method,
            top_k=config.top_k,
            include_curated=config.metadata_demo,
            custom_queries=config.metadata_queries,
        )
        print(
            f"Warming {dataset_id}: method={method}, limit={config.limit}, "
            f"top_k={config.top_k}, metadata={len(extra_payloads)}"
        )
        summary = warm_dataset(
            client=client,
            dataset_id=dataset_id,
            method=method,
            limit=config.limit,
            top_k=config.top_k,
            verify_cache_hit=config.verify_cache_hit,
            sleep_seconds=config.sleep_seconds,
            extra_payloads=extra_payloads,
        )
        summaries.append(summary)
        print(
            f"{summary.dataset_id}: warmed={summary.warmed}/{summary.requested}, "
            f"failed={summary.failed}, verified_hits={summary.verified_hits}"
        )

    verification_failed = False
    if config.verify_cache_hit:
        verification_failed = any(summary.verified_hits != summary.requested for summary in summaries)
    return 1 if any(not summary.ok for summary in summaries) or verification_failed else 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except Exception as exc:
        print(f"warm_demo_cache failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
