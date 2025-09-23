from supabase import create_client

supabase_url = 'https://lxxeywvpmykkgfcnzexm.supabase.co'
import os
supabase_key = os.environ.get('SUPABASE_SERVICE_KEY')  # Your service_role key

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