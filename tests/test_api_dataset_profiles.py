from __future__ import annotations

import pytest

from src.api.dataset_profiles import get_dataset_profile, list_dataset_profiles


def test_dataset_registry_exposes_hotpotqa_and_vimqa_profiles() -> None:
    profiles = list_dataset_profiles()

    assert [profile.id for profile in profiles] == ["hotpotqa", "vimqa"]
    hotpotqa = get_dataset_profile("hotpotqa")
    vimqa = get_dataset_profile("vimqa")

    assert hotpotqa.label == "HotpotQA Full Corpus"
    assert hotpotqa.language == "en"
    assert hotpotqa.index == "hotpotqa_full_bm25_current"
    assert hotpotqa.methods == ("tv_hybrid", "tv_bridge_title_entities_rrf")
    assert hotpotqa.default_method == "tv_hybrid"
    assert hotpotqa.dense_backend == "turbovec"
    assert hotpotqa.embedding_model == "BAAI/bge-small-en-v1.5"
    assert hotpotqa.vector_dims == 384
    assert hotpotqa.primary_metric == "full_support_recall@10"

    assert vimqa.label == "VimQA Retrieval Proxy"
    assert vimqa.language == "vi"
    assert vimqa.index == "vimqa_all_dense_bkai_current"
    assert vimqa.methods == ("es_bm25", "es_dense", "es_hybrid")
    assert vimqa.default_method == "es_bm25"
    assert vimqa.dense_backend == "elasticsearch_dense_vector"
    assert vimqa.embedding_model == "bkai-foundation-models/vietnamese-bi-encoder"
    assert vimqa.vector_dims == 768
    assert vimqa.primary_metric == "recall@10"


def test_dataset_profile_serializes_paths_as_strings() -> None:
    profile = get_dataset_profile("vimqa")
    payload = profile.to_public_dict()

    assert payload["id"] == "vimqa"
    assert payload["query_file"] == "evaluation/results/vimqa/vimqa_queries.tsv"
    assert payload["qrels_file"] == "evaluation/results/vimqa/vimqa_qrels.tsv"
    assert payload["benchmark_files"] == [
        "evaluation/results/vimqa/bm25_vimqa_full.json",
        "evaluation/results/vimqa/dense_bkai_vimqa_full.json",
    ]


def test_unknown_dataset_profile_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_dataset_profile("unknown")
