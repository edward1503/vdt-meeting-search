from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "VDT Meeting Search"
    es_host: str = "http://localhost:9201"
    embedding_model: str = "intfloat/e5-base-v2"
    embedding_dim: int = 768
    chunk_size: int = 512
    chunk_overlap: int = 100
    search_top_k: int = 10
    ingest_api_key: str = "dev-ingest-key"

    class Config:
        env_file = ".env"


settings = Settings()
