const _axios = require('axios').default;
const keyBy = require('lodash.keyby');
const qs = require('qs');

const fossa = (options) => {
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
  })

  // axios.interceptors.request.use(request => {
  //   console.log('Starting Request', JSON.stringify(request, null, 2))
  //   return request
  // });

  return {
    options,
    async getProjects(params) {
      return axios.get('/projects', params).then(res => res.data);
    },
    async getIssues(params) {
      return axios.get('/issues', params).then(res => res.data);
    },
    async getDependencies(revision) {
      // TODO page through results, limit on FOSSA UI is 750 dependencies per page
      return axios.get(`/revisions/${encodeURIComponent(revision)}/dependencies`, { include_ignored: true }).then(res => res.data);
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
    async getRevisions(locator, params) {
      return axios.get(`/projects/${encodeURIComponent(locator)}/revisions`, params).then(res => [locator, res.data]);
    },
    async getParentProjects(locator) {
      return axios.get(`/revisions/${encodeURIComponent(locator)}/parent_projects`).then(res => res.data);
    }
  };
};

module.exports = fossa;
