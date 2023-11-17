import os
import requests
import sys

# Check if FOSSA_API_KEY is set
fossa_api_key = os.environ.get('FOSSA_API_KEY')
if not fossa_api_key:
    exit("FOSSA_API_KEY is not set. Please set the environment variable.")

# Set the FOSSA API base URL
v2_api_base_url = "https://app.fossa.com/api/v2"
fossa_api_key_header = {"Authorization": f"Bearer {fossa_api_key}"}

# Function to get team names for a project
def get_team_names(project):
    teams = project.get('teams', [])
    team_names = [team['name'] for team in teams]
    return ",".join(team_names)

# Get all projects from v2 endpoint with pagination
page = 1
projects_data = []
while True:
    response = requests.get(f"{v2_api_base_url}/projects?count=1000&page={page}", headers=fossa_api_key_header)
    response.raise_for_status()
    page_data = response.json().get('projects', [])
    if not page_data:
        break
    projects_data.extend(page_data)
    page += 1

# Print CSV header
print("ProjectTitle,TeamNames")

# Loop through each project and print project details
for project in projects_data:
    project_title = project.get('title', 'Unknown Project')
    team_names = get_team_names(project)
    print(f"{project_title},{team_names}")
