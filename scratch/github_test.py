import requests
import base64
import os
from dotenv import load_dotenv
from langchain_experimental.tools import PythonREPLTool

load_dotenv()

github_pat = os.environ.get('GITHUB_PAT')
repo = 'JFraser74/V-Me2'  # Your repo

headers = {
    'Authorization': f'token {github_pat}',
    'Accept': 'application/vnd.github.v3+json'
}

# Read: GET repo
read_url = f'https://api.github.com/repos/{repo}'
read_response = requests.get(read_url, headers=headers)
print('Read test (repo details):', read_response.json() if read_response.ok else read_response.text)

# Write/Edit: PUT test.txt
content = base64.b64encode(b'Test content from Grok').decode('utf-8')
file_path = 'test.txt'
write_url = f'https://api.github.com/repos/{repo}/contents/{file_path}'

check_response = requests.get(write_url, headers=headers)
sha = check_response.json().get('sha') if check_response.ok else None

write_data = {
    'message': 'Test commit from Grok',
    'content': content
}
if sha:
    write_data['sha'] = sha

write_response = requests.put(write_url, headers=headers, json=write_data)
print('Write/Edit test:', write_response.json() if write_response.ok else write_response.text)

# Cleanup: DELETE
if write_response.ok:
    sha = write_response.json()['content']['sha']
    delete_data = {'message': 'Cleanup test file', 'sha': sha}
    delete_response = requests.delete(write_url, headers=headers, json=delete_data)
    print('Cleanup:', delete_response.status_code, delete_response.text)