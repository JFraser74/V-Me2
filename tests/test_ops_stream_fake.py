import os
from fastapi.testclient import TestClient
import time
from main import app

client = TestClient(app)


def test_stream_ticks_and_done():
    os.environ['SETTINGS_ADMIN_TOKEN'] = 'adm'
    os.environ['DEV_LOCAL_LLM'] = '1'
    headers = {'X-Admin-Token':'adm'}
    r = client.post('/ops/tasks', json={'title':'t'}, headers=headers)
    assert r.status_code == 200
    tid = r.json()['id']
    with client.stream('GET', f'/ops/tasks/{tid}/stream', headers=headers) as resp:
        assert resp.status_code == 200
        assert resp.headers.get('content-type','').startswith('text/event-stream')
        data = resp.iter_lines()
        # collect events, wait up to ~1s for 'done' to appear
        lines = []
        start = time.time()
        while time.time() - start < 1.0:
            try:
                line = next(data)
            except StopIteration:
                break
            if line:
                lines.append(line)
                joined = '\n'.join(lines)
                if 'done' in joined:
                    break
        joined = '\n'.join(lines)
        assert 'tick' in joined
        assert 'done' in joined
