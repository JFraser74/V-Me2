from fastapi import APIRouter, HTTPException, Query
import os
import sys
try:
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PROJECT_ROOT and _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
except Exception:
    pass
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

import os
from vme_lib.supabase_client import safe_log_message, create_session, safe_log_tool_event, select_tool_events
from graph.va_graph import get_graph
from fastapi import Query
from typing import List, Dict
from vme_lib import supabase_client as _sbmod
from pathlib import Path
import asyncio
import json
from fastapi.responses import StreamingResponse

from pydantic import Field

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
    # Development/testing: allow a local/mock LLM response when DEV_LOCAL_LLM is set.
    # This is useful when you don't have a usable OpenAI secret key available.
    if os.getenv("DEV_LOCAL_LLM", "").lower() in ("1", "true", "yes"):
        # Keep the fake LLM deterministic but ensure the prefix matches test expectations.
        text = f"Echo: {payload.message}"
        # best-effort log of assistant text
        try:
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

    graph = get_graph()
    state_in = {
        "session_id": session_id,
        "messages": [{"role": "user", "content": payload.message}],
    }
    # Best-effort: also log the user message when we have a session
    try:
        if session_id:
            safe_log_message(session_id=session_id, role="user", content=payload.message)
    except Exception:
        pass
    try:
        result = graph.invoke(
            state_in,
            config={"configurable": {"thread_id": session_id or None}},
        )
    except Exception as e:
        # LangGraph/LangChain/OpenAI may raise a BadRequest when message roles
        # like 'tool' are passed directly to the OpenAI chat endpoint. Detect
        # that specific case and return a helpful error so the developer can
        # decide whether the issue is the key, the prompt, or the graph/tooling.
        msg = str(e)
        if "messages with role 'tool'" in msg or "role 'tool'" in msg:
            raise HTTPException(status_code=400, detail=(
                "OpenAI rejected the request: messages with role 'tool' were sent to the model. "
                "This typically means the agent included tool messages in the chat payload. "
                "Try running with DEV_LOCAL_LLM=true to avoid external calls, or adjust the graph/tool integration."))
        # For other errors, surface a 500 with the original message for debugging
        raise HTTPException(status_code=500, detail=f"agent error: {msg}")
    text = result.get("last_text", "")

    # Log assistant reply (best-effort)
    safe_log_message(session_id=session_id, role="assistant", content=text)

    # Log any tool events captured by the graph (best-effort)
    try:
        for evt in result.get("tool_events", []) or []:
            safe_log_tool_event(session_id=session_id, tool_name=evt.get("tool_name") or "unknown", input_json=evt.get("input_json"), output_json=evt.get("output_json"))
    except Exception:
        pass

    return ChatOut(session_id=session_id, text=text)


