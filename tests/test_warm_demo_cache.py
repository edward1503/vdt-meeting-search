from __future__ import annotations

from scripts import warm_demo_cache
from scripts.warm_demo_cache import (
    DatasetWarmupConfig,
    WarmupSummary,
    build_metadata_payloads,
    build_search_payload,
    parse_metadata_queries,
    parse_method_overrides,
    select_dataset_method,
    warm_dataset,
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
        metadata_demo=True,
        metadata_queries={},
    )

    assert config.base_url == "http://localhost:8001"
    assert config.dataset_ids == ["hotpotqa", "vimqa"]


def test_parse_metadata_queries_accepts_dataset_double_colon_query() -> None:
    assert parse_metadata_queries(["hotpotqa::find documents about anarchism by Nguyen An before 01/31/2024"]) == {
        "hotpotqa": ["find documents about anarchism by Nguyen An before 01/31/2024"]
    }


def test_build_metadata_payloads_uses_curated_and_custom_queries() -> None:
    profile = {"id": "hotpotqa", "default_method": "tv_hybrid"}
    payloads = build_metadata_payloads(
        profile,
        method="tv_hybrid",
        top_k=10,
        include_curated=True,
        custom_queries={"hotpotqa": ["find documents about ozone modified after 2024-02-03"]},
    )

    assert payloads[0] == {
        "query_id": None,
        "query": "find documents about anarchism by Nguyen An before 01/31/2024",
        "method": "tv_hybrid",
        "top_k": 10,
        "semantic_metadata": True,
    }
    assert payloads[-1] == {
        "query_id": None,
        "query": "find documents about ozone modified after 2024-02-03",
        "method": "tv_hybrid",
        "top_k": 10,
        "semantic_metadata": True,
    }


class FakeClient:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []
        self.post_counts: dict[tuple[str, str | None], int] = {}

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
        key = (path, payload.get("query_id"))
        self.post_counts[key] = self.post_counts.get(key, 0) + 1
        cache_hit = self.post_counts[key] > 1
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
        extra_payloads=[],
    )

    assert summary == WarmupSummary(dataset_id="hotpotqa", method="tv_hybrid", requested=2, warmed=2, failed=0, verified_hits=2)
    assert client.posts[0] == (
        "/datasets/hotpotqa/search",
        {"query_id": "q1", "query": "Question one?", "method": "tv_hybrid", "top_k": 10},
    )
    assert len(client.posts) == 4


def test_warm_dataset_includes_metadata_payloads() -> None:
    client = FakeClient()
    metadata_payload = {
        "query_id": "metadata_demo_hotpotqa_001",
        "query": "find documents about anarchism by Nguyen An before 01/31/2024",
        "method": "tv_hybrid",
        "top_k": 10,
        "semantic_metadata": True,
    }

    summary = warm_dataset(
        client=client,
        dataset_id="hotpotqa",
        method="tv_hybrid",
        limit=2,
        top_k=10,
        verify_cache_hit=False,
        sleep_seconds=0.0,
        extra_payloads=[metadata_payload],
    )

    assert summary == WarmupSummary(dataset_id="hotpotqa", method="tv_hybrid", requested=3, warmed=3, failed=0, verified_hits=0)
    assert client.posts[-1] == ("/datasets/hotpotqa/search", metadata_payload)


def test_warm_dataset_allows_metadata_only_without_loading_queries() -> None:
    class MetadataOnlyClient(FakeClient):
        def get_json(self, path: str) -> dict:
            raise AssertionError("queries endpoint should not be called when limit is 0")

    metadata_payload = {
        "query_id": "metadata_demo_hotpotqa_001",
        "query": "find documents about anarchism by Nguyen An before 01/31/2024",
        "method": "tv_hybrid",
        "top_k": 10,
        "semantic_metadata": True,
    }
    client = MetadataOnlyClient()

    summary = warm_dataset(
        client=client,
        dataset_id="hotpotqa",
        method="tv_hybrid",
        limit=0,
        top_k=10,
        verify_cache_hit=False,
        sleep_seconds=0.0,
        extra_payloads=[metadata_payload],
    )

    assert summary == WarmupSummary(dataset_id="hotpotqa", method="tv_hybrid", requested=1, warmed=1, failed=0, verified_hits=0)


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
        extra_payloads=[],
    )

    assert summary == WarmupSummary(dataset_id="hotpotqa", method="tv_hybrid", requested=2, warmed=1, failed=1, verified_hits=0)


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
