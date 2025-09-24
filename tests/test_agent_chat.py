from fastapi.testclient import TestClient
import main


def test_agent_chat_echo():
    client = TestClient(main.app)
    r = client.post('/agent/chat', json={'message': 'hello test', 'label': 'T1'})
    assert r.status_code == 200
    body = r.json()
    assert 'text' in body
    assert body['text'].startswith('Echo:')
