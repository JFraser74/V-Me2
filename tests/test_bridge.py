from fastapi.testclient import TestClient
import main


def test_bridge_crud():
    import uuid
    client = TestClient(main.app)

    # generate a unique peer name to avoid collisions
    name = f"test-{uuid.uuid4().hex[:8]}"

    # determine admin token (env override or settings file)
    import os
    from vme_lib.supabase_client import settings_get
    token = os.getenv('SETTINGS_ADMIN_TOKEN') or settings_get('SETTINGS_ADMIN_TOKEN')
    headers = {'X-Admin-Token': token} if token else {}

    # ensure empty list (ok if empty or present)
    r = client.get('/api/bridge/peers', headers=headers)
    assert r.status_code == 200
    assert r.json().get('ok') is True

    # create peer
    payload = {'name': name, 'url': 'http://localhost:8000', 'token': 'sekret'}
    r = client.post('/api/bridge/peers', json=payload, headers=headers)
    assert r.status_code in (200, 201, 409)
    body = r.json()
    # if it already existed, treat as ok for idempotency
    assert body.get('ok') is True or body.get('error') == 'peer exists'

    # list and check
    r = client.get('/api/bridge/peers', headers=headers)
    assert r.status_code == 200
    peers = r.json().get('peers')
    assert name in peers

    # update peer
    r = client.put(f'/api/bridge/peers/{name}', json={'url': 'http://127.0.0.1:9000'}, headers=headers)
    assert r.status_code == 200
    assert r.json().get('peer', {}).get('url') == 'http://127.0.0.1:9000'

    # delete peer
    r = client.delete(f'/api/bridge/peers/{name}', headers=headers)
    assert r.status_code == 200
    assert client.get('/api/bridge/peers', headers=headers).json().get('peers', {}).get(name) is None
