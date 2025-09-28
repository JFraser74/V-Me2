from fastapi.testclient import TestClient
import os
import main


def test_bridge_requires_admin_token(monkeypatch):
    monkeypatch.setenv("SETTINGS_ADMIN_TOKEN", "adm")
    c = TestClient(main.app)
    r = c.get("/api/bridge/peers")
    assert r.status_code == 403
    r2 = c.get("/api/bridge/peers", headers={"X-Admin-Token": "adm"})
    assert r2.status_code in (200, 204, 200)
