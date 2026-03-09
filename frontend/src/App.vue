<!-- 作者: lxl -->
<!-- 说明: 前端页面/组件模块。 -->
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessageBox } from "element-plus";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from "echarts/components";
import VChart from "vue-echarts";
import { api, clearStoredToken, getStoredToken, setStoredToken, setUnauthorizedHandler } from "./api";
import AppHeader from "./components/AppHeader.vue";
import CaseListPanel from "./components/CaseListPanel.vue";
import HistoryPanel from "./components/HistoryPanel.vue";
import TestCaseFormPanel from "./components/TestCaseFormPanel.vue";
import AiGeneratorPanel from "./components/AiGeneratorPanel.vue";
import AutomationPanel from "./components/AutomationPanel.vue";
import ScenarioReportPanel from "./components/ScenarioReportPanel.vue";
import JsonEditorField from "./components/JsonEditorField.vue";
import {
  Edit,
  DataLine,
  FolderOpened,
  Files,
  Operation,
  DocumentCopy,
  MagicStick,
  Lock,
  Menu,
} from "@element-plus/icons-vue";
import { blankForm, caseToForm, formToPayload } from "./utils/testCaseForm";

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent]);

const UI_STATE_STORAGE_KEY = "api_test_studio_ui_state";
const AUTH_USER_STORAGE_KEY = "api_test_studio_auth_user";
const AI_CONFIG_STORAGE_KEY = "api_test_studio_ai_config";
const page = ref("dashboard");
const selectedCaseId = ref(null);
const selectedAssetModuleId = ref(null);
const selectedModuleCaseIds = ref([]);
const moduleCasePage = ref(1);
const moduleCasePageSize = ref(10);
const selectedProjectId = ref(null);
const projects = ref([]);
const modules = ref([]);
const projectForm = reactive({ id: null, name: "", description: "" });
const showProjectEditor = ref(false);
const showModuleEditor = ref(false);
const moduleForm = reactive({ id: null, name: "", parent_id: null, description: "" });
const cases = ref([]);
const histories = ref([]);
const historyQuery = reactive({ keyword: "", ordering: "-created_at", page: 1, pageSize: 20 });
const historyMeta = reactive({ total: 0, totalPages: 0, hasNext: false, hasPrev: false });
const assetCaseKeyword = ref("");
const assetCaseOrdering = ref("-updated_at");
const form = reactive(blankForm());
const casePreviewLoading = ref(false);
const showCasePreview = ref(false);
const casePreviewData = ref(null);
const aiGeneratedCases = ref([]);
const aiOpenapiSummary = ref(null);
const aiConfig = reactive({
  apiBaseUrl: "https://api.openai.com/v1",
  apiKey: "",
  model: "gpt-4o-mini",
  timeoutSeconds: 60
});
const showApiImportEditor = ref(false);
const apiImportPreview = ref([]);
const apiImportSummary = ref(null);
const apiImportFileName = ref("");
const apiImportFileInputRef = ref(null);
const apiImportUploadedText = ref("");
const apiImportForm = reactive({
  schemaUrl: "",
  schemaText: "",
  extraRequirements: "",
  moduleId: null,
  environmentId: null,
  dedupeStrategy: "skip"
});
const importLoading = reactive({
  parse: false,
  save: false
});
const parseProgress = ref(0);
const parseProgressText = ref("");
let parseProgressTimer = null;
const dashboardData = ref({
  meta: {
    project_name: "-",
    window_days: 7,
    pass_rate_7d: 0
  },
  kpis: {
    api_count: 0,
    scenario_count: 0,
    case_run_count: 0,
    scenario_run_count: 0,
    pass_count: 0,
    fail_count: 0,
    avg_latency_ms: 0,
    today_run_count: 0
  },
  trend: [],
  recent_runs: [],
  latest_failures: [],
  slow_cases: [],
  fail_top_services: [],
  fail_top_apis: [],
  latency_top_apis: [],
  ai_pending_review: { count: 0, items: [], message: "" }
});
const environmentData = ref({ items: [], summary: { total: 0, message: "" } });
const selectedEnvironmentId = ref(null);
const environmentForm = reactive({
  id: null,
  project_id: null,
  name: "",
  description: "",
  base_url: "",
  variables_text: "{}",
  default_headers_text: "{}",
  is_active: true
});
const environmentVariablesMode = ref("table");
const environmentVariableRows = ref([{ enabled: true, key: "", value: "", value_mode: "custom", builtin_key: "timestamp_int" }]);
const environmentHeadersMode = ref("table");
const environmentHeaderRows = ref([{ enabled: true, key: "", value: "" }]);
const builtinVariableOptions = [
  { key: "timestamp_int", label: "整型时间戳(秒)" },
  { key: "timestamp_ms", label: "整型时间戳(毫秒)" },
  { key: "date_ymd", label: "日期(YYYY-MM-DD)" },
  { key: "datetime", label: "日期时间(YYYY-MM-DD HH:mm:ss)" },
  { key: "phone_cn", label: "手机号(11位)" }
];
const showEnvironmentEditor = ref(false);
const scenarioReportFocus = ref({ scenarioId: null, historyId: null, ts: 0 });
const rbacData = ref({
  members: [],
  projects: [],
  audits: [],
  summary: { member_count: 0, role_count: 0, audit_count: 0, message: "" }
});
const monitorPlatforms = ref([]);
const monitorLogs = ref([]);
const selectedMonitorPlatformId = ref(null);
const selectedMonitorTargetHost = ref("");
const monitorTimeRange = ref(60);
const monitorTimeRangeOptions = [
  { label: "最近15分钟", value: 15 },
  { label: "最近1小时", value: 60 },
  { label: "最近6小时", value: 360 },
  { label: "最近24小时", value: 1440 },
  { label: "最近7天", value: 10080 },
];
const monitorMetrics = ref({
  cpu_usage_percent: null,
  cpu_iowait_percent: null,
  cpu_cores: null,
  load1: null,
  load5: null,
  host_uptime_hours: null,
  memory_usage_percent: null,
  memory_available_gb: null,
  swap_usage_percent: null,
  disk_usage_percent: null,
  disk_free_gb: null,
  disk_read_mbps: null,
  disk_write_mbps: null,
  disk_await_ms: null,
  network_throughput_mbps: null,
  network_rx_mbps: null,
  network_tx_mbps: null,
  network_drop_rate: null,
  network_interfaces: [],
  tcp_established: null,
  tcp_time_wait: null,
  process_running: null,
  process_blocked: null,
  container_restart_count: null,
  pod_abnormal_count: null,
  api_qps: null,
  api_p95_ms: null,
  api_5xx_rate: null,
  db_active_connections: null,
  db_slow_queries: null,
  redis_hit_rate: null,
  container_running: null,
  targets_up: null,
  targets_down: null,
});
const monitorSnapshotMeta = ref({
  collectedAt: "",
  source: "",
  snapshotAgeSeconds: null,
  warning: "",
});
const monitorTrendPoints = ref([]);
const monitorPackageInputRef = ref(null);
const monitorUploadingId = ref(null);
const showMonitorEditor = ref(false);
const showMonitorLogs = ref(false);
const monitorForm = reactive({
  id: null,
  name: "",
  platform_type: "single",
  host: "",
  ssh_port: 22,
  ssh_username: "root",
  ssh_password: "",
  deploy_mode: "online",
  target_hosts_text: "",
});
const monitorRuntimeCheck = ref(null);
const monitorRuntimeChecking = ref(false);
const showUserEditor = ref(false);
const userForm = reactive({
  id: null,
  username: "",
  email: "",
  project_ids: [],
  is_active: true,
  password: ""
});
const userSaving = ref(false);
const loading = reactive({
  cases: false,
  histories: false,
  save: false,
  run: false,
  ai: false,
  dashboard: false,
  rbac: false,
  monitor: false,
});
const noticeByPage = reactive({});
const toastList = ref([]);
let toastSeq = 0;
const authLoading = ref(true);
const authForm = reactive({ username: "admin", password: "" });
const authUser = ref(null);
const showPasswordEditor = ref(false);
const passwordForm = reactive({ current_password: "", new_password: "", confirm_password: "" });
const passwordSaving = ref(false);

const selectedCase = computed(() => cases.value.find((c) => c.id === selectedCaseId.value) || null);
const selectedEnvironment = computed(() => {
  const items = environmentData.value?.items || [];
  if (!items.length) return null;
  const target = items.find((env) => Number(env.id) === Number(selectedEnvironmentId.value));
  return target || items[0];
});
const selectedMonitorPlatform = computed(() =>
  (monitorPlatforms.value || []).find((item) => Number(item.id) === Number(selectedMonitorPlatformId.value)) || null
);
const monitorTargetHostOptions = computed(() => {
  const platform = selectedMonitorPlatform.value;
  if (!platform) return [];
  const rows = Array.isArray(platform.monitor_targets) ? platform.monitor_targets : [];
  const fromTargets = rows
    .filter((row) => row && row.enabled !== false && String(row.host || "").trim())
    .map((row) => ({ label: String(row.name || row.host), value: String(row.host || "").trim() }));
  if (fromTargets.length) return fromTargets;
  const host = String(platform.host || "").trim();
  return host ? [{ label: host, value: host }] : [];
});
const activeEnvironmentItems = computed(() =>
  (environmentData.value?.items || []).filter((env) => env?.is_active !== false)
);
const selectedEnvironmentVariableRows = computed(() => {
  const variables = selectedEnvironment.value?.variables;
  if (!variables || typeof variables !== "object" || Array.isArray(variables)) return [];
  const builtinLabelMap = Object.fromEntries(
    (builtinVariableOptions || []).map((item) => [String(item.key), item.label])
  );
  return Object.entries(variables).map(([key, value]) => ({
    key,
    valueType: value && typeof value === "object" && !Array.isArray(value) && value.__builtin__ ? "内置参数" : "自定义",
    value:
      value && typeof value === "object" && !Array.isArray(value) && value.__builtin__
        ? builtinLabelMap[String(value.__builtin__)] || String(value.__builtin__)
        : String(value ?? "")
  }));
});
const selectedEnvironmentHeaderRows = computed(() => {
  const headers = selectedEnvironment.value?.default_headers;
  if (!headers || typeof headers !== "object" || Array.isArray(headers)) return [];
  return Object.entries(headers).map(([key, value]) => ({
    key,
    value: String(value ?? "")
  }));
});
const moduleNameMap = computed(() => {
  const map = new Map();
  for (const item of modules.value || []) {
    map.set(Number(item.id), item.name || `模块#${item.id}`);
  }
  return map;
});

