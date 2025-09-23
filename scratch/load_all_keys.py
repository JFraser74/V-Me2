from supabase import create_client

supabase_url = 'https://lxxeywvpmykkgfcnzexm.supabase.co'
import os
supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')  # Your service_role key

client = create_client(supabase_url, supabase_key)

# Fetch and print all keys
settings = client.table('va_settings').select('*').execute().data
for setting in settings:
    print(f"{setting['key']}: {setting['value']}")