#!/usr/bin/python3

import requests
import json
import os

# build the request
fossa_api_token = os.environ['FOSSA_API_KEY']
url_endpoint = 'https://app.fossa.com/api/issues'

headersAuth = {
'accept': 'application/json',
    'Authorization': 'Bearer ' + fossa_api_token,
}

params = (
('scanScope[type]', 'project'),
('scanScope[projectId]', ''),
('scanScope[revisionId]', ''),
('scanScope[revisionScanId]', ''),
('type', 'vulnerability')
)


response = requests.get(url_endpoint, headers=headersAuth, params=params, verify=True)
api_response = json.dumps(response.json())

print(api_response)
