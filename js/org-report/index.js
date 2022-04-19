const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');
const axiosRetry = require('axios-retry');

const argv = yargs(hideBin(process.argv))
  .command('$0 <file>')
  .option('team', {
    type: 'string',
    description: 'FOSSA team name to fetch issues from'
  })
  .option('endpoint', {
    type: 'string',
    description: 'FOSSA base URL, used for private FOSSA deployments',
    default: 'https://app.fossa.com',
  })
  .demandOption(['file'])
  .parse();

require('dotenv-safe').config();
const fossa = require('../fossa')({
  token: process.env.FOSSA_API_TOKEN,
  cookie: process.env.FOSSA_COOKIE,
  endpoint: argv.endpoint,
});

axiosRetry(fossa.axios, {
  retries: 10,
  retryDelay: axiosRetry.exponentialDelay,
});

const ExcelJS = require('exceljs');
const groupBy = require('lodash.groupby');
const Promise = require('bluebird');

const pluralize = count => {
  if (count > 1) return `${count} issues found`;
  if (count == 1) return '1 issue found';
  return 'No issues found';
}

const reportedProjects = argv.team ? fossa.getProjectsForTeam(argv.team) : fossa.getProjects();


reportedProjects
  .then(async projects => {
    projects.sort((a, b) => a.title.localeCompare(b.title));
    const workbook = new ExcelJS.Workbook();

    const summarySheet = workbook.addWorksheet('Summary');
    summarySheet.columns = [
      { header: 'Project', key: 'project' },
      { header: 'Compliance notes', key: 'compliance' },
      { header: 'Security notes', key: 'security' },
      { header: 'Dependencies', key: 'bom' },
    ];

    const bomSheet = workbook.addWorksheet('Software bill of materials');
    bomSheet.columns = [
      { header: 'Project', key: 'project' },
      { header: 'Dependency', key: 'name' },
      { header: 'Revision', key: 'revision' },
      { header: 'License(s)', key: 'licenses' },
      { header: 'Origin', key: 'fetcher' },
    ];

    const parseLocator = locator => {
      const parsed = /(?<fetcher>.*)\+(?<title>.*)\$(?<revision>.*)/.exec(locator);
      if (!parsed) return null;
      const {groups: {fetcher, title, revision}} = parsed;
      return {
        project: {
          title,
        },
        licenses: [{ title: '(unknown dependency)' }],
        loc: {
          revision,
          fetcher,
        },
      };
    };
    const wasAnalyzed = p => Boolean(p.last_analyzed_revision);
    const bom = Promise.all(Promise.map(projects.filter(wasAnalyzed), p => fossa.getDependencies(p.last_analyzed_revision).then(deps => [p, deps]), { concurrency: 10 }).then(res => {
      return res.flatMap(([project, dependencies]) => {
        // Unknown dependencies are returned in a special project named "NULL".
        // Each unknown dependency is just a locator which needs to be manually parsed.
        const {'true': knownDependencies, 'false': unknown} = groupBy(dependencies, dep => dep.locator !== 'NULL');
        const unknownDependencies = unknown?.flatMap(uDep => uDep.unresolved_locators.filter(l => l !== 'NULL').map(parseLocator).filter(Boolean))
        return [...knownDependencies||[], ...unknownDependencies||[]].map(dep => {
          return {
            project: project.title,
            name: dep.project.url ? { text: dep.project.title, hyperlink: dep.project.url } : dep.project.title,
            revision: dep.loc.revision,
            licenses: dep.licenses.map(l => l.title).join('\n') || '(no license detected)',
            fetcher: dep.loc.fetcher === 'user' ? '(manually provided)' : dep.loc.fetcher,
          };
        });
      });
    }));
    bom.then(rows => { return bomSheet.addRows(rows) });

    const issuesPerProject = Promise.all(Promise.map(projects, p => fossa.getIssues({
      params: {
        'scanScope[type]': 'project',
        'scanScope[projectId]': p.locator,
        'status': 'active',
        // TODO any better way to get the latest revision?
        'scanScope[revisionId]': p.last_analyzed_revision?.split('$')[1],
      }
    }, { concurrency: 10 }).then(issues => issues.flatMap(i => Object.assign(i, {project: p})))));

    return Promise.all([issuesPerProject, fossa.getPoliciesById(), bom]).then(([projectIssues, policies, bom]) => {
      // TODO show resolved issues separately
      const {'true': vulnerabilities, 'false': licenseIssues} = groupBy(projectIssues.flat(), issue => issue.type === 'vulnerability')

      let complianceSheet;
      if (licenseIssues?.length > 0) {
        complianceSheet = workbook.addWorksheet('Dependency license issues');
        complianceSheet.columns = [
          { header: 'Affected project', key: 'project' },
          { header: 'Dependency', key: 'dependency' },
          { header: 'Revision', key: 'revision' },
          { header: 'Issue (link to details)', key: 'type' },
          { header: 'Raised by policy', key: 'policy' },
          { header: 'License', key: 'license' },
          { header: 'Details', key: 'details' },
        ];
      }
      licenseIssues?.map(issue => {
        const dependencyURL = issue.revision.project.url;
        let dependency;
        if (dependencyURL) {
          dependency = { text: issue.revision.project.title, hyperlink: dependencyURL };
        } else {
          dependency = issue.revision.project.title;
        }
        return {
          project: issue.project.title,
          dependency: dependency,
          _title: issue.revision.project.title,
          revision: issue.revision.loc.revision,
          type: { text: issue.type?.replace(/_/g, ' '), hyperlink: `https://app.fossa.com/issues/licensing/${encodeURIComponent(issue.id)}` },
          policy: issue.license ? policies[issue.project.policyId]?.title : '',
          license: issue.license?.name, // Unlicensed dependencies do not have license or rule
          details: issue.rule?.notes,
        };
      }).sort((a, b) =>
        a.project.localeCompare(b.project) ||
        a.type.text.localeCompare(b.type.text) ||
        a._title?.localeCompare(b._title)
      ).forEach(issue => complianceSheet?.addRow(issue));

      let securitySheet;
      if (vulnerabilities?.length > 0) {
        securitySheet = workbook.addWorksheet('Security issues');
        securitySheet.columns = [
          { header: 'Affected project', key: 'project' },
          { header: 'Dependency', key: 'dependency' },
          { header: 'Revision', key: 'revision' },
          { header: 'CVE', key: 'cve' },
          { header: 'CWE', key: 'cwe' },
          { header: 'CVSS score', key: 'cvss' },
          { header: 'Affected versions', key: 'affected' },
          { header: 'Details', key: 'details', alignment: { textWrap: true } },
          { header: 'More information', key: 'fossaLink' },
        ];
      }
      vulnerabilities?.map(vuln => ({
        project: vuln.project.title,
        dependency: { text: vuln.revision.loc.package, hyperlink: vuln.revision.project.url },
        revision: vuln.revision.loc.revision,
        cve: { text: vuln.vulnerability.cve, hyperlink: `https://nvd.nist.gov/vuln/detail/${vuln.vulnerability.cve}` },
        cwe: vuln.vulnerability.cwe || 'N/A',
        cvss: vuln.vulnerability.cvss + ` (${vuln.vulnerability.severityScore})`,
        _score: vuln.vulnerability.cvss,
        affected: vuln.vulnerability.affectedVersionRanges.join('\n'),
        details: vuln.vulnerability.description,
        fossaLink: { text: 'Link', hyperlink: `https://app.fossa.com/issues/security/${encodeURIComponent(vuln.id)}` },
      })).sort((a, b) => {
        // Sort by CVSS within each project
        return a.project.localeCompare(b.project) || b._score - a._score;
      }).forEach(vuln => securitySheet?.addRow(vuln));

      const vulnsPerProject = groupBy(vulnerabilities, v => v.project.locator);
      const licenseIssuesPerProject = groupBy(licenseIssues, i => i.project.locator);
      const issueCount = project => vulnsPerProject[project.locator]?.length || 0 + licenseIssuesPerProject[project.locator]?.length || 0;

      const bomPerProject = groupBy(bom, dep => dep.project);
      projects.sort((a, b) => issueCount(b) - issueCount(a)).map(p => ({
        project: {
          text: p.title,
          // TODO point link at specific revision, not the latest one
          hyperlink: 'https://app.fossa.com/projects/' + encodeURIComponent(p.last_analyzed_revision),
        },
        bom: `${bomPerProject[p.title]?.length || 0} dependencies`,
        compliance: pluralize(licenseIssuesPerProject[p.locator]?.length),
        security: pluralize(vulnsPerProject[p.locator]?.length),
      })).forEach(r => summarySheet.addRow(r));
  }).then(() => workbook.xlsx.writeFile(argv.file))
  }).catch(e => {
      console.error(e);
      process.exit(1);
  });
