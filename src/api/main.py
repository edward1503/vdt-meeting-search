from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.search.searcher import MeetingSearcher

app = FastAPI(title="VDT Meeting Search", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    speaker: str | None = None
    backend: str | None = None


@lru_cache(maxsize=8)
def get_searcher(backend: str | None = None) -> MeetingSearcher:
    return MeetingSearcher(backend_name=backend or "faiss")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search")
def search(request: SearchRequest) -> dict:
    try:
        return get_searcher(request.backend).search(request.query, request.top_k, request.speaker)
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: str) -> dict:
    try:
        meeting = get_searcher().get_meeting(meeting_id)
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting
