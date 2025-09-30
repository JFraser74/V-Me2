from fastapi import APIRouter, Request, Header, HTTPException, Body
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional, Dict, Any
import hmac, hashlib, base64, secrets
from datetime import datetime, timedelta
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


# --- SSE token helpers -------------------------------------------------
def _b64u_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode('ascii')

def _b64u_decode(s: str) -> bytes:
    # add padding
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode('ascii'))

def _get_stream_secret() -> Optional[bytes]:
    s = os.getenv('OPS_STREAM_SECRET') or os.getenv('SETTINGS_ADMIN_TOKEN')
    if not s:
        return None
    return s.encode('utf-8')

def _make_token(payload: dict, ttl_seconds: int = 300) -> str:
    secret = _get_stream_secret()
    exp = int(time.time()) + int(ttl_seconds)
    payload2 = dict(payload)
    payload2['exp'] = exp
    payload2['nonce'] = secrets.token_hex(8)
    j = json.dumps(payload2, separators=(',', ':'), sort_keys=True).encode('utf-8')
    b64 = _b64u_encode(j)
    if secret is None:
        # unsigned token (not recommended) - still usable in dev if no secret configured
        sig = _b64u_encode(b'')
    else:
        mac = hmac.new(secret, j, hashlib.sha256).digest()
        sig = _b64u_encode(mac)
    return f"{b64}.{sig}", payload2['exp']

def _validate_token(token: str) -> Optional[dict]:
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        b64, sig = parts
        j = _b64u_decode(b64)
        payload = json.loads(j.decode('utf-8'))
        exp = int(payload.get('exp', 0))
        if int(time.time()) > exp:
            return None
        secret = _get_stream_secret()
        if secret is None:
            # if no secret configured, accept unsigned tokens
            return payload
        expected_mac = hmac.new(secret, j, hashlib.sha256).digest()
        provided = _b64u_decode(sig)
        if not hmac.compare_digest(expected_mac, provided):
            return None
        return payload
    except Exception:
        return None



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


@router.post('/stream_tokens')
async def create_stream_token(request: Request, payload: Dict[str, Any] = Body(...), x_admin_token: Optional[str] = Header(None)):
    """Admin-gated: issue a short-lived token for a given task_id used for SSE streams."""
    if not _is_admin(request, x_admin_token):
        return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
    try:
        task_id = int(payload.get('task_id'))
    except Exception:
        raise HTTPException(400, 'task_id required')
    token, exp = _make_token({'task_id': task_id}, ttl_seconds=300)
    return {'token': token, 'expires_at': datetime.utcfromtimestamp(exp).isoformat() + 'Z'}


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
    # allow either admin token (legacy) or a time-limited stream token via query param
    token = None
    try:
        token = request.query_params.get('token')
    except Exception:
        token = None
    if token:
        payload = _validate_token(token)
        if not payload:
            return JSONResponse({'ok': False, 'error': 'invalid or expired token'}, status_code=403)
        if int(payload.get('task_id', -1)) != int(task_id):
            return JSONResponse({'ok': False, 'error': 'token task_id mismatch'}, status_code=403)
    else:
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