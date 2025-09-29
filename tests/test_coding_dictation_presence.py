from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_coding_html_has_mic_and_input():
    r = client.get("/static/coding.html")
    assert r.status_code == 200
    txt = r.text
    assert 'id="mic-btn"' in txt
    assert 'id="composer-input"' in txt

def test_coding_js_contains_dictation_funcs():
    r = client.get('/static/coding.js')
    assert r.status_code == 200
    txt = r.text
    assert 'startDictation' in txt
    assert 'stopDictation' in txt
