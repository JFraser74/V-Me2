from fastapi.testclient import TestClient
from main import app


def test_version_endpoint():
    c = TestClient(app)
    r = c.get("/status/version")
    assert r.status_code == 200
    data = r.json()
    assert "commit" in data and isinstance(data["commit"], str)
    assert "build_time" in data and isinstance(data["build_time"], str)
