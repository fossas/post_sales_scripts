from python.utils import api, locators, projects, urls


def main(api_key) -> None:
	"""
	Retrieve the policy ID of a scan for a given revision of your FOSSA project.

	:param api_key:
	"""
	print('To get the link required, please open a project, and then select a revision beneath the project name')
	a = 'The link should look like: https://app.fossa.com/projects/custom%2B<org-id>>%2F<project-name>/refs/branch/<b' \
	    'ranch-name>/<revision-id>'
	print(a)
	print('Please enter the link to the summary page of the project revision you want to evaluate:')
	link = input('>')
	locator_dict = urls.project_locator_from_url(link)
	if locator_dict is None:
		print('The link you provided is not valid.')
		return

	revision_scans = api.revisions(locator_dict, api_key)['revisionScans']
	if revision_scans is None:
		print('The revisions were unable to be found. Please try again.')
		return main(api_key)

	scans: list = []
	if len(revision_scans) == 0:
		print('No scans were found for this revision.')
		return None
	elif len(revision_scans) == 1:
		print(f'Only one scan was found for revision #{locator_dict["revision"]}.')
		print('The policy ID of the scan is:')
		print(revision_scans[0]['licensingPolicyVersionId'])
	else:

		if len(revision_scans) > 10:
			print(f'There are {len(revision_scans)} scans for revision #{locator_dict["revision"]}.')
			print('Currently, no filtering is available beyond the most recent <number> scans. Filtering by date is coming.')
			print('Please enter the number of the scan you want to see (0 for all scans:')
			scan_number = input('> ')
			if scan_number == '0':
				scans = revision_scans
			else:
				scans = revision_scans[:int(scan_number)]
		for scan in scans:
			print(f'The policy ID of scan {scan["id"]} ({scan["scanned_at"]} UTC) is:')
			print(scan['licensingPolicyVersionId'])
