from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.search.prompt_methods import METHODS
from src.search.searcher import MeetingSearcher

app = FastAPI(title="VDT Meeting Search", version="0.1.0")
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
    method: str = Field(default="embedding")

@lru_cache(maxsize=1)
def get_searcher() -> MeetingSearcher:
    return MeetingSearcher()

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/search")
def search(request: SearchRequest) -> dict:
    method = request.method.strip().lower()
    if method not in METHODS:
        raise HTTPException(status_code=400, detail=f"Unknown prompt search method: {request.method}")
    try:
        return get_searcher().search(request.query, request.top_k, request.speaker, method)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@app.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: str) -> dict:
    try:
        meeting = get_searcher().get_meeting(meeting_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting