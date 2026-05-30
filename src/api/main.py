from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from elasticsearch import Elasticsearch
from pydantic import BaseModel, Field

from src.core.config import settings
from src.indexing.bulk_index import (
    DEFAULT_INDEX,
    create_index,
    delete_meeting,
    index_chunk_docs,
)
from src.preprocessing.chunking import chunk_meetings
from src.search.hybrid import search_meetings

app = FastAPI(title=settings.app_name)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Bảo vệ các endpoint ghi/xóa. Đặt qua biến môi trường INGEST_API_KEY."""
    if x_api_key != settings.ingest_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class Turn(BaseModel):
    speaker: str | None = None
    speaker_agent: str | None = None
    speaker_role: str | None = None
    text: str
    time_start: float | None = None
    time_end: float | None = None


class MeetingIn(BaseModel):
    meeting_id: str = Field(min_length=1)
    raw_meeting_id: str | None = None
    source: str = Field(min_length=1)
    title: str | None = None
    date: str | None = None
    start_time: str | None = None
    participants: list[str] = []
    turns: list[Turn] = Field(min_length=1)
    metadata: dict = {}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    mode: str = Field(default="hybrid", pattern="^(bm25|semantic|hybrid)$")
    source: str | None = None
    speaker: str | None = None
    date_range: list[str] | None = None
    parse_prompt: bool = True


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
        date_range=request.date_range,
        parse_prompt=request.parse_prompt,
    )


_frontend_dir = Path(__file__).resolve().parents[2] / "frontend"


def _reindex_meeting(meeting: dict) -> int:
    """Chunk → embed → index một meeting; thay thế toàn bộ chunk cũ (atomic theo góc nhìn API)."""
    chunks = chunk_meetings(
        [meeting],
        target_tokens=max(128, settings.chunk_size - settings.chunk_overlap),
        max_tokens=settings.chunk_size,
        overlap_tokens=settings.chunk_overlap,
    )
    if not chunks:
        raise HTTPException(status_code=400, detail="Meeting produced no chunks (empty turns?)")
    es = Elasticsearch(settings.es_host, request_timeout=60)
    try:
        create_index(es, index_name=DEFAULT_INDEX)
        delete_meeting(es, meeting["meeting_id"], index_name=DEFAULT_INDEX)
        count = index_chunk_docs(es, chunks, index_name=DEFAULT_INDEX)
        es.indices.refresh(index=DEFAULT_INDEX)
        return count
    finally:
        es.close()


@app.post("/meetings", status_code=201)
async def create_meeting(meeting: MeetingIn, _: None = Depends(require_api_key)):
    count = _reindex_meeting(meeting.model_dump())
    return {"meeting_id": meeting.meeting_id, "indexed_chunks": count}


@app.put("/meetings/{meeting_id}")
async def update_meeting(meeting_id: str, meeting: MeetingIn, _: None = Depends(require_api_key)):
    if meeting.meeting_id != meeting_id:
        raise HTTPException(status_code=400, detail="meeting_id in path and body must match")
    count = _reindex_meeting(meeting.model_dump())
    return {"meeting_id": meeting_id, "indexed_chunks": count}


@app.delete("/meetings/{meeting_id}")
async def remove_meeting(meeting_id: str, _: None = Depends(require_api_key)):
    es = Elasticsearch(settings.es_host, request_timeout=60)
    try:
        deleted = delete_meeting(es, meeting_id, index_name=DEFAULT_INDEX)
    finally:
        es.close()
    return {"meeting_id": meeting_id, "deleted_chunks": deleted}


if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
