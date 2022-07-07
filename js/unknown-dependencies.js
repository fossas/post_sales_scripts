#!/usr/bin/env node

// Fetches all unknown dependencies from all FOSSA projects. The output of this program can be processed by tools such as jq in different ways:
//
// Show a simple list of all unknown dependencies
// jq --raw-output .unknownDeps[] | sort | uniq
//
// Ignore different versions of the same unknown dependency:
// jq --raw-output .unknownDeps[] | awk --field-separator $ '{print $1}' | sort | uniq
//
// Show only project names and not any dependencies
// jq --raw-output .project

const Promise = require('bluebird');
const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');

const argv = yargs(hideBin(process.argv))
  .command('$0')
  .option('endpoint', {
    type: 'string',
    description: 'FOSSA API service base URL',
  })
  .option('project', {
    type: 'array',
    description: 'Project locator to fetch unknown dependencies from',
  })
  .parse();

require('dotenv-safe').config();

const fossa = require('./fossa')({ token: process.env.FOSSA_API_TOKEN, endpoint: argv.endpoint });
const parseProjectLocator = locator => /(?<title>custom\+([0-9]+)\/(.*))\$(?<revision>.*)/.exec(locator)?.groups || {title: null, revision: null};
const projectURL = locator => {
  const { title, revision } = parseProjectLocator(locator);
  return `${fossa.options.endpoint}/projects/${encodeURIComponent(title)}/refs/revision/${encodeURIComponent(revision)}`;
};

async function main() {
  let projects = [];
  if (!argv.project.length) {
    console.error('Fetching all projects...') ;
    projects = await fossa.getProjects();
  } else {
    projects = await Promise.all(argv.project.map(locator => {
      console.error(`Fetching project ${locator}...`);
      return fossa.getProject(locator);
    }));
  }
  console.error(`Fetching dependencies for ${projects.length} project(s)...`);
  const projectRevisions = await Promise.map(projects, ({last_analyzed_revision}) => {
      return fossa
        .getUnknownDependencies(last_analyzed_revision)
        .then(unknownDeps => ({ project: projectURL(last_analyzed_revision), unknownDeps }))
    }, { concurrency: 3 })
    .filter(({unknownDeps}) => unknownDeps.length > 0);
  projectRevisions.forEach(r => console.log(JSON.stringify(r)))
}

main();

