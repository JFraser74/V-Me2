#!/usr/bin/env python3
# (2025-09-23 16:49 ET - Boot/Deploy Fix - solid)
# Early sys.path hardening: make sure the repository root is the first entry
# on sys.path before any other imports run. This is defensive for PaaS/Docker
# environments where the working directory may not be the project root.
import os
import sys
# calculate project root and ensure it's at the front of sys.path
try:
  _PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
  if _PROJECT_ROOT and _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
except Exception:
  pass
# Early diagnostic output for PaaS debugging: print minimal environment info so
# the deploy logs reveal the working directory, module search path, and whether
# the application code (including `lib/`) is present at runtime.
try:
  import json as _json
  print("DEBUG: CWD=", os.getcwd())
  print("DEBUG: __file__=", __file__)
  print("DEBUG: PROJECT_ROOT=", _PROJECT_ROOT)
  # Print first few sys.path entries to avoid huge logs
  print("DEBUG: sys.path[:5]=", _json.dumps(sys.path[:5]))
  try:
    _app_list = os.listdir('/app') if os.path.exists('/app') else []
    print("DEBUG: /app entries=", _json.dumps(_app_list[:20]))
  except Exception as _e:
    print("DEBUG: /app list error=", _e)
except Exception:
  pass
# Ensure PYTHONPATH includes the app location so subprocesses / runtime loaders
# that respect PYTHONPATH will find our package directories.
try:
  if 'PYTHONPATH' in os.environ:
    if '/app' not in os.environ['PYTHONPATH']:
      os.environ['PYTHONPATH'] = '/app:' + os.environ['PYTHONPATH']
  else:
    os.environ['PYTHONPATH'] = '/app'
except Exception:
  pass

from dotenv import load_dotenv, find_dotenv
# Locate .env (if present) so we can log which file was used at startup.
DOTENV_PATH = find_dotenv() or None
if DOTENV_PATH:
  load_dotenv(dotenv_path=DOTENV_PATH)
else:
  # fall back to default behavior (also handles env var already present in shell)
  load_dotenv()
# Ensure Path is available before we try to use it to modify sys.path.
from pathlib import Path
# Ensure the project root is on sys.path so package imports like `lib` resolve
# when running inside containers (Railway, Docker) where the working directory
# may not be the repository root.
try:
  _PROJECT_ROOT = Path(__file__).resolve().parent
  if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
except Exception:
  pass
import logging
_log = logging.getLogger("uvicorn.error")
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.staticfiles import StaticFiles as StarletteStaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from routes.agent import router as agent_router
from fastapi import Request, Header
import json
from pathlib import Path
import importlib
from vme_lib import supabase_client as _sbmod
from vme_lib.supabase_client import settings_list, settings_put, settings_refresh

app = FastAPI(title="V-Me2")


@app.on_event("startup")
def _check_openai_key():
  """Sanity-check OPENAI_API_KEY at startup and log a masked status message.

  This avoids printing secrets while giving a clear hint if the key is missing
  or looks like a project-style key (starts with 'sk-proj-') which is not
  valid for API requests.
  """
  key = os.getenv("OPENAI_API_KEY")
  if not key:
    _log.warning("OPENAI_API_KEY: MISSING (set it in .env or the environment)")
    # Log which .env (if any) was used to attempt loading environment variables
    try:
      if DOTENV_PATH:
        _log.info(".env loaded from: %s", DOTENV_PATH)
      else:
        _log.info(".env file: not found or not loaded")
    except Exception:
      pass
    return
  # Mask but show a short prefix/suffix for debugging without exposing the key
  try:
    masked = f"{key[:4]}***{key[-4:]}"
  except Exception:
    masked = "***MASKED***"
  if key.startswith("sk-proj-"):
    _log.warning("OPENAI_API_KEY appears to be a project key (sk-proj-...). This type of key cannot be used for API calls. Replace with a standard sk-... API key. %s", masked)
  else:
    _log.info("OPENAI_API_KEY loaded: %s", masked)
    try:
      if DOTENV_PATH:
        _log.info(".env loaded from: %s", DOTENV_PATH)
    except Exception:
      pass


