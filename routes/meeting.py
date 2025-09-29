from __future__ import annotations
import os, time, uuid
from typing import Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/meeting", tags=["meeting"])

_MEETING_FAKE = lambda: os.getenv("MEETING_FAKE", "1") == "1"

# In-memory store only for fake mode (CI/tests)
_store: Dict[str, List[dict]] = {}

# We'll dynamically import `lib.supabase_client` inside handlers so tests can monkeypatch its
# functions after the app / router modules are imported. This keeps startup safe while
# allowing runtime best-effort writes when helpers are available.


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
    # In fake mode we use in-memory store and a UUID meeting id
    if _MEETING_FAKE():
        _store[mid] = []
        return BeginOut(meeting_id=mid)

    # Real mode: attempt best-effort insert into Supabase to get a numeric meeting id.
    try:
        # Resolve helper at runtime so tests can monkeypatch lib.supabase_client
        import importlib
        sc = importlib.import_module("lib.supabase_client")
        insert_meeting = getattr(sc, "insert_meeting", None)
        if insert_meeting:
            try:
                mid_num = insert_meeting(label=None)
                if mid_num:
                    # return numeric id as string to keep client types stable
                    return BeginOut(meeting_id=str(mid_num))
            except Exception:
                pass
    except Exception:
        # unable to import supabase client; continue with fallback
        pass
    # Fallback: return a UUID (write-only mode will no-op if we couldn't create a row)
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

    # Real mode: best-effort insert of segment if supabase helper exists and meeting_id is numeric
    count = 0
    try:
        import importlib
        sc = importlib.import_module("lib.supabase_client")
        insert_segment = getattr(sc, "insert_segment", None)
        if insert_segment:
            try:
                mid_int = int(payload.meeting_id)
                seg_id = insert_segment(meeting_id=mid_int, text=payload.text.strip(), ts=payload.ts)
                # we don't know total count without reading DB; return 1 to indicate accepted
                if seg_id:
                    count = 1
            except ValueError:
                # non-numeric meeting id (UUID) — cannot insert into numeric PK table
                pass
    except Exception:
        pass
    return IngestOut(count=count)


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
    # In real mode, try best-effort to persist summary/bullets if we have a numeric meeting id and helper
    if not _MEETING_FAKE():
        try:
            import importlib
            sc = importlib.import_module("lib.supabase_client")
            finalize_meeting = getattr(sc, "finalize_meeting", None)
            try:
                mid_int = int(payload.meeting_id)
            except ValueError:
                mid_int = None
            if mid_int and finalize_meeting:
                try:
                    finalize_meeting(meeting_id=mid_int, summary=summary, bullets=bullets, segment_count=len(segs) or None)
                except Exception:
                    pass
        except Exception:
            pass

    return EndOut(summary=summary, bullets=bullets, segment_count=len(segs))
