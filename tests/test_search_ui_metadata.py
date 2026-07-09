from __future__ import annotations

import csv
import re
from pathlib import Path


def _search_view_source() -> str:
    return Path("frontend/src/components/SearchView.tsx").read_text(encoding="utf-8")


def test_search_view_omits_metadata_filter_controls_from_primary_search() -> None:
    source = _search_view_source()

    assert "Metadata Filters" not in source
    assert "metadataFilters" not in source
    assert "supports_metadata_filters" not in source
    assert "Metadata unsupported" not in source
    assert "Metadata enabled" not in source
    assert "compactMetadataFilters" not in source

    for field in [
        "created_at_from",
        "created_at_to",
        "modified_at_from",
        "modified_at_to",
    ]:
        assert field not in source

    assert "searchDataset(dataset.id, trimmed, nextMethod, nextTopK, nextQueryId, {}, nextSemanticMetadata)" in source


def test_search_view_keeps_opt_in_semantic_metadata_mode_and_parsed_output() -> None:
    source = _search_view_source()

    assert "semanticMetadata" in source
    assert "Semantic Metadata" in source
    assert "ParsedQueryChips" in source
    assert "parsed_query" in source
    assert "parsed_chips" in source
    assert "response?.effective_query" in source
    assert "semanticMetadata" in Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")


def test_result_card_renders_retrieved_document_metadata_near_uid() -> None:
    source = _search_view_source()

    assert "ResultMetadata" in source
    assert "result.author" in source
    assert "result.created_at" in source
    assert "result.modified_at" in source
    assert "result.source_split" in source
    assert "result.answer" in source

    for label in ["Author", "Created", "Modified", "Split", "Answer"]:
        assert label in source


def test_search_view_has_visible_loading_feedback_and_disables_controls() -> None:
    source = _search_view_source()

    assert "SearchingIndicator" in source
    assert "animate-spin" in source
    assert "disabled={isLoading" in source
    assert "{isLoading && <SearchingIndicator" in source


def test_search_view_renders_retrieval_trace_pipeline() -> None:
    source = _search_view_source()
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert "RetrievalTrace" in source
    assert "Search Pipeline" in source
    assert "aria-expanded={isOpen}" in source
    assert "setIsOpen((current) => !current)" in source
    assert "{isOpen && (" in source
    assert "retrieval_trace" in source
    assert "retrieval_trace" in api_source
    assert "BM25 Search" in source
    assert "TurboVec Dense Search" in source
    assert "RRF Fusion" in source
    assert "Support Overlay" in source


def test_hotpotqa_demo_method_selector_only_surfaces_hybrid_and_best_bridge() -> None:
    source = _search_view_source()
    queries_source = Path("frontend/src/components/QueriesView.tsx").read_text(encoding="utf-8")

    assert "tv_bridge_title_entities_rrf" in source
    assert "const FALLBACK_METHODS = ['tv_hybrid', 'tv_bridge_title_entities_rrf'];" in source
    assert "Standard BM25 (Keyword Only)" not in source
    assert "TurboVec Dense (Vector Only)" not in source
    assert "Filtered TurboVec Hybrid" not in source
    assert 'label="BM25"' not in queries_source


def test_hotpotqa_search_suggestions_preserve_query_ids_for_gold_support() -> None:
    source = _search_view_source()
    hotpotqa_block = source[source.index("const HOTPOTQA_SUGGESTIONS"):source.index("const VIMQA_SUGGESTIONS")]
    query_ids = re.findall(r"queryId: '([^']+)'", hotpotqa_block)
    labels = re.findall(r"label: '([^']+)'", hotpotqa_block)

    with Path("evaluation/results/hotpotqa_full_dev_queries.tsv").open(encoding="utf-8", newline="") as handle:
        rows = {row["query_id"]: row for row in csv.DictReader(handle, delimiter="\t")}

    assert query_ids
    assert len(query_ids) == len(labels)
    for query_id, label in zip(query_ids, labels):
        assert query_id in rows
        assert rows[query_id]["query"] == label
        assert rows[query_id]["support_doc_ids"]

    assert "runSearch(suggestion.label, suggestion.queryId);" in source
