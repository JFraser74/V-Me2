from fastapi.testclient import TestClient
import main


def test_agent_ls_root():
    client = TestClient(main.app)
    r = client.get('/agent/ls')
    assert r.status_code == 200
    body = r.json()
    assert body.get('ok') is True
    assert 'items' in body
    # root should contain README or main.py in this repo
    names = [it['name'] for it in body['items']]
    assert 'main.py' in names or 'README.md' in names
