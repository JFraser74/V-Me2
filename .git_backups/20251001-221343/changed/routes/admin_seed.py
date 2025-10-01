from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse
from typing import Optional
from vme_lib import supabase_client as sb
import os

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _is_local_request(request: Request) -> bool:
    host = request.client.host if request.client else None
    return host in ("127.0.0.1", "::1", "localhost", None)


def _allowed_admin_tokens():
    out = set()
    try:
        t = os.getenv('SETTINGS_ADMIN_TOKEN') or sb.settings_get('SETTINGS_ADMIN_TOKEN')
        if t:
            out.add(t)
    except Exception:
        pass
    try:
        t2 = os.getenv('CI_SETTINGS_ADMIN_TOKEN') or sb.settings_get('CI_SETTINGS_ADMIN_TOKEN')
        if t2:
            out.add(t2)
    except Exception:
        pass
    return out


@router.post('/seed_memory')
async def seed_memory(request: Request, x_admin_token: Optional[str] = Header(None)):
    """Seed two foundational sessions/messages into Supabase.

    Protected: requires X-Admin-Token matching SETTINGS_ADMIN_TOKEN or CI_SETTINGS_ADMIN_TOKEN
    if configured; otherwise call must come from localhost.
    """
    allowed = _allowed_admin_tokens()
    if allowed:
        if not x_admin_token or x_admin_token not in allowed:
            return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
    else:
        if not _is_local_request(request):
            return JSONResponse({'ok': False, 'error': 'admin token not set; restricted to localhost'}, status_code=403)

    # Ensure supabase client exists
    cli = sb._client()
    if not cli:
        return JSONResponse({'ok': False, 'error': 'supabase client not configured on server'}, status_code=500)

    # Define payloads
    label_a = "System Setup & Current Status — M0"
    content_a = (
        "VME2_STATUS_V1\n"
        "build: Railway main (no-store hot asset active)\n"
        "ui: Coding panel with streaming SSE, Save & Name, Admin mode link, Ops viewer\n"
        "ops: In-app orchestrator live (create/list/get/cancel + tokenized SSE), DEV_LOCAL_LLM=fake supported\n"
        "voice: Fake-mode upload + mic UI merged; real Whisper gated by OPENAI_API_KEY & toggle\n"
        "meeting: Fake-mode scaffold + write-only Supabase wiring\n"
        "memory: va_sessions/va_messages live; threads API + Save & Name UI\n"
        "security: SETTINGS_ADMIN_TOKEN/CI_SETTINGS_ADMIN_TOKEN; OPS_STREAM_SECRET for SSE; confirm=True for write tools\n"
        "ci: deterministic flags supported; smoke workflow exists (manual dispatch by admin)\n"
        "next: planner hand-off live (/agent/plan); attachments placeholder; SSE tokens"
    )

    label_b = "Agent Personality & Operating Principles"
    content_b = (
        "PLACEHOLDER: Agent Personality & Operating Principles\n\n"
        "This is a system-level personality prompt for the in-app assistant. Replace this\n"
        "placeholder with the real system prompt when you have it. For now this row\n"
        "establishes the memory slot and will be used by the agent as baseline context."
    )

    # Idempotent: find existing sessions by label
    try:
        res_a = cli.table('va_sessions').select('*').eq('label', label_a).limit(1).execute()
        sid_a = res_a.data[0]['id'] if getattr(res_a, 'data', None) else None
    except Exception:
        sid_a = None
    if not sid_a:
        try:
            ins = cli.table('va_sessions').insert({'label': label_a}).execute()
            sid_a = ins.data[0]['id'] if getattr(ins, 'data', None) else None
        except Exception as e:
            return JSONResponse({'ok': False, 'error': 'failed to create session A', 'detail': str(e)}, status_code=500)

    try:
        res_b = cli.table('va_sessions').select('*').eq('label', label_b).limit(1).execute()
        sid_b = res_b.data[0]['id'] if getattr(res_b, 'data', None) else None
    except Exception:
        sid_b = None
    if not sid_b:
        try:
            ins = cli.table('va_sessions').insert({'label': label_b}).execute()
            sid_b = ins.data[0]['id'] if getattr(ins, 'data', None) else None
        except Exception as e:
            return JSONResponse({'ok': False, 'error': 'failed to create session B', 'detail': str(e)}, status_code=500)

    # Insert messages (safe_log_message is tolerant)
    try:
        sb.safe_log_message(sid_a, 'assistant', content_a)
        sb.safe_log_message(sid_b, 'system', content_b)
    except Exception as e:
        return JSONResponse({'ok': False, 'error': 'failed to write messages', 'detail': str(e)}, status_code=500)

    return JSONResponse({'ok': True, 'session_a': sid_a, 'session_b': sid_b})
