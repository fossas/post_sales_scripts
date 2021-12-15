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
const projectURL = locator => `${fossa.options.endpoint}/projects/${encodeURIComponent(locator)}`;

console.error(`Fetching projects that have these dependencies: \n${argv.locators.join('\n')}`);

const dependencies = argv.locators.map(locator => {
  console.error(`Fetching dependency ${locator}...`);
  return fossa.getProject(locator);
});

Promise.all(dependencies).then(_ => {
  // all dependencies exist, but they might not have any references
  // dependencies without references are ignored

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
    }).catch(error => {
      if (error.response?.status === 500 && error.response?.dat?.message?.includes('No starting point elected for revision traversal')) {
        console.error(`No references found for locator ${locator}, will be ignored`);
        return Promise.resolve();
      }
      return Promise.reject(error);
    });
  });

  return Promise.all(revisions)
    .then(res => {
      const result = {};
      // filter out projects with no revisions
      return Promise.all(res.filter(Boolean).map(([dependency, revisions]) => {
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
      Object.keys(res).sort().forEach(dependency => {
        if (res[dependency].size) {
          const projects = Array.from(res[dependency]).sort();
          console.log(`${dependency} (${projects.length})`);
          console.log(projects.join('\n') + '\n');
        }
      });
    })

}).catch(err => {
  console.error(err);
  process.exit(1);
});
