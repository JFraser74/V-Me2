import os
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.mark.parametrize('env_val', ['1', 'true'])
def test_agent_stream_fake_param(tmp_path, monkeypatch, env_val):
    # ensure fake-mode
    monkeypatch.setenv('DEV_LOCAL_LLM', env_val)
    client = TestClient(app)
    with client.stream('GET', '/agent/stream?message=hi') as resp:
        assert resp.status_code == 200
        body = ''
        for chunk in resp.iter_text():
            body += chunk
        # should contain tick and done event payloads
        assert '"type": "tick"' in body
        assert '"type": "done"' in body


def test_stream_fake_mode_simple():
    # Ensure fake/local mode
    os.environ['DEV_LOCAL_LLM'] = '1'
    client = TestClient(app)
    with client.stream("GET", "/agent/stream") as resp:
        assert resp.status_code == 200
        data = b""
        chunks = []
        for chunk in resp.iter_bytes():
            data += chunk
            text = chunk.decode('utf-8', errors='ignore')
            chunks.append(text)
            if 'done' in text.lower():
                break
        joined = ''.join(chunks)
        # Expect at least one tick and then a done JSON object
        assert 'thinking' in joined.lower() or 'tick' in joined.lower()
    assert 'done' in joined.lower()
