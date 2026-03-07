<!-- 作者: lxl -->
<!-- 说明: 前端页面/组件模块。 -->
<script setup>
import { computed, ref, watch } from "vue";
import { api } from "../api";

const props = defineProps({
  projectId: { type: [Number, String, null], default: null },
  modules: { type: Array, default: () => [] },
  focus: { type: Object, default: () => ({}) },
  confirmBox: { type: Function, default: null }
});

const emit = defineEmits(["notify"]);

const loadingScenarios = ref(false);
const loadingHistories = ref(false);
const scenarios = ref([]);
const histories = ref([]);
const selectedModuleId = ref(null);
const selectedScenarioId = ref(null);
const activeHistory = ref(null);
const collapsedSteps = ref({});
const collapsedScenarioGroups = ref({});
const showPassAssertions = ref({});
const detailScenarioResultFilter = ref("all");
const selectedHistoryIds = ref([]);
const historyKeyword = ref("");
const historyOrdering = ref("-created_at");
const pageSize = ref(10);
const currentPage = ref(1);
const historyTotal = ref(0);

function unwrapListPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.items)) return payload.items;
  return [];
}

const totalPages = computed(() => {
  const size = Math.max(1, Number(pageSize.value || 10));
  const total = Math.max(0, Number(historyTotal.value || 0));
  return Math.max(1, Math.ceil(total / size));
});

const moduleSelectOptions = computed(() => {
  const source = (props.modules || []).map((m) => ({
    id: Number(m.id),
    name: m.name || "未命名模块",
    parentId: m.parent_id ? Number(m.parent_id) : null,
    children: []
  }));
  const map = new Map(source.map((m) => [m.id, m]));
  const roots = [];
  for (const item of source) {
    if (item.parentId && map.has(item.parentId)) map.get(item.parentId).children.push(item);
    else roots.push(item);
  }
  const rows = [];
  const walk = (node, depth = 0) => {
    rows.push({ id: node.id, label: `${"　".repeat(depth)}${node.name}` });
    for (const child of node.children) walk(child, depth + 1);
  };
  for (const root of roots) walk(root, 0);
  return rows;
});

const visibleScenarios = computed(() => {
  if (!selectedModuleId.value) return scenarios.value;
  const moduleIds = new Set(getDescendantModuleIds(Number(selectedModuleId.value)));
  return (scenarios.value || []).filter((s) => s.module_id && moduleIds.has(Number(s.module_id)));
});

const isAllFilteredSelected = computed(() => {
  const ids = histories.value.map((item) => Number(item.id));
  if (!ids.length) return false;
  const selected = new Set((selectedHistoryIds.value || []).map((item) => Number(item)));
  return ids.every((id) => selected.has(id));
});

function sanitizeRequest(value) {
  // 明细展示前清理敏感上下文字段，避免变量值泄露到页面。
  const raw = value && typeof value === "object" ? JSON.parse(JSON.stringify(value)) : {};
  raw.body_text = tryParseJsonString(raw.body_text);
  raw.body_json = tryParseJsonString(raw.body_json);
  delete raw.environment_variables;
  delete raw.environment_variable_keys;
  return raw;
}

function sanitizeResult(value) {
  // 对响应体做“可解析则转对象”的标准化，便于 UI 统一 pretty 展示。
  const raw = value && typeof value === "object" ? JSON.parse(JSON.stringify(value)) : {};
  raw.response_body = tryParseJsonString(raw.response_body);
  delete raw.request;
  if (raw.request_snapshot && typeof raw.request_snapshot === "object") {
    delete raw.request_snapshot.environment_variables;
    delete raw.request_snapshot.environment_variable_keys;
  }
  return raw;
}

function tryParseJsonString(value) {
  // 仅在看起来像 JSON 的字符串上尝试解析，避免误伤普通文本。
  if (typeof value !== "string") return value;
  const text = value.trim();
  if (!text) return value;
  const isObjectLike = text.startsWith("{") && text.endsWith("}");
  const isArrayLike = text.startsWith("[") && text.endsWith("]");
  if (!isObjectLike && !isArrayLike) return value;
  try {
    return JSON.parse(text);
  } catch {
    return value;
  }
}

