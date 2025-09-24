from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from lib.supabase_client import safe_log_message, create_session
from graph.va_graph import get_graph
from fastapi import Query
from typing import List, Dict
from lib import supabase_client as _sbmod
from pathlib import Path

# try to import workspace read/write tools; fall back to local FS
try:
    from tools.codespace import read_file_tool, write_file_tool
    _TOOLING_AVAILABLE = True
except Exception:
    _TOOLING_AVAILABLE = False

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatIn(BaseModel):
    message: str
    session_id: Optional[str] = None
    label: Optional[str] = None


class ChatOut(BaseModel):
    session_id: str
    text: str


@router.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn):
    if not payload.message:
        raise HTTPException(status_code=400, detail="message required")

    # Ensure a numeric session id exists in DB (BIGINT)
    session_id = payload.session_id
    if not session_id:
        sid = create_session(payload.label or "default")
        session_id = str(sid) if sid is not None else ""

    # Prepare graph input
    graph = get_graph()
    state_in = {
        "session_id": session_id,
        "messages": [{"role": "user", "content": payload.message}],
    }
    result = graph.invoke(
        state_in,
        config={"configurable": {"thread_id": session_id or None}},
    )
    text = result.get("last_text", "")

    # Log reply (best-effort)
    try:
        # prefer integer session IDs when possible for DB storage
        sid_for_log = session_id
        if isinstance(sid_for_log, str):
            try:
                sid_for_log = int(sid_for_log)
            except Exception:
                sid_for_log = None
        safe_log_message(session_id=sid_for_log, role="assistant", content=text)
    except Exception:
        pass

    return ChatOut(session_id=session_id, text=text)


@router.get("/messages")
def messages(session_id: str = Query(...), limit: int = Query(12)) -> List[Dict]:
    """Return recent messages for a session (best-effort)."""
    sb = None
    try:
        sb = _sbmod._client()
    except Exception:
        sb = None
    if not sb:
        return []
    try:
        res = (sb.table("va_messages")
                 .select("*")
                 .eq("session_id", int(session_id))
                 .order("id", desc=True)
                 .limit(limit)
                 .execute())
        rows = res.data or []
        rows.reverse()
        return rows
    except Exception:
        return []


# ===== added: analytics + safe file read/write =====
@router.get("/api/sessions")
def api_sessions(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    # Returns {total_sessions,total_messages,last_session,recent:[...]}; [] if SB not configured.
    try:
        from lib import supabase_client as _sbmod2
        sb = _sbmod2._client()
    except Exception:
        sb = None
    if not sb:
        return {"total_sessions": None, "total_messages": None, "last_session": None, "recent": []}
    try:
        # total sessions/messages (best effort with count='exact')
        sess = sb.table("va_sessions").select("*", count="exact").order("id", desc=True).range((page-1)*page_size, page*page_size-1).execute()
        total_sessions = getattr(sess, "count", None)
        recent = sess.data or []
        last_session = recent[0] if recent else None
        msgs = sb.table("va_messages").select("*", count="exact").limit(1).execute()
        total_messages = getattr(msgs, "count", None)
        return {"total_sessions": total_sessions, "total_messages": total_messages, "last_session": last_session, "recent": recent}
    except Exception:
        return {"total_sessions": None, "total_messages": None, "last_session": None, "recent": []}


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
def _safe_resolve(path: str) -> Path:
    p = (_PROJECT_ROOT / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if not str(p).startswith(str(_PROJECT_ROOT)):
        raise ValueError("Path escapes project root")
    return p

class ReadReq(BaseModel):
    path: str
    start: int = 0
    end: int = 200000


@router.post("/read")
def agent_read(req: ReadReq):
    # Prefer tooling implementation if available
    if _TOOLING_AVAILABLE:
        try:
            out = read_file_tool.invoke(req.model_dump())
            return {"ok": True, "result": out}
        except Exception as e:
            return {"ok": False, "error": f"tool read error: {e}"}

    # Fallback to safe filesystem read
    try:
        _PROJECT_ROOT = Path(__file__).resolve().parents[1]
        def _safe_resolve(path: str) -> Path:
            p = (_PROJECT_ROOT / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
            if not str(p).startswith(str(_PROJECT_ROOT)):
                raise ValueError("Path escapes project root")
            return p

        fp = _safe_resolve(req.path)
        if not fp.exists() or not fp.is_file():
            return {"ok": False, "error": f"Not a file: {fp}"}
        data = fp.read_text(errors="replace")
        return {"ok": True, "content": data[req.start:req.end]}
    except Exception as e:
        return {"ok": False, "error": f"{e}"}


class WriteReq(BaseModel):
    path: str
    content: str
    confirm: bool = False
    create_dirs: bool = True


@router.post("/write")
def agent_write(req: WriteReq):
    if _TOOLING_AVAILABLE:
        try:
            out = write_file_tool.invoke(req.model_dump())
            return {"ok": True, "result": out}
        except Exception as e:
            return {"ok": False, "error": f"tool write error: {e}"}

    try:
        _PROJECT_ROOT = Path(__file__).resolve().parents[1]
        def _safe_resolve(path: str) -> Path:
            p = (_PROJECT_ROOT / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
            if not str(p).startswith(str(_PROJECT_ROOT)):
                raise ValueError("Path escapes project root")
            return p

        fp = _safe_resolve(req.path)
        if req.create_dirs:
            fp.parent.mkdir(parents=True, exist_ok=True)
        original = ""
        if fp.exists():
            try:
                original = fp.read_text(errors="replace")
            except Exception:
                original = "(binary or unreadable)"
        if not req.confirm:
            return {"ok": True, "dry_run": True, "note": f"Would write {len(req.content)} bytes to {fp.relative_to(_PROJECT_ROOT)}. Set confirm=true to persist."}
        fp.write_text(req.content)
        return {"ok": True, "dry_run": False, "bytes": len(req.content), "path": str(fp.relative_to(_PROJECT_ROOT))}
    except Exception as e:
        return {"ok": False, "error": f"{e}"}


@router.get("/sessions")
def sessions(limit: int = Query(20)) -> List[Dict]:
    """List recent sessions (id, label, created_at). Returns [] if SB not configured."""
    try:
        sb = _sbmod._client()
    except Exception:
        sb = None
    if not sb:
        return []
    try:
        res = (sb.table("va_sessions")
                 .select("id,label,created_at")
                 .order("id", desc=True)
                 .limit(limit)
                 .execute())
        return res.data or []
    except Exception:
        return []


@router.get("/select")
def select(table: str = Query(...), limit: int = Query(5), order: str | None = None) -> List[Dict]:
    """Simple read-only table select. Args: table, limit, order ('created_at desc')."""
    try:
        sb = _sbmod._client()
    except Exception:
        sb = None
    if not sb:
        return []
    try:
        q = sb.table(table).select("*")
        if order:
            parts = order.split()
            col = parts[0]
            desc = len(parts) > 1 and parts[1].lower().startswith("desc")
            q = q.order(col, desc=desc)
        q = q.limit(limit)
        res = q.execute()
        return res.data or []
    except Exception:
        return []
