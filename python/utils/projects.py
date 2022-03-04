def list_of_revisions_from_project_dict(project_dict: dict = None) -> list[str]:
	"""
	Returns a list of revisions for a given project.
	"""
	if project_dict is None:
		return []

	revisions = []
	for revision in project_dict['revisions']:
		revisions.append(revision['loc']['revision'])
	return revisions
