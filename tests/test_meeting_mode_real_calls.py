import os
from fastapi.testclient import TestClient


def test_real_mode_calls_helpers(monkeypatch):
    # Force real mode
    monkeypatch.setenv("MEETING_FAKE", "0")

    # Import after env set so router mounts in real-mode path
    from main import app
    client = TestClient(app)

    calls = {"begin": 0, "ingest": 0, "end": 0}

    def fake_insert_meeting(label=None):
        calls["begin"] += 1
        return 123  # numeric id to enable ingest path

    def fake_insert_segment(meeting_id, text, ts=None, idx=None):
        calls["ingest"] += 1
        return None

    def fake_finalize_meeting(meeting_id, summary, bullets, segment_count=None):
        calls["end"] += 1
        return True

    # Monkeypatch helpers in place
    import lib.supabase_client as sc
    monkeypatch.setattr(sc, "insert_meeting", fake_insert_meeting, raising=False)
    monkeypatch.setattr(sc, "insert_segment", fake_insert_segment, raising=False)
    monkeypatch.setattr(sc, "finalize_meeting", fake_finalize_meeting, raising=False)

    # Begin → numeric id
    r = client.post("/api/meeting/begin")
    assert r.status_code == 200
    mid = r.json()["meeting_id"]
    assert mid == "123"

    # Ingest a segment
    r = client.post("/api/meeting/ingest", json={"meeting_id": mid, "text": "hello"})
    assert r.status_code == 200

    # End → summary/bullets returned
    r = client.post("/api/meeting/end", json={"meeting_id": mid})
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body and "bullets" in body

    assert calls == {"begin": 1, "ingest": 1, "end": 1}