watch(activeEnvironmentItems, (items) => {
  const validIds = new Set((items || []).map((env) => Number(env.id)));
  if (apiImportForm.environmentId && !validIds.has(Number(apiImportForm.environmentId))) {
    apiImportForm.environmentId = null;
  }
});
const selectedAssetModuleCases = computed(() => {
  const selected = Number(selectedAssetModuleId.value || 0);
  if (!selected) return [];
  if (selected === -1) {
    return (cases.value || []).filter((item) => !Number(item.module_id || item.module || 0));
  }
  const ids = new Set(getDescendantModuleIds(selected));
  return (cases.value || []).filter((item) => ids.has(Number(item.module_id || item.module || 0)));
});
const filteredSelectedAssetModuleCases = computed(() => {
  const keyword = String(assetCaseKeyword.value || "").trim().toLowerCase();
  let list = selectedAssetModuleCases.value || [];
  if (keyword) {
    list = list.filter((item) => {
      const name = String(item?.name || "").toLowerCase();
      const path = String(item?.path || "").toLowerCase();
      const method = String(item?.method || "").toLowerCase();
      const moduleName = String(moduleNameMap.get(Number(item?.module_id || item?.module || 0)) || "").toLowerCase();
      return name.includes(keyword) || path.includes(keyword) || method.includes(keyword) || moduleName.includes(keyword);
    });
  }
  const ordering = String(assetCaseOrdering.value || "-updated_at");
  const factor = ordering.startsWith("-") ? -1 : 1;
  const field = ordering.startsWith("-") ? ordering.slice(1) : ordering;
  const rows = list.slice();
  rows.sort((left, right) => {
    const lv = left?.[field];
    const rv = right?.[field];
    if (field === "module_name") {
      const leftModule = String(moduleNameMap.get(Number(left?.module_id || left?.module || 0)) || "未分组");
      const rightModule = String(moduleNameMap.get(Number(right?.module_id || right?.module || 0)) || "未分组");
      return leftModule.localeCompare(rightModule, "zh-Hans-CN") * factor;
    }
    if (field === "name" || field === "path" || field === "method") {
      return String(lv || "").localeCompare(String(rv || ""), "zh-Hans-CN") * factor;
    }
    return String(lv || "").localeCompare(String(rv || ""), "zh-Hans-CN") * factor;
  });
  return rows;
});
const pagedSelectedAssetModuleCases = computed(() => {
  const page = Math.max(1, Number(moduleCasePage.value || 1));
  const size = Math.max(1, Number(moduleCasePageSize.value || 10));
  const start = (page - 1) * size;
  return filteredSelectedAssetModuleCases.value.slice(start, start + size);
});
const allModuleCaseIds = computed(() =>
  (filteredSelectedAssetModuleCases.value || []).map((item) => Number(item.id)).filter((id) => id > 0)
);
const currentPageModuleCaseIds = computed(() =>
  (pagedSelectedAssetModuleCases.value || []).map((item) => Number(item.id)).filter((id) => id > 0)
);
const selectedModuleCaseCount = computed(() => selectedModuleCaseIds.value.length);
const moduleCaseAllChecked = computed(() => {
  const currentIds = currentPageModuleCaseIds.value;
  if (!currentIds.length) return false;
  const selectedSet = new Set(selectedModuleCaseIds.value.map((id) => Number(id)));
  return currentIds.every((id) => selectedSet.has(id));
});
const moduleCaseIndeterminate = computed(() => {
  const currentIds = currentPageModuleCaseIds.value;
  if (!currentIds.length) return false;
  const selectedSet = new Set(selectedModuleCaseIds.value.map((id) => Number(id)));
  const checkedCount = currentIds.filter((id) => selectedSet.has(id)).length;
  return checkedCount > 0 && checkedCount < currentIds.length;
});
const selectedImportCount = computed(() =>
  (apiImportPreview.value || []).filter((item) => item.enabled).length
);
const existingCaseMapByImportKey = computed(() => {
  const map = new Map();
  for (const item of cases.value || []) {
    const key = buildImportCaseKey(item);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  }
  return map;
});
const passCount = computed(() => Number(dashboardData.value?.kpis?.pass_count || 0));
const failCount = computed(() => Number(dashboardData.value?.kpis?.fail_count || 0));
const avgMs = computed(() => Number(dashboardData.value?.kpis?.avg_latency_ms || 0));
const monitorTimeRangeLabel = computed(() => (
  monitorTimeRangeOptions.find((item) => Number(item.value) === Number(monitorTimeRange.value))?.label || "最近1小时"
));
const monitorServiceBarOption = computed(() => ({
  title: { text: `应用与系统指标（${monitorTimeRangeLabel.value}）`, left: "left", textStyle: { fontSize: 14 } },
  tooltip: { trigger: "axis" },
  grid: { left: 36, right: 16, top: 42, bottom: 48 },
  xAxis: {
    type: "category",
    data: ["API QPS", "API P95(ms)", "API 5xx(%)", "DB连接", "慢查询", "Redis命中(%)", "TCP建立", "TIME_WAIT", "运行进程"],
    axisLabel: { interval: 0, rotate: 16 },
  },
  yAxis: { type: "value", min: 0 },
  series: [
    {
      type: "bar",
      barWidth: 24,
      data: [
        Number(monitorMetrics.value?.api_qps ?? 0),
        Number(monitorMetrics.value?.api_p95_ms ?? 0),
        Number(monitorMetrics.value?.api_5xx_rate ?? 0),
        Number(monitorMetrics.value?.db_active_connections ?? 0),
        Number(monitorMetrics.value?.db_slow_queries ?? 0),
        Number(monitorMetrics.value?.redis_hit_rate ?? 0),
        Number(monitorMetrics.value?.tcp_established ?? 0),
        Number(monitorMetrics.value?.tcp_time_wait ?? 0),
        Number(monitorMetrics.value?.process_running ?? 0),
      ],
      itemStyle: { color: "#0f766e", borderRadius: [4, 4, 0, 0] },
    },
  ],
}));
const monitorTrendLineOption = computed(() => {
  const points = monitorTrendPoints.value || [];
  return {
    title: { text: `主要指标趋势（${monitorTimeRangeLabel.value}）`, left: "left", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    legend: { top: 0, right: 10 },
    grid: { left: 36, right: 16, top: 42, bottom: 28 },
    xAxis: { type: "category", data: points.map((p) => p.t) },
    yAxis: { type: "value", name: "%", min: 0, max: 100, axisLabel: { formatter: "{value}%" } },
    series: [
      { name: "CPU", type: "line", smooth: true, data: points.map((p) => p.cpu), itemStyle: { color: "#2563eb" } },
      { name: "内存", type: "line", smooth: true, data: points.map((p) => p.mem), itemStyle: { color: "#16a34a" } },
      { name: "磁盘", type: "line", smooth: true, data: points.map((p) => p.disk), itemStyle: { color: "#dc2626" } },
    ],
  };
});
const monitorNetworkTrendOption = computed(() => {
  const points = monitorTrendPoints.value || [];
  const labels = points.map((p) => p.t);
  const step = labels.length > 20 ? Math.ceil(labels.length / 10) : 0;
  return {
    title: { text: `网络趋势（吞吐/丢包，${monitorTimeRangeLabel.value}）`, left: 10, top: 8, textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    legend: { bottom: 4, left: "center" },
    grid: { left: 50, right: 56, top: 48, bottom: 56 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: {
        hideOverlap: true,
        interval: step,
      },
    },
    yAxis: [
      { type: "value", name: "Mbps", position: "left", min: 0, splitLine: { show: true } },
      { type: "value", name: "drop/s", position: "right", min: 0, splitLine: { show: false } },
    ],
    series: [
      {
        name: "吞吐(Mbps)",
        type: "line",
        smooth: true,
        yAxisIndex: 0,
        data: points.map((p) => p.netThroughput),
        lineStyle: { width: 2 },
        showSymbol: false,
        itemStyle: { color: "#0ea5e9" },
      },
      {
        name: "丢包速率",
        type: "line",
        smooth: true,
        yAxisIndex: 1,
        data: points.map((p) => p.netDrop),
        lineStyle: { width: 2, type: "dashed" },
        areaStyle: { opacity: 0.08 },
        showSymbol: false,
        itemStyle: { color: "#f97316" },
      },
    ],
  };
});
const monitorNicTrafficOption = computed(() => {
  const nics = Array.isArray(monitorMetrics.value?.network_interfaces) ? monitorMetrics.value.network_interfaces : [];
  const labels = nics.map((n) => String(n.device || "-"));
  return {
    title: { text: `网卡吞吐分布（全部网卡，${monitorTimeRangeLabel.value}）`, left: "left", textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: "axis",
      formatter: (params) => {
        const rows = Array.isArray(params) ? params : [];
        const title = rows.length ? String(rows[0]?.axisValueLabel || rows[0]?.name || "-") : "-";
        const lines = [title];
        for (const item of rows) {
          lines.push(`${item.marker || ""}${item.seriesName}: ${formatTrafficRate(item.value)}`);
        }
        return lines.join("<br/>");
      },
    },
    legend: { top: 0, right: 10 },
    grid: { left: 44, right: 14, top: 44, bottom: 44 },
    xAxis: { type: "category", data: labels, axisLabel: { rotate: 20, interval: 0 } },
    yAxis: {
      type: "value",
      min: 0,
      axisLabel: {
        formatter: (value) => formatTrafficRate(value),
      },
    },
    series: [
      {
        name: "入流量",
        type: "bar",
        stack: "nic",
        data: nics.map((n) => Number(n.rx_mbps ?? 0)),
        itemStyle: { color: "#2563eb" },
      },
      {
        name: "出流量",
        type: "bar",
        stack: "nic",
        data: nics.map((n) => Number(n.tx_mbps ?? 0)),
        itemStyle: { color: "#14b8a6" },
      },
    ],
  };
});
const trendChart = computed(() => {
  const rows = (dashboardData.value?.trend || []).map((item) => ({
    date: String(item?.date || ""),
    runs: Number(item?.runs || 0),
    pass: Number(item?.pass || 0),
    fail: Number(item?.fail || 0)
  }));
  const countMetrics = [
    { key: "runs", label: "执行次数", color: "#2563eb", unit: "", axis: "left" },
    { key: "pass", label: "通过", color: "#16a34a", unit: "", axis: "left" },
    { key: "fail", label: "失败", color: "#dc2626", unit: "", axis: "left" }
  ];
  const metrics = [...countMetrics];
  const width = 760;
  const height = 240;
  const padding = { left: 40, right: 16, top: 14, bottom: 28 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;
  const maxCountValue = Math.max(1, ...rows.flatMap((item) => countMetrics.map((metric) => Number(item[metric.key] || 0))));
  const stepX = rows.length > 1 ? innerW / (rows.length - 1) : 0;
  const mapX = (index) => (rows.length <= 1 ? padding.left + innerW / 2 : padding.left + index * stepX);
  const mapYCount = (value) => padding.top + innerH * (1 - Number(value || 0) / maxCountValue);
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((rate) => ({
    y: padding.top + innerH * rate,
    label: Math.round(maxCountValue * (1 - rate))
  }));
  const labels = rows.map((item, index) => ({
    x: mapX(index),
    label: item.date
  }));
  const series = metrics.map((metric) => {
    const nodes = rows.map((row, index) => ({
      x: mapX(index),
      y: mapYCount(row[metric.key]),
      value: Number(row[metric.key] || 0)
    }));
    return {
      ...metric,
      nodes,
      points: nodes.map((node) => `${node.x},${node.y}`).join(" ")
    };
  });
  return { rows, width, height, yTicks, labels, series, plotLeft: padding.left, plotRight: width - padding.right };
});
const currentNotice = computed(() => noticeByPage[page.value] || { message: "", error: "" });
const moduleParentOptions = computed(() => {
  // 生成可选父模块树，并在编辑时剔除“自己+后代”，防止形成环。
  const source = (modules.value || []).map((item) => ({
    id: Number(item.id),
    name: item.name || "未命名模块",
    parentId: item.parent_id ? Number(item.parent_id) : null,
    children: []
  }));
  const map = new Map(source.map((item) => [item.id, item]));
  const roots = [];
  for (const item of source) {
    if (item.parentId && map.has(item.parentId)) map.get(item.parentId).children.push(item);
    else roots.push(item);
  }
  const excluded = new Set();
  if (moduleForm.id) {
    const queue = [Number(moduleForm.id)];
    while (queue.length) {
      const current = queue.shift();
      if (excluded.has(current)) continue;
      excluded.add(current);
      for (const item of source) {
        if (Number(item.parentId || 0) === Number(current)) queue.push(item.id);
      }
    }
  }
  const rows = [];
  const walk = (node, depth = 0) => {
    if (!excluded.has(node.id)) {
      rows.push({ id: node.id, label: `${"　".repeat(depth)}${node.name}` });
      for (const child of node.children) walk(child, depth + 1);
      return;
    }
    for (const child of node.children) walk(child, depth);
  };
  for (const root of roots) walk(root, 0);
  return rows;
});

const navItems = [
  { key: "dashboard", label: "仪表盘", group: "工作台" },
  { key: "projects", label: "项目管理", group: "工作台" },
  { key: "assets", label: "接口管理", group: "工作台" },
  { key: "testcases", label: "自动化测试", group: "工作台" },
  { key: "scenario_reports", label: "场景报告", group: "工作台" },
  { key: "runs", label: "执行记录", group: "工作台" },
  { key: "monitor_config", label: "监控配置", group: "监控管理" },
  { key: "resource_monitor", label: "资源监控", group: "监控管理" },
  { key: "ai", label: "AI 助手", group: "智能与配置" },
  { key: "rbac", label: "权限与审计", group: "智能与配置" }
];
const navGroups = ["工作台", "智能与配置", "监控管理"];
const navIconMap = {
  dashboard: DataLine,
  projects: FolderOpened,
  assets: Files,
  testcases: Operation,
  scenario_reports: DocumentCopy,
  runs: DataLine,
  monitor_config: Edit,
  resource_monitor: DataLine,
  ai: MagicStick,
  rbac: Lock,
};

function navIcon(key) {
  return navIconMap[key] || Menu;
}
const isAdmin = computed(() => Boolean(authUser.value?.is_root_admin));
const visibleNavItems = computed(() =>
  navItems.filter((item) => (item.key === "rbac" ? isAdmin.value : true))
);
const currentPageTitle = computed(() => visibleNavItems.value.find((x) => x.key === page.value)?.label || "页面");

function pageDesc(key) {
  const map = {
    dashboard: "查看最近执行趋势、失败热点与耗时分布。",
    projects: "管理项目、项目环境与默认变量。",
    assets: "管理接口定义并查看执行历史。",
    testcases: "支持多接口场景编排。",
    scenario_reports: "查看场景执行报告与步骤明细。",
    runs: "查看执行记录与统计指标。",
    monitor_config: "管理监控平台接入、部署与离线包上传。",
    resource_monitor: "在本平台查看 Prometheus 聚合后的资源监控指标。",
    ai: "通过业务描述或 OpenAPI 文档生成测试用例。",
    rbac: "权限与审计页面。"
  };
  return map[key] || "";
}

function persistAuthUser() {
  try {
    if (!authUser.value) {
      window.localStorage.removeItem(AUTH_USER_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(AUTH_USER_STORAGE_KEY, JSON.stringify(authUser.value));
  } catch {}
}

function clearAuthState() {
  clearStoredToken();
  authUser.value = null;
  persistAuthUser();
}

function loadUiState() {
  try {
    const raw = window.localStorage.getItem(UI_STATE_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    const savedPage = String(parsed?.page || "").trim();
    const savedProjectId = Number(parsed?.selectedProjectId || 0);
    if (savedPage && navItems.some((item) => item.key === savedPage)) {
      page.value = savedPage;
    }
    if (savedProjectId > 0) {
      selectedProjectId.value = savedProjectId;
    }
  } catch {}
}

function persistUiState() {
  try {
    window.localStorage.setItem(
      UI_STATE_STORAGE_KEY,
      JSON.stringify({
        page: page.value,
        selectedProjectId: selectedProjectId.value || null
      })
    );
  } catch {}
}

function loadAiConfig() {
  try {
    const raw = window.localStorage.getItem(AI_CONFIG_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    aiConfig.apiBaseUrl = String(parsed?.apiBaseUrl || "https://api.openai.com/v1").trim();
    aiConfig.apiKey = String(parsed?.apiKey || "").trim();
    aiConfig.model = String(parsed?.model || "gpt-4o-mini").trim();
    const timeoutNum = Number(parsed?.timeoutSeconds || 60);
    aiConfig.timeoutSeconds = Number.isFinite(timeoutNum) && timeoutNum > 0 ? timeoutNum : 60;
  } catch {}
}

function persistAiConfig() {
  try {
    window.localStorage.setItem(
      AI_CONFIG_STORAGE_KEY,
      JSON.stringify({
        apiBaseUrl: String(aiConfig.apiBaseUrl || "").trim(),
        apiKey: String(aiConfig.apiKey || "").trim(),
        model: String(aiConfig.model || "").trim(),
        timeoutSeconds: Number(aiConfig.timeoutSeconds || 60)
      })
    );
  } catch {}
}

function updateAiConfig(next) {
  aiConfig.apiBaseUrl = String(next?.apiBaseUrl || "").trim();
  aiConfig.apiKey = String(next?.apiKey || "").trim();
  aiConfig.model = String(next?.model || "").trim();
  const timeoutNum = Number(next?.timeoutSeconds || 60);
  aiConfig.timeoutSeconds = Number.isFinite(timeoutNum) && timeoutNum > 0 ? timeoutNum : 60;
}

async function saveAiConfigWithValidation(next, done) {
  try {
    // 先调用后端连通性校验，通过后再落地到本地状态。
    const payload = {
      ai_base_url: String(next?.apiBaseUrl || "").trim() || null,
      ai_api_key: String(next?.apiKey || "").trim() || null,
      ai_model: String(next?.model || "").trim() || null,
      ai_timeout_seconds: Number(next?.timeoutSeconds || 60)
    };
    const { data } = await api.validateAiConfig(payload);
    updateAiConfig({
      apiBaseUrl: payload.ai_base_url || "",
      apiKey: payload.ai_api_key || "",
      model: payload.ai_model || "",
      timeoutSeconds: payload.ai_timeout_seconds
    });
    const modelHint =
      data?.model_exists === false
        ? "（连通成功，但模型不在可用列表中）"
        : "";
    setMessage("AI 配置已保存，连通性检测通过" + modelHint, "ai");
    if (typeof done === "function") done(true);
  } catch (e) {
    setError(e?.response?.data?.detail || "AI 配置连通性检测失败", "ai");
    if (typeof done === "function") done(false);
  }
}

async function loadCurrentUser() {
  const token = getStoredToken();
  if (!token) {
    authUser.value = null;
    authLoading.value = false;
    return;
  }
  try {
    const raw = window.localStorage.getItem(AUTH_USER_STORAGE_KEY);
    if (raw) {
      authUser.value = JSON.parse(raw);
    }
  } catch {}
  try {
    const { data } = await api.authMe();
    authUser.value = data || null;
    persistAuthUser();
  } catch {
    clearAuthState();
  } finally {
    authLoading.value = false;
  }
}

async function bootstrapAfterLogin() {
  await loadProjects();
  await loadModules();
  await loadCases();
  await loadHistories();
  await loadDashboard();
  await loadEnvironments();
  await loadMonitorPlatforms();
  if (isAdmin.value) {
    await loadRbac();
  }
}

async function handleLogin() {
  const username = String(authForm.username || "").trim();
  const password = String(authForm.password || "");
  if (!username || !password) {
    setError("请输入用户名和密码");
    return;
  }
  loading.save = true;
  try {
    const { data } = await api.authLogin({ username, password });
    setStoredToken(data?.token || "");
    authUser.value = data?.user || null;
    persistAuthUser();
    setMessage(`登录成功：${authUser.value?.username || username}`);
    await bootstrapAfterLogin();
  } catch (e) {
    clearAuthState();
    setError(e?.response?.data?.detail || "登录失败");
  } finally {
    loading.save = false;
  }
}

async function handleLogout() {
  try {
    await api.authLogout();
  } catch {}
  clearAuthState();
  page.value = "dashboard";
  selectedCaseId.value = null;
  selectedProjectId.value = null;
  projects.value = [];
  modules.value = [];
  cases.value = [];
  histories.value = [];
  setMessage("已退出登录");
}

function resetPasswordForm() {
  passwordForm.current_password = "";
  passwordForm.new_password = "";
  passwordForm.confirm_password = "";
}

function openPasswordEditor() {
  resetPasswordForm();
  showPasswordEditor.value = true;
}

function closePasswordEditor() {
  showPasswordEditor.value = false;
  resetPasswordForm();
}

async function savePassword() {
  const currentPassword = String(passwordForm.current_password || "");
  const newPassword = String(passwordForm.new_password || "");
  const confirmPassword = String(passwordForm.confirm_password || "");
  if (!currentPassword || !newPassword || !confirmPassword) {
    return setError("请完整填写密码信息");
  }
  if (newPassword.length < 6) {
    return setError("新密码长度至少6位");
  }
  if (newPassword !== confirmPassword) {
    return setError("两次输入的新密码不一致");
  }
  passwordSaving.value = true;
  try {
    await api.authChangePassword({
      current_password: currentPassword,
      new_password: newPassword
    });
    closePasswordEditor();
    setMessage("密码修改成功，请重新登录");
    await handleLogout();
  } catch (e) {
    setError(e?.response?.data?.detail || "修改密码失败");
  } finally {
    passwordSaving.value = false;
  }
}

function resolveNoticePage(pageKey) {
  if (pageKey && navItems.some((item) => item.key === pageKey)) return pageKey;
  return page.value;
}

function ensureNoticeBucket(pageKey) {
  if (!noticeByPage[pageKey]) {
    noticeByPage[pageKey] = { message: "", error: "" };
  }
  return noticeByPage[pageKey];
}

function setMessage(message, pageKey = null) {
  const targetPage = resolveNoticePage(pageKey);
  const bucket = ensureNoticeBucket(targetPage);
  bucket.message = message;
  bucket.error = "";
  if (targetPage === page.value) pushToast("success", message);
}

function setError(error, pageKey = null) {
  const targetPage = resolveNoticePage(pageKey);
  const bucket = ensureNoticeBucket(targetPage);
  bucket.error = error;
  bucket.message = "";
  if (targetPage === page.value) pushToast("error", error);
}

function setWarning(message, pageKey = null) {
  const targetPage = resolveNoticePage(pageKey);
  const bucket = ensureNoticeBucket(targetPage);
  bucket.message = message;
  bucket.error = "";
  if (targetPage === page.value) pushToast("warning", message);
}

function setException(message, pageKey = null) {
  const targetPage = resolveNoticePage(pageKey);
  const bucket = ensureNoticeBucket(targetPage);
  bucket.error = message;
  bucket.message = "";
  if (targetPage === page.value) pushToast("exception", message);
}

function pushToast(type, text) {
  const message = String(text || "").trim();
  if (!message) return;
  toastSeq += 1;
  const id = toastSeq;
  const normalized = type === "exception" ? "exception" : (type === "warning" ? "warning" : (type === "error" ? "error" : "success"));
  toastList.value.push({ id, type: normalized, message });
  const duration = normalized === "success" ? 2200 : 4200;
  window.setTimeout(() => {
    removeToast(id);
  }, duration);
}

function removeToast(id) {
  const idx = toastList.value.findIndex((item) => Number(item.id) === Number(id));
  if (idx >= 0) toastList.value.splice(idx, 1);
}

async function showConfirm(options = {}) {
  try {
    await ElMessageBox.confirm(
      options.message || "",
      options.title || "确认操作",
      {
        confirmButtonText: options.confirmText || "确定",
        cancelButtonText: options.cancelText || "取消",
        type: options.danger ? "warning" : "info",
        autofocus: true,
      }
    );
    return true;
  } catch {
    return false;
  }
}

function getApiErrorMessage(error, fallback = "操作失败") {
  const detail = error?.response?.data?.detail;
  if (detail) return detail;
  const data = error?.response?.data;
  if (data && typeof data === "object") {
    for (const value of Object.values(data)) {
      if (Array.isArray(value) && value.length) return String(value[0]);
      if (typeof value === "string" && value.trim()) return value;
    }
  }
  return fallback;
}

function clearNotice(pageKey = null) {
  const bucket = ensureNoticeBucket(resolveNoticePage(pageKey));
  bucket.message = "";
  bucket.error = "";
}

function unwrapListPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.items)) return payload.items;
  return [];
}

function updateHistoryQuery(patch = {}) {
  const nextKeyword = Object.prototype.hasOwnProperty.call(patch, "keyword") ? String(patch.keyword || "") : historyQuery.keyword;
  const nextOrdering = Object.prototype.hasOwnProperty.call(patch, "ordering") ? String(patch.ordering || "-created_at") : historyQuery.ordering;
  const nextPageSize = Object.prototype.hasOwnProperty.call(patch, "pageSize") ? Number(patch.pageSize || historyQuery.pageSize || 20) : historyQuery.pageSize;
  const nextPage = Object.prototype.hasOwnProperty.call(patch, "page") ? Number(patch.page || historyQuery.page || 1) : historyQuery.page;
  const needResetPage = nextKeyword !== historyQuery.keyword || nextOrdering !== historyQuery.ordering || nextPageSize !== historyQuery.pageSize;
  historyQuery.keyword = nextKeyword;
  historyQuery.ordering = nextOrdering;
  historyQuery.pageSize = Number.isFinite(nextPageSize) && nextPageSize > 0 ? nextPageSize : 20;
  historyQuery.page = needResetPage ? 1 : (Number.isFinite(nextPage) && nextPage > 0 ? nextPage : 1);
}

function handleChildNotify(payload) {
  if (!payload) return;
  if (payload.type === "err" || payload.type === "error") {
    setError(payload.message);
    return;
  }
  if (payload.type === "warn" || payload.type === "warning") {
    setWarning(payload.message);
    return;
  }
  if (payload.type === "exception") {
    setException(payload.message);
    return;
  }
  setMessage(payload.message);
}

function resetForm(moduleId = null) {
  Object.assign(form, blankForm());
  if (moduleId) {
    form.module = Number(moduleId);
  }
  selectedCaseId.value = null;
  page.value = "assets";
  setMessage("已切换到新建接口模式");
}

function openScenarioReport(payload) {
  scenarioReportFocus.value = {
    scenarioId: Number(payload?.scenarioId || 0) || null,
    historyId: Number(payload?.historyId || 0) || null,
    clearScenarioFilter: !!payload?.clearScenarioFilter,
    ts: Date.now()
  };
  page.value = "scenario_reports";
  persistUiState();
}

async function loadCases() {
  loading.cases = true;
  try {
    cases.value = unwrapListPayload((await api.listCases(selectedProjectId.value)).data);
  } catch (e) {
    setError(e?.response?.data?.detail || "加载接口失败");
  } finally {
    loading.cases = false;
  }
}

async function loadHistories(caseId = null) {
  loading.histories = true;
  try {
    const response = await api.listHistories(caseId, selectedProjectId.value, {
      page: historyQuery.page,
      page_size: historyQuery.pageSize,
      keyword: historyQuery.keyword,
      ordering: historyQuery.ordering,
    });
    const payload = response.data;
    histories.value = unwrapListPayload(payload);
    if (payload && !Array.isArray(payload)) {
      historyMeta.total = Number(payload.total || histories.value.length || 0);
      historyMeta.totalPages = Number(payload.total_pages || 1);
      historyMeta.hasNext = Boolean(payload.has_next);
      historyMeta.hasPrev = Boolean(payload.has_prev);
      historyQuery.page = Number(payload.page || historyQuery.page || 1);
      historyQuery.pageSize = Number(payload.page_size || historyQuery.pageSize || 20);
    } else {
      historyMeta.total = histories.value.length;
      historyMeta.totalPages = 1;
      historyMeta.hasNext = false;
      historyMeta.hasPrev = false;
    }
  } catch (e) {
    histories.value = [];
    historyMeta.total = 0;
    historyMeta.totalPages = 0;
    historyMeta.hasNext = false;
    historyMeta.hasPrev = false;
    setError(e?.response?.data?.detail || "加载执行历史失败");
  } finally {
    loading.histories = false;
  }
}

async function handleHistoryQueryChange(patch = {}) {
  updateHistoryQuery(patch || {});
  await loadHistories(selectedCaseId.value || null);
}

async function loadDashboard() {
  loading.dashboard = true;
  try {
    const hasCurrentProject = projects.value.some((item) => Number(item.id) === Number(selectedProjectId.value));
    const projectId = hasCurrentProject ? selectedProjectId.value : null;
    dashboardData.value = (await api.getDashboardSummary(projectId)).data;
  } catch (e) {
    setError(e?.response?.data?.detail || "加载仪表盘数据失败", "dashboard");
  } finally {
    loading.dashboard = false;
  }
}

async function loadEnvironments() {
  try {
    environmentData.value = (await api.listEnvironments(selectedProjectId.value)).data;
    const items = environmentData.value?.items || [];
    if (!items.length) {
      selectedEnvironmentId.value = null;
      return;
    }
    const hasCurrent = items.some((env) => Number(env.id) === Number(selectedEnvironmentId.value));
    if (!hasCurrent) {
      selectedEnvironmentId.value = items[0].id;
    }
  } catch (e) {
    setError(e?.response?.data?.detail || "加载环境数据失败");
  }
}

async function loadProjects() {
  try {
    projects.value = (await api.listProjects()).data || [];
    if (!projects.value.length) {
      selectedProjectId.value = null;
      return;
    }
    const hasCurrent = projects.value.some((item) => Number(item.id) === Number(selectedProjectId.value));
    if ((!selectedProjectId.value || !hasCurrent) && projects.value.length) {
      selectedProjectId.value = projects.value[0].id;
    }
  } catch (e) {
    setError(e?.response?.data?.detail || "加载项目失败");
  }
}

function editProject(project) {
  projectForm.id = project.id;
  projectForm.name = project.name || "";
  projectForm.description = project.description || "";
  page.value = "projects";
  showProjectEditor.value = true;
}

function resetProjectForm() {
  projectForm.id = null;
  projectForm.name = "";
  projectForm.description = "";
}

function openProjectCreate() {
  resetProjectForm();
  showProjectEditor.value = true;
}

function resetEnvironmentForm() {
  environmentForm.id = null;
  environmentForm.project_id = selectedProjectId.value || null;
  environmentForm.name = "";
  environmentForm.description = "";
  environmentForm.base_url = "";
  environmentForm.variables_text = "{}";
  environmentForm.default_headers_text = "{}";
  environmentForm.is_active = true;
  environmentVariablesMode.value = "table";
  environmentHeadersMode.value = "table";
  loadEnvironmentVariableRows();
  loadEnvironmentHeaderRows();
}

function editEnvironment(env) {
  selectedEnvironmentId.value = env.id;
  environmentForm.id = env.id;
  environmentForm.project_id = env.project || selectedProjectId.value || null;
  environmentForm.name = env.name || "";
  environmentForm.description = env.description || "";
  environmentForm.base_url = env.base_url || "";
  environmentForm.variables_text = JSON.stringify(env.variables || {}, null, 2);
  environmentForm.default_headers_text = JSON.stringify(env.default_headers || {}, null, 2);
  environmentForm.is_active = env.is_active !== false;
  environmentVariablesMode.value = "table";
  environmentHeadersMode.value = "table";
  loadEnvironmentVariableRows();
  loadEnvironmentHeaderRows();
  page.value = "projects";
  showEnvironmentEditor.value = true;
}

function openEnvironmentCreate() {
  resetEnvironmentForm();
  showEnvironmentEditor.value = true;
}

function environmentObjectToRows(obj) {
  // JSON 对象 -> 可编辑表格行（含内置变量模式）。
  const rows = Object.entries(obj || {}).map(([key, value]) => ({
    enabled: true,
    key: String(key),
    value:
      value === null || value === undefined || (typeof value === "object" && !Array.isArray(value))
        ? ""
        : String(value),
    value_mode: typeof value === "object" && value && !Array.isArray(value) && value.__builtin__ ? "builtin" : "custom",
    builtin_key:
      typeof value === "object" && value && !Array.isArray(value) && value.__builtin__
        ? String(value.__builtin__)
        : "timestamp_int"
  }));
  return rows.length
    ? rows
    : [{ enabled: true, key: "", value: "", value_mode: "custom", builtin_key: "timestamp_int" }];
}

function environmentRowsToObject() {
  // 表格行 -> JSON 对象，过滤未启用/空 key 的项。
  const variables = {};
  for (const row of environmentVariableRows.value) {
    if (!row.enabled) continue;
    const key = String(row.key || "").trim();
    if (!key) continue;
    if (row.value_mode === "builtin") {
      variables[key] = { __builtin__: String(row.builtin_key || "timestamp_int") };
    } else {
      variables[key] = String(row.value ?? "");
    }
  }
  return variables;
}

function syncEnvironmentVariablesTextFromRows() {
  const variables = environmentRowsToObject();
  environmentForm.variables_text = JSON.stringify(variables, null, 2);
}

function loadEnvironmentVariableRows() {
  try {
    const parsed = environmentForm.variables_text?.trim() ? JSON.parse(environmentForm.variables_text) : {};
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      environmentVariableRows.value = [{ enabled: true, key: "", value: "", value_mode: "custom", builtin_key: "timestamp_int" }];
      setError("环境变量必须是 JSON 对象");
      return;
    }
    environmentVariableRows.value = environmentObjectToRows(parsed);
  } catch {
    environmentVariableRows.value = [{ enabled: true, key: "", value: "", value_mode: "custom", builtin_key: "timestamp_int" }];
    setError("环境变量不是合法 JSON");
  }
}

function environmentHeadersObjectToRows(obj) {
  const rows = Object.entries(obj || {}).map(([key, value]) => ({
    enabled: true,
    key: String(key),
    value: String(value ?? "")
  }));
  return rows.length ? rows : [{ enabled: true, key: "", value: "" }];
}

function environmentHeaderRowsToObject() {
  const headers = {};
  for (const row of environmentHeaderRows.value) {
    if (!row.enabled) continue;
    const key = String(row.key || "").trim();
    if (!key) continue;
    headers[key] = String(row.value ?? "");
  }
  return headers;
}

function syncEnvironmentHeadersTextFromRows() {
  const headers = environmentHeaderRowsToObject();
  environmentForm.default_headers_text = JSON.stringify(headers, null, 2);
}

function loadEnvironmentHeaderRows() {
  try {
    const parsed = environmentForm.default_headers_text?.trim()
      ? JSON.parse(environmentForm.default_headers_text)
      : {};
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      environmentHeaderRows.value = [{ enabled: true, key: "", value: "" }];
      setError("默认 Header 必须是 JSON 对象");
      return;
    }
    environmentHeaderRows.value = environmentHeadersObjectToRows(parsed);
  } catch {
    environmentHeaderRows.value = [{ enabled: true, key: "", value: "" }];
    setError("默认 Header 不是合法 JSON");
  }
}

function addEnvironmentHeaderRow() {
  environmentHeaderRows.value.push({ enabled: true, key: "", value: "" });
  syncEnvironmentHeadersTextFromRows();
}

function removeEnvironmentHeaderRow(index) {
  environmentHeaderRows.value.splice(index, 1);
  if (!environmentHeaderRows.value.length) {
    environmentHeaderRows.value.push({ enabled: true, key: "", value: "" });
  }
  syncEnvironmentHeadersTextFromRows();
}

function switchEnvironmentHeadersMode(mode) {
  environmentHeadersMode.value = mode;
  if (mode === "table") {
    loadEnvironmentHeaderRows();
  }
}

function beautifyEnvironmentHeaders() {
  try {
    const parsed = JSON.parse(environmentForm.default_headers_text || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return setError("默认 Header 必须是 JSON 对象");
    }
    environmentForm.default_headers_text = JSON.stringify(parsed, null, 2);
    loadEnvironmentHeaderRows();
  } catch {
    setError("默认 Header 不是合法 JSON");
  }
}

async function loadModules() {
  if (!selectedProjectId.value) {
    modules.value = [];
    return;
  }
  try {
    modules.value = (await api.listModules(selectedProjectId.value)).data || [];
  } catch (e) {
    setError(e?.response?.data?.detail || "加载模块失败");
  }
}

async function createModule(parentId = null) {
  if (!selectedProjectId.value) return setError("请先选择项目");
  moduleForm.id = null;
  moduleForm.name = "";
  moduleForm.parent_id = parentId ? Number(parentId) : null;
  moduleForm.description = "";
  showModuleEditor.value = true;
}

function createCaseInModule(moduleId) {
  resetForm(moduleId);
}

async function editModule(moduleItem) {
  if (!moduleItem?.id) return;
  moduleForm.id = Number(moduleItem.id);
  moduleForm.name = moduleItem.name || "";
  moduleForm.parent_id = moduleItem.parent_id ? Number(moduleItem.parent_id) : null;
  moduleForm.description = moduleItem.description || "";
  showModuleEditor.value = true;
}

function closeModuleEditor() {
  showModuleEditor.value = false;
}

async function saveModule() {
  if (!selectedProjectId.value) return setError("请先选择项目");
  const name = String(moduleForm.name || "").trim();
  if (!name) return setError("模块名称不能为空");
  if (moduleForm.id && moduleForm.parent_id && Number(moduleForm.id) === Number(moduleForm.parent_id)) {
    return setError("父模块不能是自己");
  }
  const payload = {
    project: selectedProjectId.value,
    parent: moduleForm.parent_id ? Number(moduleForm.parent_id) : null,
    name,
    description: String(moduleForm.description || "").trim() || null
  };
  try {
    if (moduleForm.id) {
      await api.updateModule(moduleForm.id, payload);
    } else {
      await api.createModule(payload);
    }
    await loadModules();
    setMessage(moduleForm.id ? "模块已更新" : "模块已创建");
    closeModuleEditor();
  } catch (e) {
    setError(e?.response?.data?.detail || (moduleForm.id ? "更新模块失败" : "创建模块失败"));
  }
}

async function moveModule(moduleItem) {
  const moduleId = Number(moduleItem?.id || 0);
  if (!moduleId) return;
  const current = modules.value.find((item) => Number(item.id) === moduleId);
  if (!current) return;
  const parentId = moduleItem?.parent_id ? Number(moduleItem.parent_id) : null;
  if (parentId !== null && parentId === moduleId) return setError("父模块不能是自己");
  const payload = {
    project: selectedProjectId.value,
    parent: parentId,
    name: current.name,
    description: current.description || null
  };
  try {
    await api.updateModule(moduleId, payload);
    await loadModules();
    setMessage("模块层级已更新");
  } catch (e) {
    setError(e?.response?.data?.detail || "更新模块层级失败");
  }
}

async function removeModule(moduleItem) {
  if (!moduleItem?.id) return;
  if (!(await showConfirm({ title: "删除模块", message: `确认删除模块【${moduleItem.name}】吗？`, danger: true }))) return;
  try {
    await api.deleteModule(moduleItem.id);
    if (Number(form.module) === Number(moduleItem.id)) {
      form.module = null;
    }
    await loadModules();
    await loadCases();
    setMessage("模块已删除");
  } catch (e) {
    setError(e?.response?.data?.detail || "删除模块失败");
  }
}

function addEnvironmentVariableRow() {
  environmentVariableRows.value.push({ enabled: true, key: "", value: "", value_mode: "custom", builtin_key: "timestamp_int" });
  syncEnvironmentVariablesTextFromRows();
}

function removeEnvironmentVariableRow(index) {
  environmentVariableRows.value.splice(index, 1);
  if (!environmentVariableRows.value.length) {
    environmentVariableRows.value.push({ enabled: true, key: "", value: "", value_mode: "custom", builtin_key: "timestamp_int" });
  }
  syncEnvironmentVariablesTextFromRows();
}

function switchEnvironmentVariablesMode(mode) {
  environmentVariablesMode.value = mode;
  if (mode === "table") {
    loadEnvironmentVariableRows();
  }
}

function beautifyEnvironmentVariables() {
  try {
    const parsed = JSON.parse(environmentForm.variables_text || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return setError("环境变量必须是 JSON 对象");
    }
    environmentForm.variables_text = JSON.stringify(parsed, null, 2);
    loadEnvironmentVariableRows();
  } catch {
    setError("环境变量不是合法 JSON");
  }
}

async function saveEnvironment() {
  const projectId = Number(environmentForm.project_id || selectedProjectId.value || projects.value?.[0]?.id || 0);
  if (!projectId) return setError("请选择所属项目");
  const baseUrlInput = String(environmentForm.base_url || "").trim();
  if (!baseUrlInput) return setError("环境地址不能为空");
  if (!/^https?:\/\//i.test(baseUrlInput)) {
    return setError("环境地址格式不正确，请使用 http://IP:端口 或 https://域名");
  }
  let baseUrl = baseUrlInput;
  try {
    const parsed = new URL(baseUrlInput);
    if (!parsed.hostname) {
      return setError("环境地址格式不正确，请检查后重试");
    }
    baseUrl = parsed.origin;
  } catch {
    return setError("环境地址格式不正确，请使用 http://IP:端口 或 https://域名");
  }
  let variables = {};
  let defaultHeaders = {};
  try {
    variables = environmentForm.variables_text?.trim() ? JSON.parse(environmentForm.variables_text) : {};
    defaultHeaders = environmentForm.default_headers_text?.trim()
      ? JSON.parse(environmentForm.default_headers_text)
      : {};
  } catch {
    return setError("环境变量和默认 Header 必须是合法 JSON 对象");
  }
  if (!variables || typeof variables !== "object" || Array.isArray(variables)) {
    return setError("环境变量必须是 JSON 对象");
  }
  if (!defaultHeaders || typeof defaultHeaders !== "object" || Array.isArray(defaultHeaders)) {
    return setError("默认 Header 必须是 JSON 对象");
  }
  const fallbackName = new URL(baseUrl).host || "";
  const name = String(environmentForm.name || "").trim()
    || fallbackName
    || projects.value.find((p) => Number(p.id) === projectId)?.name
    || `环境-${projectId}`;

  const payload = {
    project: projectId,
    name,
    description: String(environmentForm.description || "").trim() || null,
    base_url: baseUrl,
    variables,
    default_headers: defaultHeaders,
    is_active: Boolean(environmentForm.is_active)
  };

  try {
    if (environmentForm.id) {
      await api.updateEnvironment(environmentForm.id, payload);
      setMessage("环境已更新");
    } else {
      await api.createEnvironment(payload);
      setMessage("环境已创建");
    }
    resetEnvironmentForm();
    showEnvironmentEditor.value = false;
    if (selectedProjectId.value !== projectId) {
      selectedProjectId.value = projectId;
      await loadProjects();
      await loadModules();
      await loadCases();
      await loadHistories();
      await loadDashboard();
    }
    await loadEnvironments();
  } catch (e) {
    setError(e?.response?.data?.detail || "保存环境失败");
  }
}

async function removeEnvironment(envId) {
  if (!(await showConfirm({ title: "删除环境", message: "确认删除该环境吗？", danger: true }))) return;
  try {
    await api.deleteEnvironment(envId);
    if (Number(environmentForm.id) === Number(envId)) {
      resetEnvironmentForm();
    }
    setMessage("环境已删除");
    await loadEnvironments();
  } catch (e) {
    setError(e?.response?.data?.detail || "删除环境失败");
  }
}

async function saveProject() {
  if (!String(projectForm.name || "").trim()) {
    return setError("项目名称不能为空");
  }
  const payload = {
    name: String(projectForm.name).trim(),
    description: String(projectForm.description || "").trim() || null
  };
  try {
    if (projectForm.id) {
      await api.updateProject(projectForm.id, payload);
      setMessage("项目已更新");
    } else {
      const { data } = await api.createProject(payload);
      selectedProjectId.value = data.id;
      setMessage("项目已创建");
    }
    resetProjectForm();
    showProjectEditor.value = false;
    await loadProjects();
    await loadModules();
    await loadCases();
    await loadHistories();
    await loadDashboard();
    await loadEnvironments();
  } catch (e) {
    setError(getApiErrorMessage(e, "保存项目失败"));
  }
}

async function removeProject(projectId) {
  if (!(await showConfirm({ title: "删除项目", message: "确认删除该项目吗？", danger: true }))) return;
  try {
    await api.deleteProject(projectId);
    if (selectedProjectId.value === projectId) {
      selectedProjectId.value = null;
    }
    setMessage("项目已删除");
    await loadProjects();
    await loadModules();
    await loadCases();
    await loadHistories();
    await loadDashboard();
    await loadEnvironments();
  } catch (e) {
    setError(e?.response?.data?.detail || "删除项目失败");
  }
}

async function switchProject(projectId) {
  if (selectedProjectId.value === projectId) return;
  selectedProjectId.value = projectId;
  selectedCaseId.value = null;
  selectedAssetModuleId.value = null;
  historyQuery.page = 1;
  Object.assign(form, blankForm());
  await loadModules();
  await loadCases();
  await loadHistories();
  await loadDashboard();
  await loadEnvironments();
}

async function handleTopProjectChange(projectId) {
  if (!projectId) return;
  await switchProject(projectId);
}

async function loadRbac() {
  if (!isAdmin.value) return;
  loading.rbac = true;
  try {
    rbacData.value = (await api.getRbacOverview()).data;
  } catch (e) {
    setError(e?.response?.data?.detail || "加载权限与审计数据失败");
  } finally {
    loading.rbac = false;
  }
}

function monitorStatusText(statusCode) {
  const code = String(statusCode || "").toLowerCase();
  if (code === "running") return "运行中";
  if (code === "deploying") return "部署中";
  if (code === "failed") return "失败";
  return "待部署";
}

function monitorStatusClass(statusCode) {
  const code = String(statusCode || "").toLowerCase();
  if (code === "running") return "tag pass";
  if (code === "failed") return "tag fail";
  return "tag";
}

async function loadMonitorPlatforms() {
  loading.monitor = true;
  try {
    monitorPlatforms.value = (await api.listMonitorPlatforms()).data || [];
    const exists = monitorPlatforms.value.some((item) => Number(item.id) === Number(selectedMonitorPlatformId.value));
    if (!exists) {
      selectedMonitorPlatformId.value = monitorPlatforms.value.length ? Number(monitorPlatforms.value[0].id) : null;
    }
    const hostExists = monitorTargetHostOptions.value.some((item) => String(item.value || "") === String(selectedMonitorTargetHost.value || ""));
    if (!hostExists) {
      selectedMonitorTargetHost.value = "";
    }
    await loadMonitorMetrics();
  } catch (e) {
    const noticePage = page.value === "resource_monitor" ? "resource_monitor" : "monitor_config";
    setError(e?.response?.data?.detail || "加载监控平台失败", noticePage);
  } finally {
    loading.monitor = false;
  }
}

function buildMonitorTrendPointsFromHistory(items) {
  if (!Array.isArray(items)) return [];
  const points = [];
  for (const item of items) {
    const metrics = item?.metrics || {};
    const rawTime = String(item?.collected_at || "");
    const dt = new Date(rawTime);
    const t = Number.isNaN(dt.getTime())
      ? (rawTime.replace("T", " ").slice(11, 19) || rawTime)
      : `${String(dt.getHours()).padStart(2, "0")}:${String(dt.getMinutes()).padStart(2, "0")}:${String(dt.getSeconds()).padStart(2, "0")}`;
    points.push({
      t,
      cpu: Number(metrics?.cpu_usage_percent ?? 0),
      mem: Number(metrics?.memory_usage_percent ?? 0),
      disk: Number(metrics?.disk_usage_percent ?? 0),
      netThroughput: Number(metrics?.network_throughput_mbps ?? 0),
      netDrop: Number(metrics?.network_drop_rate ?? 0),
    });
  }
  return points;
}

function countMonitorMetricValues(metrics) {
  if (!metrics || typeof metrics !== "object") return 0;
  let count = 0;
  for (const value of Object.values(metrics)) {
    if (Array.isArray(value)) {
      if (value.length) count += 1;
      continue;
    }
    if (value !== null && value !== undefined) count += 1;
  }
  return count;
}

function formatTrafficRate(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  const abs = Math.abs(num);
  if (abs > 0 && abs < 1) {
    const kbps = num * 1024;
    const digits = Math.abs(kbps) >= 100 ? 0 : Math.abs(kbps) >= 10 ? 1 : 2;
    return `${kbps.toFixed(digits)} Kbps`;
  }
  const digits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2;
  return `${num.toFixed(digits)} Mbps`;
}

function pickBetterMonitorPayload(primary, secondary) {
  const primaryCount = countMonitorMetricValues(primary?.metrics);
  const secondaryCount = countMonitorMetricValues(secondary?.metrics);
  if (secondaryCount > primaryCount) return secondary;
  return primary;
}

function buildEmptyMonitorMetrics() {
  return {
    cpu_usage_percent: null,
    cpu_iowait_percent: null,
    cpu_cores: null,
    load1: null,
    load5: null,
    host_uptime_hours: null,
    memory_usage_percent: null,
    memory_available_gb: null,
    swap_usage_percent: null,
    disk_usage_percent: null,
    disk_free_gb: null,
    disk_read_mbps: null,
    disk_write_mbps: null,
    disk_await_ms: null,
    network_throughput_mbps: null,
    network_rx_mbps: null,
    network_tx_mbps: null,
    network_drop_rate: null,
    network_interfaces: [],
    tcp_established: null,
    tcp_time_wait: null,
    process_running: null,
    process_blocked: null,
    container_restart_count: null,
    pod_abnormal_count: null,
    api_qps: null,
    api_p95_ms: null,
    api_5xx_rate: null,
    db_active_connections: null,
    db_slow_queries: null,
    redis_hit_rate: null,
    container_running: null,
    targets_up: null,
    targets_down: null,
  };
}

function buildEmptyMonitorSnapshotMeta() {
  return {
    collectedAt: "",
    source: "",
    snapshotAgeSeconds: null,
    warning: "",
  };
}

function formatMonitorSnapshotSource(source) {
  const key = String(source || "").trim();
  if (key === "live") return "实时采集";
  if (key === "snapshot") return "缓存快照";
  if (key === "snapshot_fallback") return "回退快照";
  if (key === "history_snapshot") return "历史快照";
  return "-";
}

function formatMonitorSnapshotTime(value) {
  const raw = String(value || "").trim();
  if (!raw) return "-";
  const normalized = raw.replace("T", " ");
  return normalized.length > 19 ? normalized.slice(0, 19) : normalized;
}

function formatMonitorSnapshotAge(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) return "-";
  if (value < 60) return `${Math.round(value)}秒前`;
  if (value < 3600) return `${Math.round(value / 60)}分钟前`;
  if (value < 86400) return `${Math.round(value / 3600)}小时前`;
  return `${Math.round(value / 86400)}天前`;
}

function resolveMonitorHistoryLimit(rangeMinutes) {
  const minutes = Number(rangeMinutes || 60);
  if (minutes <= 60) return 120;
  if (minutes <= 360) return 240;
  if (minutes <= 1440) return 360;
  return 500;
}

async function loadMonitorMetrics(forceRefresh = false) {
  const id = Number(selectedMonitorPlatformId.value || 0);
  const targetHost = String(selectedMonitorTargetHost.value || "").trim();
  if (!id) {
    monitorMetrics.value = buildEmptyMonitorMetrics();
    monitorSnapshotMeta.value = buildEmptyMonitorSnapshotMeta();
    monitorTrendPoints.value = [];
    return;
  }
  const rangeMinutes = Number(monitorTimeRange.value || 60);
  const historyLimit = resolveMonitorHistoryLimit(rangeMinutes);
  let latestMetrics = null;
  let latestCollectedAt = "";
  let latestSource = "";
  let latestSnapshotAgeSeconds = null;
  let latestWarning = "";
  let historyItems = [];
  let latestError = null;
  let historyError = null;
  monitorSnapshotMeta.value = buildEmptyMonitorSnapshotMeta();
  try {
    const { data } = await api.getMonitorPlatformMetricsLatest(id, targetHost, forceRefresh);
    latestMetrics = data?.metrics && typeof data.metrics === "object" ? data.metrics : null;
    latestCollectedAt = String(data?.collected_at || "");
    latestSource = String(data?.source || "");
    latestSnapshotAgeSeconds = data?.snapshot_age_seconds ?? null;
    latestWarning = String(data?.warning || "");
  } catch (e) {
    latestError = e;
  }
  try {
    const historyResp = await api.getMonitorPlatformMetricsHistory(id, historyLimit, rangeMinutes, targetHost);
    historyItems = Array.isArray(historyResp?.data?.items) ? historyResp.data.items : [];
  } catch (e) {
    historyError = e;
  }

  monitorTrendPoints.value = buildMonitorTrendPointsFromHistory(historyItems);
  if (!monitorTrendPoints.value.length && latestMetrics && typeof latestMetrics === "object") {
    monitorTrendPoints.value = buildMonitorTrendPointsFromHistory([
      { collected_at: latestCollectedAt || new Date().toISOString(), metrics: latestMetrics }
    ]);
  }
  const lastHistoryItem = historyItems.length ? historyItems[historyItems.length - 1] : null;
  const historyPayload = lastHistoryItem && typeof lastHistoryItem?.metrics === "object"
    ? {
      metrics: lastHistoryItem.metrics,
      collectedAt: String(lastHistoryItem.collected_at || ""),
      source: "history_snapshot",
      snapshotAgeSeconds: null,
      warning: "",
    }
    : null;
  const latestPayload = latestMetrics && typeof latestMetrics === "object"
    ? {
      metrics: latestMetrics,
      collectedAt: latestCollectedAt,
      source: latestSource,
      snapshotAgeSeconds: latestSnapshotAgeSeconds,
      warning: latestWarning,
    }
    : null;
  const bestPayload = pickBetterMonitorPayload(latestPayload, historyPayload);
  if (bestPayload && typeof bestPayload.metrics === "object") {
    monitorMetrics.value = { ...buildEmptyMonitorMetrics(), ...bestPayload.metrics };
    monitorSnapshotMeta.value = {
      collectedAt: String(bestPayload.collectedAt || ""),
      source: String(bestPayload.source || ""),
      snapshotAgeSeconds: bestPayload.snapshotAgeSeconds ?? null,
      warning: String(bestPayload.warning || ""),
    };
  } else {
    monitorMetrics.value = buildEmptyMonitorMetrics();
    monitorSnapshotMeta.value = buildEmptyMonitorSnapshotMeta();
  }

  if (latestError && historyError) {
    setError(getApiErrorMessage(historyError, "加载监控指标失败"), "resource_monitor");
    return;
  }

  const values = Object.values(monitorMetrics.value || {}).filter((v) => !Array.isArray(v));
  const allEmpty = values.length > 0 && values.every((v) => v === null || v === undefined);
  if (allEmpty) {
    setError("未获取到监控指标：请检查 Prometheus 地址连通性、9090 端口开放情况，或 SSH 凭证是否可用于回退采集。", "resource_monitor");
  }
}

function parseMonitorTargetHostsText(text) {
  const rows = [];
  const lines = String(text || "").split(/\r?\n/);
  for (const raw of lines) {
    const line = String(raw || "").trim();
    if (!line || line.startsWith("#")) continue;
    const parts = line.split(":").map((item) => String(item || "").trim()).filter(Boolean);
    const host = parts[0] || "";
    if (!host) continue;
    const nodePort = Number(parts[1] || 9100);
    const cadvisorPort = Number(parts[2] || 8080);
    rows.push({
      host,
      node_exporter_port: Number.isFinite(nodePort) && nodePort > 0 ? nodePort : 9100,
      cadvisor_port: Number.isFinite(cadvisorPort) && cadvisorPort > 0 ? cadvisorPort : 8080,
      enabled: true,
    });
  }
  return rows;
}

function formatMonitorTargetHostsText(rows) {
  const list = Array.isArray(rows) ? rows : [];
  return list
    .map((row) => {
      const host = String(row?.host || "").trim();
      if (!host) return "";
      const nodePort = Number(row?.node_exporter_port || 9100) || 9100;
      const cadvisorPort = Number(row?.cadvisor_port || 8080) || 8080;
      if (nodePort === 9100 && cadvisorPort === 8080) return host;
      return `${host}:${nodePort}:${cadvisorPort}`;
    })
    .filter(Boolean)
    .join("\n");
}

function resetMonitorForm() {
  monitorForm.id = null;
  monitorForm.name = "";
  monitorForm.platform_type = "single";
  monitorForm.host = "";
  monitorForm.ssh_port = 22;
  monitorForm.ssh_username = "root";
  monitorForm.ssh_password = "";
  monitorForm.deploy_mode = "online";
  monitorForm.target_hosts_text = "";
  monitorRuntimeCheck.value = null;
  monitorRuntimeChecking.value = false;
}

function buildMonitorSavePayload() {
  const name = String(monitorForm.name || "").trim();
  const host = String(monitorForm.host || "").trim();
  const username = String(monitorForm.ssh_username || "").trim();
  if (!name || !host || !username) {
    setError("平台名称、地址、用户名不能为空", "monitor_config");
    return null;
  }
  const platformType = String(monitorForm.platform_type || "single");
  const monitorTargets = platformType === "host_cluster" ? parseMonitorTargetHostsText(monitorForm.target_hosts_text) : [];
  if (platformType === "host_cluster" && !monitorTargets.length) {
    setError("主机集群模式至少需要一个目标主机", "monitor_config");
    return null;
  }
  const payload = {
    id: monitorForm.id || undefined,
    name,
    platform_type: platformType,
    host,
    ssh_port: Number(monitorForm.ssh_port || 22),
    ssh_username: username,
    deploy_mode: String(monitorForm.deploy_mode || "online"),
    monitor_targets: monitorTargets,
    auto_deploy: true,
  };
  const password = String(monitorForm.ssh_password || "");
  if (password.trim()) payload.ssh_password = password;
  return payload;
}

function buildMonitorDeployMessage(data, fallback) {
  if (data?.adopted_existing) {
    return "检测到平台已安装监控组件，已复用现有组件并刷新采集配置";
  }
  const runtime = data?.docker_runtime || {};
  if (runtime && runtime.ssh_connected === false && runtime.detail) {
    return `${fallback}；但 Docker 环境检测失败：${runtime.detail}`;
  }
  if (runtime && runtime.docker_installed === false) {
    return `${fallback}；未检测到 Docker，系统已尝试自动安装后继续部署`;
  }
  if (runtime?.docker_installed && runtime?.docker_compose_installed === false) {
    return `${fallback}；已检测到 Docker，但未检测到 Compose，系统已尝试补装后继续部署`;
  }
  if (runtime?.docker_installed && runtime?.docker_accessible === false) {
    return `${fallback}；已检测到 Docker，但当前不可直接访问，系统已继续尝试修复并部署`;
  }
  return fallback;
}

async function checkMonitorPlatformRuntime() {
  const payload = buildMonitorSavePayload();
  if (!payload) return;
  monitorRuntimeChecking.value = true;
  try {
    const { data } = await api.checkMonitorPlatformRuntime(payload);
    monitorRuntimeCheck.value = data || null;
    setMessage(data?.detail || "Docker 环境检测完成", "monitor_config");
  } catch (e) {
    monitorRuntimeCheck.value = null;
    setError(getApiErrorMessage(e, "Docker 环境检测失败"), "monitor_config");
  } finally {
    monitorRuntimeChecking.value = false;
  }
}

function openMonitorCreate() {
  resetMonitorForm();
  showMonitorEditor.value = true;
}

function openMonitorEdit(item) {
  monitorForm.id = Number(item?.id || 0) || null;
  monitorForm.name = String(item?.name || "");
  monitorForm.platform_type = String(item?.platform_type || "single");
  monitorForm.host = String(item?.host || "");
  monitorForm.ssh_port = Number(item?.ssh_port || 22) || 22;
  monitorForm.ssh_username = String(item?.ssh_username || "root");
  monitorForm.ssh_password = "";
  monitorForm.deploy_mode = String(item?.deploy_mode || "online");
  monitorForm.target_hosts_text = formatMonitorTargetHostsText(item?.monitor_targets || []);
  showMonitorEditor.value = true;
}

function closeMonitorEditor() {
  showMonitorEditor.value = false;
  resetMonitorForm();
}

async function saveMonitorPlatform() {
  const payload = buildMonitorSavePayload();
  if (!payload) return;
  loading.save = true;
  try {
    if (monitorForm.id) {
      await api.updateMonitorPlatform(monitorForm.id, payload);
      const { data } = await api.deployMonitorPlatform(monitorForm.id, { deploy_mode: payload.deploy_mode });
      setMessage(buildMonitorDeployMessage(data, "监控平台已更新并触发部署"), "monitor_config");
    } else {
      const { data } = await api.createMonitorPlatform(payload);
      setMessage(buildMonitorDeployMessage(data, "监控平台已创建并触发部署"), "monitor_config");
    }
    closeMonitorEditor();
    await loadMonitorPlatforms();
  } catch (e) {
    setError(getApiErrorMessage(e, "保存监控平台失败"), "monitor_config");
  } finally {
    loading.save = false;
  }
}

async function removeMonitorPlatform(item) {
  if (!(await showConfirm({ title: "删除监控平台", message: `确认删除平台「${item?.name || "-"}」吗？`, danger: true }))) return;
  try {
    await api.deleteMonitorPlatform(item.id);
    setMessage("监控平台已删除", "monitor_config");
    await loadMonitorPlatforms();
  } catch (e) {
    setError(getApiErrorMessage(e, "删除监控平台失败"), "monitor_config");
  }
}

async function redeployMonitorPlatform(item) {
  try {
    const { data } = await api.deployMonitorPlatform(item.id, { deploy_mode: item?.deploy_mode || "online" });
    setMessage(buildMonitorDeployMessage(data, `已触发平台「${item?.name || "-"}」重新部署`), "monitor_config");
    await loadMonitorPlatforms();
  } catch (e) {
    setError(getApiErrorMessage(e, "触发部署失败"), "monitor_config");
  }
}

function triggerMonitorPackageUpload(id) {
  monitorUploadingId.value = Number(id || 0) || null;
  monitorPackageInputRef.value?.click();
}

async function onMonitorPackageChange(event) {
  const file = event?.target?.files?.[0];
  if (!file || !monitorUploadingId.value) {
    event.target.value = "";
    return;
  }
  try {
    await api.uploadMonitorPlatformPackage(monitorUploadingId.value, file, true);
    setMessage("离线包上传成功，已触发离线部署", "monitor_config");
    await loadMonitorPlatforms();
  } catch (e) {
    setError(getApiErrorMessage(e, "离线包上传失败"), "monitor_config");
  } finally {
    monitorUploadingId.value = null;
    event.target.value = "";
  }
}

async function openMonitorLogs(item) {
  try {
    const { data } = await api.getMonitorPlatformLogs(item.id);
    monitorLogs.value = Array.isArray(data?.logs) ? data.logs : [];
    showMonitorLogs.value = true;
  } catch (e) {
    setError(getApiErrorMessage(e, "读取部署日志失败"), "monitor_config");
  }
}

function resetUserForm() {
  userForm.id = null;
  userForm.username = "";
  userForm.email = "";
  userForm.project_ids = [];
  userForm.is_active = true;
  userForm.password = "";
}

function openCreateUser() {
  resetUserForm();
  if (selectedProjectId.value) {
    userForm.project_ids = [Number(selectedProjectId.value)];
  }
  showUserEditor.value = true;
}

function openEditUser(member) {
  userForm.id = Number(member?.id || 0) || null;
  userForm.username = String(member?.username || "");
  userForm.email = String(member?.email || "");
  userForm.project_ids = Array.isArray(member?.project_ids) ? member.project_ids.map((x) => Number(x)).filter(Boolean) : [];
  userForm.is_active = member?.is_active !== false;
  userForm.password = "";
  showUserEditor.value = true;
}

function closeUserEditor() {
  showUserEditor.value = false;
  resetUserForm();
}

async function saveUser() {
  const username = String(userForm.username || "").trim();
  if (!userForm.id && !username) return setError("用户名不能为空");
  if (!userForm.id && !String(userForm.password || "").trim()) return setError("新建用户必须填写密码");
  userSaving.value = true;
  try {
    if (userForm.id) {
      const payload = {
        email: String(userForm.email || "").trim(),
        project_ids: Array.isArray(userForm.project_ids) ? userForm.project_ids.map((x) => Number(x)).filter(Boolean) : [],
        is_active: !!userForm.is_active
      };
      if (String(userForm.password || "").trim()) payload.password = String(userForm.password || "");
      await api.updateUser(userForm.id, payload);
      setMessage("用户已更新");
    } else {
      await api.createUser({
        username,
        password: String(userForm.password || ""),
        email: String(userForm.email || "").trim(),
        project_ids: Array.isArray(userForm.project_ids) ? userForm.project_ids.map((x) => Number(x)).filter(Boolean) : [],
        is_active: !!userForm.is_active
      });
      setMessage("用户已创建");
    }
    closeUserEditor();
    await loadRbac();
  } catch (e) {
    setError(e?.response?.data?.detail || "保存用户失败");
  } finally {
    userSaving.value = false;
  }
}

async function toggleUserActive(member) {
  const target = member?.is_active === false;
  const action = target ? "启用" : "禁用";
  if (!(await showConfirm({ title: `${action}用户`, message: `确认${action}用户「${member?.username || "-"}」吗？`, danger: !target }))) return;
  try {
    await api.updateUser(member.id, {
      email: member?.email || "",
      project_ids: Array.isArray(member?.project_ids) ? member.project_ids.map((x) => Number(x)).filter(Boolean) : [],
      is_active: target
    });
    setMessage(`用户已${action}`);
    await loadRbac();
  } catch (e) {
    setError(e?.response?.data?.detail || `${action}用户失败`);
  }
}

async function resetUserPassword(member) {
  const newPwd = window.prompt(`请输入用户「${member?.username || "-"}」的新密码（至少6位）`);
  if (newPwd === null) return;
  const password = String(newPwd || "").trim();
  if (password.length < 6) return setError("密码长度至少6位");
  try {
    await api.updateUser(member.id, { password });
    setMessage("密码已重置");
  } catch (e) {
    setError(e?.response?.data?.detail || "重置密码失败");
  }
}

async function removeUser(member) {
  if (!(await showConfirm({ title: "删除用户", message: `确认删除用户「${member?.username || "-"}」吗？`, danger: true }))) return;
  try {
    await api.deleteUser(member.id);
    setMessage("用户已删除");
    await loadRbac();
  } catch (e) {
    setError(e?.response?.data?.detail || "删除用户失败");
  }
}

function selectCase(item) {
  selectedCaseId.value = item.id;
  Object.assign(form, caseToForm(item));
  page.value = "assets";
  historyQuery.page = 1;
  loadHistories(item.id);
}

function getDescendantModuleIds(moduleId) {
  const ids = new Set();
  const queue = [Number(moduleId)];
  while (queue.length) {
    const current = queue.shift();
    if (!current || ids.has(current)) continue;
    ids.add(current);
    for (const item of modules.value || []) {
      if (Number(item.parent_id || 0) === current) queue.push(Number(item.id));
    }
  }
  return Array.from(ids);
}

function onAssetModuleSelect(moduleId) {
  selectedAssetModuleId.value = moduleId ? Number(moduleId) : null;
  selectedModuleCaseIds.value = [];
  moduleCasePage.value = 1;
}

watch(allModuleCaseIds, (ids) => {
  const valid = new Set(ids);
  selectedModuleCaseIds.value = selectedModuleCaseIds.value.filter((id) => valid.has(Number(id)));
});
watch(filteredSelectedAssetModuleCases, (list) => {
  const total = Array.isArray(list) ? list.length : 0;
  const size = Math.max(1, Number(moduleCasePageSize.value || 10));
  const maxPage = Math.max(1, Math.ceil(total / size));
  if (Number(moduleCasePage.value || 1) > maxPage) moduleCasePage.value = maxPage;
});
watch([assetCaseKeyword, assetCaseOrdering, selectedAssetModuleId], () => {
  moduleCasePage.value = 1;
});

function toggleSelectAllModuleCases(checked) {
  const pageIds = currentPageModuleCaseIds.value;
  if (!pageIds.length) return;
  if (!checked) {
    const pageSet = new Set(pageIds);
    selectedModuleCaseIds.value = selectedModuleCaseIds.value.filter((id) => !pageSet.has(Number(id)));
    return;
  }
  const merged = new Set(selectedModuleCaseIds.value.map((id) => Number(id)));
  for (const id of pageIds) merged.add(Number(id));
  selectedModuleCaseIds.value = Array.from(merged);
}

function toggleSelectModuleCase(caseId, checked) {
  const id = Number(caseId);
  if (!id) return;
  const exists = selectedModuleCaseIds.value.includes(id);
  if (checked && !exists) {
    selectedModuleCaseIds.value = [...selectedModuleCaseIds.value, id];
    return;
  }
  if (!checked && exists) {
    selectedModuleCaseIds.value = selectedModuleCaseIds.value.filter((item) => Number(item) !== id);
  }
}

async function removeModuleCases(ids, removeAll = false) {
  // 批量删除采用 allSettled，保证部分失败时也能返回成功统计。
  const targetIds = Array.from(new Set((ids || []).map((item) => Number(item)).filter((item) => item > 0)));
  if (!targetIds.length) {
    setError(removeAll ? "当前模块暂无可删除接口" : "请先勾选要删除的接口");
    return;
  }
  const ok = await showConfirm({
    title: removeAll ? "全部删除接口" : "批量删除接口",
    message: removeAll
      ? `确认删除当前模块列表内全部 ${targetIds.length} 条接口吗？`
      : `确认删除选中的 ${targetIds.length} 条接口吗？`,
    danger: true
  });
  if (!ok) return;
  loading.save = true;
  try {
    const results = await Promise.allSettled(targetIds.map((id) => api.deleteCase(id)));
    const failCount = results.filter((item) => item.status === "rejected").length;
    const successCount = targetIds.length - failCount;
    if (selectedCaseId.value && targetIds.includes(Number(selectedCaseId.value))) {
      resetForm();
    }
    selectedModuleCaseIds.value = [];
    await loadCases();
    await loadHistories();
    await loadDashboard();
    if (!failCount) {
      setMessage(`删除成功，共 ${successCount} 条`);
    } else {
      setError(`部分删除失败：成功 ${successCount} 条，失败 ${failCount} 条`);
    }
  } catch (e) {
    setError(getApiErrorMessage(e, "删除失败"));
  } finally {
    loading.save = false;
  }
}

async function saveCase() {
  if (!selectedProjectId.value) {
    return setError("请先选择一个项目");
  }
  let payload;
  try {
    payload = formToPayload(form);
    payload.project = selectedProjectId.value;
  } catch (e) {
    return setError(e.message || "表单校验失败");
  }
  if (payload.module && !(modules.value || []).some((m) => Number(m.id) === Number(payload.module))) {
    return setError("所属模块无效，请重新选择");
  }

  const normalizedName = String(payload.name || "").trim().toLowerCase();
  const duplicate = cases.value.find(
    (item) =>
      String(item.name || "").trim().toLowerCase() === normalizedName &&
      Number(item.id) !== Number(form.id || 0)
  );
  if (duplicate) {
    return setError("接口名称“" + payload.name + "”在当前项目已存在，请更换名称");
  }

  loading.save = true;
  try {
    if (form.id) {
      const { data } = await api.updateCase(form.id, payload);
      Object.assign(form, caseToForm(data));
      setMessage("接口已更新");
    } else {
      const { data } = await api.createCase(payload);
      Object.assign(form, caseToForm(data));
      selectedCaseId.value = data.id;
      setMessage("接口已创建");
    }
    await loadCases();
    if (selectedCaseId.value) await loadHistories(selectedCaseId.value);
    await loadDashboard();
  } catch (e) {
    setError(getApiErrorMessage(e, "保存失败"));
  } finally {
    loading.save = false;
  }
}

function closeCasePreview() {
  showCasePreview.value = false;
  casePreviewData.value = null;
}

function hasPreviewContent(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return String(value).trim() !== "";
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return true;
}

async function previewCurrentCase() {
  if (!selectedProjectId.value) {
    return setError("请先选择一个项目");
  }
  let payload;
  try {
    payload = formToPayload(form);
    payload.project = selectedProjectId.value;
    if (form.id) payload.case_id = Number(form.id);
  } catch (e) {
    return setError(e?.message || "预检失败");
  }
  casePreviewLoading.value = true;
  try {
    const { data } = await api.previewCase(payload);
    casePreviewData.value = data || null;
    showCasePreview.value = true;
    setMessage("接口预检完成");
  } catch (e) {
    setError(getApiErrorMessage(e, "接口预检失败"));
  } finally {
    casePreviewLoading.value = false;
  }
}

async function removeCase(id) {
  if (!(await showConfirm({ title: "删除接口", message: "确认删除该接口吗？", danger: true }))) return;
  try {
    await api.deleteCase(id);
    if (selectedCaseId.value === id) resetForm();
    setMessage("接口已删除");
    await loadCases();
    await loadHistories();
  } catch (e) {
    setError(e?.response?.data?.detail || "删除失败");
  }
}

async function runCurrentCase() {
  if (!form.id) return setError("请先选择或创建一个接口");
  loading.run = true;
  try {
    const { data } = await api.runCase(form.id);
    setMessage("执行完成：" + (data.history.success ? "通过" : "失败") + " / " + (data.history.response_time_ms ?? 0) + "ms");
    await loadHistories(form.id);
    await loadDashboard();
    page.value = "runs";
  } catch (e) {
    setError(e?.response?.data?.detail || "执行失败");
  } finally {
    loading.run = false;
  }
}

async function generateCasesByAi({ prompt, baseUrlHint, aiConfig: runtimeAiConfig }) {
  loading.ai = true;
  try {
    const cfg = runtimeAiConfig || aiConfig;
    const { data } = await api.generateCasesByAi({
      prompt,
      base_url_hint: baseUrlHint || null,
      ai_base_url: String(cfg.apiBaseUrl || "").trim() || null,
      ai_api_key: String(cfg.apiKey || "").trim() || null,
      ai_model: String(cfg.model || "").trim() || null,
      ai_timeout_seconds: Number(cfg.timeoutSeconds || 60)
    });
    aiGeneratedCases.value = data.cases || [];
    aiOpenapiSummary.value = null;
    page.value = "ai";
    setMessage("AI 已生成 " + aiGeneratedCases.value.length + " 条接口草稿");
  } catch (e) {
    setError(e?.response?.data?.detail || "AI 生成失败");
  } finally {
    loading.ai = false;
  }
}

async function generateCasesFromOpenapi({ schemaUrl, schemaText, extraRequirements, aiConfig: runtimeAiConfig }) {
  loading.ai = true;
  try {
    const cfg = runtimeAiConfig || aiConfig;
    const { data } = await api.generateCasesFromOpenapi({
      schema_url: schemaUrl || null,
      schema_text: schemaText || null,
      extra_requirements: extraRequirements || null,
      ai_base_url: String(cfg.apiBaseUrl || "").trim() || null,
      ai_api_key: String(cfg.apiKey || "").trim() || null,
      ai_model: String(cfg.model || "").trim() || null,
      ai_timeout_seconds: Number(cfg.timeoutSeconds || 60)
    });
    aiGeneratedCases.value = data.cases || [];
    aiOpenapiSummary.value = data.summary || null;
    page.value = "ai";
    setMessage("OpenAPI 解析完成，生成 " + aiGeneratedCases.value.length + " 条接口草稿");
  } catch (e) {
    setError(e?.response?.data?.detail || "OpenAPI 生成失败");
  } finally {
    loading.ai = false;
  }
}

function loadAiCaseToForm(item) {
  Object.assign(form, caseToForm(item));
  selectedCaseId.value = null;
  page.value = "assets";
  setMessage("已将 AI 草稿载入接口编辑器");
}

async function createAllAiCases(items) {
  if (!items?.length) return;
  let ok = 0;
  let fail = 0;
  loading.save = true;
  for (const item of items) {
    try {
      await api.createCase({ ...item, project: selectedProjectId.value });
      ok += 1;
    } catch {
      fail += 1;
    }
  }
  loading.save = false;
  await loadCases();
  await loadDashboard();
  if (fail) setError("批量导入完成：成功 " + ok + "，失败 " + fail);
  else setMessage("批量导入成功：" + ok + " 条接口");
}

function resetApiImportForm() {
  apiImportForm.schemaUrl = "";
  apiImportForm.schemaText = "";
  apiImportForm.extraRequirements = "";
  apiImportForm.moduleId = selectedAssetModuleId.value || null;
  const defaultEnv = (activeEnvironmentItems.value || []).find(
    (env) => Number(env.id) === Number(selectedEnvironmentId.value)
  ) || (activeEnvironmentItems.value || [])[0];
  apiImportForm.environmentId = defaultEnv ? Number(defaultEnv.id) : null;
  apiImportForm.dedupeStrategy = "skip";
  apiImportSummary.value = null;
  apiImportPreview.value = [];
  apiImportFileName.value = "";
  apiImportUploadedText.value = "";
  if (apiImportFileInputRef.value) {
    apiImportFileInputRef.value.value = "";
  }
}

function openApiImportEditor() {
  if (!selectedProjectId.value) {
    setError("请先选择项目");
    return;
  }
  resetApiImportForm();
  showApiImportEditor.value = true;
}

function closeApiImportEditor() {
  showApiImportEditor.value = false;
}

function triggerApiImportFileSelect() {
  apiImportFileInputRef.value?.click();
}

async function onApiImportFileChange(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  const name = String(file.name || "").toLowerCase();
  if (!(name.endsWith(".json") || name.endsWith(".yaml") || name.endsWith(".yml"))) {
    setError("仅支持上传 .json / .yaml / .yml 文件");
    event.target.value = "";
    return;
  }
  try {
    const text = await file.text();
    apiImportUploadedText.value = String(text || "");
    apiImportForm.schemaUrl = "";
    apiImportFileName.value = file.name || "";
    await parseOpenapiForImport({ fromUpload: true });
  } catch {
    setError("读取文件失败");
  } finally {
    event.target.value = "";
  }
}

async function parseOpenapiForImport(options = {}) {
  const uploadedText = String(apiImportUploadedText.value || "");
  const manualText = String(apiImportForm.schemaText || "");
  const schemaText = manualText.trim() ? manualText : uploadedText;
  if (!apiImportForm.schemaUrl.trim() && !schemaText.trim()) {
    setError("请提供文档 URL 或 OpenAPI 文本");
    return;
  }
  importLoading.parse = true;
  startParseProgress();
  try {
    const { data } = await api.generateCasesFromOpenapi({
      schema_url: apiImportForm.schemaUrl || null,
      schema_text: schemaText || null,
      extra_requirements: apiImportForm.extraRequirements || null
    });
    apiImportSummary.value = data.summary || null;
    apiImportPreview.value = decorateImportPreview(data.cases || []);
    if (options?.fromUpload) {
      setMessage(`文件解析完成：${apiImportFileName.value || "本地文件"}，预生成 ${apiImportPreview.value.length} 条接口`);
    } else {
      setMessage("解析完成，预生成 " + apiImportPreview.value.length + " 条接口");
    }
    finishParseProgress(true);
  } catch (e) {
    setError(e?.response?.data?.detail || "解析接口文档失败");
    finishParseProgress(false);
  } finally {
    importLoading.parse = false;
  }
}

function startParseProgress() {
  parseProgress.value = 3;
  parseProgressText.value = "正在读取文档...";
  if (parseProgressTimer) clearInterval(parseProgressTimer);
  parseProgressTimer = setInterval(() => {
    if (parseProgress.value < 35) parseProgressText.value = "正在解析接口路径...";
    else if (parseProgress.value < 70) parseProgressText.value = "正在构建请求参数...";
    else parseProgressText.value = "正在生成接口草稿...";
    if (parseProgress.value < 90) {
      const step = parseProgress.value < 50 ? 4 : (parseProgress.value < 80 ? 2 : 1);
      parseProgress.value = Math.min(90, parseProgress.value + step);
    }
  }, 180);
}

function finishParseProgress(success) {
  if (parseProgressTimer) {
    clearInterval(parseProgressTimer);
    parseProgressTimer = null;
  }
  parseProgress.value = 100;
  parseProgressText.value = success ? "解析完成" : "解析失败";
}

onBeforeUnmount(() => {
  if (parseProgressTimer) clearInterval(parseProgressTimer);
});

function toggleAllImportCases(enabled) {
  apiImportPreview.value = (apiImportPreview.value || []).map((item) => ({ ...item, enabled }));
}

function resolveImportBaseUrl(rawBaseUrl, fallbackBaseUrl, summaryBaseUrl) {
  const candidates = [rawBaseUrl, fallbackBaseUrl, summaryBaseUrl];
  for (const value of candidates) {
    const normalized = String(value || "").trim();
    if (normalized) return normalized;
  }
  return "";
}

function normalizeImportedHeaders(rawHeaders) {
  if (!rawHeaders || typeof rawHeaders !== "object" || Array.isArray(rawHeaders)) return {};
  const normalizeHeaderValue = (val) => {
    if (val === null || val === undefined) return val;
    const text = String(val);
    return text
      .replace(/\{\{\s*data-plat-id\s*\}\}/gi, "{{platId}}")
      .replace(/\{\{\s*admin-token-id\s*\}\}/gi, "{{adminTokenId}}");
  };
  const normalized = {};
  for (const [rawKey, val] of Object.entries(rawHeaders)) {
    const mappedVal = normalizeHeaderValue(val);
    const key = String(rawKey || "").trim();
    normalized[key] = mappedVal;
  }
  return normalized;
}

async function confirmImportCases() {
  const selectedItems = (apiImportPreview.value || []).filter((item) => item.enabled);
  if (!selectedItems.length) {
    setError("请至少选择一条接口");
    return;
  }
  importLoading.save = true;
  try {
    let ok = 0;
    let fail = 0;
    let skipped = 0;
    const failReasons = [];
    const strategy = apiImportForm.dedupeStrategy || "skip";
    const runtimeCaseIdByKey = new Map();
    for (const [key, list] of existingCaseMapByImportKey.value.entries()) {
      if (list?.length) runtimeCaseIdByKey.set(key, Number(list[0].id));
    }
    const usedNames = new Set((cases.value || []).map((item) => String(item.name || "").trim()));
    const selectedEnv = (activeEnvironmentItems.value || []).find(
      (env) => Number(env.id) === Number(apiImportForm.environmentId || 0)
    );
    const fallbackBaseUrl = String(selectedEnv?.base_url || "").trim();
    const summaryBaseUrl = String(apiImportSummary.value?.base_url || "").trim();
    for (const item of selectedItems) {
      const key = buildImportCaseKey(item);
      const duplicated = runtimeCaseIdByKey.has(key);
      const payload = {
        ...item,
        project: selectedProjectId.value
      };
      delete payload.__tmp_id;
      delete payload.enabled;
      delete payload.__import_key;
      delete payload.__duplicate_existing;
      delete payload.__duplicate_in_preview;
      delete payload.__duplicate_case_id;
      delete payload.__duplicate_case_name;
      payload.base_url = resolveImportBaseUrl(payload.base_url, fallbackBaseUrl, summaryBaseUrl);
      payload.path = String(payload.path || "").trim() || "/";
      if (!payload.path.startsWith("/")) payload.path = "/" + payload.path;
      payload.method = String(payload.method || "GET").toUpperCase();
      payload.headers = normalizeImportedHeaders(payload.headers);
      payload.params = payload.params && typeof payload.params === "object" ? payload.params : {};
      payload.assert_status = null;
      payload.assert_contains = "";
      payload.custom_assertions = null;
      if (!payload.base_url) {
        fail += 1;
        failReasons.push(`【${payload.name || payload.path}】缺少 Base URL（请在导入面板选择默认关联环境，或在 OpenAPI servers 中配置地址）`);
        continue;
      }
      if (apiImportForm.moduleId) payload.module = Number(apiImportForm.moduleId);
      if (apiImportForm.environmentId) payload.environment = Number(apiImportForm.environmentId);
      const originName = String(payload.name || "").trim() || `${payload.method} ${payload.path}`;
      payload.name = originName;
      try {
        if (duplicated && strategy === "skip") {
          skipped += 1;
          continue;
        }
        if (duplicated && strategy === "overwrite") {
          const targetId = Number(runtimeCaseIdByKey.get(key));
          await api.updateCase(targetId, payload);
          ok += 1;
          usedNames.add(payload.name);
          continue;
        }
        if (usedNames.has(payload.name) || (duplicated && strategy === "rename")) {
          payload.name = buildUniqueImportName(payload.name, usedNames);
        }
        const { data } = await api.createCase(payload);
        usedNames.add(String(payload.name || "").trim());
        if (!duplicated && data?.id) runtimeCaseIdByKey.set(key, Number(data.id));
        ok += 1;
      } catch (e) {
        fail += 1;
        const msg = getApiErrorMessage(e, "未知错误");
        failReasons.push(`【${payload.name || payload.path}】${msg}`);
      }
    }
    await loadCases();
    await loadDashboard();
    if (!fail) {
      const parts = ["成功 " + ok + " 条"];
      if (skipped) parts.push("跳过 " + skipped + " 条");
      setMessage("导入完成：" + parts.join("，"));
      closeApiImportEditor();
    } else {
      const head = "导入完成：成功 " + ok + "，失败 " + fail + (skipped ? "，跳过 " + skipped : "");
      const detailText = failReasons.slice(0, 3).join("；");
      setError(detailText ? `${head}。${detailText}` : head);
    }
  } catch (e) {
    setError(getApiErrorMessage(e, "导入保存失败"));
  } finally {
    importLoading.save = false;
  }
}

function buildImportCaseKey(item) {
  const method = String(item?.method || "GET").trim().toUpperCase();
  let path = String(item?.path || "/").trim();
  if (!path) path = "/";
  if (!path.startsWith("/")) path = "/" + path;
  return method + " " + path;
}

function decorateImportPreview(rawItems) {
  const existing = existingCaseMapByImportKey.value;
  const seen = new Set();
  return (rawItems || []).map((item, index) => {
    const key = buildImportCaseKey(item);
    const existingList = existing.get(key) || [];
    const inPreviewDup = seen.has(key);
    seen.add(key);
    return {
      ...item,
      __tmp_id: `${index}-${key}`,
      __import_key: key,
      __duplicate_existing: !!existingList.length,
      __duplicate_in_preview: inPreviewDup,
      __duplicate_case_id: existingList.length ? Number(existingList[0].id) : null,
      __duplicate_case_name: existingList.length ? String(existingList[0].name || "") : "",
      enabled: true
    };
  });
}

function buildUniqueImportName(baseName, usedNames) {
  const raw = String(baseName || "未命名接口").trim() || "未命名接口";
  let name = raw;
  let seq = 1;
  while (usedNames.has(name)) {
    seq += 1;
    name = `${raw}-导入${seq}`;
  }
  return name;
}

onMounted(async () => {
  setUnauthorizedHandler(() => {
    clearAuthState();
    authLoading.value = false;
  });
  loadAiConfig();
  loadUiState();
  await loadCurrentUser();
  if (authUser.value) {
    await bootstrapAfterLogin();
  }
});

watch(
  () => [page.value, selectedProjectId.value],
  () => {
    persistUiState();
  }
);

watch(
  () => page.value,
  async (next) => {
    if ((next === "resource_monitor" || next === "monitor_config") && authUser.value) {
      await loadMonitorPlatforms();
    }
  }
);

watch(
  () => selectedMonitorPlatformId.value,
  async () => {
    if (page.value === "resource_monitor") {
      const hostExists = monitorTargetHostOptions.value.some((item) => String(item.value || "") === String(selectedMonitorTargetHost.value || ""));
      if (!hostExists) {
        selectedMonitorTargetHost.value = "";
      }
      monitorTrendPoints.value = [];
      await loadMonitorMetrics();
    }
  }
);

watch(
  () => selectedMonitorTargetHost.value,
  async () => {
    if (page.value === "resource_monitor") {
      monitorTrendPoints.value = [];
      await loadMonitorMetrics();
    }
  }
);

watch(
  () => monitorTimeRange.value,
  async () => {
    if (page.value === "resource_monitor") {
      monitorTrendPoints.value = [];
      await loadMonitorMetrics();
    }
  }
);

watch(
  aiConfig,
  () => {
    persistAiConfig();
  },
  { deep: true }
);

watch(
  () => visibleNavItems.value.map((item) => item.key),
  (keys) => {
    if (!keys.includes(page.value)) {
      page.value = "dashboard";
    }
  },
  { immediate: true }
);
</script>

<template>
  <div v-if="authLoading" class="auth-wrap">
    <el-card class="auth-card" shadow="always">
      <el-skeleton :rows="3" animated />
    </el-card>
  </div>
  <div v-else-if="!authUser" class="auth-wrap">
    <el-card class="auth-card" shadow="always">
      <template #header>
        <div class="actions-inline" style="justify-content: space-between; width: 100%">
          <strong>登录系统</strong>
          <span class="badge">Element Plus</span>
        </div>
      </template>
      <el-form label-position="top" class="login-form">
        <el-form-item label="用户名">
          <el-input v-model="authForm.username" placeholder="请输入用户名" clearable />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="authForm.password"
            type="password"
            show-password
            placeholder="请输入密码"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading.save" style="width: 100%" @click="handleLogin">
            {{ loading.save ? "登录中..." : "登录" }}
          </el-button>
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        show-icon
        :closable="false"
        title="默认管理员账号：admin / admin123456（首次启动自动创建）"
      />
    </el-card>
  </div>
  <div v-else class="app-shell">
    <AppHeader
      :loading-save="loading.save"
      :project-name="dashboardData.meta?.project_name || '-'"
      :pass-rate7d="Number(dashboardData.meta?.pass_rate_7d || 0)"
      :projects="projects"
      :selected-project-id="selectedProjectId"
      :auth-user="authUser"
      @open-ai="page = 'ai'"
      @project-change="handleTopProjectChange"
      @change-password="openPasswordEditor"
      @logout="handleLogout"
    />

    <aside class="sidebar">
      <template v-for="group in navGroups" :key="group">
        <div v-if="visibleNavItems.some((n) => n.group === group)" class="menu-title">{{ group }}</div>
        <nav class="nav">
          <a
            v-for="item in visibleNavItems.filter((n) => n.group === group)"
            :key="item.key"
            href="#"
            :class="{ active: page === item.key }"
            @click.prevent="page = item.key"
          >
            <span class="nav-icon-wrap">
              <component :is="navIcon(item.key)" class="nav-icon" />
            </span>
            <span class="nav-label">{{ item.label }}</span>
          </a>
        </nav>
      </template>

      <div class="hint">
        <b>原型风格布局</b><br />
        页面框架和导航已对齐你的原型，当前已接入功能模块：
        接口管理、自动化测试、执行记录、AI 助手。
      </div>
    </aside>

    <main class="main">
      <section class="page-head">
        <div>
          <h1>{{ currentPageTitle }}</h1>
          <p>{{ pageDesc(page) }}</p>
        </div>
        <div class="right-tools">
          <span class="badge">{{ authUser?.username || "-" }}</span>
          <span class="badge">当前项目 {{ projects.find((p) => p.id === selectedProjectId)?.name || "-" }}</span>
          <span class="badge">接口 {{ dashboardData.kpis?.api_count || 0 }}</span>
          <span class="badge">场景 {{ dashboardData.kpis?.scenario_count || 0 }}</span>
          <span class="badge good">通过 {{ passCount }}</span>
          <span class="badge bad">失败 {{ failCount }}</span>
          <span class="badge warn">平均耗时 {{ avgMs }}ms</span>
          <el-button v-if="page === 'assets'" @click="resetForm">新建接口</el-button>
          <el-button v-if="page === 'assets'" @click="openApiImportEditor">导入接口</el-button>
          <el-button v-if="page === 'assets'" :loading="casePreviewLoading" @click="previewCurrentCase">
            {{ casePreviewLoading ? "预检中..." : "执行预检" }}
          </el-button>
          <el-button v-if="page === 'assets'" type="success" :loading="loading.run" @click="runCurrentCase">
            {{ loading.run ? "执行中..." : "快速执行" }}
          </el-button>
        </div>
      </section>

      <div v-if="showCasePreview" class="history-modal-mask" @click.self="closeCasePreview">
        <section class="history-modal card">
          <div class="card-head">
            <div>
              <h3>接口执行预检</h3>
              <div class="sub">展示最终渲染请求、断言计划与未解析占位符，不实际发送请求</div>
            </div>
            <div class="actions-inline">
              <el-button class="btn" @click="closeCasePreview">关闭</el-button>
            </div>
          </div>
          <div class="history-detail-grid">
            <section class="detail-block full">
              <h4>请求地址</h4>
              <pre class="mono detail-pre">{{ JSON.stringify({ method: casePreviewData?.request?.method || 'GET', url: casePreviewData?.request?.url || '-' }, null, 2) }}</pre>
            </section>
            <section v-if="hasPreviewContent(casePreviewData?.request?.headers)" class="detail-block">
              <h4>请求头</h4>
              <pre class="mono detail-pre">{{ JSON.stringify(casePreviewData?.request?.headers || {}, null, 2) }}</pre>
            </section>
            <section v-if="hasPreviewContent(casePreviewData?.request?.params)" class="detail-block">
              <h4>Query 参数</h4>
              <pre class="mono detail-pre">{{ JSON.stringify(casePreviewData?.request?.params || {}, null, 2) }}</pre>
            </section>
            <section v-if="hasPreviewContent(casePreviewData?.request?.body_json)" class="detail-block">
              <h4>JSON 请求体</h4>
              <pre class="mono detail-pre">{{ JSON.stringify(casePreviewData?.request?.body_json || {}, null, 2) }}</pre>
            </section>
            <section v-if="hasPreviewContent(casePreviewData?.request?.body_text)" class="detail-block">
              <h4>文本请求体</h4>
              <pre class="mono detail-pre">{{ JSON.stringify(casePreviewData?.request?.body_text || "", null, 2) }}</pre>
            </section>
            <section v-if="hasPreviewContent(casePreviewData?.assertions)" class="detail-block">
              <h4>断言计划</h4>
              <pre class="mono detail-pre">{{ JSON.stringify(casePreviewData?.assertions || [], null, 2) }}</pre>
            </section>
            <section v-if="hasPreviewContent(casePreviewData?.unresolved_placeholders)" class="detail-block">
              <h4>未解析占位符</h4>
              <pre class="mono detail-pre">{{ JSON.stringify(casePreviewData?.unresolved_placeholders || [], null, 2) }}</pre>
            </section>
          </div>
        </section>
      </div>

      <div v-if="showPasswordEditor" class="history-modal-mask" @click.self="closePasswordEditor">
        <section class="history-modal project-modal card">
          <div class="card-head">
            <h3>修改密码</h3>
            <div class="actions-inline">
              <el-button @click="closePasswordEditor">关闭</el-button>
            </div>
          </div>
          <div class="form-grid">
            <label class="full">
              <span>当前密码</span>
              <el-input v-model="passwordForm.current_password" type="password" show-password placeholder="请输入当前密码" />
            </label>
            <label class="full">
              <span>新密码</span>
              <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="请输入新密码（至少6位）" />
            </label>
            <label class="full">
              <span>确认新密码</span>
              <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
            </label>
            <label class="full">
              <el-button type="primary" :loading="passwordSaving" @click="savePassword">
                {{ passwordSaving ? "提交中..." : "确认修改" }}
              </el-button>
            </label>
          </div>
        </section>
      </div>

      <div v-if="showMonitorEditor" class="history-modal-mask" @click.self="closeMonitorEditor">
        <section class="history-modal project-modal card">
          <div class="card-head">
            <h3>{{ monitorForm.id ? "编辑监控平台" : "新增监控平台" }}</h3>
            <div class="actions-inline">
              <el-button @click="closeMonitorEditor">关闭</el-button>
            </div>
          </div>
          <div class="form-grid">
            <label class="full">
              <span>平台名称</span>
              <el-input v-model="monitorForm.name" placeholder="如：生产监控平台" />
            </label>
            <label class="full">
              <span>平台类型</span>
              <el-radio-group v-model="monitorForm.platform_type">
                <el-radio label="single">单机</el-radio>
                <el-radio label="host_cluster">主机集群</el-radio>
              </el-radio-group>
            </label>
            <label>
              <span>服务器地址</span>
              <el-input v-model="monitorForm.host" placeholder="如：192.168.1.10" />
            </label>
            <label>
              <span>SSH 端口</span>
              <el-input-number v-model="monitorForm.ssh_port" :min="1" :max="65535" style="width: 100%" />
            </label>
            <label>
              <span>用户名</span>
              <el-input v-model="monitorForm.ssh_username" placeholder="root" />
            </label>
            <label>
              <span>密码</span>
              <el-input v-model="monitorForm.ssh_password" type="password" show-password placeholder="留空则不修改" />
            </label>
            <label class="full">
              <span>部署方式</span>
              <el-radio-group v-model="monitorForm.deploy_mode">
                <el-radio label="online">联网部署</el-radio>
                <el-radio label="offline">离线包部署（需先上传离线包）</el-radio>
              </el-radio-group>
            </label>
            <label class="full">
              <span>Docker 环境检测</span>
              <div class="card" style="width:100%;">
                <div class="card-body" style="padding:12px;">
                  <div class="actions-inline" style="justify-content:space-between; gap:12px; flex-wrap:wrap;">
                    <el-button :loading="monitorRuntimeChecking" @click="checkMonitorPlatformRuntime">
                      {{ monitorRuntimeChecking ? "检测中..." : "检测 Docker 环境" }}
                    </el-button>
                    <span class="sub">{{ monitorRuntimeCheck?.detail || "保存前可先检测目标机是否已安装 Docker / Compose。" }}</span>
                  </div>
                  <div v-if="monitorRuntimeCheck" class="actions-inline" style="margin-top:10px; gap:8px; flex-wrap:wrap;">
                    <span :class="['tag', monitorRuntimeCheck.ssh_connected ? 'pass' : 'bad']">SSH {{ monitorRuntimeCheck.ssh_connected ? '已连接' : '失败' }}</span>
                    <span :class="['tag', monitorRuntimeCheck.docker_installed ? 'pass' : 'warn']">Docker {{ monitorRuntimeCheck.docker_installed ? '已安装' : '未安装' }}</span>
                    <span :class="['tag', monitorRuntimeCheck.docker_compose_installed ? 'pass' : 'warn']">Compose {{ monitorRuntimeCheck.docker_compose_installed ? '已安装' : '未安装' }}</span>
                    <span :class="['tag', monitorRuntimeCheck.docker_accessible ? 'pass' : 'warn']">引擎 {{ monitorRuntimeCheck.docker_accessible ? '可访问' : '不可访问' }}</span>
                  </div>
                  <div v-if="monitorRuntimeCheck" class="sub" style="margin-top:8px; display:grid; gap:4px;">
                    <div v-if="monitorRuntimeCheck.docker_version">Docker：{{ monitorRuntimeCheck.docker_version }}</div>
                    <div v-if="monitorRuntimeCheck.docker_compose_version">Compose：{{ monitorRuntimeCheck.docker_compose_version }}</div>
                    <div v-if="monitorRuntimeCheck.docker_service_status">服务状态：{{ monitorRuntimeCheck.docker_service_status }}</div>
                    <div v-if="monitorRuntimeCheck.error">错误详情：{{ monitorRuntimeCheck.error }}</div>
                  </div>
                </div>
              </div>
            </label>
            <label class="full">
              <span>监控目标主机</span>
              <el-input
                v-model="monitorForm.target_hosts_text"
                type="textarea"
                :rows="5"
                placeholder="每行一个主机，支持 host 或 host:node_exporter端口:cadvisor端口，例如：&#10;192.168.200.195&#10;192.168.200.196:9100:8080"
                :disabled="monitorForm.platform_type !== 'host_cluster'"
              />
            </label>
            <label class="full">
              <el-button type="primary" :loading="loading.save" @click="saveMonitorPlatform">
                {{ loading.save ? "保存中..." : "保存并部署" }}
              </el-button>
            </label>
          </div>
        </section>
      </div>

      <div v-if="showMonitorLogs" class="history-modal-mask" @click.self="showMonitorLogs = false">
        <section class="history-modal project-modal card">
          <div class="card-head">
            <h3>部署日志</h3>
            <div class="actions-inline">
              <el-button @click="showMonitorLogs = false">关闭</el-button>
            </div>
          </div>
          <div class="card-body">
            <pre class="mono detail-pre" style="max-height: 480px; overflow: auto;">{{ JSON.stringify(monitorLogs, null, 2) }}</pre>
          </div>
        </section>
      </div>

      <div v-if="showApiImportEditor" class="history-modal-mask" @click.self="closeApiImportEditor">
        <section class="history-modal card import-modal">
          <div class="card-head">
            <h3>导入接口文档</h3>
            <div class="actions-inline">
              <el-button @click="resetApiImportForm">重置</el-button>
              <el-button @click="closeApiImportEditor">关闭</el-button>
            </div>
          </div>
          <div class="card-body import-grid">
            <label class="full">
              <span>文档 URL（可选）</span>
              <el-input v-model="apiImportForm.schemaUrl" placeholder="https://example.com/openapi.json" />
            </label>
            <label class="full">
              <span>OpenAPI 文本（可选，JSON/YAML）</span>
              <el-input v-model="apiImportForm.schemaText" type="textarea" :rows="6" placeholder='{"openapi":"3.0.0","paths":{...}}' />
              <div class="actions-inline" style="margin-top: 8px">
                <el-button size="small" @click="triggerApiImportFileSelect">上传本地文件</el-button>
                <span v-if="apiImportFileName" class="sub">已选择：{{ apiImportFileName }}</span>
                <el-input
                  ref="apiImportFileInputRef"
                  type="file"
                  accept=".json,.yaml,.yml,application/json,text/yaml,application/x-yaml"
                  style="display: none"
                  @change="onApiImportFileChange" />
              </div>
            </label>
            <label class="full">
              <span>补充要求（可选）</span>
              <el-input v-model="apiImportForm.extraRequirements" placeholder="例如：优先包含鉴权失败和边界值场景" />
            </label>
            <label>
              <span>默认所属模块</span>
              <el-select v-model="apiImportForm.moduleId" placeholder="不指定" clearable>
                <el-option label="不指定" :value="null" />
                <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
            </label>
            <label>
              <span>默认关联环境</span>
              <el-select v-model="apiImportForm.environmentId" placeholder="不指定" clearable>
                <el-option label="不指定" :value="null" />
                <el-option v-for="env in activeEnvironmentItems" :key="env.id" :label="env.name" :value="env.id" />
              </el-select>
            </label>
            <label>
              <span>去重策略</span>
              <el-select v-model="apiImportForm.dedupeStrategy">
                <el-option label="跳过重复（Method + Path）" value="skip" />
                <el-option label="覆盖更新（Method + Path）" value="overwrite" />
                <el-option label="保留并重命名" value="rename" />
              </el-select>
            </label>
            <label class="full">
              <div class="actions-inline">
                <el-button type="primary" :loading="importLoading.parse" @click="parseOpenapiForImport">
                  {{ importLoading.parse ? "解析中..." : "解析并预览" }}
                </el-button>
                <span class="sub" v-if="apiImportSummary">
                  {{ apiImportSummary.title || "未命名文档" }} / 接口数 {{ apiImportSummary.operation_count ?? 0 }}
                </span>
              </div>
              <div v-if="importLoading.parse || parseProgress >= 100" style="margin-top:8px;">
                <el-progress :percentage="parseProgress" :status="parseProgressText === '解析失败' ? 'exception' : undefined" />
                <div class="sub">{{ parseProgressText }}</div>
              </div>
            </label>
          </div>

          <div class="split-line"></div>
          <div class="card-head">
            <h3>预览结果（{{ apiImportPreview.length }}）</h3>
            <div class="actions-inline">
              <el-button size="small" @click="toggleAllImportCases(true)">全选</el-button>
              <el-button size="small" @click="toggleAllImportCases(false)">清空</el-button>
              <span class="badge">已选 {{ selectedImportCount }}</span>
              <el-button type="primary" :loading="importLoading.save" :disabled="!selectedImportCount" @click="confirmImportCases">
                {{ importLoading.save ? "保存中..." : "确认保存" }}
              </el-button>
            </div>
          </div>
          <div class="card-body import-preview-wrap">
            <table>
              <thead>
                <tr>
                  <th style="width: 70px">选择</th>
                  <th style="width: 90px">Method</th>
                  <th style="width: 280px">名称</th>
                  <th>Path</th>
                  <th style="width: 220px">去重状态</th>
                  <th>描述</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in apiImportPreview" :key="item.__tmp_id">
                  <td><el-checkbox v-model="item.enabled" /></td>
                  <td><span class="tag pass">{{ item.method || "GET" }}</span></td>
                  <td>{{ item.name || "-" }}</td>
                  <td class="break-word">{{ item.path || "/" }}</td>
                  <td>
                    <span v-if="item.__duplicate_existing" class="badge warn">
                      已存在 #{{ item.__duplicate_case_id }} {{ item.__duplicate_case_name || "" }}
                    </span>
                    <span v-else-if="item.__duplicate_in_preview" class="badge bad">导入列表内重复</span>
                    <span v-else class="badge good">新增</span>
                  </td>
                  <td class="break-word">{{ item.description || "-" }}</td>
                </tr>
                <tr v-if="!apiImportPreview.length">
                  <td colspan="6" class="empty-row">请先解析接口文档生成预览</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section v-show="page === 'dashboard'" class="page">
        <div class="grid cols-4">
          <div class="card"><div class="card-body"><div class="kpi"><div class="s">今日执行次数</div><div class="v">{{ dashboardData.kpis?.today_run_count || 0 }}</div><div class="s">来自后端接口</div></div></div></div>
          <div class="card"><div class="card-body"><div class="kpi"><div class="s">平均耗时</div><div class="v">{{ dashboardData.kpis?.avg_latency_ms || 0 }}ms</div><div class="s">接口 + 场景</div></div></div></div>
          <div class="card"><div class="card-body"><div class="kpi"><div class="s">失败 Top 服务</div><div class="v">{{ (dashboardData.fail_top_services || []).length }}</div><div class="s">来自后端接口</div></div></div></div>
          <div class="card"><div class="card-body"><div class="kpi"><div class="s">待评审 AI 生成</div><div class="v">{{ dashboardData.ai_pending_review?.count || 0 }}</div><div class="s">来自后端接口</div></div></div></div>
        </div>
        <div style="height:14px"></div>
        <div class="grid cols-2">
          <div class="card">
            <div class="card-head">
              <h3>执行趋势（最近7天）</h3>
            </div>
            <div class="card-body">
              <div v-if="trendChart.rows.length" class="trend-chart-wrap">
                <svg class="trend-chart" :viewBox="`0 0 ${trendChart.width} ${trendChart.height}`" preserveAspectRatio="none">
                  <g class="trend-grid">
                    <line
                      v-for="tick in trendChart.yTicks"
                      :key="`y-${tick.y}`"
                      :x1="trendChart.plotLeft"
                      :x2="trendChart.plotRight"
                      :y1="tick.y"
                      :y2="tick.y"
                    />
                  </g>
                  <g class="trend-axis-y">
                    <text v-for="tick in trendChart.yTicks" :key="`yl-${tick.y}`" x="6" :y="tick.y + 4">{{ tick.label }}</text>
                  </g>
                  <g class="trend-axis-x">
                    <text
                      v-for="item in trendChart.labels"
                      :key="`x-${item.x}`"
                      :x="item.x"
                      :y="trendChart.height - 8"
                      text-anchor="middle"
                    >
                      {{ item.label }}
                    </text>
                  </g>
                  <g v-for="line in trendChart.series" :key="line.key">
                    <polyline class="trend-line" :style="{ stroke: line.color }" :points="line.points" />
                    <circle
                      v-for="node in line.nodes"
                      :key="`${line.key}-${node.x}`"
                      class="trend-node"
                      :style="{ fill: line.color }"
                      :cx="node.x"
                      :cy="node.y"
                      r="3"
                    />
                  </g>
                </svg>
                <div class="trend-legend">
                  <div v-for="line in trendChart.series" :key="`legend-${line.key}`" class="trend-legend-item">
                    <span class="trend-dot" :style="{ backgroundColor: line.color }"></span>
                    <span>{{ line.label }}</span>
                    <span class="muted">最新 {{ line.nodes.at(-1)?.value ?? 0 }}{{ line.unit }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="empty-row">暂无趋势数据</div>
            </div>
          </div>
          <div class="card">
            <div class="card-head"><h3>最近执行</h3><span class="badge">后端接口</span></div>
            <div class="card-body">
              <table>
                <thead>
                  <tr>
                    <th>类型</th>
                    <th>名称</th>
                    <th>结果</th>
                    <th>耗时</th>
                    <th>时间</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="r in dashboardData.recent_runs || []" :key="`${r.kind}-${r.id}`">
                    <td>{{ r.kind }}</td>
                    <td>{{ r.name }}</td>
                    <td><span :class="r.success ? 'tag pass' : 'tag fail'">{{ r.success ? "通过" : "失败" }}</span></td>
                    <td>{{ r.duration_ms ?? "-" }}ms</td>
                    <td>{{ (r.created_at || "").replace("T", " ").slice(0, 19) }}</td>
                  </tr>
                  <tr v-if="!(dashboardData.recent_runs || []).length">
                    <td colspan="5" class="empty-row">暂无执行记录</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div style="height:14px"></div>
        <div class="grid cols-3">
          <div class="card">
            <div class="card-head"><h3>失败 Top 服务</h3><span class="badge bad">TOP</span></div>
            <div class="card-body">
              <div v-if="(dashboardData.fail_top_services || []).length" class="stack">
                <div v-for="s in dashboardData.fail_top_services" :key="s.service" class="rowline">
                  <div class="grow">{{ s.service }}</div>
                  <span class="badge bad">{{ s.fail_count }}</span>
                </div>
              </div>
              <div v-else class="empty-row">暂无失败服务</div>
            </div>
          </div>
          <div class="card">
            <div class="card-head"><h3>失败 Top 接口</h3><span class="badge bad">TOP</span></div>
            <div class="card-body">
              <div v-if="(dashboardData.fail_top_apis || []).length" class="stack">
                <div v-for="f in dashboardData.fail_top_apis" :key="f.test_case_id" class="rowline">
                  <span class="mono">#{{ f.test_case_id }}</span>
                  <div class="grow">
                    <div>{{ f.name }}</div>
                    <div class="muted small">失败次数</div>
                  </div>
                  <span class="badge bad">{{ f.fail_count }}</span>
                </div>
              </div>
              <div v-else class="empty-row">暂无失败接口</div>
            </div>
          </div>
          <div class="card">
            <div class="card-head"><h3>耗时 Top 接口</h3><span class="badge warn">TOP</span></div>
            <div class="card-body">
              <div v-if="(dashboardData.latency_top_apis || []).length" class="stack">
                <div v-for="s in dashboardData.latency_top_apis" :key="s.test_case_id" class="rowline">
                  <span class="mono">#{{ s.test_case_id }}</span>
                  <div class="grow">
                    <div>{{ s.name }}</div>
                    <div class="muted small">样本 {{ s.sample_count }} / 最大 {{ s.max_latency_ms }}ms</div>
                  </div>
                  <span class="badge warn">{{ s.avg_latency_ms }}ms</span>
                </div>
              </div>
              <div v-else class="empty-row">暂无耗时数据</div>
            </div>
          </div>
        </div>
        <div style="height:14px"></div>
        <div class="grid cols-2">
          <div class="card">
            <div class="card-head"><h3>待评审 AI 生成</h3><span class="badge">后端接口</span></div>
            <div class="card-body">
              <div class="mono">{{ dashboardData.ai_pending_review?.message || "暂无后端消息" }}</div>
              <div style="height:12px"></div>
              <div v-if="(dashboardData.ai_pending_review?.items || []).length" class="stack">
                <div v-for="(item, idx) in dashboardData.ai_pending_review.items" :key="idx" class="rowline">
                  <div class="grow">{{ item.name || "-" }}</div>
                  <span class="badge">{{ item.status || "-" }}</span>
                </div>
              </div>
              <div v-else class="empty-row">暂无待评审 AI 草稿</div>
            </div>
          </div>
          <div class="card">
            <div class="card-head"><h3>最近失败记录</h3><span class="badge bad">后端接口</span></div>
            <div class="card-body">
              <div v-if="(dashboardData.latest_failures || []).length" class="stack">
                <div v-for="f in dashboardData.latest_failures" :key="`${f.kind}-${f.id}`" class="rowline">
                  <span class="tag fail">{{ f.kind }}</span>
                  <div class="grow">
                    <div>{{ f.name }}</div>
                    <div class="muted small">{{ f.error_message || "-" }}</div>
                  </div>
                  <span class="mono">{{ (f.created_at || '').replace('T', ' ').slice(0, 19) }}</span>
                </div>
              </div>
              <div v-else class="empty-row">暂无失败记录</div>
            </div>
          </div>
        </div>
      </section>

      <section v-show="page === 'projects'" class="page">
        <div class="grid cols-2">
          <el-card shadow="never">
            <template #header>
              <div class="card-head">
              <h3>项目列表</h3>
              <div class="actions-inline">
                <el-button type="primary" @click="openProjectCreate">新增项目</el-button>
              </div>
            </div>
            </template>
            <el-table :data="projects" stripe style="width: 100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column label="项目名称" min-width="180">
                <template #default="{ row }">
                  <span>{{ row.name }}</span>
                  <el-tag v-if="row.id === selectedProjectId" size="small" type="success" style="margin-left: 8px">当前</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="描述" min-width="180">
                <template #default="{ row }">{{ row.description || "-" }}</template>
              </el-table-column>
              <el-table-column label="操作" width="220">
                <template #default="{ row }">
                  <div class="actions-inline">
                    <el-button size="small" @click="switchProject(row.id)">切换</el-button>
                    <el-button size="small" @click="editProject(row)">编辑</el-button>
                    <el-button size="small" type="danger" plain @click="removeProject(row.id)">删除</el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>

        <div style="height:14px"></div>
        <div class="grid cols-2">
          <el-card shadow="never">
            <template #header>
              <div class="card-head">
              <h3>项目环境</h3>
              <div class="actions-inline">
                <el-button type="primary" @click="openEnvironmentCreate">新增环境</el-button>
              </div>
            </div>
            </template>
            <el-table
              :data="environmentData.items || []"
              stripe
              highlight-current-row
              :row-class-name="({ row }) => Number(selectedEnvironmentId) === Number(row.id) ? 'row-selected' : ''"
              @row-click="(row) => { selectedEnvironmentId = row.id; }"
              style="width: 100%"
            >
              <el-table-column prop="name" label="环境名称" min-width="140" />
              <el-table-column prop="base_url" label="地址" min-width="180">
                <template #default="{ row }">{{ row.base_url || "-" }}</template>
              </el-table-column>
              <el-table-column label="变量数" width="90">
                <template #default="{ row }">{{ row.variables_count ?? Object.keys(row.variables || {}).length }}</template>
              </el-table-column>
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">{{ row.is_active ? "启用" : "停用" }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="170">
                <template #default="{ row }">
                  <div class="actions-inline">
                    <el-button size="small" @click.stop="editEnvironment(row)">编辑</el-button>
                    <el-button size="small" type="danger" plain @click.stop="removeEnvironment(row.id)">删除</el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
          <el-card shadow="never">
            <template #header>
              <div class="card-head">
              <h3>环境详情</h3>
              <span class="badge">{{ selectedEnvironment ? "已选中" : "未选择" }}</span>
            </div>
            </template>
            <div v-if="selectedEnvironment" class="card-body">
              <div class="stack">
                <div class="rowline">
                  <div class="grow">环境名称</div>
                  <span class="badge">{{ selectedEnvironment.name || "-" }}</span>
                </div>
                <div class="rowline">
                  <div class="grow">环境地址</div>
                  <span class="mono">{{ selectedEnvironment.base_url || "-" }}</span>
                </div>
                <div class="rowline">
                  <div class="grow">启用状态</div>
                  <span :class="selectedEnvironment.is_active ? 'badge good' : 'badge bad'">
                    {{ selectedEnvironment.is_active ? "启用" : "停用" }}
                  </span>
                </div>
                <div class="rowline">
                  <div class="grow">变量数量</div>
                  <span class="badge">{{ selectedEnvironmentVariableRows.length }}</span>
                </div>
                <div class="rowline">
                  <div class="grow">默认Header数量</div>
                  <span class="badge">{{ selectedEnvironmentHeaderRows.length }}</span>
                </div>
              </div>
              <div style="height: 10px"></div>
              <table>
                <thead>
                  <tr>
                    <th style="width: 180px">变量名</th>
                    <th style="width: 120px">值类型</th>
                    <th>变量值</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in selectedEnvironmentVariableRows" :key="item.key">
                    <td>{{ item.key }}</td>
                    <td>{{ item.valueType }}</td>
                    <td class="break-word">{{ item.value || "-" }}</td>
                  </tr>
                  <tr v-if="!selectedEnvironmentVariableRows.length">
                    <td colspan="3" class="empty-row">当前环境暂无变量</td>
                  </tr>
                </tbody>
              </table>
              <div style="height: 10px"></div>
              <table>
                <thead>
                  <tr>
                    <th style="width: 180px">Header键</th>
                    <th>Header值</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in selectedEnvironmentHeaderRows" :key="item.key">
                    <td>{{ item.key }}</td>
                    <td class="break-word">{{ item.value || "-" }}</td>
                  </tr>
                  <tr v-if="!selectedEnvironmentHeaderRows.length">
                    <td colspan="2" class="empty-row">当前环境未配置默认Header</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="card-body empty-row">当前项目暂无环境详情</div>
          </el-card>
        </div>

        <el-dialog v-model="showProjectEditor" :title="projectForm.id ? '编辑项目' : '新建项目'" width="560px" destroy-on-close>
          <el-form label-position="top">
            <el-form-item label="项目名称 *">
              <el-input v-model="projectForm.name" placeholder="例如：电商平台" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="projectForm.description" placeholder="项目描述（可选）" />
            </el-form-item>
          </el-form>
          <template #footer>
            <div class="actions-inline" style="justify-content: flex-end; width: 100%">
              <el-button @click="resetProjectForm">重置</el-button>
              <el-button @click="showProjectEditor = false">关闭</el-button>
              <el-button type="primary" @click="saveProject">{{ projectForm.id ? "保存项目" : "创建项目" }}</el-button>
            </div>
          </template>
        </el-dialog>

        <el-dialog
          v-model="showEnvironmentEditor"
          :title="environmentForm.id ? '编辑环境' : '新建环境'"
          width="860px"
          class="env-editor-dialog"
          append-to-body
          align-center
          destroy-on-close
        >
            <div class="actions-inline" style="justify-content: flex-end; margin-bottom: 8px;">
              <el-button @click="resetEnvironmentForm">重置</el-button>
              <el-button @click="showEnvironmentEditor = false">关闭</el-button>
            </div>
            <div class="form-grid env-form-grid">
              <label>
                <span>所属项目 *</span>
                <el-select v-model="environmentForm.project_id" placeholder="请选择项目" :disabled="!!environmentForm.id">
                  <el-option label="请选择项目" :value="null" />
                  <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
                </el-select>
                <small class="sub" v-if="environmentForm.id">编辑时不支持修改所属项目</small>
              </label>
              <label>
                <span>环境名称</span>
                <el-input v-model="environmentForm.name" placeholder="例如：测试环境A" />
              </label>
              <label>
                <span>启用状态</span>
                <div class="switch-inline">
                  <el-switch v-model="environmentForm.is_active" />
                  <span class="sub">{{ environmentForm.is_active ? "启用" : "停用" }}</span>
                </div>
              </label>
              <label class="full">
                <span>环境地址 *</span>
                <el-input v-model="environmentForm.base_url" placeholder="https://api-test.example.com" />
              </label>
              <label class="full">
                <span>环境描述</span>
                <el-input v-model="environmentForm.description" placeholder="可选" />
              </label>
              <label class="full">
                <div class="field-head">
                  <span>环境变量</span>
                  <div class="actions-inline">
                    <el-button native-type="button"
                      class="btn mini"
                      :class="{ primary: environmentVariablesMode === 'table' }"
                      @click="switchEnvironmentVariablesMode('table')"
                    >
                      键值对
                    </el-button>
                    <el-button native-type="button"
                      class="btn mini"
                      :class="{ primary: environmentVariablesMode === 'json' }"
                      @click="switchEnvironmentVariablesMode('json')"
                    >
                      JSON
                    </el-button>
                  </div>
                </div>
                <div v-if="environmentVariablesMode === 'table'" class="kv-table-wrap">
                  <table class="kv-table">
                    <thead>
                      <tr>
                        <th>启用</th>
                        <th>变量名</th>
                        <th style="width: 160px">值类型</th>
                        <th>变量值（可选）</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, idx) in environmentVariableRows" :key="`env-var-${idx}`">
                        <td>
                          <el-switch v-model="row.enabled" @change="syncEnvironmentVariablesTextFromRows" />
                        </td>
                        <td><el-input v-model="row.key" placeholder="变量名" @input="syncEnvironmentVariablesTextFromRows" /></td>
                        <td class="env-value-mode-cell">
                          <el-select v-model="row.value_mode" @change="syncEnvironmentVariablesTextFromRows">
                            <el-option label="自定义（可选）" value="custom" />
                            <el-option label="内置参数" value="builtin" />
                          </el-select>
                        </td>
                        <td>
                          <el-input
                            v-if="row.value_mode === 'custom'"
                            v-model="row.value"
                            placeholder="变量值（可留空）"
                            @input="syncEnvironmentVariablesTextFromRows" />
                          <el-select v-else v-model="row.builtin_key" @change="syncEnvironmentVariablesTextFromRows">
                            <el-option v-for="opt in builtinVariableOptions" :key="opt.key" :label="opt.label" :value="opt.key" />
                          </el-select>
                        </td>
                        <td><el-button native-type="button" class="btn mini danger" @click="removeEnvironmentVariableRow(idx)">删除</el-button></td>
                      </tr>
                    </tbody>
                  </table>
                  <el-button native-type="button" class="btn mini" @click="addEnvironmentVariableRow">新增变量</el-button>
                </div>
                <JsonEditorField
                  v-else
                  v-model="environmentForm.variables_text"
                  height="260px"
                />
              </label>
              <label class="full">
                <div class="field-head">
                  <span>默认 Header（键值对）</span>
                  <div class="actions-inline">
                    <el-button native-type="button"
                      class="btn mini"
                      :class="{ primary: environmentHeadersMode === 'table' }"
                      @click="switchEnvironmentHeadersMode('table')"
                    >
                      键值对
                    </el-button>
                    <el-button native-type="button"
                      class="btn mini"
                      :class="{ primary: environmentHeadersMode === 'json' }"
                      @click="switchEnvironmentHeadersMode('json')"
                    >
                      JSON
                    </el-button>
                  </div>
                </div>
                <div v-if="environmentHeadersMode === 'table'" class="kv-table-wrap">
                  <table class="kv-table">
                    <thead>
                      <tr>
                        <th>启用</th>
                        <th>Header键</th>
                        <th>Header值</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, idx) in environmentHeaderRows" :key="`env-header-${idx}`">
                        <td>
                          <el-switch v-model="row.enabled" @change="syncEnvironmentHeadersTextFromRows" />
                        </td>
                        <td><el-input v-model="row.key" placeholder="如 Authorization" @input="syncEnvironmentHeadersTextFromRows" /></td>
                        <td><el-input v-model="row.value" placeholder="如 Bearer xxx" @input="syncEnvironmentHeadersTextFromRows" /></td>
                        <td><el-button native-type="button" class="btn mini danger" @click="removeEnvironmentHeaderRow(idx)">删除</el-button></td>
                      </tr>
                    </tbody>
                  </table>
                  <el-button native-type="button" class="btn mini" @click="addEnvironmentHeaderRow">新增Header</el-button>
                </div>
                <JsonEditorField
                  v-else
                  v-model="environmentForm.default_headers_text"
                  height="240px"
                />
              </label>
              <label class="full">
                <el-button type="primary" @click="saveEnvironment">{{ environmentForm.id ? "保存环境" : "创建环境" }}</el-button>
              </label>
            </div>
        </el-dialog>

      </section>
      <section v-show="page === 'assets'" class="page split">
        <div v-if="!selectedProjectId" class="card">
          <div class="card-body">请先到“项目管理”创建并切换项目后，再管理接口。</div>
        </div>
        <template v-else>
        <CaseListPanel
          :items="cases"
          :modules="modules"
          :selected-id="selectedCaseId"
          :loading="loading.cases"
          @refresh="loadCases"
          @select="selectCase"
          @delete="removeCase"
          @create-module="createModule"
          @create-in-module="createCaseInModule"
          @edit-module="editModule"
          @delete-module="removeModule"
          @select-module="onAssetModuleSelect"
        />
        <div class="single-col">
          <div v-if="selectedAssetModuleId" class="card">
            <div class="card-head">
              <div>
                <h3>模块接口列表</h3>
                <div class="sub">
                  当前模块：{{ Number(selectedAssetModuleId) === -1 ? "未分组" : (moduleNameMap.get(Number(selectedAssetModuleId)) || `#${selectedAssetModuleId}`) }}（含下级）
                </div>
              </div>
              <div class="actions-inline">
                <el-input
                  v-model="assetCaseKeyword"
                  clearable
                  placeholder="搜索名称 / Path / 方法"
                  style="width: 220px"
                />
                <el-select v-model="assetCaseOrdering" style="width: 160px">
                  <el-option label="最近更新" value="-updated_at" />
                  <el-option label="最早更新" value="updated_at" />
                  <el-option label="名称 A-Z" value="name" />
                  <el-option label="名称 Z-A" value="-name" />
                  <el-option label="Path A-Z" value="path" />
                  <el-option label="Path Z-A" value="-path" />
                  <el-option label="方法 A-Z" value="method" />
                  <el-option label="模块 A-Z" value="module_name" />
                </el-select>
                <span class="badge">{{ filteredSelectedAssetModuleCases.length }} / {{ selectedAssetModuleCases.length }}</span>
                <el-button size="small" :disabled="!selectedModuleCaseCount" @click="removeModuleCases(selectedModuleCaseIds, false)">
                  批量删除
                </el-button>
                <el-button size="small" type="danger" :disabled="!filteredSelectedAssetModuleCases.length" @click="removeModuleCases(allModuleCaseIds, true)">
                  全部删除
                </el-button>
              </div>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style="width: 56px">
                      <el-checkbox
                        :model-value="moduleCaseAllChecked"
                        :indeterminate="moduleCaseIndeterminate"
                        @change="toggleSelectAllModuleCases"
                      />
                    </th>
                    <th>接口名称</th>
                    <th>所属模块</th>
                    <th>方法</th>
                    <th>Path</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in pagedSelectedAssetModuleCases" :key="`module-case-${row.id}`">
                    <td>
                      <el-checkbox
                        :model-value="selectedModuleCaseIds.includes(Number(row.id))"
                        @change="(val) => toggleSelectModuleCase(row.id, val)"
                      />
                    </td>
                    <td>{{ row.name }}</td>
                    <td>{{ moduleNameMap.get(Number(row.module_id || row.module || 0)) || "未分组" }}</td>
                    <td>{{ row.method }}</td>
                    <td>{{ row.path }}</td>
                    <td>
                      <el-button class="icon-btn" title="编辑接口" aria-label="编辑接口" @click="selectCase(row)">
                        <Edit class="ep-icon" />
                      </el-button>
                    </td>
                  </tr>
                  <tr v-if="!filteredSelectedAssetModuleCases.length">
                    <td colspan="6" class="empty-row">当前模块及下级暂无接口</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="filteredSelectedAssetModuleCases.length" class="actions-inline" style="justify-content:flex-end; padding: 10px 4px 0;">
              <el-pagination
                v-model:current-page="moduleCasePage"
                v-model:page-size="moduleCasePageSize"
                :total="filteredSelectedAssetModuleCases.length"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next"
                small
              />
            </div>
          </div>
          <TestCaseFormPanel
            :form="form"
            :selected-case="selectedCase"
            :saving="loading.save"
            :environments="activeEnvironmentItems"
            :modules="modules"
            @save="saveCase"
          />
        </div>
        </template>
      </section>

      <section v-show="page === 'testcases'" class="page">
        <AutomationPanel
          :cases="cases"
          :modules="modules"
          :environments="activeEnvironmentItems"
          :project-id="selectedProjectId"
          :confirm-box="showConfirm"
          @notify="handleChildNotify"
          @create-module="createModule"
          @edit-module="editModule"
          @delete-module="removeModule"
          @move-module="moveModule"
          @open-report="openScenarioReport"
        />
      </section>

      <section v-show="page === 'scenario_reports'" class="page">
        <ScenarioReportPanel :project-id="selectedProjectId" :modules="modules" :focus="scenarioReportFocus" :confirm-box="showConfirm" @notify="handleChildNotify" />
      </section>

      <section v-show="page === 'runs'" class="page">
        <div class="grid cols-2">
          <HistoryPanel
            :histories="histories"
            :loading="loading.histories"
            :selected-case-id="selectedCaseId"
            :query="historyQuery"
            :total="historyMeta.total"
            @refresh="loadHistories(selectedCaseId)"
            @query-change="handleHistoryQueryChange"
          />
          <div class="card">
            <div class="card-head"><h3>执行汇总</h3><span class="badge">最近 100 条</span></div>
            <div class="card-body">
              <div class="grid cols-2">
                <div class="kpi"><div class="s">通过</div><div class="v">{{ passCount }}</div></div>
                <div class="kpi"><div class="s">失败</div><div class="v">{{ failCount }}</div></div>
                <div class="kpi"><div class="s">平均耗时</div><div class="v">{{ avgMs }}ms</div></div>
                <div class="kpi"><div class="s">当前接口</div><div class="v">{{ selectedCaseId || "-" }}</div></div>
              </div>
              <div style="height:12px"></div>
              <div class="mono">场景级执行历史请在“自动化测试”页面查看。</div>
            </div>
          </div>
        </div>
      </section>

      <section v-show="page === 'resource_monitor'" class="page">
        <div class="card monitor-overview-card">
          <div class="card-head">
            <h3>资源监控总览</h3>
            <div class="actions-inline monitor-overview-tools">
              <el-select
                v-model="selectedMonitorPlatformId"
                class="monitor-platform-select"
                placeholder="选择监控平台"
                clearable
              >
                <el-option
                  v-for="item in monitorPlatforms"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
              <el-select v-model="selectedMonitorTargetHost" class="monitor-host-select" placeholder="全部主机">
                <el-option label="全部主机" value="" />
                <el-option
                  v-for="item in monitorTargetHostOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
              <el-select v-model="monitorTimeRange" class="monitor-range-select" placeholder="时间维度">
                <el-option
                  v-for="item in monitorTimeRangeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
              <el-button @click="loadMonitorMetrics(true)">刷新指标</el-button>
            </div>
          </div>
          <div class="card-body">
            <div class="monitor-meta-bar">
              <div class="monitor-meta-chip">
                <span class="label">数据来源</span>
                <strong>{{ formatMonitorSnapshotSource(monitorSnapshotMeta.source) }}</strong>
              </div>
              <div class="monitor-meta-chip">
                <span class="label">快照时间</span>
                <strong>{{ formatMonitorSnapshotTime(monitorSnapshotMeta.collectedAt) }}</strong>
              </div>
              <div class="monitor-meta-chip">
                <span class="label">快照年龄</span>
                <strong>{{ formatMonitorSnapshotAge(monitorSnapshotMeta.snapshotAgeSeconds) }}</strong>
              </div>
            </div>
            <div v-if="monitorSnapshotMeta.warning" class="monitor-meta-warning">
              {{ monitorSnapshotMeta.warning }}
            </div>
            <div class="monitor-overview-grid">
              <div class="monitor-overview-item kpi"><div class="s">在线主机数</div><div class="v">{{ monitorMetrics.targets_up ?? "-" }}</div></div>
              <div class="monitor-overview-item kpi"><div class="s">离线主机数</div><div class="v">{{ monitorMetrics.targets_down ?? "-" }}</div></div>
              <div class="monitor-overview-item kpi"><div class="s">当前平台</div><div class="v text">{{ monitorPlatforms.find((x) => Number(x.id) === Number(selectedMonitorPlatformId))?.name || "-" }}</div></div>
              <div class="monitor-overview-item kpi"><div class="s">当前主机</div><div class="v text">{{ selectedMonitorTargetHost || "全部主机" }}</div></div>
              <div class="monitor-overview-item kpi"><div class="s">系统负载(1m)</div><div class="v">{{ monitorMetrics.load1 ?? "-" }}</div></div>
              <div class="monitor-overview-item kpi"><div class="s">系统负载(5m)</div><div class="v">{{ monitorMetrics.load5 ?? "-" }}</div></div>
              <div class="monitor-overview-item kpi"><div class="s">运行时长</div><div class="v">{{ monitorMetrics.host_uptime_hours ?? "-" }}<span v-if="monitorMetrics.host_uptime_hours !== null">h</span></div></div>
              <div class="monitor-overview-item kpi"><div class="s">CPU 核心数</div><div class="v">{{ monitorMetrics.cpu_cores ?? "-" }}</div></div>
              <div class="monitor-overview-item kpi"><div class="s">运行容器数</div><div class="v">{{ monitorMetrics.container_running ?? "-" }}</div></div>
            </div>
          </div>
        </div>
        <div style="height:14px"></div>
        <div class="monitor-kpi-grid">
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">CPU 使用率</div><div class="v">{{ monitorMetrics.cpu_usage_percent ?? "-" }}<span v-if="monitorMetrics.cpu_usage_percent !== null">%</span></div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">CPU iowait</div><div class="v">{{ monitorMetrics.cpu_iowait_percent ?? "-" }}<span v-if="monitorMetrics.cpu_iowait_percent !== null">%</span></div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">内存使用率</div><div class="v">{{ monitorMetrics.memory_usage_percent ?? "-" }}<span v-if="monitorMetrics.memory_usage_percent !== null">%</span></div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">可用内存</div><div class="v">{{ monitorMetrics.memory_available_gb ?? "-" }}<span v-if="monitorMetrics.memory_available_gb !== null">GB</span></div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">Swap 使用率</div><div class="v">{{ monitorMetrics.swap_usage_percent ?? "-" }}<span v-if="monitorMetrics.swap_usage_percent !== null">%</span></div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">磁盘使用率</div><div class="v">{{ monitorMetrics.disk_usage_percent ?? "-" }}<span v-if="monitorMetrics.disk_usage_percent !== null">%</span></div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">磁盘剩余</div><div class="v">{{ monitorMetrics.disk_free_gb ?? "-" }}<span v-if="monitorMetrics.disk_free_gb !== null">GB</span></div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">磁盘读速率</div><div class="v">{{ monitorMetrics.disk_read_mbps ?? "-" }}<span v-if="monitorMetrics.disk_read_mbps !== null">Mbps</span></div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">磁盘写速率</div><div class="v">{{ monitorMetrics.disk_write_mbps ?? "-" }}<span v-if="monitorMetrics.disk_write_mbps !== null">Mbps</span></div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">磁盘 await</div><div class="v">{{ monitorMetrics.disk_await_ms ?? "-" }}<span v-if="monitorMetrics.disk_await_ms !== null">ms</span></div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">网络吞吐</div><div class="v">{{ formatTrafficRate(monitorMetrics.network_throughput_mbps) }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">网络入流量</div><div class="v">{{ formatTrafficRate(monitorMetrics.network_rx_mbps) }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">网络出流量</div><div class="v">{{ formatTrafficRate(monitorMetrics.network_tx_mbps) }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">网络丢包速率</div><div class="v">{{ monitorMetrics.network_drop_rate ?? "-" }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">TCP 已建立</div><div class="v">{{ monitorMetrics.tcp_established ?? "-" }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">TCP TIME_WAIT</div><div class="v">{{ monitorMetrics.tcp_time_wait ?? "-" }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">运行进程</div><div class="v">{{ monitorMetrics.process_running ?? "-" }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">阻塞进程</div><div class="v">{{ monitorMetrics.process_blocked ?? "-" }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">容器重启次数</div><div class="v">{{ monitorMetrics.container_restart_count ?? "-" }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">Pod 异常数</div><div class="v">{{ monitorMetrics.pod_abnormal_count ?? "-" }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">DB 活跃连接</div><div class="v">{{ monitorMetrics.db_active_connections ?? "-" }}</div></div></div></div>
          <div class="card monitor-kpi-card"><div class="card-body"><div class="kpi"><div class="s">Redis 命中率</div><div class="v">{{ monitorMetrics.redis_hit_rate ?? "-" }}<span v-if="monitorMetrics.redis_hit_rate !== null">%</span></div></div></div></div>
        </div>
        <div style="height:14px"></div>
        <div class="monitor-chart-grid">
          <div class="card"><div class="card-body"><VChart :option="monitorTrendLineOption" autoresize style="height: 300px" /></div></div>
          <div class="card"><div class="card-body"><VChart :option="monitorNetworkTrendOption" autoresize style="height: 300px" /></div></div>
          <div class="card"><div class="card-body"><VChart :option="monitorServiceBarOption" autoresize style="height: 300px" /></div></div>
          <div class="card"><div class="card-body"><VChart :option="monitorNicTrafficOption" autoresize style="height: 300px" /></div></div>
        </div>
      </section>

      <section v-show="page === 'monitor_config'" class="page">
        <div class="card">
          <div class="card-head">
            <h3>Prometheus 监控平台配置</h3>
            <div class="actions-inline">
              <el-button type="primary" @click="openMonitorCreate">新增平台并自动部署</el-button>
              <el-button @click="loadMonitorPlatforms">刷新</el-button>
            </div>
          </div>
          <div class="card-body">
            <table>
              <thead>
                <tr>
                  <th>平台名称</th>
                  <th>类型</th>
                  <th>地址</th>
                  <th>目标数</th>
                  <th>部署模式</th>
                  <th>状态</th>
                  <th>Prometheus</th>
                  <th>错误信息</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in monitorPlatforms" :key="item.id">
                  <td>{{ item.name }}</td>
                  <td>{{ item.platform_type === "host_cluster" ? "主机集群" : "单机" }}</td>
                  <td>{{ item.host }}:{{ item.ssh_port }}</td>
                  <td>{{ (item.monitor_targets || []).filter((x) => x && x.enabled !== false).length || 1 }}</td>
                  <td>{{ item.deploy_mode === "offline" ? "离线包部署" : "联网部署" }}</td>
                  <td><span :class="monitorStatusClass(item.status)">{{ monitorStatusText(item.status) }}</span></td>
                  <td>
                    <a v-if="item.prometheus_url" :href="item.prometheus_url" target="_blank" rel="noreferrer">{{ item.prometheus_url }}</a>
                    <span v-else>-</span>
                  </td>
                  <td class="break-word">{{ item.last_error || "-" }}</td>
                  <td>
                    <div class="actions-inline">
                      <el-button class="btn mini" @click="openMonitorEdit(item)">编辑</el-button>
                      <el-button class="btn mini run" @click="redeployMonitorPlatform(item)">重新部署</el-button>
                      <el-button class="btn mini" @click="triggerMonitorPackageUpload(item.id)">上传离线包</el-button>
                      <el-button class="btn mini" @click="openMonitorLogs(item)">日志</el-button>
                      <el-button class="btn mini danger" @click="removeMonitorPlatform(item)">删除</el-button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!monitorPlatforms.length">
                  <td colspan="9" class="empty-row">{{ loading.monitor ? "加载中..." : "暂无监控平台，点击上方按钮创建并自动部署" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
      <input
        ref="monitorPackageInputRef"
        type="file"
        accept=".tar.gz,.tgz,.zip"
        style="display:none"
        @change="onMonitorPackageChange"
      />

      <section v-show="page === 'ai'" class="page">
        <AiGeneratorPanel
          :loading="loading.ai"
          :generated-cases="aiGeneratedCases"
          :openapi-summary="aiOpenapiSummary"
          :ai-config="aiConfig"
          @generate="generateCasesByAi"
          @generate-from-openapi="generateCasesFromOpenapi"
          @save-ai-config="saveAiConfigWithValidation"
          @load-to-form="loadAiCaseToForm"
          @batch-create="createAllAiCases"
        />
      </section>

      <section v-show="page === 'rbac'" class="page">
        <div class="grid cols-2">
          <div class="card">
            <div class="card-head">
              <h3>成员与项目授权</h3>
              <div class="actions-inline" v-if="isAdmin">
                <el-button class="btn primary" @click="openCreateUser">新增用户</el-button>
              </div>
            </div>
            <div class="card-body">
              <div class="grid cols-3">
                <div class="kpi"><div class="s">成员数</div><div class="v">{{ rbacData.summary?.member_count || 0 }}</div></div>
                <div class="kpi"><div class="s">项目数</div><div class="v">{{ (rbacData.projects || []).length }}</div></div>
                <div class="kpi"><div class="s">审计条数</div><div class="v">{{ rbacData.summary?.audit_count || 0 }}</div></div>
              </div>
              <div style="height:12px"></div>
              <table>
                <thead>
                  <tr>
                    <th>用户名</th>
                    <th>邮箱</th>
                    <th>可访问项目</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="member in rbacData.members || []" :key="member.id">
                    <td>{{ member.username }}</td>
                    <td>{{ member.email || "-" }}</td>
                    <td>
                      <span class="mono">
                        {{
                          (member.project_ids || [])
                            .map((id) => (rbacData.projects || []).find((p) => Number(p.id) === Number(id))?.name || `#${id}`)
                            .join("、") || "-"
                        }}
                      </span>
                    </td>
                    <td><span :class="member.is_active ? 'tag pass' : 'tag fail'">{{ member.is_active ? "启用" : "禁用" }}</span></td>
                    <td>
                      <div class="actions-inline" v-if="isAdmin">
                        <el-button class="btn mini" @click="openEditUser(member)">编辑</el-button>
                        <el-button class="btn mini" @click="toggleUserActive(member)">{{ member.is_active ? "禁用" : "启用" }}</el-button>
                        <el-button class="btn mini" @click="resetUserPassword(member)">重置密码</el-button>
                        <el-button class="btn mini danger" @click="removeUser(member)">删除</el-button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="!(rbacData.members || []).length">
                    <td colspan="5" class="empty-row">暂无成员</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="card">
            <div class="card-head"><h3>审计日志</h3><span class="badge">后端接口</span></div>
            <div class="card-body">
              <div class="mono">{{ rbacData.summary?.message || "" }}</div>
              <div style="height:12px"></div>
              <table>
                <thead>
                  <tr>
                    <th>动作</th>
                    <th>操作用户</th>
                    <th>目标</th>
                    <th>结果</th>
                    <th>时间</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="log in rbacData.audits || []" :key="log.id">
                    <td>{{ log.action }}</td>
                    <td>{{ log.operator || "-" }}</td>
                    <td>{{ log.target }}</td>
                    <td><span :class="log.result === 'success' ? 'tag pass' : 'tag fail'">{{ log.result }}</span></td>
                    <td>{{ (log.time || "").replace("T", " ").slice(0, 19) }}</td>
                  </tr>
                  <tr v-if="!(rbacData.audits || []).length">
                    <td colspan="5" class="empty-row">暂无审计日志</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      <div v-if="showUserEditor" class="history-modal-mask" @click.self="closeUserEditor">
        <section class="history-modal project-modal card">
          <div class="card-head">
            <h3>{{ userForm.id ? "编辑用户" : "新增用户" }}</h3>
            <div class="actions-inline">
              <el-button class="btn" @click="closeUserEditor">关闭</el-button>
            </div>
          </div>
          <div class="form-grid">
            <label>
              <span>用户名 {{ userForm.id ? "" : "*" }}</span>
              <el-input v-model="userForm.username" :disabled="!!userForm.id" placeholder="请输入用户名" />
            </label>
            <label>
              <span>邮箱</span>
              <el-input v-model="userForm.email" placeholder="请输入邮箱（可选）" />
            </label>
            <label>
              <span>可访问项目</span>
              <el-select v-model="userForm.project_ids" multiple collapse-tags collapse-tags-tooltip clearable>
                <el-option v-for="p in rbacData.projects || []" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </label>
            <label>
              <span>状态</span>
              <el-select v-model="userForm.is_active">
                <el-option :value="true" label="启用" />
                <el-option :value="false" label="禁用" />
              </el-select>
            </label>
            <label class="full">
              <span>密码{{ userForm.id ? "（留空不修改）" : "*" }}</span>
              <el-input v-model="userForm.password" type="password" placeholder="请输入密码" />
            </label>
            <label class="full">
              <el-button class="btn primary" :disabled="userSaving" @click="saveUser">{{ userSaving ? "保存中..." : "保存用户" }}</el-button>
            </label>
          </div>
        </section>
      </div>

      <div v-if="showModuleEditor" class="history-modal-mask" @click.self="closeModuleEditor">
        <section class="history-modal project-modal card">
          <div class="card-head">
            <h3>{{ moduleForm.id ? "编辑模块" : "新建模块" }}</h3>
            <div class="actions-inline">
              <el-button class="btn" @click="closeModuleEditor">关闭</el-button>
            </div>
          </div>
          <div class="form-grid">
            <label class="full">
              <span>模块名称 *</span>
              <el-input v-model="moduleForm.name" placeholder="请输入模块名称" />
            </label>
            <label class="full">
              <span>父模块</span>
              <el-select v-model="moduleForm.parent_id" placeholder="顶级模块" clearable>
                <el-option label="顶级模块" :value="null" />
                <el-option v-for="item in moduleParentOptions" :key="item.id" :label="item.label" :value="item.id" />
              </el-select>
            </label>
            <label class="full">
              <span>描述</span>
              <el-input v-model="moduleForm.description" placeholder="可选" />
            </label>
            <label class="full">
              <el-button class="btn primary" @click="saveModule">{{ moduleForm.id ? "保存模块" : "创建模块" }}</el-button>
            </label>
          </div>
        </section>
      </div>
    </main>
  </div>
  <div v-if="toastList.length" class="toast-stack">
    <div
      v-for="toast in toastList"
      :key="toast.id"
      class="toast-item"
      :class="`t-${toast.type}`"
      @click="removeToast(toast.id)"
    >
      <span class="toast-dot" />
      <span class="toast-text">{{ toast.message }}</span>
    </div>
  </div>
</template>
