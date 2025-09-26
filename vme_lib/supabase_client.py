import os, time, json, base64
from typing import Optional, Union, Dict, Any
from supabase import create_client, Client

_sb: Optional[Client] = None
_SETTINGS_CACHE: Dict[str, tuple[float, Any]] = {}
_SETTINGS_CACHE_TTL = int(os.getenv("SETTINGS_CACHE_TTL", "30"))
_SECRET_KEYS = set(
    (os.getenv("SETTINGS_SECRET_KEYS") or "OPENAI_API_KEY,SUPABASE_SERVICE_ROLE_KEY,SUPABASE_ANON_KEY,SETTINGS_ADMIN_TOKEN,CI_SETTINGS_ADMIN_TOKEN,GITHUB_TOKEN,GITHUB_PAT,SUPABASE_SERVICE_KEY").split(",")
)
try:
    from cryptography.fernet import Fernet
    _CRYPTO_OK = True
except Exception:
    _CRYPTO_OK = False

def _fernet():
    key = os.getenv("APP_ENCRYPTION_KEY")
    if _CRYPTO_OK and key:
        try:
            return Fernet(key)
        except Exception:
            return None
    return None

def _client() -> Optional[Client]:
    """Create or return a cached Supabase client. Returns None if credentials are missing.

    Environment variables checked:
      - SUPABASE_URL
      - SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
    """
    global _sb
    if _sb is not None:
        return _sb
    url = os.getenv("SUPABASE_URL")
    # Accept either SUPABASE_SERVICE_ROLE_KEY (official name) or
    # SUPABASE_SERVICE_KEY (common shorthand stored in Railway in this repo)
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or
        os.getenv("SUPABASE_SERVICE_KEY") or
        os.getenv("SUPABASE_ANON_KEY"))
    if not url or not key:
        return None
    try:
        _sb = create_client(url, key)
    except Exception:
        _sb = None
    return _sb


def create_session(label: Optional[str] = None) -> Optional[int]:
    sb = _client()
    if not sb:
        return None
    try:
        res = sb.table("va_sessions").insert({"label": label}).execute()
        return res.data[0]["id"] if res.data else None
    except Exception:
        return None


def safe_log_message(session_id: Union[int, str, None], role: str, content: str):
    sb = _client()
    if not sb:
        return
    try:
        sid = session_id
        if isinstance(sid, str):
            try:
                sid = int(sid)
            except ValueError:
                sid = None
        sb.table("va_messages").insert({
            "session_id": sid,
            "role": role,
            "content": content,
        }).execute()
    except Exception:
        pass


def safe_log_tool_event(session_id: Union[int, str, None], tool_name: str, input_json: dict | None, output_json: dict | str | None):
    sb = _client()
    if not sb:
        return
    try:
        sid = session_id
        if isinstance(sid, str):
            try:
                sid = int(sid)
            except ValueError:
                sid = None
        payload = {
            "session_id": sid,
            "tool_name": tool_name,
            "input_json": input_json,
            "output_json": output_json,
        }
        sb.table("va_tool_events").insert(payload).execute()
    except Exception:
        pass


def select_tool_events(session_id: Union[int, str], limit: int = 10):
    sb = _client()
    if not sb:
        return []
    try:
        sid = int(session_id) if isinstance(session_id, str) else session_id
        res = sb.table("va_tool_events").select("*").eq("session_id", sid).order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception:
        return []


# ---------------- Settings helpers (backed by va_settings) ----------------
def _cache_get(k: str):
    t = _SETTINGS_CACHE.get(k)
    if not t: return None
    ts, val = t
    if (time.time()-ts) > _SETTINGS_CACHE_TTL:
        _SETTINGS_CACHE.pop(k, None)
        return None
    return val

def _cache_set(k: str, v: Any):
    _SETTINGS_CACHE[k] = (time.time(), v)

def settings_refresh():
    _SETTINGS_CACHE.clear()

def settings_get(key: str, default: Any=None, decrypt: bool=True) -> Any:
    """Fetch a setting from va_settings. Uses small in-proc cache."""
    cv = _cache_get(key)
    if cv is not None:
        return cv
    sb = _client()
    if not sb:
        return default
    try:
        res = sb.table("va_settings").select("*").eq("key", key).limit(1).execute()
        rows = res.data or []
        if not rows:
            return default
        v = rows[0].get("value")
        # decrypt if needed
        if decrypt and isinstance(v, str) and v.startswith("enc:v1:"):
            f = _fernet()
            if f:
                try:
                    raw = f.decrypt(base64.b64decode(v.split("enc:v1:",1)[1]))
                    v = json.loads(raw.decode("utf-8"))
                except Exception:
                    v = default
        _cache_set(key, v)
        return v
    except Exception:
        return default

def settings_put(mapping: Dict[str, Any]):
    """Upsert settings into va_settings. Secrets are optionally encrypted if APP_ENCRYPTION_KEY is set."""
    sb = _client()
    if not sb:
        raise RuntimeError("Supabase not configured")
    f = _fernet()
    for k, v in mapping.items():
        store_v: Any = v
        if k in _SECRET_KEYS and f:
            payload = json.dumps(v).encode("utf-8")
            token = f.encrypt(payload)
            store_v = "enc:v1:" + base64.b64encode(token).decode("ascii")
        sb.table("va_settings").upsert({"key": k, "value": store_v}).on_conflict("key").execute()
        _SETTINGS_CACHE.pop(k, None)

def settings_list() -> Dict[str, Any]:
    """Return all settings as {key:value}, masking secrets."""
    sb = _client()
    if not sb:
        return {}
    rows = sb.table("va_settings").select("*").execute().data or []
    out: Dict[str, Any] = {}
    for r in rows:
        k = r["key"]; v = r.get("value")
        if k in _SECRET_KEYS:
            # mask secrets: show only last 4 chars if string
            s = ""
            if isinstance(v, str):
                # show enc marker or last 4
                if v.startswith("enc:v1:"):
                    s = "enc(v1)"
                else:
                    s = ("*"*6) + (v[-4:] if len(v) >= 4 else "")
            out[k] = s or "*****"
        else:
            out[k] = v
    return out
