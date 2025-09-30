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
# Railway support supplied this corrected GraphQL query body; it returns the
# current authenticated user's workspaces and projects. Use RAILWAY_API_TOKEN
# (or RAILWAY_PAT) in the environment when calling the backboard GraphQL API.
read_query = {
  "query": """query me {
    me {
      workspaces {
        projects {
          edges {
            node {
              id
              name
            }
          }
        }
      }
    }
  }"""
}
read_response = requests.post(read_url, headers=headers, json=read_query)
print('Read test (projects):', read_response.json() if read_response.ok else read_response.text)

# For write/edit/cleanup, we'd need a test resource; skip for now or use dashboard to confirm project linked to V-Me2 repo.

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

# install (if not installed) — check Railway docs for installer
# CLI examples (commented out so this file remains valid Python):
# railway login
#
# link/init project from this repo
# railway init            # or `railway link` to attach to existing project
# create a new service (if CLI supports)
# railway service create <service-name>  # CLI command may differ; check `railway help`
# set a variable in the current Railway project (recommended over putting tokens in files)
# railway variables set RAILWAY_PAT "paste_token_here"