@app.on_event("startup")
def _load_github_tokens_from_supabase():
  """Load GitHub-related tokens from Supabase-backed settings into the
  process environment if they aren't already set.

  This allows tools run inside the container (or subprocesses) to pick up
  a token stored in `va_settings` without requiring the runtime env to be
  manually updated. Tokens are fetched with `settings_get(..., decrypt=True)`.
  """
  try:
    keys = ["GITHUB_TOKEN", "GITHUB_PAT", "GITHUB_ACTOR"]
    for k in keys:
      # prefer existing environment value (explicit override), then Supabase
      if os.getenv(k):
        continue
      try:
        v = _sbmod.settings_get(k, default=None, decrypt=True)
      except Exception:
        v = None
      if v:
        # coerce non-strings
        if not isinstance(v, str):
          v = str(v)
        os.environ[k] = v
        try:
          masked = f"{v[:4]}***{v[-4:]}"
        except Exception:
          masked = "***MASKED***"
        _log.info("Loaded %s from settings: %s", k, masked)
  except Exception as e:
    _log.debug("_load_github_tokens_from_supabase: %s", e)


@app.on_event("startup")
def _load_openai_key_from_supabase():
  """If OPENAI_API_KEY isn't present in the environment, attempt to load it
  from Supabase-backed settings (va_settings) using the existing
  vme_lib.supabase_client.settings_get helper. This mirrors how GitHub
  tokens are loaded and keeps secrets in Supabase if preferred.
  """
  # Opt-in: only attempt to bootstrap OPENAI_API_KEY from Supabase if the
  # environment explicitly enables it. This avoids making network calls or
  # performing Supabase-related work during startup in PaaS environments
  # where the credentials or network may not be available.
  if os.getenv("SUPABASE_BOOTSTRAP_OPENAI", "0") != "1":
    _log.debug("SUPABASE_BOOTSTRAP_OPENAI not set; skipping OpenAI bootstrap at startup")
    return

  # Prefer an explicit env var if set
  if os.getenv("OPENAI_API_KEY"):
    return
  try:
    # settings_get may raise if Supabase isn't configured; handle safely
    val = _sbmod.settings_get("OPENAI_API_KEY", default=None, decrypt=True)
  except Exception:
    val = None
  if not val:
    _log.debug("OPENAI_API_KEY not present in env and not found in Supabase settings")
    return
  try:
    # coerce to string and set in process env
    if not isinstance(val, str):
      val = str(val)
    os.environ["OPENAI_API_KEY"] = val
    try:
      masked = f"{val[:4]}***{val[-4:]}"
    except Exception:
      masked = "***MASKED***"
    _log.info("Loaded OPENAI_API_KEY from Supabase settings: %s", masked)
  except Exception as e:
    _log.debug("Failed to apply OPENAI_API_KEY from Supabase: %s", e)

# CORS (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional static mount (only if folder exists)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
  # StaticFiles sometimes bypasses application middleware; to guarantee
  # the Cache-Control header for our hot asset after deploy, subclass
  # StaticFiles and explicitly set the header for the targeted file.
  class NoStoreStatic(StarletteStaticFiles):
    async def get_response(self, path, scope):
      resp = await super().get_response(path, scope)
      try:
        # Narrow to the hot asset we care about
        if path == "show_me_window.js" or path.endswith("/show_me_window.js"):
          resp.headers["Cache-Control"] = "no-store"
      except Exception:
        pass
      return resp

  app.mount("/static", NoStoreStatic(directory=str(STATIC_DIR)), name="static")

# include API routers
app.include_router(agent_router)
try:
  from routes.fs import router as fs_router
  if fs_router:
    app.include_router(fs_router)
except Exception:
  pass

# Ensure bridge router is mounted (safe include)
try:
  from routes.bridge import router as bridge_router
  if bridge_router:
    app.include_router(bridge_router)
except Exception:
  pass


