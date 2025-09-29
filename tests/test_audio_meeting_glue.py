import os
import sys, types, asyncio
# Ensure optional runtime deps used elsewhere are present at import time
if 'aiofiles' not in sys.modules:
    import types as _types
    sys.modules['aiofiles'] = _types.ModuleType('aiofiles')
if 'multipart' not in sys.modules:
    import types as _types
    sys.modules['multipart'] = _types.ModuleType('multipart')
from routes.audio import upload_audio


class DummyUpload:
    def __init__(self):
        self.filename = 't.wav'
        self.content_type = 'application/octet-stream'
    async def read(self, n=-1):
        return b''


def test_audio_upload_calls_insert_segment_when_meeting_id(monkeypatch):
    # Voice may run in fake mode in CI
    monkeypatch.setenv("VOICE_FAKE", "1")
    # Force real meeting mode branch in the handler
    monkeypatch.setenv("MEETING_FAKE", "0")

    called = {"n": 0}
    def fake_insert_segment(mid, text, ts=None, idx=None):
        called["n"] += 1
        assert mid == 123
        assert isinstance(text, str) and len(text) > 0
        return None

    import lib.supabase_client as sc
    monkeypatch.setattr(sc, "insert_segment", fake_insert_segment, raising=False)

    # Build dummy request with query_params dict-like
    class DummyReq:
        def __init__(self, qp):
            self.query_params = qp

    req = DummyReq({'meeting_id': '123'})
    upload = DummyUpload()

    # Call the upload_audio coroutine directly
    res = asyncio.get_event_loop().run_until_complete(upload_audio(req, upload, None, None))
    # res is a JSONResponse or dict depending on path; normalize
    if hasattr(res, 'body'):
        # starlette response: render then decode body
        try:
            res.render()
        except Exception:
            pass
        import json as _json
        body = _json.loads(res.body.decode('utf-8')) if res.body else {}
    else:
        body = res
    assert 'transcript' in body and 'reply' in body
    assert called['n'] == 1
