import json
from fastapi.testclient import TestClient
import pytest

from main import app


def test_threads_endpoints_no_supabase(monkeypatch):
    # Force no Supabase by monkeypatching the client helper to return None
    import vme_lib.supabase_client as sc
    monkeypatch.setattr(sc, "_client", lambda: None)
    client = TestClient(app)

    # Create thread (should return id key)
    r = client.post("/api/threads", json={})
    assert r.status_code == 200
    j = r.json()
    assert "id" in j and "title" in j

    # Update title (should return ok key)
    r2 = client.put("/api/threads/123/title", params={"title": "X"})
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2.get("ok") in (True, False)

    # Recent list
    r3 = client.get("/api/threads")
    assert r3.status_code == 200
    assert isinstance(r3.json().get("items"), list)

    # Messages
    r4 = client.get("/api/threads/123/messages")
    assert r4.status_code == 200
    assert isinstance(r4.json().get("items"), list)
