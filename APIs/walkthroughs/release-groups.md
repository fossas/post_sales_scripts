## Release Groups

### Add projects to a release group
The API is POST https://app.fossa.com/api/project_group. Here's an example payload:
```
{
	"title": "Test-Name",
	"release": {
		"projects": [{
			"projectId": "custom+12948/python-test",
			"branch": "master",
			"revisionId": "custom+12948/python-test$2023-03-01T14:56:57Z"
		}, {
			"projectId": "custom+12948/github.com/fossas/fossa-vendored-dependencies-test",
			"branch": "master",
			"revisionId": "custom+12948/github.com/fossas/fossa-vendored-dependencies-test$c75cfe87e51a34eeaf4fff393cc1bcc5b62b6697"
		}, {
			"projectId": "custom+12948/git@github.com:fossas/post_sales_scripts.git",
			"branch": "main",
			"revisionId": "custom+12948/git@github.com:fossas/post_sales_scripts.git$ce78dcbb04fb232e5a5956dac90545d95829340a"
		}, {
			"projectId": "custom+12948/c-cpp-test",
			"branch": "master",
			"revisionId": "custom+12948/c-cpp-test$2022-12-09T22:39:16Z"
		}],
		"title": "Test-Release"
	},
	"licensingPolicyId": 32585,
	"securityPolicyId": 77403,
	"teams": [1768, 2000]
}
```

This assumes the teams have access to the repos in the release group. If not, you would have to run this endpoint first: `PUT https://app.fossa.com/api/teams/<team id>/projects`
Here's an example payload of that:
```
{
	"projects": [
    "custom+12948/python-test", 
    "custom+12948/github.com/fossas/fossa-vendored-dependencies-test", 
    "custom+12948/git@github.com:fossas/post_sales_scripts.git", 
    "custom+12948/c-cpp-test"
  ],
	"action": "add"
}
```
Do note that specifying the policies and teams are optional though, so you'd have to adjust the first request payload above accordingly.



### Update an existing release group

Here's the endpoint: `PUT https://app.fossa.com/api/project_group/<project-group-id>/release/<release-group-id>`,
where `<project-group-id>` is basically the ID of the release group and `<release-group-id>` is the version of release group.

Here's the request payload to update an existing release group:
```
{
	"title": "<specify-existing-version>",
	"projects": [{
		"projectId": "<project-locator>",
		"branch": "<branch>",
		"revisionId": "<project-locator>$<revision-id>",
		"projectGroupReleaseId": <release-group-id-which-is-basically-the-version>
	}],
	"projectsToDelete": []
}
```
Example:

```
{
	"title": "1.0",
	"projects": [{
		"projectId": "custom+8617/dummycom/experience-everything/experience-something",
		"branch": "main",
		"revisionId": "custom+8617/dummycom/experience-everything/experience-something$some-revision-id",
		"projectGroupReleaseId": some-number
	}]
	"projectsToDelete": []
}
```

You can get the latest revision by sorting the response by updatedAt
API: `https://app.fossa.com/api/revisions?projectId=<url-encoded-project-locator>`

### Troubleshooting

#### What if I receive a 500 error code from running this POST endpoint?
It could mean that you have duped projects in the request payload.
