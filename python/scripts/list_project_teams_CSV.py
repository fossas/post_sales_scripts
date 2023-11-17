import os
import requests

# Check if FOSSA_API_KEY is set
fossa_api_key = os.environ.get('FOSSA_API_KEY')
if not fossa_api_key:
    exit("FOSSA_API_KEY is not set. Please set the environment variable.")

# Set FOSSA API base URL
fossa_api_base_url = "https://app.fossa.com/api"
fossa_api_key_header = {"Authorization": f"Bearer {fossa_api_key}"}

# Get all projects
projects = requests.get(f"{fossa_api_base_url}/projects", headers=fossa_api_key_header).json()

# Create and print CSV header
print("ProjectTitle,TeamNames")

# Loop through projects and print their details
for p in projects:
    title = p.get('title')
    teams = [requests.get(f"{fossa_api_base_url}/teams/{t['teamId']}", headers=fossa_api_key_header).json().get('name') for t in p.get('teamProjects', [])]
    print(f"{title},{','.join(teams)}")
