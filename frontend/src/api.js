// 作者: lxl
// 说明: 前端接口请求封装（统一鉴权、401回调、业务API方法）。
import axios from "axios";


const runtimeHost = typeof window !== "undefined" ? window.location.hostname : "127.0.0.1";
const runtimeProtocol = typeof window !== "undefined" ? window.location.protocol : "http:";
const apiBaseFromEnv = import.meta.env.VITE_API_BASE_URL;
const defaultApiBase = `${runtimeProtocol}//${runtimeHost}:8000/api`;
const AUTH_TOKEN_KEY = "api_test_studio_auth_token";
const MONITOR_DEPLOY_TIMEOUT_MS = 10 * 60 * 1000;
const MONITOR_UPLOAD_TIMEOUT_MS = 15 * 60 * 1000;
let unauthorizedHandler = null;

const request = axios.create({
  baseURL: apiBaseFromEnv || defaultApiBase,
  timeout: 15000
});

export function getStoredToken() {
  if (typeof window === "undefined") return "";
  return String(window.localStorage.getItem(AUTH_TOKEN_KEY) || "");
}

export function setStoredToken(token) {
  if (typeof window === "undefined") return;
  const safe = String(token || "").trim();
  if (safe) {
    window.localStorage.setItem(AUTH_TOKEN_KEY, safe);
  } else {
    window.localStorage.removeItem(AUTH_TOKEN_KEY);
  }
}

export function clearStoredToken() {
  setStoredToken("");
}

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = typeof handler === "function" ? handler : null;
}

request.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    // 统一注入登录态，避免业务层重复处理 Authorization 头。
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

request.interceptors.response.use(
  (response) => response,
  (error) => {
    // 仅拦截 401 并触发全局回调，具体错误提示由调用页面决定。
    if (error?.response?.status === 401 && unauthorizedHandler) {
      unauthorizedHandler(error);
    }
    return Promise.reject(error);
  }
);

