from python.utils import api, locators, urls


def upload_custom_build(params={}, data={}, api_key=None):
	data = {
		"N"
	}
	...


def get_project_dependencies(revision_dict):
	""" Gets array containing locators of all dependencies of a project. """
	deps = []
	for dep in revision_dict['dependencies']:
		deps.append(dep['locator'])
	return deps


def main(api_key):
	print("Which revision would you like to replace?")
	print("(Please enter the link to the revision")
	revision_link = input("> ")
	revision_loc = urls.project_locator_from_url(revision_link)
	revision = api.revisions(revision_loc, api_key)
	parent_loc = revision['parent_locator']
	print(f'Would you like to replace this with {parent_loc}?')
	yn = input("> ")
	if yn.lower() == 'y':
		# Get the parent revision and upload custom build to current revision
		ploc = locators.project_locator_dict_from_str(parent_loc)
		parent_rev = api.revisions(ploc, api_key)
		parent_deps = get_project_dependencies(parent_rev)
		print(parent_deps)
	else:
		print("Aborting...")
