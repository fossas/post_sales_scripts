# Create a new release using the latest revision of each project

# Get release group
# Query for latest revision of each project in the group
# Create a new release using those revisions

# POST release
# title: string, projects: [o]
# p: {branch, projectId, revisionId}

import requests
import json

base_url = 'https://app.fossa.com/api'
  
def encode(project_locator):
  encoded = project_locator.replace('/', '%2F').replace('+', '%2B').replace('$', '%24')
  return encoded

def get_real_latest_revision(headers):
  def tmp(project_locator, branch):
    proj = requests.get(url=f'{base_url}/projects/{encode(project_locator)}', headers=headers).json()['references']
    latest = list(filter(lambda x: x['name'] == branch, proj))
    return latest[0]['revision_id']
  return tmp
  
def get_all_projects(headers, group_id):
  url = f'{base_url}/project_group/{group_id}'
  group = requests.get(url, headers=headers).json()
  latest = list(sorted(group['releases'], key=(lambda x: x['id']), reverse=True))[0]
  projects = requests.get(url=f'{url}/release/{latest["id"]}', headers=headers).json()['projects']
  return list(map(lambda x: (x["projectId"], x["branch"]),projects))
  
def main():
  release_group_id = input("Please enter your release group ID. It can be found in between group and releases in the URL for your release group\n")
  api_key = input("Please enter your API key\n")
  title = input("Please enter the title of the new release\n")
  
  header = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
  projects = get_all_projects(header, release_group_id)
  latest_revisions = list(map(lambda x: (get_real_latest_revision(header)(x[0], x[1]), x[1]), projects))
  p_list = list(map(lambda x: {'branch': x[1], 'revisionId': x[0], 'projectId': x[0].split('$')[0]}, latest_revisions))
  payload = json.dumps({
    'title': title,
    'projects': p_list
  })
  # post
  update = requests.post(url=f'{base_url}/project_group/{release_group_id}/release', headers=header, data=payload)
  if update.status_code == 200:
    print('Successfully created new release')
  else:
    print('Error!')
    # print(update.text)
  
if __name__ == '__main__':
  main()