# This program makes an api call to FOSSA to retrieve all issues
# and then sorts those results by length of `parents` attribute

# Because this pulls from /issues, this will list a given dependency for every vulnerability in that dependency
# For example, if npm+my_package$1.0.0 has 4 vulnerabilities, then my_package will be listed as an entry 4 times
# TODO: de-dupe entries

# usage: python3 projects_affected_by_issues.py <fossa auth token>

import sys
import requests

def api_call():
	bearer_token = sys.argv[1]
	link = "https://app.fossa.com/api/issues"
	headers = {"Authorization" : f"Bearer {bearer_token}"}

	response = requests.get(link, headers=headers)
	return response.json()

def sort_func(el):
	return len(el['parents'])


def main_func():
	api_response = api_call()
	sorted_response = sorted(api_response, key=sort_func, reverse=True)

	for el in sorted_response:
		loc = el["revision"]["locator"] # getting the FOSSA locator, which provides the type, name, and version of the dependency
		print(el["revision"]["project"]["title"] + " v" + loc.split('$')[1]) # prints the name of the dependency along with the version
		print(f" | FOSSA Locator: {loc}") # provides full locator
		print(" | Affected Projects:")
		for parent in el["parents"]:
			title = parent['title']
			print(f' | | {title}') # prints the title of all projects containing the problematic dependency
		print('-------------')


if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Please enter your FOSSA Auth Token")
		print("Usage: python3 demo.py <FOSSA Auth Token>")
	else:
		main_func()