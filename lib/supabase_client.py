import os, time, json, base64
from typing import Optional, Union, Dict, Any
from supabase import create_client, Client

_sb: Optional[Client] = None
_SETTINGS_CACHE: Dict[str, tuple[float, Any]] = {}
_SETTINGS_CACHE_TTL = int(os.getenv("SETTINGS_CACHE_TTL", "30"))
_SECRET_KEYS = set(
    (os.getenv("SETTINGS_SECRET_KEYS") or "OPENAI_API_KEY,SUPABASE_SERVICE_ROLE_KEY,SUPABASE_ANON_KEY").split(",")
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
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
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


def update_session_title(session_id: int, title: str) -> bool:
    """Best-effort: update the label/title of an existing session. Returns True on success."""
    sb = _client()
    if not sb:
        return False
    try:
        sb.table("va_sessions").update({"label": title}).eq("id", int(session_id)).execute()
        return True
    except Exception:
        return False


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


# ---------------- Meetings write helpers (best-effort, write-only) ----------------
def insert_meeting(label: Optional[str] = None) -> Optional[int]:
    """Insert a meeting row and return the new id, or None on failure / missing client."""
    sb = _client()
    if not sb:
        return None
    try:
        res = sb.table("va_meetings").insert({"label": label}).execute()
        return res.data[0]["id"] if res.data else None
    except Exception:
        return None


def insert_segment(meeting_id: int, text: str, ts: float | None = None, idx: int | None = None) -> Optional[int]:
    """Append a segment to va_meeting_segments. Returns segment id or None."""
    sb = _client()
    if not sb:
        return None
    try:
        payload = {
            "meeting_id": meeting_id,
            "ts": float(ts) if ts is not None else None,
            "idx": idx,
            "text": text,
        }
        res = sb.table("va_meeting_segments").insert(payload).execute()
        return res.data[0]["id"] if res.data else None
    except Exception:
        return None


def finalize_meeting(meeting_id: int, summary: str | None, bullets: list | None, segment_count: int | None = None) -> bool:
    """Update va_meetings with summary/bullets and optionally segment_count. Returns True on success."""
    sb = _client()
    if not sb:
        return False
    try:
        upd: Dict[str, Any] = {}
        if summary is not None:
            upd["summary"] = summary
        if bullets is not None:
            upd["bullets"] = bullets
        if segment_count is not None:
            upd["segment_count"] = int(segment_count)
        if not upd:
            return True
        sb.table("va_meetings").update(upd).eq("id", int(meeting_id)).execute()
        return True
    except Exception:
        return False


# ---------------- Tasks helpers (write-only) ----------------
def insert_task(title: str, body: str | None = None) -> int | None:
    """Insert a va_tasks row and return the new id, or None on failure / missing client."""
    sb = _client()
    if not sb:
        return None
    try:
        payload = {'title': title, 'body': body}
        res = sb.table('va_tasks').insert(payload).execute()
        return res.data[0]['id'] if res.data else None
    except Exception:
        return None


def update_task_status(id: int, status: str, branch: str | None = None, pr_number: int | None = None, error: str | None = None) -> bool:
    sb = _client()
    if not sb:
        return False
    try:
        upd = {'status': status}
        if branch is not None: upd['branch'] = branch
        if pr_number is not None: upd['pr_number'] = pr_number
        if error is not None: upd['error'] = error
        sb.table('va_tasks').update(upd).eq('id', int(id)).execute()
        return True
    except Exception:
        return False


def insert_task_event(task_id: int, kind: str, data_dict: dict | None = None) -> None:
    sb = _client()
    if not sb:
        return
    try:
        sb.table('va_task_events').insert({'task_id': int(task_id), 'kind': kind, 'data': data_dict or {}}).execute()
    except Exception:
        pass
