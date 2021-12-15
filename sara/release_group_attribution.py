base_url = "https://app.fossa.com/api/project_group"
group_id = "480"
release_id = "711"
format = "TXT" 		# HTML | MD | PDF | CSV | TXT | SPDX
preview = "true" 	# API call will return a preview response
email = "false"		# API call wil email the report to the user who owns the API token

api_token = ""

url = f"{base_url}/{group_id}/release/{release_id}/attribution/{format}?preview={preview}&email={email}"

import requests

payload={}
headers = {
  'Authorization': f'Bearer {api_token}',
}

response = requests.request("GET", url, headers=headers, data=payload)

print(response.text)
