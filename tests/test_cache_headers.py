from main import app
from fastapi.testclient import TestClient

def test_showme_and_js_have_no_store():
    client = TestClient(app)
    r = client.get('/showme')
    assert 'Cache-Control' in r.headers and r.headers['Cache-Control'] == 'no-store'
    r2 = client.get('/static/show_me_window.js')
    assert 'Cache-Control' in r2.headers and r2.headers['Cache-Control'] == 'no-store'
