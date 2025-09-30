from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_ops_list_shape():
    # ensure list endpoint returns JSON array of objects with id and status
    r = client.get('/ops/tasks')
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j, list)
    if len(j) > 0:
        it = j[0]
        assert 'id' in it
        assert 'status' in it
