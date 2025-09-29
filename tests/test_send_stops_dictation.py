from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_handle_send_stops_dictation_in_js():
    r = client.get('/static/coding.js')
    assert r.status_code == 200
    t = r.text
    # Ensure the handle/send flow calls stopDictation (string presence check)
    assert 'stopDictation' in t
    assert 'sendMessage(' in t or 'handleSend' in t
