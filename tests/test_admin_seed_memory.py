from fastapi.testclient import TestClient
import importlib, os, sys

def test_seed_memory_dev_mode_ok(monkeypatch):
    monkeypatch.setenv("DEV_LOCAL_LLM", "1")
    # ensure no admin token is configured so dev-local path is allowed
    monkeypatch.setenv("SETTINGS_ADMIN_TOKEN", "")
    monkeypatch.setenv("CI_SETTINGS_ADMIN_TOKEN", "")
    # provide a fake supabase client so the route can run without a real DB
    from vme_lib import supabase_client as sb

    class _FakeRes:
        def __init__(self, data=None):
            self.data = data or []

    class _FakeTable:
        def __init__(self):
            pass
        def select(self, *args, **kwargs):
            return self
        def eq(self, *args, **kwargs):
            return self
        def limit(self, *args, **kwargs):
            return self
        def execute(self):
            return _FakeRes([])
        def insert(self, payload):
            class _Ins:
                def execute(self_inner):
                    return _FakeRes([{"id": 123}])
            return _Ins()

    class _FakeClient:
        def table(self, name):
            return _FakeTable()

    monkeypatch.setattr(sb, "_client", lambda: _FakeClient())

    # ensure fresh import
    sys.modules.pop('main', None)
    import main
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    r = client.post("/api/admin/seed_memory")
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is True
    # response should include session_a and session_b ids
    assert isinstance(d.get("session_a"), int)
    assert isinstance(d.get("session_b"), int)
