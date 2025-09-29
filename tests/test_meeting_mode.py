import os
from fastapi.testclient import TestClient
from main import app


def test_meeting_fake_happy(monkeypatch):
    monkeypatch.setenv("MEETING_FAKE", "1")
    c = TestClient(app)
    b = c.post("/api/meeting/begin")
    assert b.status_code == 200
    mid = b.json()["meeting_id"]
    r1 = c.post("/api/meeting/ingest", json={"meeting_id": mid, "text":"Agenda: ship Voice MVP today."})
    assert r1.status_code == 200 and r1.json()["count"] == 1
    r2 = c.post("/api/meeting/ingest", json={"meeting_id": mid, "text":"Next: Meeting Mode scaffold, then DB wiring."})
    assert r2.json()["count"] == 2
    e = c.post("/api/meeting/end", json={"meeting_id": mid})
    j = e.json()
    assert e.status_code == 200
    assert j["segment_count"] == 2
    # ensure some content made it into summary/bullets
    assert "Voice MVP" in (j["summary"] + " " + " ".join(j["bullets"]))


def test_meeting_fake_errors(monkeypatch):
    monkeypatch.setenv("MEETING_FAKE", "1")
    c = TestClient(app)
    # missing mid
    e = c.post("/api/meeting/end", json={"meeting_id": ""})
    assert e.status_code in (400, 404)
    # unknown mid
    e2 = c.post("/api/meeting/end", json={"meeting_id": "00000000-0000-0000-0000-000000000000"})
    assert e2.status_code in (400, 404)
