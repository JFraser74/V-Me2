from fastapi.testclient import TestClient
from main import app


def test_coding_js_served_contains_stream_helpers():
    client = TestClient(app)
    r = client.get('/static/coding.js')
    assert r.status_code == 200
    text = r.text
    # expect the streaming helper names to be present
    assert 'sendMessageStreaming' in text
    assert 'appendPartial' in text
    assert 'finalizeAssistant' in text
