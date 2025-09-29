from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional
import os, aiofiles, tempfile, httpx

from graph.va_graph import get_graph
from lib.supabase_client import safe_log_message, create_session

router = APIRouter(prefix="/api/audio", tags=["audio"])

MAX_BYTES = 15 * 1024 * 1024
OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")

async def _to_tempfile(upload: UploadFile) -> str:
    # upload.size may be None depending on the client
    suffix = "." + (upload.filename.split(".")[-1] if upload.filename and "." in upload.filename else "webm")
    fd, path = tempfile.mkstemp(prefix="voice_", suffix="."+suffix.strip("."))
    os.close(fd)
    size = 0
    async with aiofiles.open(path, "wb") as out:
        while True:
            chunk = await upload.read(65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                try:
                    await out.close()
                except Exception:
                    pass
                try:
                    os.remove(path)
                except Exception:
                    pass
                raise HTTPException(413, detail="file too large")
            await out.write(chunk)
    return path


@router.post("/upload")
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    label: Optional[str] = Form(None),
):
    # Ensure session
    if not session_id:
        sid = create_session(label or "voice")
        session_id = str(sid) if sid is not None else ""

    # Fake mode (for CI/local)
    if os.getenv("VOICE_FAKE", "0") == "1" or not os.getenv("OPENAI_API_KEY"):
        transcript = "FAKE_TRANSCRIPT"
        try:
            graph = get_graph()
            res = graph.invoke({"session_id": session_id, "messages": [{"role": "user", "content": transcript}]})
            reply = res.get("last_text", "")
        except Exception:
            reply = ""
        try:
            safe_log_message(session_id, "user", transcript)
        except Exception:
            pass
        try:
            safe_log_message(session_id, "assistant", reply)
        except Exception:
            pass
        # Optional: best-effort meeting logging when meeting_id provided and not fake
        try:
            mid = (request.query_params.get("meeting_id")
                   or None)

            if mid and os.getenv("MEETING_FAKE") != "1":
                try:
                    from importlib import import_module
                    sc = import_module("lib.supabase_client")
                    try:
                        mid_int = int(str(mid))
                        getattr(sc, "insert_segment", lambda *a, **k: None)(mid_int, transcript, ts=None, idx=None)
                    except ValueError:
                        pass
                except Exception:
                    pass
        except Exception:
            pass
        return JSONResponse({"session_id": session_id, "transcript": transcript, "reply": reply, "fake": True})

    # Real Whisper call
    path = await _to_tempfile(file)
    try:
        headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}
        form = {"model": OPENAI_MODEL}
        files = {"file": (file.filename or "audio.webm", open(path, "rb"), file.content_type or "application/octet-stream")}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(OPENAI_URL, headers=headers, data=form, files=files)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, detail=f"OpenAI error: {r.text}")
        data = r.json()
        transcript = data.get("text") or data.get("text", "")
        if not transcript:
            transcript = str(data)
        try:
            graph = get_graph()
            res = graph.invoke({"session_id": session_id, "messages": [{"role": "user", "content": transcript}]})
            reply = res.get("last_text", "")
        except Exception:
            reply = ""
        try:
            safe_log_message(session_id, "user", transcript)
            safe_log_message(session_id, "assistant", reply)
        except Exception:
            pass
        # Optional: best-effort meeting logging when meeting_id provided and not fake
        try:
            mid = (request.query_params.get("meeting_id")
                   or None)
            if mid and os.getenv("MEETING_FAKE") != "1":
                try:
                    from importlib import import_module
                    sc = import_module("lib.supabase_client")
                    try:
                        mid_int = int(str(mid))
                        getattr(sc, "insert_segment", lambda *a, **k: None)(mid_int, transcript, ts=None, idx=None)
                    except ValueError:
                        pass
                except Exception:
                    pass
        except Exception:
            pass
        return {"session_id": session_id, "transcript": transcript, "reply": reply}
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
