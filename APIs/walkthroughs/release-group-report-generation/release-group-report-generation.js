const axios = require('axios');
const querystring = require('querystring');
const fs = require('fs');
const https = require('https');

// Function to submit the release group generation request
// Note modify the query params in this function to your needs
async function submitRequest(projectGroup, releaseID, format, bearerToken) {
  try {
    const queryParams = querystring.stringify({
      includeDeepDependencies: true,
      includeDirectDependencies: true,
      includeLicenseList: true,
      includeLicenseScan: true,
      includeProjectLicense: true,
      includeCopyrightList: true,
      includeFileMatches: true,
      includeVulnerabilities: true,
      includeDependencySummary: true,
      includeLicenseHeaders: true,
    });

    const url = `https://app.fossa.com/api/project_group/${projectGroup}/release/${releaseID}/attribution/${format}?${queryParams}`;

    const response = await axios.post(url, null, {
      headers: {
        'Authorization': `Bearer ${bearerToken}`,
        'Accept': 'application/json',
      },
    });

    const taskId = response.data.taskId;
    console.log('POST request succeeded. Task ID:', taskId);

    // Check the status and get the S3 URL
    await checkStatus(taskId, bearerToken, format);
  } catch (error) {
    console.error('Error submitting POST request:', error.response.data);
  }
}

// Function to check the status and get the S3 URL
async function checkStatus(taskId, bearerToken, format) {
  try {
    const response = await axios.get(`https://app.fossa.com/api/project_group/attribution/${taskId}`, {
      headers: {
        'Authorization': `Bearer ${bearerToken}`,
      },
    });

    const status = response.data.status;
    console.log('Status:', status);

    if (status === 'SUCCEEDED') {
      const s3URL = response.data.url;
      console.log('S3 URL:', s3URL);

      // Generate a timestamp in ISO format
      const timestamp = new Date().toISOString().replace(/:/g, '-');
      const releaseGroupFileName = `release-group-report-${timestamp}.${getOutputFormat(format)}`;

      // Download from S3
      downloadFromS3(s3URL, releaseGroupFileName)
        .then(() => {
          console.log('Download completed successfully!');
        })
        .catch((error) => {
          console.error('Error downloading file:', error);
        });
    } else if (status === 'FAILED') {
      console.error('Task failed. Unable to generate the report.');
    } else {
      // Retry after a certain interval or handle the pending status
      console.log('Task is still pending. Retrying after an interval...');
      setTimeout(() => checkStatus(taskId, bearerToken, format), 5000);
    }
  } catch (error) {
    console.error('Error with report generation:', error);
  }
}

// Function to download report from S3
function downloadFromS3(url, destinationPath) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(destinationPath);

    https.get(url, (response) => {
      response.pipe(file);

      file.on('finish', () => {
        file.close();
        resolve();
      });
    }).on('error', (error) => {
      fs.unlink(destinationPath, () => {
        reject(error);
      });
    });
  });
}

// Get the output format based on the given format
function getOutputFormat(format) {
  if (format === 'SPDX_JSON') {
    return 'json';
  }

  return format.toLowerCase();
}

// Parse command-line arguments using flags
function parseFlags(args) {
  const flags = {};
  let currentFlag = null;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg.startsWith('--')) {
      currentFlag = arg.slice(2);
      flags[currentFlag] = true;
    } else if (currentFlag) {
      flags[currentFlag] = arg;
      currentFlag = null;
    }
  }

  return flags;
}

// Validate required flags
function validateFlags(flags) {
  const requiredFlags = ['project-group', 'release-id', 'format', 'fossa-api-key'];
  const missingFlags = requiredFlags.filter((flag) => !flags[flag]);

  if (missingFlags.length > 0) {
    console.error('Missing required flags:', missingFlags.join(', '));
    return false;
  }

  return true;
}

// Display help message
function displayHelp() {
  console.log('Usage: node release-group-report-generation.js --project-group <project-group-id> --release-id <release-id> --format <format> --fossa-api-key <fossa-api-key>');
  console.log('');
  console.log('Required flags:');
  console.log('  --project-group    <project-group-id>  Project Group ID');
  console.log('  --release-id       <release-id>        Release ID');
  console.log('  --format           <format>            Format of the release group report (e.g. HTML, CSV, MD, PDF, TXT, SPDX, SPDX_JSON)');
  console.log('  --fossa-api-key    <fossa-api-key>     FOSSA full access token for authentication');
  console.log('');
  console.log('Example:');
  console.log('  node release-group-report-generation.js --project-group 123 --release-id 456 --format HTML --fossa-api-key abc123');
}

// Main function
function main() {
  const args = process.argv.slice(2);
  const flags = parseFlags(args);

  if (flags['--help']) {
    displayHelp();
    return;
  }

  if (!validateFlags(flags)) {
    displayHelp();
    return;
  }

  submitRequest(flags['project-group'], flags['release-id'], flags['format'], flags['fossa-api-key']);
}

// Run the script
main();
n