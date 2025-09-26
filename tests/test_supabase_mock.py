# tests/test_supabase_mock.py
import sys
# ensure project root is on sys.path
sys.path.insert(0, '.')

from vme_lib import supabase_client

# Provide a mock _client that exposes table(...).insert(...).execute()
def _mock_client():
    class MockExecResult:
        def __init__(self):
            self.data = [{"id": 999}]
        def execute(self):
            return self

    class Inserter:
        def insert(self, payload):
            # ignore payload and return an object that .execute() returns itself
            return MockExecResult()

    class TableAccessor:
        def table(self, name):
            # return an inserter object (for chain .insert(...).execute())
            return Inserter()

    return TableAccessor()

# Inject mock into the module under test
supabase_client._client = _mock_client

# Call create_session - should return the mock id 999
print("create_session returned:", supabase_client.create_session("test label"))

# Call safe_log_message - shouldn't raise, just returns None
supabase_client.safe_log_message("999", "user", "hello world")
print("safe_log_message completed (no exception)")

