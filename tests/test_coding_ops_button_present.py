from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_ops_button_present():
    r = client.get('/static/coding.html')
    assert r.status_code == 200
    soup = BeautifulSoup(r.text, 'html.parser')
    btn = soup.select_one('#btnNewOps')
    assert btn is not None
