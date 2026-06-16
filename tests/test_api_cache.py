from src.api.main import build_search_cache_key


def test_build_search_cache_key_is_stable_and_scoped() -> None:
    key_a = build_search_cache_key(
        index="hotpotqa_nano_current",
        query="What occupations do both Ian Hunter and Rob Thomas have?",
        method="tv_hybrid",
        top_k=10,
    )
    key_b = build_search_cache_key(
        index="hotpotqa_nano_current",
        query="What occupations do both Ian Hunter and Rob Thomas have?",
        method="tv_hybrid",
        top_k=10,
    )
    key_c = build_search_cache_key(
        index="hotpotqa_full_current",
        query="What occupations do both Ian Hunter and Rob Thomas have?",
        method="tv_hybrid",
        top_k=10,
    )
    key_d = build_search_cache_key(
        index="hotpotqa_nano_current",
        query="What occupations do both Ian Hunter and Rob Thomas have?",
        method="tv_hybrid",
        top_k=10,
        query_id="q1",
    )

    assert key_a == key_b
    assert key_a.startswith("search:v2:")
    assert key_a != key_c
    assert key_a != key_d
