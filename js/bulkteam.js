const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');
const fs = require('fs').promises;
const keyBy = require('lodash.keyby');

const argv = yargs(hideBin(process.argv))
  .command('$0 <file>')
  .option('team', {
    type: 'string',
    description: 'FOSSA team name to add projects to',
  })
  .demandOption(['team', 'file'])
  .parse();

require('dotenv-safe').config();
const fossa = require('./fossa')(process.env.FOSSA_API_TOKEN);

const targetURLs = fs.readFile(argv.file, 'utf8').then(f => 
  f.replace(/\r\n/g,'\n').split('\n').reduce((obj, str) => { obj[str] = true; return obj; }, {})
)

const teamId = fossa.getTeamByName(argv.team).then(t => t.id);

Promise.all([targetURLs, fossa.getProjects(), teamId]).then(async ([targetURLs, projects, teamId]) => {
  const targetProjects = projects.filter(p => targetURLs[p.url]).map(p => p.locator);
  await fossa.assignTeamProjects(teamId, targetProjects);

  console.log(`Assigned ${targetProjects.length} out of ${projects.length} projects to team ${argv.team}`);

  if (Object.keys(targetURLs).length > targetProjects.length) {
    console.log(`Target list had ${Object.keys(targetURLs).length} projects`);
    const fossaProjectsByURL = keyBy(projects, p => p.url);
    const inTargetButNotFossa = Object.keys(targetURLs).filter(url => !fossaProjectsByURL[url]);
    console.log(`These projects were in the target list but were not found in FOSSA:\n${inTargetButNotFossa.join('\n')}`);
  }

}).catch(e => {
  console.error(e);
  process.exit(1);
});
