const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');

const argv = yargs(hideBin(process.argv))
  .command('$0')
  .option('locators', {
    type: 'array',
    description: 'Locator names of dependencies to find vulnerable projects for',
  })
  .option('endpoint', {
    type: 'string',
    description: 'FOSSA API service base URL',
  })
  .demandOption(['locators'])
  .parse();

require('dotenv-safe').config();
const fossa = require('./fossa')({ token: process.env.FOSSA_API_TOKEN, endpoint: argv.endpoint });

console.error(`Fetching vulnerable projects for dependencies: \n${argv.locators.join('\n')}`);

const revisions = argv.locators.map(locator => {
  console.error(`Fetching revisions for ${locator}...`);
  return fossa.getRevisions(locator, {
    params: {
      count: 100,
      offset: 0,
      refs: ['master'],
      refs_type: 'branch',
    }
  }).then(result => {
    console.error(`Fetched revisions for ${locator}`);
    return result;
  });
});

const projectURL = locator => `${fossa.options.endpoint}/projects/${encodeURIComponent(locator)}`;

Promise.all(revisions)
  .then(res => {
    const result = {};
    return Promise.all(res.map(([dependency, revisions]) => {
      if (!result[dependency]) result[dependency] = new Set();
      return Promise.all(revisions.branch.master.map(rev => {
        console.error(`Fetching parent projects for ${rev.locator}...`);
        return fossa.getParentProjects(rev.locator).then(parents => {
          console.error(`Fetched parent projects for ${rev.locator}`);
          parents.forEach(p => result[dependency].add(projectURL(p.locator)));
        });
      }));
    })).then(_ => result);
}).then(res => {
  console.log('\n');
  Object.keys(res).forEach(dependency => {
    if (res[dependency].size) {
      console.log(dependency);
      console.log(Array.from(res[dependency]).join('\n') + '\n');
    }
  })
}).catch(err => console.error(err));