# Ensure status router (read-only goals UI) is mounted (safe include)
try:
  from routes.status import router as status_router
  if status_router:
    app.include_router(status_router)
except Exception:
  pass


# Ensure audio router (Voice MVP) is mounted (safe include)
try:
  from routes.audio import router as audio_router
  if audio_router:
    app.include_router(audio_router)
# remove merge markers and ensure meeting router is included
except Exception:
  pass

# Ensure meeting router (Meeting Mode scaffold) is mounted (safe include)
try:
  from routes.meeting import router as meeting_router
  if meeting_router:
    app.include_router(meeting_router)
except Exception:
  pass

# Ensure threads router (Coding panel threads) is mounted (safe include)
try:
  from routes.threads import router as threads_router
  if threads_router:
    app.include_router(threads_router)
except Exception:
  pass

# Ensure ops/router (Ops orchestrator) is mounted (safe include)
try:
  from routes.ops import router as ops_router
  if ops_router:
    app.include_router(ops_router)
except Exception:
  pass

# Mount admin seeding route (provides protected /api/admin/seed_memory)
try:
  from routes.admin_seed import router as admin_seed_router
  if admin_seed_router:
    app.include_router(admin_seed_router)
except Exception:
  pass

# start internal ops runner if available
try:
  from ops_runner import start_worker
  @app.on_event('startup')
  def _start_ops_runner():
    try:
      start_worker()
    except Exception:
      pass
except Exception:
  pass

# Simple file-backed settings API used by the UI. This keeps settings local to the
# repository (no external dependency) and allows toggling features such as
# AGENT_USE_LANGGRAPH from the web UI. Settings are persisted to
# <project>/.vme2_settings.json. Changes attempt an in-process graph reload but
# a server restart may be required in some environments.
_PROJECT_ROOT = Path(__file__).resolve().parents[0]


def _load_settings():
  # defaults
  s = {
    "tts_speed": 1.0,
    "queue_reminder_minutes": 5,
    "agent_use_langgraph": os.getenv("AGENT_USE_LANGGRAPH", "0") in ("1", "true", "yes"),
  }
  # Try Supabase first
  try:
    sb = _sbmod._client()
    if sb:
      res = sb.table('va_settings').select('key,value').execute()
      rows = res.data or []
      for r in rows:
        k = r.get('key')
        v = r.get('value')
        try:
          # value is stored as JSON; coerce common keys
          if k == 'tts_speed':
            s['tts_speed'] = float(v)
          elif k == 'queue_reminder_minutes':
            s['queue_reminder_minutes'] = int(v)
          elif k == 'agent_use_langgraph':
            s['agent_use_langgraph'] = bool(v)
          else:
            s[k] = v
        except Exception:
          s[k] = v
      return s
  except Exception:
    pass

  # Fallback to file-backed
  _SETTINGS_FILE = _PROJECT_ROOT / '.vme2_settings.json'
  try:
    if _SETTINGS_FILE.exists():
      data = json.loads(_SETTINGS_FILE.read_text())
      s.update(data or {})
  except Exception:
    pass
  return s


def _save_settings(payload: dict):
  # Try Supabase first
  try:
    sb = _sbmod._client()
    if sb:
      # Upsert each key into va_settings (simple delete/insert for simplicity)
      for k, v in (payload or {}).items():
        try:
          sb.table('va_settings').upsert({'key': k, 'value': v}).execute()
        except Exception:
          # fallback to insert-on-conflict
          try:
            sb.table('va_settings').insert({'key': k, 'value': v}).execute()
          except Exception:
            pass
      # Return current settings after write
      return _load_settings()
  except Exception:
    pass

  # Fallback to file-backed
  _SETTINGS_FILE = _PROJECT_ROOT / '.vme2_settings.json'
  try:
    data = _load_settings()
    data.update(payload or {})
    _SETTINGS_FILE.write_text(json.dumps(data, indent=2))
    return data
  except Exception:
    return None


