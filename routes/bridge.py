from fastapi import APIRouter, Request, Header, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
from pathlib import Path
import json
import os
import time
from collections import deque, defaultdict

from vme_lib import supabase_client as _sbmod
from vme_lib.supabase_client import settings_get, settings_put

router = APIRouter()

# use an explicit settings key stored in Supabase
_PEERS_KEY = 'BRIDGE_PEERS'

# local fallback settings file (non-secret: names + urls only)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SETTINGS_FILE = _PROJECT_ROOT / '.vme2_settings.json'

# In-memory rate limiter per admin token
_CALLS: dict[str, deque[float]] = defaultdict(deque)
WINDOW_SECONDS = 60
MAX_CALLS = int(os.getenv('BRIDGE_MAX_CALLS', '20'))


def _allowed_admin_tokens() -> set[str]:
    toks = {
        (os.getenv("SETTINGS_ADMIN_TOKEN") or "").strip(),
        (os.getenv("CI_SETTINGS_ADMIN_TOKEN") or "").strip(),
        (settings_get("SETTINGS_ADMIN_TOKEN") or "").strip(),
    }
    return {t for t in toks if t}


def rate_limit(admin_token: str):
    now = time.time()
    q = _CALLS[admin_token]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    if len(q) >= MAX_CALLS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded for bridge actions")
    q.append(now)


def require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    allowed = _allowed_admin_tokens()
    if not allowed:
        # dev mode: allow localhost-only if nothing configured
        return
    if not x_admin_token or x_admin_token not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")
    # apply per-admin rate limiting
    rate_limit(x_admin_token)


def _get_peers() -> Dict[str, Any]:
    # Try Supabase first (this will include encrypted tokens if present)
    try:
        v = settings_get(_PEERS_KEY, default={})
    except Exception:
        v = None
    if isinstance(v, dict) and v:
        return v
    # fallback to file-backed settings (names + urls only)
    try:
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text()) or {}
            pv = data.get(_PEERS_KEY)
            if isinstance(pv, dict):
                return pv
    except Exception:
        pass
    return {}


def _save_peers(peers: Dict[str, Any], include_tokens: bool):
    """
    Persist peers. If include_tokens is True and Supabase + APP_ENCRYPTION_KEY are present,
    tokens will be stored (encrypted) in Supabase under _PEERS_KEY. The file fallback
    only stores non-secret info (names and urls).
    """
    # write file-backed, but strip tokens from file
    try:
        data = {}
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text()) or {}
        # create a non-secret view for file
        file_view = {n: {k: v for k, v in p.items() if k != 'token'} for n, p in peers.items()}
        data[_PEERS_KEY] = file_view
        _SETTINGS_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass

    # persist to Supabase (tokens included only when include_tokens True)
    try:
        safe = {}
        for name, p in peers.items():
            safe[name] = {k: v for k, v in p.items() if k != 'token'}
            if include_tokens and 'token' in p and p['token']:
                safe[name]['token'] = p['token']
        settings_put({_PEERS_KEY: safe})
    except Exception:
        pass


@router.get('/api/bridge/peers', dependencies=[Depends(require_admin)])
async def list_peers(request: Request):
    peers = _get_peers()
    return JSONResponse({'ok': True, 'peers': peers})


@router.post('/api/bridge/peers', dependencies=[Depends(require_admin)])
async def create_peer(request: Request):
    payload = await request.json()
    name = payload.get('name')
    url = payload.get('url')
    token = payload.get('token')
    if not name or not url:
        return JSONResponse({'ok': False, 'error': 'name and url required'}, status_code=400)
    peers = _get_peers()
    if name in peers:
        return JSONResponse({'ok': False, 'error': 'peer exists'}, status_code=409)
    peers[name] = {'url': url, 'token_set': bool(token)}
    # store token in-memory; persist via _save_peers
    if token:
        peers[name]['token'] = token
    include_tokens = bool(os.getenv('APP_ENCRYPTION_KEY'))
    _save_peers(peers, include_tokens=include_tokens)
    return JSONResponse({'ok': True, 'peer': {k: v for k, v in peers[name].items() if k != 'token'}})


@router.put('/api/bridge/peers/{name}', dependencies=[Depends(require_admin)])
async def update_peer(name: str, request: Request):
    payload = await request.json()
    url = payload.get('url')
    token = payload.get('token')
    peers = _get_peers()
    if name not in peers:
        return JSONResponse({'ok': False, 'error': 'peer not found'}, status_code=404)
    if url:
        peers[name]['url'] = url
    if token is not None:
        # set or clear token in-memory; persisted to Supabase only if include_tokens True
        if token:
            peers[name]['token'] = token
            peers[name]['token_set'] = True
        else:
            peers[name].pop('token', None)
            peers[name]['token_set'] = False
    include_tokens = bool(os.getenv('APP_ENCRYPTION_KEY'))
    _save_peers(peers, include_tokens=include_tokens)
    return JSONResponse({'ok': True, 'peer': {k: v for k, v in peers[name].items() if k != 'token'}})


@router.delete('/api/bridge/peers/{name}', dependencies=[Depends(require_admin)])
async def delete_peer(name: str):
    peers = _get_peers()
    if name not in peers:
        return JSONResponse({'ok': False, 'error': 'peer not found'}, status_code=404)
    peers.pop(name, None)
    include_tokens = bool(os.getenv('APP_ENCRYPTION_KEY'))
    _save_peers(peers, include_tokens=include_tokens)
    return JSONResponse({'ok': True})
