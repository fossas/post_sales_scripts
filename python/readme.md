# Sara's Scripts

This is just an overview of each script I've written, and how to use them.

### projects_affected_by_issues.py
> This script will make an API call to FOSSA, retrieving all issues for an organization. It will then sort the issues by the length of the `parents` attribute, which contains the affected projects. The result is an output containing every issue and which projects are affected, sorted by affected project count. There are some issues surrounding the way issues are handled in the API (we instead provide all vulnerabilities and license issues), so the list will have duplicates. The script might be updated to account for this in the future.
```bash
$ python3 projects_affected_by_issues.py $FOSSA_API_KEY
```
### projects_by_dependency.py
> This script will make an API call to FOSSA, retrieving a list of every project containing a given dependency. Due to the nature of this script, it is better used importing and calling the packages yourself.
```py
import projects_by_dependency

projects = get_packages_using_dependency(package_manager="npm", package_name="coa", package_version="2.0.2")
```

### upload_custom_build.py
> This script will take the output of `fossa analyze -o` and upload it via the `POST /api/builds/custom` endpoint.
```bash
$ fossa analyze -o > fossa_analyze_output.json
$ python3 upload_custom_build.py $FOSSA_API_KEY
```
