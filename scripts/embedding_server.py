from __future__ import annotations

import argparse
import logging
import threading
import time
from functools import lru_cache
from typing import Any

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn.error")


class EmbedRequest(BaseModel):
    text: str = Field(min_length=1)


class EmbedResponse(BaseModel):
    embedding: list[float]


def create_app(model_name: str, warmup: bool = True) -> FastAPI:
    app = FastAPI(title="Local Embedding Service", version="0.1.0")

    @lru_cache(maxsize=1)
    def get_model() -> Any:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_name)

    def warm_model() -> None:
        start = time.perf_counter()
        logger.info("Warming local embedding model %s", model_name)
        get_model().encode(["warmup"], normalize_embeddings=True, convert_to_numpy=True)
        logger.info("Local embedding model warm-up finished in %.2fs", time.perf_counter() - start)

    @app.on_event("startup")
    def startup() -> None:
        if warmup:
            threading.Thread(target=warm_model, name="local-embedding-warmup", daemon=True).start()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "model": model_name}

    @app.post("/embed", response_model=EmbedResponse)
    def embed(request: EmbedRequest) -> EmbedResponse:
        vector = get_model().encode([request.text], normalize_embeddings=True, convert_to_numpy=True)[0]
        if hasattr(vector, "astype"):
            vector = vector.astype(float)
        if hasattr(vector, "tolist"):
            values = vector.tolist()
        else:
            values = list(vector)
        return EmbedResponse(embedding=[float(value) for value in values])

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local embedding service used by the Docker API.")
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5", help="SentenceTransformer model name")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8010, help="Port to bind")
    parser.add_argument("--no-warmup", action="store_true", help="Disable background model warm-up")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    uvicorn.run(create_app(args.model, warmup=not args.no_warmup), host=args.host, port=args.port)
