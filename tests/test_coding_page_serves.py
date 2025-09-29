from fastapi.testclient import TestClient

from main import app


def test_coding_page_serves():
    client = TestClient(app)
    r = client.get('/static/coding.html')
    assert r.status_code == 200
    body = r.text
    assert 'id="coding-app"' in body
    assert 'Save & name' in body
