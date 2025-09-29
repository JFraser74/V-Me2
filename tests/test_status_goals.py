from fastapi.testclient import TestClient
from main import app


def test_goals_endpoint_serves_html():
    c = TestClient(app)
    r = c.get("/status/goals")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
