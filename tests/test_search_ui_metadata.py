from __future__ import annotations

import csv
import re
from pathlib import Path


def _search_view_source() -> str:
    return Path("frontend/src/components/SearchView.tsx").read_text(encoding="utf-8")


def test_search_view_exposes_supported_metadata_filters_only_for_dataset_profiles() -> None:
    source = _search_view_source()

    assert "type SearchFilters" in source
    assert "metadataFilters" in source
    assert "supports_metadata_filters" in source
    assert "Metadata unsupported" in source
    assert "compactMetadataFilters" in source

    for field in [
        "author",
        "created_at_from",
        "created_at_to",
        "modified_at_from",
        "modified_at_to",
    ]:
        assert field in source

    assert "searchDataset(dataset.id, trimmed, nextMethod, nextTopK, nextQueryId, activeFilters)" in source


def test_search_view_has_visible_loading_feedback_and_disables_controls() -> None:
    source = _search_view_source()

    assert "SearchingIndicator" in source
    assert "animate-spin" in source
    assert "disabled={isLoading" in source
    assert "{isLoading && <SearchingIndicator" in source

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
