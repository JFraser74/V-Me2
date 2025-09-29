import os
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_stream_fake_mode():
    # Ensure fake/local mode
    os.environ['DEV_LOCAL_LLM'] = '1'
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

*** End Patch