def _is_local_request(request: Request) -> bool:
  # Allow local-only access when SETTINGS_ADMIN_TOKEN is not set.
  host = request.client.host if request.client else None
  return host in ("127.0.0.1", "::1", "localhost", None)


def _allowed_admin_tokens():
  """Return a set of admin tokens that are accepted by the server.

  This supports two kinds of tokens:
    - SETTINGS_ADMIN_TOKEN (rotatable via UI / Supabase or environment)
    - CI_SETTINGS_ADMIN_TOKEN (optional long-lived token used by CI/workflows)

  The function checks both environment variables and the Supabase-backed
  settings store (via settings_get). Any non-empty values are returned in a
  set. If the set is empty the server treats settings endpoints as localhost-only.
  """
  out = set()
  try:
    # primary (rotatable) admin token: env override first, then Supabase-backed
    t = os.getenv('SETTINGS_ADMIN_TOKEN') or _sbmod.settings_get('SETTINGS_ADMIN_TOKEN')
    if t:
      out.add(t)
  except Exception:
    pass
  try:
    # optional CI-only token kept stable for CI so you don't need to update
    # GitHub/GitLab secrets every time you rotate the UI token.
    t2 = os.getenv('CI_SETTINGS_ADMIN_TOKEN') or _sbmod.settings_get('CI_SETTINGS_ADMIN_TOKEN')
    if t2:
      out.add(t2)
  except Exception:
    pass
  return out


@app.get('/api/settings')
async def api_get_settings(request: Request, x_admin_token: str | None = Header(None)):
  # Admin token may be configured as an environment variable, or managed in va_settings via the UI.
  allowed = _allowed_admin_tokens()
  if allowed:
    if not x_admin_token or x_admin_token not in allowed:
      return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
  else:
    # Allow only local calls when no admin token is configured
    if not _is_local_request(request):
      return JSONResponse({'ok': False, 'error': 'admin token not set; settings API restricted to localhost'}, status_code=403)
  # Prefer Supabase-backed settings list
  try:
    sb = _sbmod._client()
    if sb:
      return JSONResponse({'ok': True, 'settings': settings_list()})
  except Exception:
    pass
  # fallback to file
  return JSONResponse({'ok': True, 'settings': _load_settings(), 'note': 'fallback file-based'})


@app.post('/api/settings')
async def api_post_settings(request: Request, payload: dict, x_admin_token: str | None = Header(None)):
  # validate minimal types
  allowed = _allowed_admin_tokens()
  if allowed:
    if not x_admin_token or x_admin_token not in allowed:
      return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
  else:
    # Allow only local calls when no admin token is configured
    if not _is_local_request(request):
      return JSONResponse({'ok': False, 'error': 'admin token not set; settings API restricted to localhost'}, status_code=403)
  ok_keys = {}
  if 'tts_speed' in payload:
    try:
      ok_keys['tts_speed'] = float(payload.get('tts_speed'))
    except Exception:
      return JSONResponse({'ok': False, 'error': 'tts_speed must be a number'}, status_code=400)
  if 'queue_reminder_minutes' in payload:
    try:
      ok_keys['queue_reminder_minutes'] = int(payload.get('queue_reminder_minutes'))
    except Exception:
      return JSONResponse({'ok': False, 'error': 'queue_reminder_minutes must be an integer'}, status_code=400)
  if 'agent_use_langgraph' in payload:
    ok_keys['agent_use_langgraph'] = bool(payload.get('agent_use_langgraph'))

  saved = _save_settings(ok_keys)
  if saved is None:
    return JSONResponse({'ok': False, 'error': 'failed to persist settings'}, status_code=500)

  # If AGENT_USE_LANGGRAPH was toggled, write to environment and attempt reload of graph
  try:
    restart_required = False
    applied = False
    if 'agent_use_langgraph' in ok_keys:
      val = '1' if ok_keys['agent_use_langgraph'] else '0'
      os.environ['AGENT_USE_LANGGRAPH'] = val
      # Persist the flag to DB/file
      _save_settings({'agent_use_langgraph': ok_keys['agent_use_langgraph']})
      # Try to reload the graph module so the in-process graph picks up the change.
      try:
        import graph.va_graph as _vg
        if hasattr(_vg, '_Wrapper'):
          _vg._singleton = _vg._Wrapper()
          applied = True
        else:
          applied = False
      except Exception:
        applied = False
      # If we couldn't apply in-process, a restart is required
      restart_required = not applied
    else:
      applied = False
      restart_required = False
  except Exception:
    applied = False
    restart_required = True

  return JSONResponse({'ok': True, 'settings': saved, 'applied_in_process': bool(applied), 'restart_required': bool(restart_required)})


