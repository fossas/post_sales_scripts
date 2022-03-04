""" This script will tell you how many projects are affected by a vulnerable library """

import re

from python.utils import api, locators


def filter_issues_to_library(library_name, issues):
	new_issues = []
	for issue in issues:
		if issue['type'] == 'vulnerability':
			locator = issue['revision']['loc']
			if locator['package'].lower() == library_name.lower():
				new_issues.append(issue)
	return new_issues


def get_list_of_projects_affected(issues):
	""" Gets list of all projects affected by a vulnerability """
	projects = []
	for issue in issues:
		parents = issue['parents']
		for parent in parents:
			if parent['locator'] not in [project[0] for project in projects]:
				projects.append((parent['locator'], locators.locator_dict_from_str(issue['revision']['locator'])['revision']))
	return projects


def main(api_key):
	# print(f'api key: {api_key}')

	issues = api.issues(api_key)
	package = ''
	user_input = input('Please enter either the library name or the FOSSA "locator" of the library: \n')
	if re.match('.+\+.+\$.+', user_input):
		package = locators.locator_dict_from_str(user_input)['package']
	else:
		package = user_input

	filtered_issues = filter_issues_to_library(package, issues)
	projects_affected = get_list_of_projects_affected(filtered_issues)

	print('---------')
	print(f'You have {len(projects_affected)} projects affected by {package}...')
	# print(f'{i}: {name}' for i, name in enumerate(projects_affected))
	for i, project in enumerate(projects_affected):
		print(f'  - {i + 1}: {project[0]} - {package} v{project[1]}')


if __name__ == '__main__':
	fossa_api_key = api.get_api_key()
	main(fossa_api_key)
