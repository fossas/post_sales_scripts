import requests

base_url = "https://app.fossa.com/api/project_group"
group_id = "480"
release_id = "711"
format = "MD" 		# HTML | MD | PDF | CSV | TXT | SPDX
result = "PREVIEW" 	# EMAIL | PREVIEW | (result will be previewed if left blank)

params = "&email=true" if result == "EMAIL" else "&preview=true"

api_token = "7bb41698795dd03f00bdc2bb66375c0f"

url = f"{base_url}/{group_id}/release/{release_id}/attribution/{format}?includeDirectDependencies=true&includeDeepDependencies=true{params}"

payload={}
headers = {
  'Authorization': f'Bearer {api_token}',
}

response = requests.request("GET", url, headers=headers, data=payload)

print(response.text)