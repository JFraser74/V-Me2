import os
import json
import base64
from cryptography.fernet import Fernet
import vme_lib.supabase_client as sbmod


def test_settings_put_and_list(monkeypatch, tmp_path):
    # Mock _client to return a fake object with table()/upsert()/select() behavior
    class FakeTable:
        def __init__(self):
            self.storage = {}

        def upsert(self, payload):
            # payload: {'key': k, 'value': v}
            self.storage[payload['key']] = payload['value']
            # Return a query-like object that supports on_conflict(...).execute()
            class Query:
                def __init__(self, table_ref):
                    self._table = table_ref

                def on_conflict(self, _):
                    return self

                def execute(self):
                    class R: pass
                    return R()

            return Query(self)

        def on_conflict(self, _):
            return self

        def select(self, *_args, **_kwargs):
            class Exec:
                def __init__(self, data):
                    self.data = data
                def execute(self):
                    class R: pass
                    inst = R()
                    inst.data = [{'key': k, 'value': v} for k, v in table.storage.items()]
                    return inst
            return Exec(None)

    class FakeClient:
        def __init__(self):
            self.table_map = {}
        def table(self, name):
            if name not in self.table_map:
                self.table_map[name] = table
            return table

    table = FakeTable()
    fake_client = FakeClient()

    monkeypatch.setattr(sbmod, '_client', lambda: fake_client)

    # Set an APP_ENCRYPTION_KEY so settings_put encrypts secret keys
    key = Fernet.generate_key().decode()
    monkeypatch.setenv('APP_ENCRYPTION_KEY', key)

    # Put a secret
    sbmod.settings_put({'OPENAI_API_KEY': 'sk-test-1234', 'OTHER': 'val'})

    # Now list settings and ensure secret is masked or shows enc(v1)
    out = sbmod.settings_list()
    assert 'OPENAI_API_KEY' in out
    # Encrypted value should show marker
    assert out['OPENAI_API_KEY'].startswith('enc') or out['OPENAI_API_KEY'].startswith('*')
