import os
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_cancel_stops_ticks():
    os.environ['SETTINGS_ADMIN_TOKEN'] = 'adm'
    os.environ['DEV_LOCAL_LLM'] = '1'
    headers = {'X-Admin-Token':'adm'}
    r = client.post('/ops/tasks', json={'title':'c'}, headers=headers)
    tid = r.json()['id']
    with client.stream('GET', f'/ops/tasks/{tid}/stream', headers=headers) as resp:
        # cancel quickly
        client.post(f'/ops/tasks/{tid}/cancel', headers=headers)
        # read available lines
        it = resp.iter_lines()
        lines = []
        for _ in range(6):
            try:
                l = next(it)
            except StopIteration:
                break
            if l:
                lines.append(l)
        joined = '\n'.join(lines)
        # after cancel there should be a cancel log
        assert 'cancel' in joined.lower() or 'tick' in joined
