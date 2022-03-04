from python.scripts import number_of_projects_containing_vulnerable_library, projects_affected_by_issues, \
	projects_by_dependency, release_group_attribution, upload_custom_build, policy_id_from_link_to_scan


def get_scripts():
	print('If you are interested in one of the deprecated scripts, please contact Sara to update it. sara@fossa.com')
	a = "DEPRECATED Get a list of all vulnerabilities in your organization, sorted by number of projects containing the " \
	    "vulnerability"

	scripts = [
		{
			"name": "Get all projects containing a vulnerable library",
			"function": number_of_projects_containing_vulnerable_library.main
		},
		{
			"name": "Generate an attribution report for a release group",
			"function": release_group_attribution.main
		},
		{
			"name": "Get the policy ID for any scans of a given project revision",
			"function": policy_id_from_link_to_scan.main
		},
		{
			"name": a,
			"function": projects_affected_by_issues.main_func
		},
		{
			"name": "DEPRECATED Get a list of all projects containing a given dependency",
			"function": projects_by_dependency.main
		},
		{
			"name": "DEPRECATED Upload the output from 'fossa analyze -o' to the FOSSA Web App",
			"function": upload_custom_build.main
		},
	]
	return scripts
