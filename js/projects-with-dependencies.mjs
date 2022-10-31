#!/usr/bin/env node

import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import Promise from 'bluebird';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import process from 'node:process';
import pickBy from 'lodash.pickby';
const fossaAPI = (await import('./fossa.js')).default


const args = yargs(hideBin(process.argv))
  .command('$0', 'Finds all FOSSA projects with any of the specified dependencies')
  .example('$0 --locators mvn+log4j:log4j mvn+org.apache.logging.log4j:log4j-core mvn+org.apache.logging.log4j:log4j-api', 'Search for projects that depend on Log4j')
  .example(`$0 --locators-file locators.txt --progress-file ${path.resolve(os.tmpdir(), 'progress.json')}`, 'Search for projects that have any dependency listed in locators.txt')
  .option('locators', {
    type: 'array',
    description: 'Locator names of dependencies to find vulnerable projects for',
  })
  .option('locators-file', {
    type: 'string',
    description: 'Path to file containing locator names of dependencies to find vulnerable projects for, separated by newlines',
  })
  .option('endpoint', {
    type: 'string',
    description: 'FOSSA API service base URL',
    default: 'https://app.fossa.com',
  })
  .option('progress-file', {
    type: 'string',
    description: 'Path to a file to load partial progress from. Allows this script to resume if it is stopped or crashes. Will be created if it does not exist.',
  })
  .option('fossa-api-key', {
    type: 'string',
  })
  .default('fossa-api-key', process.env.FOSSA_API_KEY, 'FOSSA_API_KEY environment variable')
  .version(false)
  .wrap(null)
const argv = args.parse();

let fileLocators = [];
if (argv['locators-file']) {
  fileLocators = fs.readFileSync(argv['locators-file'], 'utf-8')
    .split('\n')
    .filter(Boolean)
    .map(s => s.trim())
}
// Merge locators from file and CLI arguments
const locators = [...new Set(fileLocators.concat(argv.locators || []))];
if (locators.length === 0) {
  args.showHelp();
  process.exit(1);
}

['unhandledRejection', 'uncaughtException'].forEach(e => {
  process.on(e, (err) => {
    if (err.response) {
      console.error('API error', err.response.data);
    } else if (err.request) {
      console.error('HTTP request failed', err.request);
    } else {
      console.error('Error', err);
    }
    // Call exit handler explicitly to save progress if needed
    process.exit(1);
  });
});

// If this script is canceled or crashes, save the current progress to the
// progress file and exit. This file can be loaded with --progress-file to avoid
// repeating API requests.
//
// If a dependency is found in the progress file, we will not fetch its
// revisions or their parent projects again.
let result = {};
if (argv['progress-file']) {
  const file = path.resolve(argv['progress-file']);
  if (!fs.existsSync(file)) {
    console.error(`Progress file ${file} does not exist, creating it...`);
    fs.openSync(file, 'w');
  }
  const progress = fs.readFileSync(file, 'utf-8') || '{}';
  result = JSON.parse(progress);
  if (Object.keys(result).length > 0) {
    console.error(`Loaded progress from ${file}`);
  }
  ['SIGINT', 'SIGTERM'].forEach(e => {
    process.on(e, () => {
      process.exit(1);
    });
  });
  process.on('exit', () => {
    fs.writeFileSync(file, JSON.stringify(result));
    console.error(`Saved progress to ${file}`);
  });
}

const fossa = fossaAPI({ token: process.env.FOSSA_API_KEY, endpoint: argv.endpoint });

const ignoreNoStartingPointElected = error => {
  if (error.response?.status === 500 && error.response?.data?.message?.includes('No starting point elected for revision traversal')) {
    console.error(`No references found for locator ${locator}, will be ignored`);
    return Promise.resolve();
  }
  return Promise.reject(error);
};

// For each target locator, fetch all its known revisions
await Promise.map(locators, async dep => {
  if (result[dep] === undefined) {
    console.error(`Fetching revisions for ${dep}...`);
    const revisionsForLocator = await fossa.getMasterRevisions(dep, { count: 1000 }).catch(ignoreNoStartingPointElected);
    result[dep] = {};
    console.error(`Fetched ${revisionsForLocator.length} revision(s) for ${dep}`);
    revisionsForLocator.forEach(r => {
      result[dep][r.locator] = undefined;
    });
    if (revisionsForLocator.length === 0) result[dep] = null;
  }

  const dependencyRevisions = Object.keys(result[dep] || {});
  await Promise.map(dependencyRevisions, async rev => {
    // For each known revision of each target locator, get the organization
    // projects that have it as a dependency
    if (result[dep][rev] === undefined) {
      console.error(`Fetching parent projects for ${rev}...`);
      const projects = await fossa.getParentProjects(rev);
      console.error(`Fetched ${projects.length} parent project(s) for ${rev}`);
      result[dep][rev] = projects;
    }
  }, { concurrency: 10 });
}, { concurrency: 10 });

// If we loaded progress from a file, the progress may contain dependency
// locators that were not requested. Filter them out before displaying the result.
const final = Object.keys(result)
  .reduce((acc, dependency) => {
    if (locators.includes(dependency)) {
      // Only show revisions that are present in at least 1 project
      acc[dependency] = pickBy(result[dependency], projects => projects.length > 0);
    }
    return acc;
  }, {});

console.log(JSON.stringify(final, null, 2));
