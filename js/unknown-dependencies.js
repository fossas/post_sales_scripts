#!/usr/bin/env node

// Fetches all unknown dependencies from all FOSSA projects

const Promise = require('bluebird');
const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');

const argv = yargs(hideBin(process.argv))
  .command('$0')
  .option('endpoint', {
    type: 'string',
    description: 'FOSSA API service base URL',
  })
  .parse();

require('dotenv-safe').config();

const fossa = require('./fossa')({ token: process.env.FOSSA_API_TOKEN, endpoint: argv.endpoint });
const projectURL = locator => `${fossa.options.endpoint}/projects/${encodeURIComponent(locator)}`;

// project revisions that haven't been scanned will return 404, which we can
// safely ignore
const ignore404 = (status) => status === 404 || (status >= 200 && status < 300)


async function main() {
  console.error('Fetching all projects...') ;
  const projects = await fossa.getProjects();
  console.error('Fetching dependencies for each project...');
  const projectRevisions = await Promise.all(
    Promise.map(projects, ({last_analyzed_revision}) => {
      return fossa.getDependenciesRaw(last_analyzed_revision, { validateStatus: ignore404 }).then(({data, status}) => status === 200 ? [projectURL(last_analyzed_revision), data] : []);
    }, { concurrency: 10 })
  );
  const isUnknownLocator = ({loc}) => loc.fetcher === null;
  const getLocator = ({DependencyLock}) => DependencyLock.unresolved_locators;
  projectRevisions
    .filter(rev => rev.length > 0)
    .map(([project, deps]) => ({project, unknownDeps: (deps || []).filter(isUnknownLocator).flatMap(getLocator)}))
    .filter(({_, unknownDeps}) => unknownDeps.length > 0)
    .forEach(r => console.log(JSON.stringify(r)));
}

main();

