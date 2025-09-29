from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Optional
import time
from vme_lib import supabase_client as _sb

router = APIRouter(prefix="/api/threads", tags=["threads"])


@router.post("")
def create_thread(label: Optional[str] = None):
    """Create a new session/thread. Returns {id, title} where id is a stringified bigint or empty string if unavailable."""
    try:
        sid = _sb.create_session(label)
        return {"id": str(sid) if sid is not None else "", "title": label or ""}
    except Exception:
        return {"id": "", "title": label or ""}


@router.put("/{id}/title")
def update_title(id: int, title: str):
    try:
        ok = _sb.update_session_title(id, title)
        return {"ok": bool(ok), "id": str(id), "title": title}
    except Exception:
        return {"ok": False, "id": str(id), "title": title}


@router.get("")
def recent_threads(limit: int = Query(20, ge=1, le=200)):
    """Return recent named threads (label not null/empty) ordered by created_at desc."""
    sb = _sb._client()
    if not sb:
        return {"items": []}
    try:
        res = (sb.table("va_sessions")
               .select("id,label,created_at")
               .not_("label", "is", None)
               .neq("label", "")
               .order("created_at", desc=True)
               .limit(limit)
               .execute())
        rows = res.data or []
        items = [{"id": str(r.get("id")), "title": r.get("label"), "created_at": r.get("created_at")} for r in rows]
        return {"items": items}
    except Exception:
        return {"items": []}


@router.get("/{id}/messages")
def thread_messages(id: int, limit: int = Query(200, ge=1, le=5000)):
    sb = _sb._client()
    if not sb:
        return {"items": []}
    try:
        res = (sb.table("va_messages")
               .select("id,role,content,created_at")
               .eq("session_id", int(id))
               .order("created_at", desc=False)
               .limit(limit)
               .execute())
        rows = res.data or []
        items = []
        for r in rows:
            items.append({
                "id": r.get("id"),
                "role": r.get("role"),
                "content": r.get("content"),
                "created_at": r.get("created_at"),
            })
        return {"items": items}
    except Exception:
        return {"items": []}
