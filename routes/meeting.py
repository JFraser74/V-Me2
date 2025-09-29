from __future__ import annotations
import os, time, uuid
from typing import Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/meeting", tags=["meeting"])

_MEETING_FAKE = lambda: os.getenv("MEETING_FAKE", "1") == "1"

# In-memory store only for fake mode (CI/tests)
_store: Dict[str, List[dict]] = {}


class BeginOut(BaseModel):
    meeting_id: str
    started_at: float = Field(default_factory=lambda: time.time())


class IngestIn(BaseModel):
    meeting_id: str
    text: str
    ts: float | None = None


class IngestOut(BaseModel):
    ok: bool = True
    count: int


class EndIn(BaseModel):
    meeting_id: str


class EndOut(BaseModel):
    summary: str
    bullets: List[str]
    segment_count: int


@router.post("/begin", response_model=BeginOut)
def begin():
    mid = str(uuid.uuid4())
    if _MEETING_FAKE():
        _store[mid] = []
    return BeginOut(meeting_id=mid)


@router.post("/ingest", response_model=IngestOut)
def ingest(payload: IngestIn):
    if not payload.meeting_id:
        raise HTTPException(400, "meeting_id required")
    if not payload.text or not payload.text.strip():
        raise HTTPException(400, "text required")
    if _MEETING_FAKE():
        if payload.meeting_id not in _store:
            raise HTTPException(404, "unknown meeting_id")
        _store[payload.meeting_id].append({
            "ts": payload.ts if payload.ts is not None else time.time(),
            "text": payload.text.strip(),
        })
        return IngestOut(count=len(_store[payload.meeting_id]))
    # Real mode (stub for now)
    return IngestOut(count=0)


@router.post("/end", response_model=EndOut)
def end(payload: EndIn):
    if not payload.meeting_id:
        raise HTTPException(400, "meeting_id required")
    segs = _store.get(payload.meeting_id, []) if _MEETING_FAKE() else []
    if _MEETING_FAKE() and not segs:
        raise HTTPException(404, "unknown or empty meeting_id")

    # Fake summarizer (deterministic, testable):
    # join → split on sentence-ish boundaries → take up to 3 longest
    full = " ".join(s["text"] for s in segs)
    parts = [p.strip() for p in full.replace("\n", " ").split(".") if p.strip()]
    parts_sorted = sorted(parts, key=len, reverse=True)
    bullets = parts_sorted[:3]
    if not bullets and full:
        bullets = [full[:140]]
    summary = full if len(full) <= 400 else (full[:397] + "...")
    return EndOut(summary=summary, bullets=bullets, segment_count=len(segs))
