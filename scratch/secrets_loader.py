import os
from dotenv import load_dotenv # type: ignore
from supabase import create_client

def load_secrets(supabase_url, supabase_key):
    client = create_client(supabase_url, supabase_key)
    settings = client.table('va_settings').select('*').execute().data
    for setting in settings:
        os.environ[setting['key']] = setting['value']
    
    with open('.env', 'w') as f:
        for k, v in os.environ.items():
            if k in ['GITHUB_PAT', 'SUPABASE_SERVICE_KEY', 'OPENAI_API_KEY', 'GROQ_API_KEY', 'SERPAPI_KEY', 'RAILWAY_API_TOKEN', 'CLOUDFLARE_API_TOKEN', 'GOOGLE_SERVICE_ACCOUNT_JSON', 'TWILIO_API_KEY']:
                f.write(f"{k}={v}\n")
    
    import datetime
    backup = f".env.bak.{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    os.system(f"cp .env {backup}")
    
    load_dotenv()
    return 'Secrets loaded and backed up.'

# Call with your Supabase details (from va_settings or Sheet2)
print(load_secrets('https://lxxeywvpmykkgfcnzexm.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx4eGV5d3ZwbXlra2dmY256ZXhtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODA3Nzc0NSwiZXhwIjoyMDczNjUzNzQ1fQ.4NDsDiZhc5C2I5QKaONhj9FhDTCUmS87w5aIlME9kTQ'))