@app.put('/api/settings')
async def api_put_settings(request: Request, x_admin_token: str | None = Header(None)):
  allowed = _allowed_admin_tokens()
  if allowed:
    if not x_admin_token or x_admin_token not in allowed:
      return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
  else:
    if not _is_local_request(request):
      return JSONResponse({'ok': False, 'error': 'admin token not set; settings API restricted to localhost'}, status_code=403)
  try:
    body = await request.json()
  except Exception:
    return JSONResponse({'ok': False, 'error': 'invalid json'}, status_code=400)
  # write to Supabase
  try:
    settings_put(body)
    return JSONResponse({'ok': True, 'updated': list(body.keys())})
  except Exception as e:
    return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


@app.post('/api/settings/refresh')
async def api_post_settings_refresh(request: Request, x_admin_token: str | None = Header(None)):
  allowed = _allowed_admin_tokens()
  if allowed:
    if not x_admin_token or x_admin_token not in allowed:
      return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
  else:
    if not _is_local_request(request):
      return JSONResponse({'ok': False, 'error': 'admin token not set; settings API restricted to localhost'}, status_code=403)
  try:
    settings_refresh()
    # Reload tokens from Supabase into the process environment so updates
    # to GITHUB_TOKEN / GITHUB_PAT via the UI take effect without restart.
    try:
      _load_github_tokens_from_supabase()
    except Exception:
      pass
    return JSONResponse({'ok': True, 'cache': 'cleared'})
  except Exception as e:
    return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)


