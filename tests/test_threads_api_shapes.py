from fastapi.testclient import TestClient

from main import app


def test_threads_shapes():
    client = TestClient(app)
    r = client.get('/api/threads?limit=5')
    assert r.status_code == 200
    j = r.json()
    assert 'items' in j and isinstance(j['items'], list)

    r2 = client.get('/api/threads/123/messages')
    assert r2.status_code == 200
    j2 = r2.json()
    assert 'items' in j2 and isinstance(j2['items'], list)
