import json
from fastapi.testclient import TestClient
from main import app


def test_plan_enqueues_task(monkeypatch):
    called = {}
    def fake_enqueue(title, body):
        called['args'] = (title, body)
        return 123
    monkeypatch.setattr('lib.ops_service.enqueue_task', fake_enqueue, raising=False)

    client = TestClient(app)
    r = client.post('/agent/plan', json={'title':'T','body':'B'})
    assert r.status_code == 200
    data = r.json()
    assert data['task_id'] == 123
    assert called['args'] == ('T','B')


def test_plan_400():
    client = TestClient(app)
    assert client.post('/agent/plan', json={'title':'','body':'x'}).status_code == 422
    assert client.post('/agent/plan', json={'title':'x','body':''}).status_code == 422
