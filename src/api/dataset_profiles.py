from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.core.config import ROOT_DIR

Readiness = Literal["ready", "partial", "missing"]


@dataclass(frozen=True)
class DatasetProfile:
    id: str
    label: str
    language: str
    task_type: str
    dataset_id: str
    index: str
    methods: tuple[str, ...]
    default_method: str
    dense_backend: str
    embedding_model: str
    vector_dims: int | None
    query_file: Path | None
    qrels_file: Path | None
    benchmark_files: tuple[Path, ...]
    readiness: Readiness
    supports_metadata_filters: bool
    primary_metric: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "language": self.language,
            "task_type": self.task_type,
            "dataset_id": self.dataset_id,
            "index": self.index,
            "methods": list(self.methods),
            "default_method": self.default_method,
            "dense_backend": self.dense_backend,
            "embedding_model": self.embedding_model,
            "vector_dims": self.vector_dims,
            "query_file": _relative_path(self.query_file),
            "qrels_file": _relative_path(self.qrels_file),
            "benchmark_files": [_relative_path(path) for path in self.benchmark_files],
            "readiness": self.readiness,
            "supports_metadata_filters": self.supports_metadata_filters,
            "primary_metric": self.primary_metric,
        }


def _relative_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return path.as_posix()


DATASET_PROFILES: tuple[DatasetProfile, ...] = (
    DatasetProfile(
        id="hotpotqa",
        label="HotpotQA Full Corpus",
        language="en",
        task_type="multi-hop retrieval",
        dataset_id="beir/hotpotqa/dev",
        index="hotpotqa_full_bm25_current",
        methods=("es_bm25", "tv_dense", "tv_hybrid", "tv_filtered_hybrid"),
        default_method="tv_hybrid",
        dense_backend="turbovec",
        embedding_model="BAAI/bge-small-en-v1.5",
        vector_dims=384,
        query_file=ROOT_DIR / "evaluation" / "results" / "hotpotqa_full_dev_queries.tsv",
        qrels_file=None,
        benchmark_files=(
            ROOT_DIR / "evaluation" / "results" / "hotpotqa_full" / "tv_full_200.json",
            ROOT_DIR / "evaluation" / "results" / "hotpotqa_full" / "tv_filtered_full_200.json",
        ),
        readiness="ready",
        supports_metadata_filters=True,
        primary_metric="full_support_recall@10",
    ),
    DatasetProfile(
        id="vimqa",
        label="VimQA Retrieval Proxy",
        language="vi",
        task_type="single-context retrieval",
        dataset_id="vimqa/all",
        index="vimqa_all_dense_bkai_current",
        methods=("es_bm25", "es_dense", "es_hybrid"),
        default_method="es_bm25",
        dense_backend="elasticsearch_dense_vector",
        embedding_model="bkai-foundation-models/vietnamese-bi-encoder",
        vector_dims=768,
        query_file=ROOT_DIR / "evaluation" / "results" / "vimqa" / "vimqa_queries.tsv",
        qrels_file=ROOT_DIR / "evaluation" / "results" / "vimqa" / "vimqa_qrels.tsv",
        benchmark_files=(
            ROOT_DIR / "evaluation" / "results" / "vimqa" / "bm25_vimqa_full.json",
            ROOT_DIR / "evaluation" / "results" / "vimqa" / "dense_bkai_vimqa_full.json",
        ),
        readiness="ready",
        supports_metadata_filters=False,
        primary_metric="recall@10",
    ),
)


def list_dataset_profiles() -> list[DatasetProfile]:
    return list(DATASET_PROFILES)


def get_dataset_profile(dataset_id: str) -> DatasetProfile:
    normalized = dataset_id.strip().lower()
    for profile in DATASET_PROFILES:
        if profile.id == normalized:
            return profile
    raise KeyError(dataset_id)
