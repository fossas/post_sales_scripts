const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');
const groupBy = require('lodash.groupby');

const argv = yargs(hideBin(process.argv))
  .command('$0')
  .option('issue', {
    type: 'string',
    description: 'ID of the FOSSA issue that references all the projects to scan',
  })
  .option('endpoint', {
    type: 'string',
    description: 'FOSSA API service base URL',
  })
  .demandOption(['issue'])
  .parse();

require('dotenv-safe').config();
const fossa = require('./fossa')({ token: process.env.FOSSA_API_TOKEN, endpoint: argv.endpoint });

// query the one issue we're looking at
// get the vulnerable dependency's locator for that issue
// query list-minimal
// filter down all parents that are relevant to that dependency locator
// for each project, re-scan

const issue = fossa.getIssues({
  params: {
    id: argv.issue,
  },
}).then(issues => {
  if (issues.length !== 1) {
    return Promise.reject(`Expected to receive exactly 1 issue, got ${issues.length}`);
  }
  return issues[0];
});

const listMinimal = fossa.listMinimal({
  params: {
    'scanScope[type]': 'global',
    'status': 'active',
    'types[0]': 'vulnerability',
  },
});

Promise.all([issue, listMinimal]).then(([issue, list]) => {
  console.log('Finding target projects to re-scan...');
  // revision.project.locator has fetcher+dependency only, to match against all
  // versions of the vulnerable dependency
  const targetRevisions = list
    .filter(i => i.revision.project.locator === issue.revision.project.locator)
    .flatMap(i => i.parents.map(p => p.last_analyzed_revision));
  const dedupedRevisions = [...new Set(targetRevisions)];
  const scans = dedupedRevisions.map(r => {
    console.log(`Scanning ${r} ...`);
    return fossa.scanRevision(r).then(locator => {
      console.log(`Successfully scanned ${locator}`);
      return locator;
    }).catch(e => {
      console.error(`Failed to scan ${r}`, e);
      throw e;
    });
  });
  return Promise.allSettled(scans);
}).then(results => {
  const { fulfilled, rejected } = groupBy(results, r => r.status);
  if (fulfilled) {
    console.log('Successfully scanned:\n');
    console.log(fulfilled.map(r => r.value).join('\n'));
  }
  if (rejected) {
    console.log('\nFailed to scan:\n');
    console.log(rejected.map(r => r.reason.config.url + '\n' + r.reason + '\n').join('\n'));
    process.exit(1);
  }
  console.log('All projects scanned successfully!');
}).catch (e => {
  console.error(e);
  process.exit(1);
})
