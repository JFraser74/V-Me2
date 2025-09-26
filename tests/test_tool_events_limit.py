from fastapi.testclient import TestClient
import routes.agent as agent_mod
from main import app


def test_tool_events_limit(monkeypatch):
    # Monkeypatch select_tool_events to return a large list so we can verify API behavior
    def fake_select(session_id, limit):
        # return as many items as requested (simulate DB)
        return [{'id': i} for i in range(int(limit))]

    monkeypatch.setattr(agent_mod, 'select_tool_events', fake_select)
    client = TestClient(app)

    # Valid small limit should return exactly that many items
    r = client.get('/agent/tool_events', params={'session_id': '1', 'limit': 10})
    assert r.status_code == 200
    payload = r.json()
    assert 'items' in payload
    assert len(payload['items']) == 10

    # Too-large limit should be rejected by FastAPI validation (422)
    r2 = client.get('/agent/tool_events', params={'session_id': '1', 'limit': 1000})
    assert r2.status_code == 422
