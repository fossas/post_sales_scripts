const _axios = require('axios').default;
const keyBy = require('lodash.keyby');
const merge = require('lodash.merge');
const qs = require('qs');

const isUnknownLocator = ({loc}) => loc.fetcher === null;

const fossa = (options) => {
  const projectURL = locator => `${options.endpoint}/projects/${encodeURIComponent(locator)}`;
  const headers = {};
  if (options.cookie) {
    // Using cookies is a workaround for when using a token returns incorrect
    // results, so it takes priority
    headers.Cookie = options.cookie;
  } else if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  } else {
    throw 'no token or cookie provided for authentication';
  }

  if (!options.endpoint) options.endpoint = 'https://app.fossa.com'

  const axios = _axios.create({
    baseURL: new URL('api', options.endpoint).href,
    paramsSerializer: params => qs.stringify(params, { arrayFormat: 'brackets' }),
    headers,
  });

  if (process.env.DEBUG) {
    axios.interceptors.request.use(request => {
      const redacter = (k, v) => {
        if (k === 'Authorization' || k === 'Cookie') return '(redacted)';
        return v;
      };
      console.error('Starting Request', JSON.stringify(request, redacter, 2));
      return request;
    });
    axios.interceptors.response.use(response => {
      console.error('Response:', response)
      return response;
    });
  }

  return {
    options,
    axios,
    async getProject(locator, params) {
      return axios.get(`/projects/${encodeURIComponent(locator)}`, params).then(res => res.data);
    },
    async getProjects(params = {}, offset = 0, projects = []) {
      const rangeRegex = /items (\d+)-(?<last>\d+)\/(?<total>\d+)/;
      return axios.get('/projects', merge({ params: { offset }}, params)).then(res => {
        if (res.data.length < 1) return projects;
        projects.push(...res.data);
        const parsedRange = res.headers['content-range'].match(rangeRegex).groups;
        const lastInPage = parseInt(parsedRange.last);
        const total = parseInt(parsedRange.total);
        if (lastInPage + 1 === total) return projects;
        return this.getProjects(params, lastInPage + 1, projects);
      });
    },
    async getIssues(params) {
      return axios.get('/issues', params).then(res => res.data);
    },
    async getDependencies(revision, params) {
      return this.getDependenciesRaw(revision, params);
    },
    async getDependenciesRaw(revision, params, dependency_count = null, offset = 0, deps = []) {
      // if (revision !== 'git+github.com/fossas/super$0756494e7c8299c05c7c47e3e3c45abc85559a97') return [];
      // project revisions that haven't been scanned will return 404, which we can
      // safely ignore
      const ignore404 = (status) => status === 404 || (status >= 200 && status < 300)

      // The endpoint to fetch dependencies doesn't return the total number of
      // dependencies. This needs to be fetched in a separate call to the
      // revision itself
      if (dependency_count === null) {
        dependency_count = (await axios.get(`/revisions/${encodeURIComponent(revision)}`, { validateStatus: ignore404 })).data.dependency_count;
      }

      // dependency_count does not include unknown dependencies, so we need to
      // fetch at least the first page of dependencies even if it is 0
      console.error(`Fetching dependencies from ${revision} (${deps.length}/${dependency_count})...`)

      const actualParams = merge({ validateStatus: ignore404, params: { offset, limit: 750 }}, params);
      return axios.get(`/revisions/${encodeURIComponent(revision)}/dependencies`, actualParams).then(res => {
        if (res.status === 404) return [];
        if (res.data.length < 1) return deps;
        deps.push(...res.data.filter(dep => !isUnknownLocator(dep)));
        if (deps.length >= dependency_count) return deps;
        return this.getDependenciesRaw(revision, params, dependency_count, offset + 750, deps);
      });
    },
    async getUnknownDependencies(revision, params, offset = 0) {
      console.error(`getting unknown deps for ${revision}...`);
      // project revisions that haven't been scanned will return 404, which we can
      // safely ignore
      const ignore404 = (status) => status === 404 || (status >= 200 && status < 300)


      const actualParams = merge({ validateStatus: ignore404, params: { offset, limit: 750 }}, params);
      return axios.get(`/revisions/${encodeURIComponent(revision)}/dependencies`, actualParams).then(res => {
        if (res.status === 404 || res.data.length < 1) return [];
        const unknownDep = res.data.find(isUnknownLocator);
        if (unknownDep) {
          return unknownDep.unresolved_locators;
        }
        return this.getUnknownDependencies(revision, params, offset + res.data.length);
      });
    },

    async getTeamByName(name, params) {
      return axios.get('/teams', params).then(res => res.data.find(t => t.name === name));
    },
    async getProjectsForTeam(teamName) {
      // Need to get organization ID somehow, /teams returns it
      const [orgId, teamId] = await axios.get('/teams')
        .then(teams => {
          const orgs = teams.data.map(t => t.organizationId);
          if (!orgs.every(o => o === orgs[0])) {
            return Promise.reject('got teams from different orgs, this should not happen: ' + orgs);
          }
          const team = teams.data.find(t => t.name === teamName);
          if (!team) {
            const teamNames = teams.data.map(t => t.name);
            return Promise.reject(`team not found: ${teamName}\nvalid teams are: ${teamNames}`);
          }
          return [orgs[0], team.id];
        });
      return axios.get('/projects', {
        params: {
          teamId: teamId,
          organizationId: orgId,
        },
      }).then(res => res.data);
    },
    async getPoliciesById(params) {
      return axios.get('/policies', params).then(res => keyBy(res.data, 'id'));
    },
    async assignTeamProjects(teamId, projects) {
      return axios.put(`/teams/${teamId}/projects`, { projects }).then(res => res.data);
    },
    async scanRevision(locator) {
      return axios.get(`/revisions/${encodeURIComponent(locator)}/issues`).then(_ => locator);
    },
    async listMinimal(params) {
      return axios.get('/issues/list-minimal', params).then(res => res.data);
    },
    // TODO This doesn't finish until all pages have been fetched. Consider
    // adding a streaming version of this method that returns each page as
    // it's fetched
    async getMasterRevisions(locator, options) {
      let lastRevision = null;
      let result = [];
      const params = {
        refs: ['master'],
        refs_type: 'branch',
        count: options.count,
      };
      do {
        params.cursor = lastRevision;
        let revisions = await axios.get(`/projects/${encodeURIComponent(locator)}/revisions`, { params }).then(res => res.data.branch.master);
        result = result.concat(revisions);
        lastRevision = revisions[revisions.length - 1]?.loc?.revision;
      } while (lastRevision !== undefined);
      return result;
    },
    async getParentProjects(locator) {
      return axios.get(`/revisions/${encodeURIComponent(locator)}/parent_projects`).then(res => {
        return res.data.map(p => ({...p, url: projectURL(p.locator)}));
      });
    }
  };
};

module.exports = fossa;
