import os, sys
from pathlib import Path

# env
os.environ['DEV_LOCAL_LLM'] = '1'
os.environ['SETTINGS_ADMIN_TOKEN'] = ''
os.environ['CI_SETTINGS_ADMIN_TOKEN'] = ''

proj_root = str(Path(__file__).resolve().parents[1])
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from vme_lib import supabase_client as sb

class _FakeRes:
    def __init__(self, data=None):
        self.data = data or []

class _FakeTable:
    def select(self, *args, **kwargs):
        return self
    def eq(self, *args, **kwargs):
        return self
    def limit(self, *args, **kwargs):
        return self
    def execute(self):
        return _FakeRes([])
    def insert(self, payload):
        return _FakeRes([{'id': 999}])

class _FakeClient:
    def table(self, name):
        return _FakeTable()

# monkeypatch the client function on module
sb._client = lambda: _FakeClient()

import main
from fastapi.testclient import TestClient

client = TestClient(main.app)
resp = client.post('/api/admin/seed_memory')
print('STATUS', resp.status_code)
try:
    print('JSON:', resp.json())
except Exception:
    print('TEXT:', resp.text)

print('RESP TEXT:\n', resp.text)
