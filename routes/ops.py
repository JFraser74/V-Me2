from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional, Dict, Any
import os, json, threading, time
from collections import deque
from vme_lib import supabase_client as _sbmod

router = APIRouter(prefix="/ops", tags=["ops"])

# In-memory stores when Supabase not configured
_tasks_store: Dict[int, Dict[str, Any]] = {}
_task_events: Dict[int, deque] = {}
_task_lock = threading.Lock()
_next_inproc_id = 1

# Admin gating helper
def _is_admin(request: Request, x_admin_token: Optional[str]):
    allowed = set()
    try:
        t = os.getenv('SETTINGS_ADMIN_TOKEN') or _sbmod.settings_get('SETTINGS_ADMIN_TOKEN')
        if t: allowed.add(t)
    except Exception:
        pass
    try:
        t2 = os.getenv('CI_SETTINGS_ADMIN_TOKEN') or _sbmod.settings_get('CI_SETTINGS_ADMIN_TOKEN')
        if t2: allowed.add(t2)
    except Exception:
        pass
    if allowed:
        # allow header or query param 'admin_token' (useful for EventSource)
        if x_admin_token is not None and x_admin_token in allowed:
            return True
        try:
            q = request.query_params.get('admin_token') if request and hasattr(request, 'query_params') else None
            if q and q in allowed:
                return True
        except Exception:
            pass
        return False
    # no tokens configured -> restrict to localhost
    host = request.client.host if request.client else None
    return host in ("127.0.0.1", "::1", "localhost", None)


def _persist_task(title: str, body: Optional[str]) -> int:
    """Try to persist task to Supabase, otherwise allocate in-proc id and store."""
    try:
        sb = _sbmod._client()
    except Exception:
        sb = None
    if sb:
        try:
            res = sb.table('va_tasks').insert({'title': title, 'body': body}).execute()
            return int(res.data[0]['id'])
        except Exception:
            pass
    global _next_inproc_id
    with _task_lock:
        tid = _next_inproc_id
        _next_inproc_id += 1
        _tasks_store[tid] = {'id': tid, 'title': title, 'body': body, 'status': 'queued', 'created_at': time.time()}
        _task_events[tid] = deque()
        return tid


def _append_event(task_id: int, kind: str, data: dict):
    """Persist event to Supabase if available, otherwise keep in-memory deque (max 200)."""
    try:
        sb = _sbmod._client()
    except Exception:
        sb = None
    if sb:
        try:
            sb.table('va_task_events').insert({'task_id': int(task_id), 'kind': kind, 'data': data}).execute()
        except Exception:
            pass
    else:
        dq = _task_events.get(task_id)
        if dq is None:
            dq = deque()
            _task_events[task_id] = dq
        dq.append({'created_at': time.time(), 'kind': kind, 'data': data})
        # bound it
        while len(dq) > 200:
            dq.popleft()


@router.post('/tasks')
async def create_task(request: Request, payload: Dict[str, Any], x_admin_token: Optional[str] = Header(None)):
    if not _is_admin(request, x_admin_token):
        return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
    title = payload.get('title')
    body = payload.get('body')
    if not title:
        raise HTTPException(400, 'title required')
    tid = _persist_task(title, body)
    # enqueue for local runner (if present)
    try:
        from ops_runner import enqueue_task
        enqueue_task({'id': tid, 'title': title, 'body': body})
    except Exception:
        pass
    return {'id': tid}


@router.get('/tasks')
async def list_tasks(limit: int = 20, x_admin_token: Optional[str] = Header(None), request: Request = None):
    # admin-gated read
    if not _is_admin(request, x_admin_token):
        return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
    try:
        sb = _sbmod._client()
    except Exception:
        sb = None
    if sb:
        try:
            res = sb.table('va_tasks').select('*').order('created_at', desc=True).limit(limit).execute()
            return {'items': res.data or []}
        except Exception:
            pass
    # fallback to in-proc
    items = sorted((_tasks_store or {}).values(), key=lambda x: x.get('created_at', 0), reverse=True)[:limit]
    return {'items': items}


@router.get('/tasks/{task_id}')
async def get_task(task_id: int, x_admin_token: Optional[str] = Header(None), request: Request = None):
    if not _is_admin(request, x_admin_token):
        return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
    try:
        sb = _sbmod._client()
    except Exception:
        sb = None
    if sb:
        try:
            res = sb.table('va_tasks').select('*').eq('id', int(task_id)).limit(1).execute()
            rows = res.data or []
            if rows:
                return rows[0]
        except Exception:
            pass
    return _tasks_store.get(task_id) or {'id': task_id, 'status': 'unknown'}


@router.post('/tasks/{task_id}/cancel')
async def cancel_task(task_id: int, x_admin_token: Optional[str] = Header(None), request: Request = None):
    if not _is_admin(request, x_admin_token):
        return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
    # mark cancelled
    try:
        sb = _sbmod._client()
    except Exception:
        sb = None
    if sb:
        try:
            sb.table('va_tasks').update({'status': 'cancelled'}).eq('id', int(task_id)).execute()
        except Exception:
            pass
    if task_id in _tasks_store:
        _tasks_store[task_id]['status'] = 'cancelled'
    _append_event(task_id, 'log', {'msg': 'cancelled'})
    return {'ok': True}


@router.get('/tasks/{task_id}/stream')
async def task_stream(request: Request, task_id: int, x_admin_token: Optional[str] = Header(None)):
    if not _is_admin(request, x_admin_token):
        return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)

    # simple SSE generator subscribing to in-proc events or querying Supabase every second
    async def gen():
        # If DEV_LOCAL_LLM fake mode, emit deterministic ticks then done
        if os.getenv('DEV_LOCAL_LLM', '').lower() in ('1', 'true', 'yes'):
            for i in range(4):
                payload = {'kind': 'tick', 'seq': i+1, 'msg': f'tick {i+1}'}
                yield f"data: {json.dumps(payload)}\n\n"
                await __import__('asyncio').sleep(0.1)
            payload = {'kind': 'done'}
            yield f"data: {json.dumps(payload)}\n\n"
            return

        last_idx = 0
        # first, if in-proc buffer exists, yield anything present
        dq = _task_events.get(task_id)
        if dq:
            for ev in list(dq):
                yield f"data: {json.dumps(ev)}\n\n"
        # then poll Supabase for new events
        while True:
            if await request.is_disconnected():
                return
            try:
                sb = _sbmod._client()
            except Exception:
                sb = None
            if sb:
                try:
                    res = sb.table('va_task_events').select('*').eq('task_id', int(task_id)).order('id', asc=True).execute()
                    rows = res.data or []
                    for r in rows:
                        yield f"data: {json.dumps(r)}\n\n"
                except Exception:
                    pass
            else:
                dq = _task_events.get(task_id)
                if dq:
                    for ev in list(dq):
                        yield f"data: {json.dumps(ev)}\n\n"
            await __import__('asyncio').sleep(0.5)

    return StreamingResponse(gen(), media_type='text/event-stream')