export const api = {
  authLogin(payload) {
    return request.post("/auth/login", payload);
  },
  authMe() {
    return request.get("/auth/me");
  },
  authLogout() {
    return request.post("/auth/logout");
  },
  authChangePassword(payload) {
    return request.post("/auth/change-password", payload);
  },
  listUsers() {
    return request.get("/auth/users");
  },
  createUser(payload) {
    return request.post("/auth/users", payload);
  },
  updateUser(id, payload) {
    return request.put(`/auth/users/${id}`, payload);
  },
  deleteUser(id) {
    return request.delete(`/auth/users/${id}`);
  },
  listProjects() {
    return request.get("/projects");
  },
  createProject(payload) {
    return request.post("/projects", payload);
  },
  updateProject(id, payload) {
    return request.put(`/projects/${id}`, payload);
  },
  deleteProject(id) {
    return request.delete(`/projects/${id}`);
  },
  listDataSets(projectId) {
    const params = projectId ? { project_id: projectId } : {};
    return request.get("/data-sets", { params });
  },
  createDataSet(payload) {
    return request.post("/data-sets", payload);
  },
  updateDataSet(id, payload) {
    return request.put(`/data-sets/${id}`, payload);
  },
  deleteDataSet(id) {
    return request.delete(`/data-sets/${id}`);
  },
  listModules(projectId) {
    const params = projectId ? { project_id: projectId } : {};
    return request.get("/modules", { params });
  },
  createModule(payload) {
    return request.post("/modules", payload);
  },
  updateModule(id, payload) {
    return request.put(`/modules/${id}`, payload);
  },
  deleteModule(id) {
    return request.delete(`/modules/${id}`);
  },
  runModuleScenarios(id, payload = null) {
    return request.post(`/modules/${id}/run-scenarios`, payload || {});
  },
  listCases(projectId, extraParams = {}) {
    const params = { ...(extraParams || {}) };
    if (projectId) params.project_id = projectId;
    return request.get("/test-cases", { params });
  },
  createCase(payload) {
    return request.post("/test-cases", payload);
  },
  updateCase(id, payload) {
    return request.put(`/test-cases/${id}`, payload);
  },
  previewCase(payload) {
    return request.post("/test-cases/preview", payload);
  },
  deleteCase(id) {
    return request.delete(`/test-cases/${id}`);
  },
  runCase(id) {
    return request.post(`/test-cases/${id}/run`);
  },
  listHistories(testCaseId, projectId, extraParams = {}) {
    const params = { ...(extraParams || {}) };
    if (testCaseId) params.test_case_id = testCaseId;
    if (projectId) params.project_id = projectId;
    return request.get("/run-histories", { params });
  },
  listScenarios(projectId, moduleId, extraParams = {}) {
    const params = { ...(extraParams || {}) };
    if (projectId) params.project_id = projectId;
    if (moduleId) params.module_id = moduleId;
    return request.get("/scenarios", { params });
  },
  createScenario(payload) {
    return request.post("/scenarios", payload);
  },
  reorderScenarios(payload) {
    return request.post("/scenarios/reorder", payload);
  },
  updateScenario(id, payload) {
    return request.put(`/scenarios/${id}`, payload);
  },
  previewScenario(payload) {
    return request.post("/scenarios/preview", payload);
  },
  previewScenariosBatch(payload) {
    return request.post("/scenarios/preview-batch", payload);
  },
  debugScenarioStep(payload) {
    return request.post("/scenarios/debug-step", payload);
  },
  deleteScenario(id) {
    return request.delete(`/scenarios/${id}`);
  },
  runScenario(id, payload = null) {
    return request.post(`/scenarios/${id}/run`, payload || {});
  },
  runScenariosBatch(payload) {
    return request.post("/scenarios/run-batch", payload);
  },
  listScenarioHistories(scenarioId, projectId, extraParams = {}) {
    const params = { ...(extraParams || {}) };
    if (scenarioId) params.scenario_id = scenarioId;
    if (projectId) params.project_id = projectId;
    return request.get("/scenario-run-histories", { params });
  },
  deleteScenarioHistories(ids) {
    return request.delete("/scenario-run-histories/batch-delete", { data: { ids } });
  },
  deleteScenarioHistory(id) {
    return request.delete(`/scenario-run-histories/${id}`);
  },
  getDashboardSummary(projectId) {
    const params = projectId ? { project_id: projectId } : {};
    return request.get("/dashboard/summary", { params });
  },
  listEnvironments(projectId) {
    const params = projectId ? { project_id: projectId } : {};
    return request.get("/environments", { params });
  },
  createEnvironment(payload) {
    return request.post("/environments", payload);
  },
  updateEnvironment(id, payload) {
    return request.put(`/environments/${id}`, payload);
  },
  deleteEnvironment(id) {
    return request.delete(`/environments/${id}`);
  },
  listMonitorPlatforms() {
    return request.get("/monitor/platforms");
  },
  createMonitorPlatform(payload) {
    return request.post("/monitor/platforms", payload, { timeout: MONITOR_DEPLOY_TIMEOUT_MS });
  },
  updateMonitorPlatform(id, payload) {
    return request.put(`/monitor/platforms/${id}`, payload);
  },
  deleteMonitorPlatform(id) {
    return request.delete(`/monitor/platforms/${id}`);
  },
  deployMonitorPlatform(id, payload = {}) {
    return request.post(`/monitor/platforms/${id}/deploy`, payload, { timeout: MONITOR_DEPLOY_TIMEOUT_MS });
  },
  uploadMonitorPlatformPackage(id, file, autoDeploy = true) {
    const formData = new FormData();
    formData.append("package", file);
    formData.append("auto_deploy", autoDeploy ? "1" : "0");
    return request.post(`/monitor/platforms/${id}/upload-package`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: MONITOR_UPLOAD_TIMEOUT_MS
    });
  },
  getMonitorPlatformStatus(id) {
    return request.get(`/monitor/platforms/${id}/status`);
  },
  getMonitorPlatformLogs(id) {
    return request.get(`/monitor/platforms/${id}/logs`);
  },
  getMonitorPlatformTargets(id, params = {}) {
    return request.get(`/monitor/platforms/${id}/targets`, { params: params || {} });
  },
  getMonitorPlatformMetricsLatest(id, targetHost = "", forceRefresh = false) {
    const params = {};
    const safeTargetHost = String(targetHost || "").trim();
    if (safeTargetHost) {
      params.target_host = safeTargetHost;
    }
    if (forceRefresh) {
      params.refresh = 1;
    }
    return request.get(`/monitor/platforms/${id}/metrics/latest`, { params });
  },
  getMonitorPlatformMetricsHistory(id, limit = 60, rangeMinutes = 0, targetHost = "") {
    const params = { limit };
    const safeRangeMinutes = Number(rangeMinutes || 0);
    if (safeRangeMinutes > 0) {
      params.range_minutes = safeRangeMinutes;
    }
    const safeTargetHost = String(targetHost || "").trim();
    if (safeTargetHost) {
      params.target_host = safeTargetHost;
    }
    return request.get(`/monitor/platforms/${id}/metrics/history`, { params });
  },
  getRbacOverview() {
    return request.get("/rbac/overview");
  },
  generateCasesByAi(payload) {
    return request.post("/ai/generate-test-cases", payload);
  },
  generateCasesFromOpenapi(payload) {
    return request.post("/ai/generate-from-openapi", payload);
  },
  validateAiConfig(payload) {
    return request.post("/ai/validate-config", payload);
  }
};
