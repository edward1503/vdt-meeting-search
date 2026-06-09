from __future__ import annotations

from collections import namedtuple

from src.data.ingest_eda import IngestEdaAccumulator, estimate_ingest_plan, make_ingest_content, render_ingest_markdown


def test_make_ingest_content_preserves_title_and_collapses_body_whitespace():
    content = make_ingest_content("Ada Lovelace", "  First programmer.\n\n Analyst.  ")

    assert content == "Ada Lovelace\nFirst programmer. Analyst."


def test_accumulator_profiles_docs_for_elasticsearch_ingest_design():
    doc_type = namedtuple("Doc", ["doc_id", "title", "text", "url"])
    accumulator = IngestEdaAccumulator(sample_limit=2, longest_limit=2)

    accumulator.add(doc_type("1", "Ada", "First programmer.", "https://example.test/ada"))
    accumulator.add(doc_type("2", "", "First programmer.", ""))
    accumulator.add(doc_type("2", "Duplicate", "Different text with more tokens.", None))
    accumulator.add(doc_type("3", "Ada", "First programmer.", None))

    summary = accumulator.summary(total_docs=4, embedding_dims=384, shard_target_gb=30)

    assert summary["iterated"] == 4
    assert summary["missing"]["title"] == 1
    assert summary["missing"]["url"] == 3
    assert summary["duplicates"]["doc_id_duplicate_count"] == 1
    assert summary["duplicates"]["content_hash_duplicate_count"] == 1
    assert summary["content_token_lengths"]["max"] == 6
    assert summary["samples"][0]["doc_id"] == "1"
    assert summary["longest_docs"][0]["doc_id"] == "2"
    assert summary["ingest_plan"]["embedding_float32_gb"] > 0
    assert summary["ingest_plan"]["recommended_primary_shards"] == 1


def test_estimate_ingest_plan_sizes_staging_bulk_and_embeddings():
    plan = estimate_ingest_plan(
        total_docs=5_233_329,
        avg_source_bytes=1_200,
        embedding_dims=384,
        shard_target_gb=30,
        staging_docs_per_file=50_000,
        bulk_target_mb=10,
    )

    assert plan["staging_file_count"] == 105
    assert plan["recommended_bulk_docs"] >= 1
    assert plan["embedding_float32_gb"] == 7.486
    assert plan["embedding_float16_gb"] == 3.743
    assert plan["recommended_primary_shards"] >= 1


def test_render_ingest_markdown_summarizes_docs_and_ingest_plan():
    report = {
        "dataset_id": "beir/hotpotqa",
        "metadata": {"docs_count": 5_233_329, "queries_count": 97_852, "qrels_count": None},
        "documents": {
            "iterated": 100_000,
            "missing": {"title": 0, "text": 0, "url": 0, "content": 0},
            "content_token_lengths": {"p50": 62, "p95": 150, "p99": 220, "max": 900, "avg": 70.2},
            "source_bytes": {"avg": 1200},
            "duplicates": {"doc_id_duplicate_count": 0, "content_hash_duplicate_count": 3},
            "ingest_plan": {
                "recommended_primary_shards": 3,
                "recommended_bulk_docs": 2048,
                "staging_file_count": 105,
                "embedding_float32_gb": 7.486,
                "estimated_index_gb": 18.3,
            },
        },
        "splits": [{"dataset_id": "beir/hotpotqa/dev", "queries_count": 5447, "qrels_count": 10894}],
    }

    markdown = render_ingest_markdown(report)

    assert "HotpotQA Full Ingest EDA" in markdown
    assert "beir/hotpotqa" in markdown
    assert "100,000" in markdown
    assert "recommended_primary_shards" in markdown
    assert "beir/hotpotqa/dev" in markdown


def test_render_ingest_markdown_marks_skipped_document_scan():
    report = {
        "dataset_id": "beir/hotpotqa",
        "metadata": {"docs_count": 5_233_329, "queries_count": 97_852, "qrels_count": None},
        "documents": {"skipped": True, "skip_reason": "corpus not cached yet"},
        "splits": [],
    }

    markdown = render_ingest_markdown(report)

    assert "Docs scan skipped" in markdown
    assert "corpus not cached yet" in markdown
