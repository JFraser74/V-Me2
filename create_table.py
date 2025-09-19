from supabase import create_client

supabase_url = 'https://lxxeywvpmykkgfcnzexm.supabase.co'
supabase_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx4eGV5d3ZwbXlra2dmY256ZXhtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODA3Nzc0NSwiZXhwIjoyMDczNjUzNzQ1fQ.4NDsDiZhc5C2I5QKaONhj9FhDTCUmS87w5aIlME9kTQ'  # Your service_role key

client = create_client(supabase_url, supabase_key)

# Create va_settings if not exists
create_sql = """
CREATE TABLE IF NOT EXISTS public.va_settings (
    key text PRIMARY KEY,
    value text NOT NULL,
    updated_at timestamptz DEFAULT now()
);
"""

response = client.rpc('execute_sql', {'sql': create_sql}).execute()
if response.data:
    print('Table created successfully.')
else:
    print('Error creating table:', response.error)