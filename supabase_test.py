import requests
import os
from dotenv import load_dotenv
load_dotenv()

supabase_url = 'https://lxxeywvpmykkgfcnzexm.supabase.co/rest/v1'
supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')

headers = {
    'apikey': supabase_key,
    'Authorization': f'Bearer {supabase_key}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}

# Read: GET va_settings temperature
read_url = f'{supabase_url}/va_settings?select=*&key=eq.temperature'
read_response = requests.get(read_url, headers=headers)
print('Read test:', read_response.json() if read_response.ok else read_response.text)

# Write: POST to errors with Wah mock
write_url = f'{supabase_url}/errors'
write_data = {'type': 'test', 'severity': 'low', 'timestamp': '2025-09-17T00:00:00Z', 'notes': 'Wah vendor H & H Rock'}
write_response = requests.post(write_url, headers=headers, json=write_data)
print('Write test:', write_response.json() if write_response.ok else write_response.text)

inserted_id = write_response.json()[0]['id'] if write_response.ok else None

# Edit: PATCH
if inserted_id:
    update_url = f'{supabase_url}/errors?id=eq.{inserted_id}'
    update_data = {'severity': 'medium'}
    update_response = requests.patch(update_url, headers=headers, json=update_data)
    print('Edit test:', update_response.json() if update_response.ok else update_response.text)

# Cleanup: DELETE
if inserted_id:
    delete_url = f'{supabase_url}/errors?id=eq.{inserted_id}'
    delete_response = requests.delete(delete_url, headers=headers)
    print('Cleanup:', delete_response.status_code, delete_response.text)