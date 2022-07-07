// Prints a summary of projects grouped by CLI version used to scan them.
//
//     node telemetry-summary.js raw-data.json

const fs = require('fs');
const _ = require('lodash');
const file = process.argv[2];

const toProjectURL = project => `https://ford.fossa.com/projects/${encodeURIComponent(project.project)}`;
const data = JSON.parse(fs.readFileSync(file));

const majorVersion = ({version}) => version[0] + '.x';

const result = _.mapValues(_.groupBy(data, majorVersion), projects => projects.map(toProjectURL));
console.log(JSON.stringify(result, null, 2));

