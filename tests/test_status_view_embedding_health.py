from __future__ import annotations

from pathlib import Path


def test_api_client_exposes_dataset_embedding_health() -> None:
    source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert "EmbeddingHealthResponse" in source
    assert "getDatasetEmbeddingHealth" in source
    assert "/datasets/${encodeURIComponent(datasetId)}/embedding-health" in source


def test_status_view_renders_embedding_health_in_status_overview() -> None:
    source = Path("frontend/src/components/StatusView.tsx").read_text(encoding="utf-8")

    assert "getDatasetEmbeddingHealth" in source
    assert "embeddingHealth" in source
    assert 'label="EMBEDDING MODEL"' in source
    assert "embeddingHealthBadge" in source
