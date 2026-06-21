from __future__ import annotations

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
