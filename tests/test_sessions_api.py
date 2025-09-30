import pytest
from fastapi.testclient import TestClient
from main import app


def test_sessions_api_no_sb(monkeypatch):
    # Simulate missing supabase client
    import vme_lib.supabase_client as sb
    monkeypatch.setattr(sb, '_client', lambda: None)
    client = TestClient(app)
    r = client.get('/agent/sessions')
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j, list) or j == []


def test_coding_page_serves():
    client = TestClient(app)
    r = client.get('/static/coding.html')
    assert r.status_code == 200
    # page structure uses #coding-app as the main wrapper
    assert '<div id="coding-app"' in r.text