@router.get("/tool_events")
def tool_events(session_id: str, limit: int = Query(10, ge=1, le=50)):
    """
    Return recent tool events for a session.
    `limit` is clamped to [1, 50] using FastAPI's Query validation.
    """
    try:
        events = select_tool_events(session_id=session_id, limit=int(limit))
        return {"items": events or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        from vme_lib import supabase_client as _sbmod2
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


@router.get("/ls")
def agent_ls(path: str = "."):
    """List directory contents under project root. Uses tools.codespace.ls_tool if available; otherwise falls back to os.listdir.

    The endpoint is sandboxed to the repository root; attempts to escape will be rejected.
    """
    try:
        target = _safe_resolve(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Prefer tooling implementation when available
    if _TOOLING_AVAILABLE:
        try:
            out = read_file_tool.invoke({"path": str(target), "start": 0, "end": 0})
            # The codespace tooling exposes a separate ls tool; try to call it if present
            try:
                from tools.codespace import ls_tool as _ls_tool
                res = _ls_tool.invoke({"path": str(target)})
                # Normalize items: tool may return list[str], list[dict], or a single
                # string containing newline-separated lines like 'DIR\tname' or 'FILE\tname'.
                if isinstance(res, str):
                    items = []
                    for line in res.splitlines():
                        if not line.strip():
                            continue
                        parts = line.split("\t", 1)
                        if len(parts) == 2:
                            kind, name = parts
                        else:
                            kind, name = "FILE", parts[0]
                        items.append({"name": name, "is_dir": kind.strip().upper().startswith("DIR"), "size": None})
                elif isinstance(res, list) and res and isinstance(res[0], str):
                    items = [{"name": n, "is_dir": False, "size": None} for n in res]
                else:
                    items = res
                return {"ok": True, "path": str(target.relative_to(_PROJECT_ROOT)), "items": items}
            except Exception:
                # Fall back to tooling read result if ls not available
                return {"ok": True, "path": str(target.relative_to(_PROJECT_ROOT)), "items": []}
        except Exception:
            # Continue to filesystem fallback
            pass

    # Filesystem fallback: list entries (names + basic metadata)
    try:
        items = []
        for name in sorted(os.listdir(target)):
            p = target / name
            items.append({
                "name": name,
                "is_dir": p.is_dir(),
                "size": p.stat().st_size if p.exists() and p.is_file() else None,
            })
        return {"ok": True, "path": str(target.relative_to(_PROJECT_ROOT)), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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


# Planner hand-off: create a task server-side and enqueue it (no external HTTP hop)
class PlanIn(BaseModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class PlanOut(BaseModel):
    task_id: int


@router.post("/plan", response_model=PlanOut)
def plan(in_: PlanIn):
    """Enqueue a task into the Ops runner (server-side enqueue, no external HTTP)."""
    try:
        # Import at call time so tests can monkeypatch lib.ops_service.enqueue_task
        try:
            from lib.ops_service import enqueue_task as enqueue_ops_task
        except Exception:
            enqueue_ops_task = None
        if enqueue_ops_task is None:
            raise RuntimeError('enqueue not available')
        tid = enqueue_ops_task(in_.title.strip(), in_.body.strip())
        return PlanOut(task_id=int(tid))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to enqueue task: {e}")


# --- SSE streaming endpoint (top-level) ---------------------------------------
@router.get("/stream")
async def stream(session_id: str | None = Query(None), label: str | None = Query(None)):
    """Server-Sent Events (SSE) endpoint that streams assistant output.

    - In DEV_LOCAL_LLM or when OPENAI_API_KEY is missing, emits deterministic ticks
      then a final done message (useful for tests and fake mode).
    - If the graph exposes a streaming interface (e.g., `stream_invoke`), this
      will attempt to use it; otherwise it falls back to a single final message.
    """

    # Ensure a session id
    sid = session_id
    if not sid:
        try:
            sidv = create_session(label or "stream")
            sid = str(sidv) if sidv is not None else ""
        except Exception:
            sid = ""

    async def event_generator():
        # Fake/local mode: deterministic tick events
        if os.getenv("DEV_LOCAL_LLM", "").lower() in ("1", "true", "yes") or not os.getenv("OPENAI_API_KEY"):
            # Emit a few thinking ticks, then a final done event with an echo
            for i in range(4):
                payload = {"type": "tick", "text": f"thinking {i+1}/4"}
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0.15)
            final = {"type": "done", "text": f"Echo stream for session {sid or ''}"}
            # best-effort log
            try:
                safe_log_message(session_id=sid, role="assistant", content=final["text"])
            except Exception:
                pass
            yield f"data: {json.dumps(final)}\n\n"
            return

        # Try to use the graph's streaming API if present
        try:
            graph = get_graph()
            # If graph provides an async generator interface 'stream_invoke', use it
            if hasattr(graph, "stream_invoke"):
                async for chunk in graph.stream_invoke({"session_id": sid, "messages": [{"role": "user", "content": ""}]}):
                    # chunk expected to be dict-like with 'delta' or 'text'
                    try:
                        if isinstance(chunk, dict):
                            payload = {"type": "chunk", "data": chunk}
                            yield f"data: {json.dumps(payload)}\n\n"
                        else:
                            yield f"data: {json.dumps({"type": "chunk", "text": str(chunk)})}\n\n"
                    except Exception:
                        yield f"data: {json.dumps({"type": "chunk", "text": str(chunk)})}\n\n"
                # After streaming, attempt to get final text
                try:
                    res = graph.invoke({"session_id": sid, "messages": [{"role": "user", "content": ""}]})
                    final_text = res.get("last_text", "")
                except Exception:
                    final_text = ""
                payload = {"type": "done", "text": final_text}
                yield f"data: {json.dumps(payload)}\n\n"
                return
        except Exception:
            # fall through to non-stream fallback
            pass

        # Fallback: no streaming available, call graph.invoke once and return final message
        try:
            graph = get_graph()
            res = graph.invoke({"session_id": sid, "messages": [{"role": "user", "content": ""}]})
            final_text = res.get("last_text", "")
            payload = {"type": "done", "text": final_text}
            # log best-effort
            try:
                safe_log_message(session_id=sid, role="assistant", content=final_text)
            except Exception:
                pass
            yield f"data: {json.dumps(payload)}\n\n"
            return
        except Exception:
            # Last-resort simulated ticks
            for i in range(3):
                payload = {"type": "tick", "text": f"thinking {i+1}/3"}
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0.2)
            yield f"data: {json.dumps({"type": "done", "text": ""})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
