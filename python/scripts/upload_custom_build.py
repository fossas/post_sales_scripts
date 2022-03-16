# This script takes the output from `fossa analyze -o` and
# 	uploads it to the FOSSA web app

# $ fossa analyze -o > fossa_analyze_output.json
# $ python3 upload_custom_build.py $FOSSA_API_KEY
import requests
import json
import sys

fetcher = 'custom' 												# DO NOT CHANGE
project_title = 'discordbot' 									# The title the project will be uploaded as in FOSSA
org_id = 27932													# Your FOSSA organization ID (hit any FOSSA API endpoint to get this (organizationId))
loc_name = 'github.com/codesupport/discord-bot'					# You can get this from the FOSSA web app :) Projects > [project name] > Settings
rev_id = '3148981cc90b359472fc8da7481bd7cd8f0878bb'				# The hash of the most recent commit on git (or whatever ID you'd like to call the revision by)
file_name = 'fossa_analyze_output.json'							# The name of the file containing the output of `fossa analyze -o`

if __name__ == "__main__":
	with open(file_name) as json_file:
		url = f"https://app.fossa.com/api/builds/custom?managedBuild=true&locator={fetcher}%2B{org_id}/{loc_name}${rev_id}"

		payload = json.load(json_file)["sourceUnits"]

		headers = {
			'Authorization': f'Bearer api_key',
			'Content-Type': 'application/json'
		}

		response = requests.request("POST", url, headers=headers, json=payload)

		print(response.text)

# TODO: Refactor for new tooling and add support for custom filepath


def main():
	...
