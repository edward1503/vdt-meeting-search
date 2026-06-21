from __future__ import annotations

import argparse
import logging
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class ModelSpec:
    model_name: str
    expected_dim: int


DEFAULT_MODEL_ID = "hotpotqa"
MODEL_REGISTRY: dict[str, ModelSpec] = {
    "hotpotqa": ModelSpec("BAAI/bge-small-en-v1.5", 384),
    "vimqa": ModelSpec("bkai-foundation-models/vietnamese-bi-encoder", 768),
}


class EmbedRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    text: str = Field(min_length=1)
    model_id: str = DEFAULT_MODEL_ID


class EmbedResponse(BaseModel):
    embedding: list[float]


def create_app(model_name: str | None = None, device: str = "auto", warmup: bool = True) -> FastAPI:
    app = FastAPI(title="Local Embedding Service", version="0.1.0")
    resolved_device = None if device == "auto" else device
    model_specs = dict(MODEL_REGISTRY)
    if model_name:
        model_specs[DEFAULT_MODEL_ID] = ModelSpec(model_name, MODEL_REGISTRY[DEFAULT_MODEL_ID].expected_dim)
    loaded_dims: dict[str, int] = {}

    @lru_cache(maxsize=len(MODEL_REGISTRY))
    def get_model(model_id: str) -> Any:
        from sentence_transformers import SentenceTransformer

        spec = model_specs[model_id]
        if resolved_device:
            return SentenceTransformer(
                spec.model_name,
                device=resolved_device,
                model_kwargs={"low_cpu_mem_usage": False},
            )
        return SentenceTransformer(spec.model_name, model_kwargs={"low_cpu_mem_usage": False})

    def encode_text(model_id: str, text: str) -> list[float]:
        if model_id not in model_specs:
            raise HTTPException(status_code=404, detail=f"Unknown embedding model_id: {model_id}")
        vector = get_model(model_id).encode([text], normalize_embeddings=True, convert_to_numpy=True)[0]
        if hasattr(vector, "astype"):
            vector = vector.astype(float)
        if hasattr(vector, "tolist"):
            values = vector.tolist()
        else:
            values = list(vector)
        loaded_dims[model_id] = len(values)
        return [float(value) for value in values]

    def warm_model() -> None:
        start = time.perf_counter()
        spec = model_specs[DEFAULT_MODEL_ID]
        logger.info("Warming local embedding model %s on device %s", spec.model_name, device)
        encode_text(DEFAULT_MODEL_ID, "warmup")
        logger.info("Local embedding model warm-up finished in %.2fs", time.perf_counter() - start)

    @app.on_event("startup")
    def startup() -> None:
        if warmup:
            threading.Thread(target=warm_model, name="local-embedding-warmup", daemon=True).start()

    @app.get("/health")
    def health() -> dict[str, object]:
        torch_cuda_available = False
        try:
            import torch

            torch_cuda_available = bool(torch.cuda.is_available())
        except Exception:
            torch_cuda_available = False
        return {
            "status": "ok",
            "model": model_specs[DEFAULT_MODEL_ID].model_name,
            "device": device,
            "torch_cuda_available": torch_cuda_available,
            "loaded_models": dict(loaded_dims),
        }

    @app.post("/embed", response_model=EmbedResponse)
    def embed(request: EmbedRequest) -> EmbedResponse:
        return EmbedResponse(embedding=encode_text(request.model_id, request.text))

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local embedding service used by the Docker API.")
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5", help="SentenceTransformer model name")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8010, help="Port to bind")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto", help="SentenceTransformer device")
    parser.add_argument("--no-warmup", action="store_true", help="Disable background model warm-up")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    uvicorn.run(create_app(args.model, device=args.device, warmup=not args.no_warmup), host=args.host, port=args.port)
