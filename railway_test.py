import requests
import os
from dotenv import load_dotenv
load_dotenv()

railway_token = os.environ.get('RAILWAY_API_TOKEN')

headers = {
    'Authorization': f'Bearer {railway_token}',
    'Content-Type': 'application/json'
}

# Read: GET projects
read_url = 'https://backboard.railway.app/graphql/v2'
read_query = {
  "query": "{ projects { edges { node { id name } } } }"
}
read_response = requests.post(read_url, headers=headers, json=read_query)
print('Read test (projects):', read_response.json() if read_response.ok else read_response.text)

# For write/edit/cleanup, we'd need a test resource; skip for now or use dashboard to confirm project linked to V-Me2 repo.