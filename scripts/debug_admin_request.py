import os, sys
from fastapi.testclient import TestClient
from pathlib import Path

# ensure no admin token env at top-level
os.environ['SETTINGS_ADMIN_TOKEN'] = ''
os.environ['CI_SETTINGS_ADMIN_TOKEN'] = ''

# emulate the test environment
os.environ['DEV_LOCAL_LLM'] = '1'
os.environ['SETTINGS_ADMIN_TOKEN'] = ''
os.environ['CI_SETTINGS_ADMIN_TOKEN'] = ''

# ensure project root is on sys.path for imports
proj_root = str(Path(__file__).resolve().parents[1])
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

# ensure fresh import of app
sys.modules.pop('main', None)
import main

client = TestClient(main.app)
resp = client.post('/api/admin/seed_memory')
print('STATUS', resp.status_code)
try:
    print('JSON:', resp.json())
except Exception:
    print('TEXT:', resp.text)

# If server raised, try to get server error details from resp.text
print('RESP TEXT:\n', resp.text)
