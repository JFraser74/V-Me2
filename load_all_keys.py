from supabase import create_client

supabase_url = 'https://lxxeywvpmykkgfcnzexm.supabase.co'
supabase_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx4eGV5d3ZwbXlra2dmY256ZXhtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODA3Nzc0NSwiZXhwIjoyMDczNjUzNzQ1fQ.4NDsDiZhc5C2I5QKaONhj9FhDTCUmS87w5aIlME9kTQ'  # Your service_role key

client = create_client(supabase_url, supabase_key)

# Fetch and print all keys
settings = client.table('va_settings').select('*').execute().data
for setting in settings:
    print(f"{setting['key']}: {setting['value']}")