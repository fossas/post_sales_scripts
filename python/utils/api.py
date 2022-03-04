import os
from typing import Optional

import requests  # type: ignore


def request(endpoint, method, data=None, api_key=None) -> requests.Response:
	"""
	Send a request to the API

	:param endpoint: The endpoint to send the request to
	:param method: The HTTP method to use
	:param data: The data to send with the request
	:param api_key: Your FOSSA API key
	"""
	base_url = 'https://app.fossa.com/api/'
	url = f'{base_url}{endpoint}'

	if api_key is None:
		if 'FOSSA_API_KEY' in os.environ:
			api_key = os.environ['FOSSA_API_KEY']
		else:
			raise PermissionError('You must provide an API key')

	headers = {
		'Authorization': 'Bearer ' + api_key,
	}
	if method == 'GET':
		response = requests.get(url, headers=headers)
	elif method == 'POST':
		response = requests.post(url, headers=headers, data=data)
	else:
		raise UserWarning('Invalid method')
	return response


def issues(api_key=None) -> list:
	"""
	Get all issues for an organization.

	:param api_key: Your FOSSA API key
	"""
	response = request('issues', 'GET', data=None, api_key=api_key)
	return response.json()


def release_group_attribution_reports(group_id, release_id, output_format, preview=True, email=None, api_key=None):
	"""
	Get a release group attribution report

	:param group_id: The group ID to get the report for
	:param release_id: The release ID to get the report for
	:param output_format: HTML | MD | PDF | CSV | TXT | SPDX
	:param preview: Whether to preview the report
	:param email: The email address to send the report to
	:param api_key: Your FOSSA API key
	"""

	include_direct_deps = 'includeDirectDependencies=true'
	include_deep_deps = 'includeDeepDependencies=true'

	params = f'{include_direct_deps}&{include_deep_deps}'
	if preview:
		params += '&preview=true'
	else:
		params += f'&email=true&emailAddress={email}'

	endpoint = f'project_group/{group_id}/release/{release_id}/attribution/{output_format}?{params}'

	response = request(endpoint, 'GET', data=None, api_key=api_key)
	return response.json()


def projects(api_key=None) -> list:
	"""
	Get all projects for an organization.

	:param api_key: Your FOSSA API key
	"""
	response = request('projects', 'GET', data=None, api_key=api_key)
	return response.json()


def project(project_locator_dict, api_key=None) -> Optional[dict]:
	"""
	Get a project by locator.

	:param project_locator_dict: {fetcher, package, revision}
	:param api_key: Your FOSSA API key

	:return: The project dict
	"""
	response = projects(api_key=api_key)
	for my_project in response:
		tmp_locator = f'{project_locator_dict["fetcher"]}/{project_locator_dict["package"]}'.replace('%2B', '+')
		if my_project['locator'] == tmp_locator:
			return my_project
	return None


def revisions(project_locator: dict, api_key: Optional[str] = None) -> dict:
	"""
	Get all revisions for a project.

	:param project_locator: {fetcher, package}
	:param api_key: Your FOSSA API key (optional)

	:return: The revisions list
	"""
	locator_url = f'{project_locator["fetcher"]}%2F{project_locator["package"]}%24{project_locator["revision"]}'
	response = request(f'revisions/{locator_url}', 'GET', data=None, api_key=api_key)
	return response.json()


def get_api_key() -> str:
	"""
	Detect the API key from the environment or asks the user for one
	"""
	api_key = None
	if 'FOSSA_API_KEY' in os.environ:
		api_key = os.environ['FOSSA_API_KEY']

	if api_key is None:
		print('No API key found in the environment...')
	else:
		print('Would you prefer to use the API key found in the environment, or provide your own?')
		print('1. Use the API key found in the environment')
		print('2. Provide your own')
		_choice = input('> ')
		if _choice == '1':
			return api_key

	print('Please provide your FOSSA API key:')
	api_key = input('> ')
	return api_key


if __name__ == '__main__':
	key = get_api_key()
	print(key)
