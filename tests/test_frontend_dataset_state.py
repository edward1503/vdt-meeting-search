from __future__ import annotations

from pathlib import Path


def test_search_view_resets_query_identity_when_dataset_changes() -> None:
    source = Path("frontend/src/components/SearchView.tsx").read_text(encoding="utf-8")

    dataset_effect_start = source.index("useEffect(() => {\n    const methods = dataset?.methods")
    dataset_effect_end = source.index("  }, [dataset?.id]);", dataset_effect_start)
    dataset_effect = source[dataset_effect_start:dataset_effect_end]

    assert "setQuery(suggestions[0]);" in dataset_effect
    assert "setQueryId(undefined);" in dataset_effect