const stepCards = computed(() => {
  // 优先使用 iterations 结构（参数化执行），否则回退兼容旧版 results。
  const iterations = Array.isArray(activeHistory.value?.iterations) ? activeHistory.value.iterations : [];
  if (iterations.length) {
    const rows = [];
    for (const iter of iterations) {
      const list = Array.isArray(iter?.results) ? iter.results : [];
      for (let idx = 0; idx < list.length; idx += 1) {
        const item = list[idx] || {};
        const baseName =
          item?.scenario_name || activeHistory.value?.scenario_name || `场景#${item?.scenario_id ?? activeHistory.value?.scenario_id ?? "-"}`;
        rows.push({
          key: `iter-${iter?.iteration_index || 1}-${item?.step_id || "s"}-${idx}`,
          order: item?.step_order ?? idx + 1,
          name: item?.step_name || `步骤${idx + 1}`,
          testCaseName: item?.test_case_name || "-",
          scenarioId: item?.scenario_id ?? activeHistory.value?.scenario_id ?? null,
          scenarioName: `${baseName} / 第${iter?.iteration_index || 1}轮`,
          iterationIndex: Number(iter?.iteration_index || 1),
          rowData: iter?.row_data || {},
          success: Boolean(item?.result?.success),
          iterationSuccess: iter?.success === undefined || iter?.success === null ? null : Boolean(iter?.success),
          iterationError: iter?.error_message || null,
          request: item?.request || {},
          result: sanitizeResult(item?.result || {}),
          assertions: Array.isArray(item?.assertions) ? item.assertions : [],
          extracted: item?.extracted || {},
          preProcessors: Array.isArray(item?.pre_processors) ? item.pre_processors : [],
          postProcessors: Array.isArray(item?.post_processors) ? item.post_processors : []
        });
      }
    }
    return rows;
  }
  const list = activeHistory.value?.results;
  if (!Array.isArray(list)) return [];
  return list.map((item, idx) => ({
    key: `${item?.step_id || "s"}-${idx}`,
    order: item?.step_order ?? idx + 1,
    name: item?.step_name || `步骤${idx + 1}`,
    testCaseName: item?.test_case_name || "-",
    scenarioId: item?.scenario_id ?? activeHistory.value?.scenario_id ?? null,
    scenarioName: item?.scenario_name || activeHistory.value?.scenario_name || `场景#${item?.scenario_id ?? activeHistory.value?.scenario_id ?? "-"}`,
    iterationIndex: Number(item?.iteration_index || 1),
    rowData: item?.row_data || {},
    success: Boolean(item?.result?.success),
    iterationSuccess: null,
    iterationError: null,
    request: item?.request || {},
    result: sanitizeResult(item?.result || {}),
    assertions: Array.isArray(item?.assertions) ? item.assertions : [],
    extracted: item?.extracted || {},
    preProcessors: Array.isArray(item?.pre_processors) ? item.pre_processors : [],
    postProcessors: Array.isArray(item?.post_processors) ? item.post_processors : []
  }));
});

const groupedStepCards = computed(() => {
  // 同一场景同一轮次聚合成组，支持“按轮次查看失败”。
  const groups = new Map();
  for (const step of stepCards.value) {
    const sid = step.scenarioId ?? "none";
    const sname = step.scenarioName || `场景#${sid}`;
    const key = `${sid}::${sname}::iter-${step.iterationIndex || 1}`;
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        scenarioId: sid,
        scenarioName: sname,
        iterationIndex: step.iterationIndex || 1,
        rowData: step.rowData || {},
        steps: [],
        passCount: 0,
        failCount: 0,
        iterationSuccess: null,
        iterationError: null,
        effectiveFailCount: 0
      });
    }
    const group = groups.get(key);
    group.steps.push(step);
    if (step.success) group.passCount += 1;
    else group.failCount += 1;
    if (step.iterationSuccess === false) {
      group.iterationSuccess = false;
      if (!group.iterationError && step.iterationError) group.iterationError = step.iterationError;
    } else if (group.iterationSuccess === null && step.iterationSuccess === true) {
      group.iterationSuccess = true;
    }
  }
  return Array.from(groups.values()).map((group) => {
    // 若轮次级失败但步骤未标 fail，补一个有效失败数用于筛选。
    const extraFail = group.iterationSuccess === false && group.failCount === 0 ? 1 : 0;
    return { ...group, effectiveFailCount: group.failCount + extraFail };
  });
});

