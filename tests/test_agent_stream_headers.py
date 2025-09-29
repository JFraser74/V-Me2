import os
from fastapi.testclient import TestClient
from main import app


def test_agent_stream_content_type_header():
    # ensure fake-mode for determinism
    os.environ['DEV_LOCAL_LLM'] = '1'
    client = TestClient(app)
    with client.stream('GET', '/agent/stream?message=hello') as resp:
        assert resp.status_code == 200
        # event-stream content type
        ctype = resp.headers.get('content-type','')
        assert 'text/event-stream' in ctype
