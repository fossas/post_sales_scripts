import requests
import json

# To use this script, just include your filters (or use an empty array
# in order to not filter) and your API token, then run it

# LIMITATIONS
# Currently, this converts the license title to lowercase and
# does a substring match. It's not exhaustive, but gives a great
# starting point.

filters = ['gpl', 'bsd', 'mit']
api_token = ""

# DO NOT EDIT
payload={}
headers = {
  "Authorization": f"Bearer {api_token}",
}
url = "https://app.fossa.com/api/projects"
# Getting list of projects
response = requests.request("GET", url, headers=headers, data=payload)
orgId = response.json()[0]["organizationId"]
revisions = [p["last_analyzed_revision"] for p in response.json()]
dep_graph = []
should_filter = len(filters) > 0
# Going through dependencies for all projects
for revision in revisions:
  pshould_add = True
  
  # Don't add project until we know one of its deps has license
  if should_filter:
    pshould_add = False
  dep_url = f"https://app.fossa.com/api/revisions/{revision.replace('/', '%2F').replace('$', '%24')}/dependencies".replace("+", "%2B")
  response = requests.request("GET", dep_url, headers=headers, data=payload)
  deps = []
  # Going through dependency for singular project
  for dep in response.json():
    licenses = list(set([l["title"] for l in dep["licenses"]]))
    should_add = True

    # Don't add dependency until we know it has license
    if should_filter:
      should_add = False
      for lic in licenses:
        for filter in filters:  
          if filter.lower() in lic.lower():
            pshould_add = True
            should_add = True
    if should_add:
      deps.append({
        "dep": dep["locator"],
        "licenses": licenses
      })
      
  if pshould_add:
    dep_graph.append({
      "project": '/'.join(revision.split('/')[1:]),
      "dependencies": deps
    })

print(json.dumps(dep_graph))
