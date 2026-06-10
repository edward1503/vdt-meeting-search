from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Settings:
    dataset_id: str = os.getenv("DATASET_ID", "nano-beir/hotpotqa")
    index_dir: Path = ROOT_DIR / "data" / "indexes"
    cache_dir: Path = ROOT_DIR / "data" / "cache"
    results_dir: Path = ROOT_DIR / "evaluation" / "results"
    history_db_path: Path = Path(os.getenv("HISTORY_DB_PATH", str(ROOT_DIR / "data" / "query_history.sqlite3")))
    rrf_k: int = int(os.getenv("RRF_K", "60"))
    multihop_first_hop: int = int(os.getenv("MULTIHOP_FIRST_HOP", "5"))
    multihop_second_hop: int = int(os.getenv("MULTIHOP_SECOND_HOP", "10"))
    multihop_context_chars: int = int(os.getenv("MULTIHOP_CONTEXT_CHARS", "256"))
    elasticsearch_url: str = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    elasticsearch_index: str = os.getenv("ELASTICSEARCH_INDEX", "hotpotqa_docs_current")
    elasticsearch_num_candidates: int = int(os.getenv("ELASTICSEARCH_NUM_CANDIDATES", "1000"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    embedding_service_url: str = os.getenv("EMBEDDING_SERVICE_URL", "")
    embedding_timeout_seconds: int = int(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))
    redis_url: str = os.getenv("REDIS_URL", "")
    search_cache_ttl_seconds: int = int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "300"))
    warmup_embedding_model: bool = os.getenv("WARMUP_EMBEDDING_MODEL", "true").lower() in {"1", "true", "yes"}

settings = Settings()
