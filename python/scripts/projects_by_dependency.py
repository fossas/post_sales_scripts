# This script is a quick way to pull all projects in an org given a specific locator or dependency information.

# Set the environment variable `API_KEY` to your [FOSSA API Key](https://docs.fossa.com/docs/api-reference)

# `get_packages_using_dependency(package_manager="npm", package_name="coa", package_version="2.0.2")`

# `get_packages_using_locator(locator="npm+coa$2.0.2")`

# TODO: refactor to use new tooling

import requests
from os import environ

def get_packages_using_dependency(package_manager="npm", package_name="coa", package_version="2.0.2"):

	url = f"https://app.fossa.com/api/revisions/{package_manager}%2B{package_name}%24{package_version}/parent_projects"

	payload={}
	headers = {
	'Authorization': f'Bearer {environ.get("API_KEY")}',
	}
	response = requests.request("GET", url, headers=headers, data=payload)

	return response.text


def get_packages_using_locator(locator="npm+coa$2.0.2"):

	new_loc = locator.replace("+", "%2B").replace("$", "%24")

	url = f"https://app.fossa.com/api/revisions/{new_loc}/parent_projects"

	payload={}
	headers = {
	'Authorization': f'Bearer {environ.get("API_KEY")}',
	}

	response = requests.request("GET", url, headers=headers, data=payload)

	return response.text

def main():
	# TODO: implement
	...

if __name__ == "__main__":
	print(get_packages_using_locator())
