from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "VDT Meeting Search"
    es_host: str = "http://elasticsearch:9200"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    chunk_size: int = 512
    chunk_overlap: int = 100
    search_top_k: int = 10
    rerank_top_k: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
