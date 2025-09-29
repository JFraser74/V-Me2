import os
from fastapi.testclient import TestClient


def test_audio_upload_calls_insert_segment_when_meeting_id(monkeypatch):
    # Voice may run in fake mode in CI
    monkeypatch.setenv("VOICE_FAKE", "1")
    # Force real meeting mode branch in the handler
    monkeypatch.setenv("MEETING_FAKE", "0")

    from main import app
    client = TestClient(app)

    called = {"n": 0}
    def fake_insert_segment(mid, text, ts=None, idx=None):
        called["n"] += 1
        assert mid == 123
        assert isinstance(text, str) and len(text) > 0
        return None

    import lib.supabase_client as sc
    monkeypatch.setattr(sc, "insert_segment", fake_insert_segment, raising=False)

    # Post a tiny dummy payload; meeting_id numeric to trigger path
    r = client.post("/api/audio/upload?meeting_id=123", files={"file": ("t.wav", b"123", "application/octet-stream")})
    assert r.status_code == 200
    body = r.json()
    assert "transcript" in body and "reply" in body
    assert called["n"] == 1
