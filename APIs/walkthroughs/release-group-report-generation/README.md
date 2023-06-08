## How to generate a release group report

The purpose of this script is to help FOSSA users generate a release group from our [Release Group Report API](https://docs.fossa.com/reference/post_project-group-groupid-release-releaseid-attribution-format).
This is simply an example of how to use it. In this example, the release group report is downloaded to _the user's_ local machine.

### Prerequisites

#### Local build environment
- Have node installed
- Run `npm install`

#### FOSSA report requirements

- Review our release group report API [here](https://docs.fossa.com/reference/post_project-group-groupid-release-releaseid-attribution-format).
- Grab your full access token from the FOSSA organization settings, if you don't have it already.
- Set your `FOSSA_API_KEY` as an environment variable.
- In the FOSSA UI, click on the release group of interest > click the releases tab
  - Notice the URL. It should look something like this `https://app.fossa.com/projects/group/<group id>/releases/<release id>` 
  - Take note of the group id and release id.
- Decide on the report format: HTML, PDF, CSV, TXT, SPDX or SPDX_JSON.
- Decide which fields you'd want to include in the report.
  - Go to `https://app.fossa.com/projects/group/<group id>/export` to see the options.
- Modify the script with the appropriate query parameters. 
- Run the script properly. 
  - For example,  `node release-group-report-generation.js --project-group 123 --release-id 456 --format TXT --fossa-api-key $FOSSA_API_KEY`
  - Run `node release-group-report-generation.js --help` for help.
