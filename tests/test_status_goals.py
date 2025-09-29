from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_goals_api():
    r = client.get('/status/goals')
    assert r.status_code == 200
    body = r.json()
    assert 'items' in body and isinstance(body['items'], list)
    assert any(i.get('status','').startswith('DONE') for i in body['items'])


def test_goals_page_serves():
    r = client.get('/static/goals.html')
    assert r.status_code == 200
    assert b'Goals status' in r.content
