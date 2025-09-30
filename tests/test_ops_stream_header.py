from fastapi.testclient import TestClient
import os
from main import app

client = TestClient(app)

def test_stream_header():
    os.environ['SETTINGS_ADMIN_TOKEN']='adm'
    os.environ['DEV_LOCAL_LLM']='1'
    headers={'X-Admin-Token':'adm'}
    r = client.post('/ops/tasks', json={'title':'s'}, headers=headers)
    tid = r.json()['id']
    with client.stream('GET', f'/ops/tasks/{tid}/stream', headers=headers) as resp:
        assert resp.status_code == 200
        assert resp.headers.get('content-type','').startswith('text/event-stream')
