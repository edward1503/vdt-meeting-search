from fastapi import FastAPI
from elasticsearch import Elasticsearch
from pydantic import BaseModel, Field

from src.core.config import settings
from src.search.hybrid import search_meetings

app = FastAPI(title=settings.app_name)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    mode: str = Field(default="hybrid", pattern="^(bm25|semantic|hybrid)$")
    source: str | None = None
    speaker: str | None = None


@app.get("/health")
async def health():
    es = Elasticsearch(settings.es_host)
    try:
        es_health = es.cluster.health()
        es_status = es_health["status"]
    except Exception as e:
        es_status = f"unavailable: {e}"
    finally:
        es.close()
    return {"status": "ok", "elasticsearch": es_status}


@app.post("/search")
async def search(request: SearchRequest):
    return search_meetings(
        query=request.query,
        top_k=request.top_k,
        mode=request.mode,
        source=request.source,
        speaker=request.speaker,
    )