const filteredGroupedStepCards = computed(() => {
  const mode = String(detailScenarioResultFilter.value || "all");
  if (mode === "pass") {
    return groupedStepCards.value.filter((group) => Number(group.effectiveFailCount || 0) === 0);
  }
  if (mode === "fail") {
    return groupedStepCards.value.filter((group) => Number(group.effectiveFailCount || 0) > 0);
  }
  return groupedStepCards.value;
});

function notify(type, message) {
  emit("notify", { type, message });
}

function prettyJson(value) {
  if (value === null || value === undefined || value === "") return "-";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function normalizeAssertionEntry(item) {
  // 兼容后端多种断言结果结构，统一为表格展示模型。
  const raw = item && typeof item === "object" ? item : { detail: String(item ?? "") };
  const detail = String(raw.detail ?? raw.message ?? "");
  const parsed = parseAssertionDetail(detail);
  let pass = null;
  if (typeof raw.pass === "boolean") pass = raw.pass;
  else if (typeof raw.ok === "boolean") pass = raw.ok;
  else if (detail.includes("FAIL")) pass = false;
  else if (detail.includes("PASS")) pass = true;
  return {
    source: String(raw.source || raw.target || "断言"),
    rule: String(raw.rule || raw.target || raw.name || parsed.rule || "-"),
    expected: raw.expected ?? parsed.expected ?? null,
    actual: raw.actual ?? parsed.actual ?? null,
    pass,
    detail
  };
}

function parseAssertionDetail(detail) {
  // 解析形如 `rule expected=..., actual=...` 的旧格式字符串。
  const text = String(detail || "").trim();
  if (!text) return { rule: null, expected: null, actual: null };
  const m = text.match(/^([a-zA-Z_]+)(?:\s+path=([^,]+))?,\s*expected=(.*?),\s*actual=(.*)$/);
  if (m) {
    const base = String(m[1] || "").trim();
    const path = String(m[2] || "").trim();
    return {
      rule: path ? `${base} ${path}` : base,
      expected: String(m[3] || "").trim(),
      actual: String(m[4] || "").trim()
    };
  }
  const m2 = text.match(/^([a-zA-Z_]+)\s+expected=(.*?),\s*actual=(.*)$/);
  if (m2) {
    return {
      rule: String(m2[1] || "").trim(),
      expected: String(m2[2] || "").trim(),
      actual: String(m2[3] || "").trim()
    };
  }
  return { rule: null, expected: null, actual: null };
}

function getStepAssertionModel(step) {
  // 默认只展示失败/未知断言，降低报告噪音；通过项按需展开。
  const rows = Array.isArray(step?.assertions) ? step.assertions.map(normalizeAssertionEntry) : [];
  const failRows = rows.filter((item) => item.pass === false);
  const passRows = rows.filter((item) => item.pass === true);
  const unknownRows = rows.filter((item) => item.pass === null);
  const visible = showPassAssertions.value[step?.key] ? [...failRows, ...unknownRows, ...passRows] : [...failRows, ...unknownRows];
  return {
    total: rows.length,
    passCount: passRows.length,
    failCount: failRows.length,
    unknownCount: unknownRows.length,
    visible
  };
}

function togglePassAssertions(stepKey) {
  if (!stepKey) return;
  showPassAssertions.value[stepKey] = !showPassAssertions.value[stepKey];
}

function getDescendantModuleIds(moduleId) {
  // BFS 收集子模块，保证模块筛选与主页面行为一致。
  const ids = new Set();
  const queue = [Number(moduleId)];
  while (queue.length) {
    const current = queue.shift();
    if (ids.has(current)) continue;
    ids.add(current);
    for (const item of props.modules || []) {
      if (Number(item.parent_id || 0) === Number(current)) queue.push(Number(item.id));
    }
  }
  return Array.from(ids);
}

async function loadScenarios() {
  if (!props.projectId) {
    scenarios.value = [];
    selectedModuleId.value = null;
    selectedScenarioId.value = null;
    return;
  }
  loadingScenarios.value = true;
  try {
    scenarios.value = unwrapListPayload((await api.listScenarios(props.projectId)).data);
    if (selectedScenarioId.value && !scenarios.value.some((item) => Number(item.id) === Number(selectedScenarioId.value))) {
      selectedScenarioId.value = null;
    }
  } catch (e) {
    notify("err", e?.response?.data?.detail || "加载场景失败");
  } finally {
    loadingScenarios.value = false;
  }
}

async function loadHistories() {
  loadingHistories.value = true;
  try {
    const res = await api.listScenarioHistories(selectedScenarioId.value || null, props.projectId || null, {
      module_id: selectedModuleId.value || undefined,
      keyword: String(historyKeyword.value || "").trim(),
      ordering: String(historyOrdering.value || "-created_at"),
      page: Number(currentPage.value || 1),
      page_size: Number(pageSize.value || 10),
    });
    const payload = res.data;
    histories.value = unwrapListPayload(payload);
    historyTotal.value = Number(payload?.total || histories.value.length || 0);
    currentPage.value = Number(payload?.page || currentPage.value || 1);
    pageSize.value = Number(payload?.page_size || pageSize.value || 10);
    const validIds = new Set(histories.value.map((item) => Number(item.id)));
    // 保持勾选状态与当前数据一致，避免“已删记录仍被勾选”。
    selectedHistoryIds.value = (selectedHistoryIds.value || []).filter((id) => validIds.has(Number(id)));
    if (activeHistory.value && !histories.value.some((item) => Number(item.id) === Number(activeHistory.value.id))) {
      activeHistory.value = null;
    }
  } catch (e) {
    histories.value = [];
    historyTotal.value = 0;
    notify("err", e?.response?.data?.detail || "加载场景报告失败");
  } finally {
    loadingHistories.value = false;
  }
}

function openHistoryDetail(item) {
  activeHistory.value = item;
  collapsedSteps.value = {};
  collapsedScenarioGroups.value = {};
  showPassAssertions.value = {};
  detailScenarioResultFilter.value = "all";
  const list = Array.isArray(item?.results) ? item.results : [];
  for (let idx = 0; idx < list.length; idx += 1) {
    const row = list[idx];
    const key = `${row?.step_id || "s"}-${idx}`;
    collapsedSteps.value[key] = true;
  }
  for (const group of groupedStepCards.value) {
    // 明细默认折叠，先看摘要再按需展开步骤。
    collapsedScenarioGroups.value[group.key] = true;
  }
}

function closeHistoryDetail() {
  activeHistory.value = null;
  collapsedSteps.value = {};
  collapsedScenarioGroups.value = {};
  showPassAssertions.value = {};
  detailScenarioResultFilter.value = "all";
}

async function deleteHistory(item) {
  const historyId = Number(item?.id || 0);
  if (!historyId) return;
  const ok = props.confirmBox
    ? await props.confirmBox({ title: "删除报告", message: `确认删除报告 #${historyId} 吗？`, danger: true })
    : false;
  if (!ok) return;
  try {
    await api.deleteScenarioHistory(historyId);
    selectedHistoryIds.value = (selectedHistoryIds.value || []).filter((id) => Number(id) !== historyId);
    if (activeHistory.value && Number(activeHistory.value.id) === historyId) {
      closeHistoryDetail();
    }
    notify("ok", "报告已删除");
    await loadHistories();
  } catch (e) {
    notify("err", e?.response?.data?.detail || "删除报告失败");
  }
}

function toggleSelectAllFiltered() {
  // 全选作用于“当前分页结果”，避免误操作到不可见页。
  if (isAllFilteredSelected.value) {
    const ids = new Set(histories.value.map((item) => Number(item.id)));
    selectedHistoryIds.value = (selectedHistoryIds.value || []).filter((id) => !ids.has(Number(id)));
    return;
  }
  const merged = new Set((selectedHistoryIds.value || []).map((item) => Number(item)));
  for (const row of histories.value) merged.add(Number(row.id));
  selectedHistoryIds.value = Array.from(merged);
}

async function applyHistorySearch() {
  if (Number(currentPage.value || 1) !== 1) {
    currentPage.value = 1;
    return;
  }
  await loadHistories();
}

async function deleteSelectedHistories() {
  const ids = (selectedHistoryIds.value || []).map((item) => Number(item)).filter((id) => id > 0);
  if (!ids.length) return;
  const ok = props.confirmBox
    ? await props.confirmBox({ title: "批量删除报告", message: `确认批量删除 ${ids.length} 条报告吗？`, danger: true })
    : false;
  if (!ok) return;
  try {
    await api.deleteScenarioHistories(ids);
    if (activeHistory.value && ids.includes(Number(activeHistory.value.id))) {
      closeHistoryDetail();
    }
    selectedHistoryIds.value = [];
    notify("ok", "批量删除成功");
    await loadHistories();
  } catch (e) {
    notify("err", e?.response?.data?.detail || "批量删除失败");
  }
}

async function deleteAllFilteredHistories() {
  const ids = histories.value.map((item) => Number(item.id)).filter((id) => id > 0);
  if (!ids.length) return;
  const ok = props.confirmBox
    ? await props.confirmBox({ title: "删除当前页报告", message: `确认删除当前页全部 ${ids.length} 条报告吗？`, danger: true })
    : false;
  if (!ok) return;
  try {
    await api.deleteScenarioHistories(ids);
    if (activeHistory.value && ids.includes(Number(activeHistory.value.id))) {
      closeHistoryDetail();
    }
    selectedHistoryIds.value = [];
    notify("ok", "已删除当前页全部报告");
    await loadHistories();
  } catch (e) {
    notify("err", e?.response?.data?.detail || "全部删除失败");
  }
}

function toggleStep(key) {
  collapsedSteps.value[key] = !collapsedSteps.value[key];
}

function toggleScenarioGroup(key) {
  const nextCollapsed = !collapsedScenarioGroups.value[key];
  collapsedScenarioGroups.value[key] = nextCollapsed;
  if (!nextCollapsed) {
    const group = groupedStepCards.value.find((item) => item.key === key);
    if (group?.steps?.length) {
      for (const step of group.steps) {
        collapsedSteps.value[step.key] = true;
      }
    }
  }
}

async function focusHistory() {
  const scenarioId = Number(props.focus?.scenarioId || 0);
  const historyId = Number(props.focus?.historyId || 0);
  if (props.focus?.clearScenarioFilter) {
    selectedScenarioId.value = null;
  } else if (scenarioId > 0) {
    selectedScenarioId.value = scenarioId;
  }
  await loadHistories();
  if (historyId > 0) {
    const hit = histories.value.find((item) => Number(item.id) === historyId);
    if (hit) activeHistory.value = hit;
  }
}

watch(
  () => props.projectId,
  async () => {
    activeHistory.value = null;
    await loadScenarios();
    await loadHistories();
  },
  { immediate: true }
);

watch(
  () => selectedModuleId.value,
  async () => {
    const needResetPage = Number(currentPage.value || 1) !== 1;
    if (needResetPage) currentPage.value = 1;
    if (selectedScenarioId.value) {
      const exists = visibleScenarios.value.some((item) => Number(item.id) === Number(selectedScenarioId.value));
      if (!exists) {
        selectedScenarioId.value = null;
        return;
      }
    }
    if (needResetPage) return;
    await loadHistories();
  }
);

watch(
  () => selectedScenarioId.value,
  async () => {
    if (Number(currentPage.value || 1) !== 1) {
      currentPage.value = 1;
      return;
    }
    await loadHistories();
  }
);

watch([pageSize, currentPage, historyOrdering], async () => {
  await loadHistories();
});

watch(
  () => props.focus?.ts,
  async () => {
    if (!props.projectId) return;
    currentPage.value = 1;
    await focusHistory();
  }
);
</script>

<template>
  <section class="card">
    <div class="card-head">
      <div>
        <h3>场景测试报告</h3>
        <div class="sub">每次场景执行都会生成一条报告，可查看步骤明细与上下文</div>
      </div>
      <div class="actions-inline">
        <el-select v-model="selectedModuleId" placeholder="全部模块" clearable :disabled="loadingScenarios || !moduleSelectOptions.length">
          <el-option label="全部模块" :value="null" />
          <el-option v-for="m in moduleSelectOptions" :key="m.id" :label="m.label" :value="m.id" />
        </el-select>
        <el-select v-model="selectedScenarioId" placeholder="全部场景" clearable :disabled="loadingScenarios || !visibleScenarios.length">
          <el-option label="全部场景" :value="null" />
          <el-option v-for="s in visibleScenarios" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-input
          v-model="historyKeyword"
          clearable
          placeholder="搜索场景 / 错误信息"
          style="width: 220px"
          @keyup.enter="applyHistorySearch"
          @clear="applyHistorySearch"
        />
        <el-select v-model="historyOrdering" style="width: 160px">
          <el-option label="最新执行" value="-created_at" />
          <el-option label="最早执行" value="created_at" />
          <el-option label="最长耗时" value="-duration_ms" />
          <el-option label="最短耗时" value="duration_ms" />
        </el-select>
        <el-button @click="applyHistorySearch">搜索</el-button>
        <el-button class="btn danger" :disabled="!selectedHistoryIds.length" @click="deleteSelectedHistories">
          批量删除{{ selectedHistoryIds.length ? `(${selectedHistoryIds.length})` : "" }}
        </el-button>
        <el-button class="btn danger" :disabled="!histories.length" @click="deleteAllFilteredHistories">
          全部删除（当前页）
        </el-button>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th style="width: 36px">
              <el-checkbox :model-value="isAllFilteredSelected" @change="toggleSelectAllFiltered"  />
            </th>
            <th>序号</th>
            <th>场景</th>
            <th>结果</th>
            <th>耗时</th>
            <th>错误信息</th>
            <th>时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(h, idx) in histories" :key="h.id">
            <td>
              <el-checkbox :label="Number(h.id)" v-model="selectedHistoryIds"  />
            </td>
            <td>{{ (currentPage - 1) * pageSize + idx + 1 }}</td>
            <td>{{ h.scenario_name || `#${h.scenario_id}` }}</td>
            <td><span :class="h.success ? 'tag pass' : 'tag fail'">{{ h.success ? "PASS" : "FAIL" }}</span></td>
            <td>{{ h.duration_ms ?? "-" }}ms</td>
            <td :title="h.error_message || '-'">{{ h.error_message || "-" }}</td>
            <td>{{ (h.created_at || "").replace("T", " ").slice(0, 19) }}</td>
            <td>
              <div class="actions-inline">
                <el-button class="btn mini" @click="openHistoryDetail(h)">查看报告</el-button>
                <el-button class="btn mini danger" @click="deleteHistory(h)">删除</el-button>
              </div>
            </td>
          </tr>
          <tr v-if="!histories.length">
            <td colspan="8" class="empty-row">暂无场景报告</td>
          </tr>
        </tbody>
      </table>
      <div v-if="historyTotal > 0" class="actions-inline" style="justify-content: flex-end; margin-top: 10px;">
        <span class="sub">共 {{ historyTotal }} 条</span>
        <span class="sub">第 {{ currentPage }} / {{ totalPages }} 页</span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="historyTotal"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          small
        />
      </div>
    </div>
  </section>

  <div v-if="activeHistory" class="history-modal-mask" @click.self="closeHistoryDetail">
    <section class="history-modal card">
      <div class="card-head">
        <div>
          <h3>场景报告 #{{ activeHistory.id }}</h3>
          <div class="sub">
            场景：{{ activeHistory.scenario_name || `#${activeHistory.scenario_id}` }}，
            结果：<span :class="activeHistory.success ? 'tag pass' : 'tag fail'">{{ activeHistory.success ? "PASS" : "FAIL" }}</span>，
            耗时：{{ activeHistory.duration_ms ?? "-" }}ms
          </div>
        </div>
        <div class="actions-inline">
          <el-select v-model="detailScenarioResultFilter" class="report-filter-select" placeholder="筛选场景结果">
            <el-option label="全部场景" value="all" />
            <el-option label="仅成功场景" value="pass" />
            <el-option label="仅失败场景" value="fail" />
          </el-select>
          <el-button class="btn mini danger" @click="deleteHistory(activeHistory)">删除报告</el-button>
          <el-button class="btn" @click="closeHistoryDetail">关闭</el-button>
        </div>
      </div>

      <div class="history-detail-grid">
        <section class="detail-block full">
          <h4>步骤执行明细</h4>
          <div v-if="filteredGroupedStepCards.length" class="step-card-list">
            <article v-for="group in filteredGroupedStepCards" :key="group.key" class="scenario-group-card">
              <header class="scenario-group-head">
                <div>
                  <strong>{{ group.scenarioName }}</strong>
                  <div class="sub">步骤数：{{ group.steps.length }}，PASS {{ group.passCount }}，FAIL {{ group.effectiveFailCount }}</div>
                  <div v-if="group.iterationSuccess === false" class="sub fail-text">
                    迭代结果：FAIL{{ group.iterationError ? `，原因：${group.iterationError}` : "" }}
                  </div>
                  <div v-if="group.rowData && Object.keys(group.rowData).length" class="sub">数据行：{{ prettyJson(group.rowData) }}</div>
                </div>
                <div class="actions-inline">
                  <el-button class="btn mini" @click="toggleScenarioGroup(group.key)">
                    {{ collapsedScenarioGroups[group.key] ? "展开场景" : "折叠场景" }}
                  </el-button>
                </div>
              </header>
              <div v-show="!collapsedScenarioGroups[group.key]" class="scenario-group-body">
                <article v-for="step in group.steps" :key="step.key" class="step-report-card">
                  <header class="step-report-head">
                    <div>
                      <strong>Step {{ step.order }} - {{ step.name }}</strong>
                      <div class="sub">接口：{{ step.testCaseName }}</div>
                    </div>
                    <div class="actions-inline">
                      <span :class="step.success ? 'tag pass' : 'tag fail'">{{ step.success ? "PASS" : "FAIL" }}</span>
                      <el-button class="btn mini" @click="toggleStep(step.key)">{{ collapsedSteps[step.key] ? "展开" : "折叠" }}</el-button>
                    </div>
                  </header>
                  <div v-show="!collapsedSteps[step.key]" class="step-report-grid">
                    <section>
                      <details>
                        <summary>请求</summary>
                        <pre class="mono detail-pre">{{ prettyJson(sanitizeRequest(step.request)) }}</pre>
                      </details>
                    </section>
                    <section>
                      <h5>结果</h5>
                      <div class="result-split">
                        <div class="result-row">
                          <strong>Status Code</strong>
                          <pre class="mono detail-pre">{{ prettyJson(step.result?.status_code ?? null) }}</pre>
                        </div>
                        <details>
                          <summary>响应详情</summary>
                          <div class="result-row">
                            <strong>Response Headers</strong>
                            <pre class="mono detail-pre">{{ prettyJson(step.result?.response_headers ?? null) }}</pre>
                          </div>
                          <div class="result-row">
                            <strong>Response Body</strong>
                            <pre class="mono detail-pre">{{ prettyJson(step.result?.response_body ?? null) }}</pre>
                          </div>
                        </details>
                      </div>
                    </section>
                    <section v-if="getStepAssertionModel(step).total">
                      <div class="assert-head">
                        <h5>断言</h5>
                        <div class="actions-inline">
                          <span class="badge">总 {{ getStepAssertionModel(step).total }}</span>
                          <span class="badge good">PASS {{ getStepAssertionModel(step).passCount }}</span>
                          <span class="badge bad">FAIL {{ getStepAssertionModel(step).failCount }}</span>
                          <el-button
                            v-if="getStepAssertionModel(step).passCount > 0"
                            class="btn mini"
                            @click="togglePassAssertions(step.key)"
                          >
                            {{ showPassAssertions[step.key] ? "折叠PASS" : "展开PASS" }}
                          </el-button>
                        </div>
                      </div>
                      <div class="assert-card-list">
                        <article
                          v-for="(a, aIdx) in getStepAssertionModel(step).visible"
                          :key="`${step.key}-assert-${aIdx}`"
                          class="assert-card"
                          :class="a.pass === false ? 'is-fail' : (a.pass === true ? 'is-pass' : 'is-unknown')"
                        >
                          <div class="assert-card-head">
                            <strong>{{ a.source }}</strong>
                            <span :class="a.pass === true ? 'tag pass' : (a.pass === false ? 'tag fail' : 'tag')">
                              {{ a.pass === true ? "PASS" : (a.pass === false ? "FAIL" : "未知") }}
                            </span>
                          </div>
                          <div class="assert-grid">
                            <div><span class="muted small">规则</span><div>{{ a.rule || "-" }}</div></div>
                            <div><span class="muted small">期望</span><div>{{ prettyJson(a.expected) }}</div></div>
                            <div><span class="muted small">实际</span><div>{{ prettyJson(a.actual) }}</div></div>
                            <div v-if="a.detail"><span class="muted small">详情</span><div>{{ a.detail }}</div></div>
                          </div>
                        </article>
                      </div>
                    </section>
                    <section v-if="step.extracted && ((typeof step.extracted === 'object' && Object.keys(step.extracted).length > 0) || typeof step.extracted !== 'object')">
                      <details>
                        <summary>变量提取</summary>
                        <pre class="mono detail-pre">{{ prettyJson(step.extracted) }}</pre>
                      </details>
                    </section>
                    <section v-if="Array.isArray(step.preProcessors) && step.preProcessors.length">
                      <details>
                        <summary>前置处理器</summary>
                        <pre class="mono detail-pre">{{ prettyJson(step.preProcessors) }}</pre>
                      </details>
                    </section>
                    <section v-if="Array.isArray(step.postProcessors) && step.postProcessors.length">
                      <details>
                        <summary>后置处理器</summary>
                        <pre class="mono detail-pre">{{ prettyJson(step.postProcessors) }}</pre>
                      </details>
                    </section>
                  </div>
                </article>
              </div>
            </article>
          </div>
          <div v-else class="empty-row">当前筛选下暂无场景明细</div>
        </section>
      </div>
    </section>
  </div>
</template>

<style scoped>
.step-card-list { display: grid; gap: 12px; }
.scenario-group-card { border: 1px solid #e8ebf2; border-radius: 10px; padding: 10px; background: #f8fafc; }
.scenario-group-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.scenario-group-body { margin-top: 10px; display: grid; gap: 10px; }
.step-report-card { border: 1px solid #e6e8ef; border-radius: 10px; padding: 10px; background: #fff; }
.step-report-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.step-report-grid { display: grid; grid-template-columns: 1fr; gap: 10px; }
.step-report-grid h5 { margin: 0 0 6px; font-size: 12px; color: #5f6472; }
.result-split { display: grid; gap: 8px; }
.result-row { display: grid; gap: 4px; }
.result-row strong { font-size: 12px; color: #374151; }
.fail-text { color: #b91c1c; }
.report-filter-select {
  min-width: 140px;
}
.assert-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.assert-card-list {
  display: grid;
  gap: 8px;
}
.assert-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  background: #ffffff;
  font-size: 12px;
}
.assert-card.is-fail {
  border-color: #fecaca;
  background: #fef2f2;
}
.assert-card.is-pass {
  border-color: #bbf7d0;
  background: #f0fdf4;
}
.assert-card.is-unknown {
  border-color: #e5e7eb;
  background: #f8fafc;
}
.assert-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.assert-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 10px;
  font-size: 12px;
}
.step-report-grid details > summary {
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  color: #1f2937;
}
details > summary::-webkit-details-marker { margin-right: 4px; }
@media (max-width: 960px) {
  .step-report-grid { grid-template-columns: 1fr; }
  .assert-grid { grid-template-columns: 1fr; }
}
</style>
