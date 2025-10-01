from fastapi.testclient import TestClient
import importlib, os, sys

def test_seed_memory_dev_mode_ok(monkeypatch):
    monkeypatch.setenv("DEV_LOCAL_LLM", "1")
    # ensure fresh import
    sys.modules.pop('main', None)
    import main
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    r = client.post("/api/admin/seed_memory")
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is True
    assert "seeded" in d
