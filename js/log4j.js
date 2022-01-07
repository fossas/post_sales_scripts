// Very similar to projects-with-dependencies.js, but only searches for log4j
// dependencies. The list of versions are hardcoded in this file because the GET
// /api/projects/{locator}/revisions endpoint only returns a maximum of 10
// versions for each dependency.
//
// Outputs a list of projects that use each log4j dependency along with their
// specific versions.

const yargs = require('yargs/yargs');
const compareVersions = require('compare-versions');
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

const log4j2Versions = [
  '2.0-alpha1',
  '2.0-alpha2',
  '2.0-beta1',
  '2.0-beta2',
  '2.0-beta3',
  '2.0-beta4',
  '2.0-beta5',
  '2.0-beta6',
  '2.0-beta7',
  '2.0-beta8',
  '2.0-beta9',
  '2.0-rc1',
  '2.0-rc2',
  '2.0',
  '2.0.1',
  '2.0.2',
  '2.1',
  '2.2',
  '2.3',
  '2.4',
  '2.4.1',
  '2.5',
  '2.6',
  '2.6.1',
  '2.6.2',
  '2.7',
  '2.8',
  '2.8.1',
  '2.8.2',
  '2.9.0',
  '2.10.0',
  '2.11.0',
  '2.11.1',
  '2.11.2',
  '2.12.0',
  '2.12.1',
  '2.12.2',
  '2.13.0',
  '2.13.1',
  '2.13.2',
  '2.13.3',
  '2.14.0',
  '2.14.1',
  '2.15.0',
  '2.16.0',
  '2.17.0',
];

const dependencies = [
  ['mvn+log4j:log4j', [
    '1.1.3',
    '1.2.4',
    '1.2.5',
    '1.2.6',
    '1.2.7',
    '1.2.8',
    '1.2.9',
    '1.2.11',
    '1.2.12',
    '1.2.13',
    '1.2.14',
    '1.2.15',
    '1.2.16',
    '1.2.17',
  ]],
  ['mvn+org.apache.logging.log4j:log4j', log4j2Versions],
  ['mvn+org.apache.logging.log4j:log4j-core', log4j2Versions],
  ['mvn+org.apache.logging.log4j:log4j-api', log4j2Versions],
];

const toLocators = (dependency, revisions) => revisions.map(rev => `${dependency}$${rev}`);
const compareLocators = (a, b) => {
  const vA = a.split('$')[1];
  const vB = b.split('$')[2];
  if (compareVersions.validate(vA) && compareVersions.validate(vB)) return compareVersions(vA, vB);
  return -1;
};
const result = {};
Promise.all(dependencies.map(([dependency, revisions]) => {

  return Promise.all(toLocators(dependency, revisions).map(loc => {
    if (!result[loc]) result[loc] = new Set();
    console.error(`Fetching parent projects for ${loc}...`);
    return fossa.getParentProjects(loc).catch(err => {
      if (err.response.status === 404) {
        console.error(err.response.data);
        return Promise.resolve([]);
      }
      return Promise.reject(err);
    }).then(parents => {
      console.error(`Fetched parent projects for ${loc}`);
      parents.forEach(p => result[loc].add(projectURL(p.locator)));
    })
  })).then(_ => {
    Object.keys(result).sort(compareLocators).forEach(locator => {
      if (result[locator].size) {
        const projects = Array.from(result[locator]).sort();
        console.log(`${locator} (${projects.length})`);
        console.log(projects.join('\n') + '\n');
      }
    });  
  }).catch(err => {
    console.error(err);
    process.exit(1);
  });    
}));
