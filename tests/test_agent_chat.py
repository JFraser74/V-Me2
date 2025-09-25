from fastapi.testclient import TestClient
import main
import os


def test_agent_chat_echo():
    client = TestClient(main.app)
    r = client.post('/agent/chat', json={'message': 'hello test', 'label': 'T1'})
    assert r.status_code == 200
    body = r.json()
    assert 'text' in body
    # In CI or when AGENT_USE_LANGGRAPH is explicitly enabled the agent may
    # use a real LLM and return non-echo text. Only enforce the Echo prefix
    # when the guarded echo fallback is active (AGENT_USE_LANGGRAPH not set).
    if os.getenv('AGENT_USE_LANGGRAPH', '').lower() not in ('1', 'true', 'yes'):
        assert body['text'].startswith('Echo:')
