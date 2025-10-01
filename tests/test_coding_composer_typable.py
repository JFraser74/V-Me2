from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_coding_html_has_textarea_and_ids():
    r = client.get("/static/coding.html")
    assert r.status_code == 200
    body = r.text
    assert 'id="composer-input"' in body
    assert '<textarea' in body
