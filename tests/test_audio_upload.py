import os
from io import BytesIO
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_audio_upload_fake(monkeypatch):
    monkeypatch.setenv("VOICE_FAKE", "1")
    # Minimal WebM-like bytes (not decoded in fake mode)
    payload = BytesIO(b"\x1A\x45\xDF\xA3\x00fake")
    files = {"file": ("fake.webm", payload, "audio/webm")}
    r = client.post("/api/audio/upload", files=files)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("fake") is True
    assert "transcript" in j and "reply" in j