@app.post('/api/settings/rotate_admin')
async def api_rotate_admin(request: Request, x_admin_token: str | None = Header(None)):
  """Generate and persist a new SETTINGS_ADMIN_TOKEN. Requires existing admin token (or localhost access when none set).

  Returns the new token in the response so the operator can copy it and, if desired, set it as an environment variable.
  """
  admin_token = os.getenv('SETTINGS_ADMIN_TOKEN') or _sbmod.settings_get('SETTINGS_ADMIN_TOKEN')
  if admin_token:
    if not x_admin_token or x_admin_token != admin_token:
      return JSONResponse({'ok': False, 'error': 'admin token required'}, status_code=403)
  else:
    if not _is_local_request(request):
      return JSONResponse({'ok': False, 'error': 'admin token not set; settings API restricted to localhost'}, status_code=403)

  try:
    import secrets
    new_token = secrets.token_urlsafe(32)
  except Exception:
    import uuid
    new_token = str(uuid.uuid4())

  # Try to persist via settings_put (Supabase-backed) and fall back to file-backed _save_settings
  try:
    settings_put({'SETTINGS_ADMIN_TOKEN': new_token})
    return JSONResponse({'ok': True, 'new_token': new_token})
  except Exception as e:
    try:
      saved = _save_settings({'SETTINGS_ADMIN_TOKEN': new_token})
      if saved is None:
        raise RuntimeError('failed to persist locally')
      return JSONResponse({'ok': True, 'new_token': new_token, 'note': 'saved to local settings file'})
    except Exception as ee:
      return JSONResponse({'ok': False, 'error': 'failed to persist new token', 'detail': str(ee)}, status_code=500)

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!doctype html>
    <html>
      <head><meta charset="utf-8"><title>V-Me2</title></head>
      <body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial">
        <h1>V-Me2</h1>
        <p>If you see this, the server is up. Try <a href="/health">/health</a> or <a href="/ui">/ui</a>.</p>
        <ul>
          <li><a href="/ui">/ui</a></li>
          <li><a href="/health">/health</a></li>
        </ul>
      </body>
    </html>
    """

@app.get("/ui")
async def ui():
    return HTMLResponse("""
      <div style="font-family: system-ui; padding: 1rem">
        <h2>V-Me UI (minimal)</h2>
        <p>Next step: connect to <code>/agent/chat</code> once we add it.</p>
        <script src="/static/ui.js"></script>
        <div style="margin-top:1rem">
          <h3>Goals (quick view)</h3>
          <iframe src="/static/goals.html" style="width:100%;height:260px;border:1px solid #ddd;border-radius:6px"></iframe>
          <p><a href="/showme">Open full Show Me window</a> · <a href="/static/goals.html" target="_blank">Open goals in new tab</a></p>
        </div>
      </div>
    """)

@app.get("/health")
async def health():
    return PlainTextResponse("ok")


@app.get("/showme", response_class=HTMLResponse)
async def showme():
  try:
    return (Path(__file__).parent / "static" / "show_me_window.html").read_text()
  except Exception:
    return "<h1>Show Me</h1><p>missing static/show_me_window.html</p>"


@app.get('/api/sessions')
async def api_sessions(page: int = 1, page_size: int = 10):
  try:
    from vme_lib import supabase_client as _sbmod
    sb = _sbmod._client()
  except Exception:
    sb = None
  if not sb:
    return JSONResponse({"ok": True, "counts": None, "page": page, "page_size": page_size})
  try:
    c1 = sb.table('va_sessions').select('*', count='exact').limit(1).execute()
    c2 = sb.table('va_messages').select('*', count='exact').limit(1).execute()
    sessions_count = getattr(c1, 'count', None)
    messages_count = getattr(c2, 'count', None)
    return JSONResponse({"ok": True, "counts": {"va_sessions": sessions_count, "va_messages": messages_count},
               "page": page, "page_size": page_size})
  except Exception as e:
    return JSONResponse({"ok": False, "error": str(e), "page": page, "page_size": page_size}, status_code=500)


@app.get('/api/_debug/status')
async def api_debug_status():
  """Temporary debug endpoint (remove after use).

  Returns minimal info useful for diagnosing why admin tokens are not
  accepted by the running server. This endpoint intentionally masks
  secret values and only reports presence / masked form.
  """
  # Provide a slightly more verbose diagnostic so we can tell whether the
  # Supabase-related environment variables are present in the deployed
  # environment (without revealing secret values).
  out = {
    'supabase_connected': False,
    'supabase_client_error': None,
    'settings_admin_env': False,
    'ci_admin_env': False,
    'supabase_url_env': False,
    'supabase_service_key_env': False,
    'supabase_anon_key_env': False,
    'database_url_env': False,
    'ci_in_settings': False,
    'settings_in_settings': False,
  }
  try:
    # env checks (presence only)
    out['settings_admin_env'] = bool(os.getenv('SETTINGS_ADMIN_TOKEN'))
    out['ci_admin_env'] = bool(os.getenv('CI_SETTINGS_ADMIN_TOKEN'))
    out['supabase_url_env'] = bool(os.getenv('SUPABASE_URL'))
    # accept either SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SERVICE_KEY (alias)
    out['supabase_service_key_env'] = bool(os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_SERVICE_KEY'))
    out['supabase_anon_key_env'] = bool(os.getenv('SUPABASE_ANON_KEY'))
    out['database_url_env'] = bool(os.getenv('DATABASE_URL'))

    # supabase client check
    try:
      sb = _sbmod._client()
      out['supabase_connected'] = bool(sb)
    except Exception as e:
      out['supabase_connected'] = False
      try:
        # truncate error to avoid overly large responses
        out['supabase_client_error'] = str(e)[:200]
      except Exception:
        out['supabase_client_error'] = 'error'

    # check values in va_settings only if client is available
    if out['supabase_connected']:
      try:
        v = _sbmod.settings_get('CI_SETTINGS_ADMIN_TOKEN', default=None, decrypt=True)
        out['ci_in_settings'] = bool(v)
      except Exception:
        out['ci_in_settings'] = False
      try:
        v2 = _sbmod.settings_get('SETTINGS_ADMIN_TOKEN', default=None, decrypt=True)
        out['settings_in_settings'] = bool(v2)
      except Exception:
        out['settings_in_settings'] = False
  except Exception as e:
    return JSONResponse({'ok': False, 'error': str(e)}, status_code=500)

  # Return booleans/presence flags only; do not reveal secret values.
  return JSONResponse({'ok': True, 'debug': out})


@app.get('/api/_debug/supacall')
async def api_debug_supacall():
  """Make a minimal authenticated Supabase call (read va_settings) and
  return a concise success/failure result. This helps surface connection
  errors from the deployed process without revealing any secret values.
  """
  try:
    sb = _sbmod._client()
  except Exception as e:
    return JSONResponse({'ok': False, 'error': 'failed to construct supabase client', 'client_error': str(e)[:400]}, status_code=500)
  if not sb:
    return JSONResponse({'ok': False, 'error': 'supabase client not configured (missing url/key)'} , status_code=500)
  try:
    # perform a lightweight read
    res = sb.table('va_settings').select('key').limit(1).execute()
    # success: don't return rows to avoid exposing values
    return JSONResponse({'ok': True, 'rows_returned': bool(getattr(res, 'data', None)), 'count': getattr(res, 'count', None)})
  except Exception as e:
    # truncate the error message for brevity; do not include secrets
    msg = None
    try:
      msg = str(e)[:500]
    except Exception:
      msg = 'error'
    return JSONResponse({'ok': False, 'error': 'supabase query failed', 'client_error': msg}, status_code=500)


# Temporary: inspect Railway using RAILWAY_API_TOKEN stored in settings or env.
# WARNING: this endpoint is temporary for debugging and returns metadata only.
@app.get('/api/_debug/railway_inspect')
async def api_debug_railway_inspect():
  import urllib.request, urllib.error, json
  # Try env first, then Supabase-backed settings
  token = os.getenv('RAILWAY_API_TOKEN')
  try:
    if not token:
      token = _sbmod.settings_get('RAILWAY_API_TOKEN', default=None, decrypt=True)
  except Exception:
    token = token

  if not token:
    return JSONResponse({'ok': False, 'error': 'RAILWAY_API_TOKEN not found in env or settings'}, status_code=404)

  headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
  endpoints = [
    ('projects', 'https://api.railway.app/v1/projects'),
    ('services', 'https://api.railway.app/v1/services')
  ]
  out = {'ok': True, 'summary': []}
  for name, ep in endpoints:
    try:
      req = urllib.request.Request(ep, headers=headers, method='GET')
      with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read().decode('utf-8')
      try:
        obj = json.loads(data)
      except Exception:
        obj = {'_raw': data[:1000]}
      # Summarize: don't return tokens or secrets
      summary = {'endpoint': name}
      if isinstance(obj, dict):
        summary['top_keys'] = list(obj.keys())[:10]
        if isinstance(obj.get('projects'), list):
          summary['projects_count'] = len(obj['projects'])
          summary['projects_sample'] = [{ 'id': p.get('id'), 'name': p.get('name') } for p in obj['projects'][:5]]
        if isinstance(obj.get('data'), list):
          summary['data_count'] = len(obj.get('data'))
      elif isinstance(obj, list):
        summary['list_count'] = len(obj)
      out['summary'].append(summary)
    except urllib.error.HTTPError as he:
      try:
        body = he.read().decode('utf-8')
      except Exception:
        body = ''
      out['summary'].append({'endpoint': name, 'http_error': he.code, 'body_snippet': body[:800]})
    except Exception as e:
      out['summary'].append({'endpoint': name, 'error': str(e)[:400]})

  return JSONResponse(out)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))  # Railway provides PORT
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
