from fastapi.testclient import TestClient
from main import app


def test_no_store_headers():
    c = TestClient(app)
    r = c.get('/showme')
    assert r.status_code == 200
    assert r.headers.get('cache-control') == 'no-store'

    r2 = c.get('/static/show_me_window.js')
    assert r2.status_code == 200
    assert r2.headers.get('cache-control') == 'no-store'
