from fastapi.testclient import TestClient
import os
from main import app

client = TestClient(app)


def test_admin_required():
    r = client.post('/ops/tasks', json={'title':'x'})
    assert r.status_code == 403


def test_create_and_get_fake():
    os.environ['SETTINGS_ADMIN_TOKEN'] = 'adm'
    headers = {'X-Admin-Token':'adm'}
    r = client.post('/ops/tasks', json={'title':'task1','body':'do stuff'}, headers=headers)
    assert r.status_code == 200
    j = r.json()
    assert 'id' in j
    tid = j['id']
    r2 = client.get(f'/ops/tasks/{tid}', headers=headers)
    assert r2.status_code == 200
    data = r2.json()
    assert data.get('id') == tid
