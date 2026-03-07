<!-- 作者: lxl -->
<!-- 说明: 前端页面/组件模块。 -->
<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ArrowDown, ArrowUp, Delete, Edit, MoreFilled, Plus, DocumentCopy } from "@element-plus/icons-vue";
import { api } from "../api";
import JsonEditorField from "./JsonEditorField.vue";

const props = defineProps({
  cases: { type: Array, default: () => [] },
  modules: { type: Array, default: () => [] },
  environments: { type: Array, default: () => [] },
  projectId: { type: [Number, String, null], default: null },
  confirmBox: { type: Function, default: null }
});
const emit = defineEmits(["notify", "create-module", "edit-module", "delete-module", "move-module", "open-report"]);

const scenarios = ref([]);
const scenarioHistories = ref([]);
const selectedScenarioId = ref(null);
const selectedModuleId = ref(null);
const scenarioEditorVisible = ref(false);
const stepEditorIndex = ref(null);
const stepEditorDraft = ref(null);
const stepEditorSaving = ref(false);
const stepCaseEntryExpanded = ref(false);
const stepCaseEntryMode = ref("view");
const scenarioLoading = ref(false);
const scenarioRunLoading = ref(false);
const scenarioPreviewLoading = ref(false);
const batchPreviewLoading = ref(false);
const stepDebugLoading = ref(false);
const stepDebugIncludePrevious = ref(true);
const batchParamEnabled = ref(false);
const batchEnvironmentId = ref(null);
const scenarioHistoryLoading = ref(false);
const dataSetLoading = ref(false);
const selectedModuleScenarioIds = ref([]);
const selectedModuleScenarioOrder = ref([]);
const selectedModuleScenarioDrag = reactive({ fromIndex: null, overIndex: null });
const moreOpenModuleId = ref(null);
const dragState = reactive({ fromIndex: null, overIndex: null });
const moduleDragId = ref(null);
const scenarioDrag = reactive({ sourceId: null, overId: null });
const scenarioDataSets = ref([]);
const showDataSetEditor = ref(false);
const dataSetColumns = ref(["列名"]);
const dataSetRows = ref([]);
const dataSetDragColIndex = ref(null);
const dataSetPasteText = ref("");
const rowAssertEditorVisible = ref(false);
const rowAssertEditor = reactive({
  rowIndex: -1,
  assert_enabled: false,
  assert_targets: [],
  assert_status_code: "",
  assert_header_jsonpath: "",
  assert_header_expected: "",
  assert_response_jsonpath: "",
  assert_response_expected: ""
});
const dataSetForm = reactive({
  id: null,
  name: "",
  description: "",
  module: null,
  source_type: "table",
  data_rows_text: "[]",
  raw_text: "",
  enabled: false,
  assert_enabled: false,
  assert_targets: [],
  assert_status_code: "",
  assert_header_jsonpath: "",
  assert_header_expected: "",
  assert_response_jsonpath: "",
  assert_response_expected: ""
});

const scenarioForm = reactive({
  id: null,
  name: "",
  description: "",
  module: null,
  param_enabled: false,
  data_set: null,
  data_mode: "all",
  data_pick: "",
  param_retry_count: 0,
  stop_on_failure: true,
  steps: []
});
const runtimeInspectorVisible = ref(false);
const runtimeInspector = reactive({
  mode: "scenario_preview",
  title: "",
  summary: null,
  steps: [],
  scenarios: [],
  prerequisiteResults: [],
  stepResult: null,
  contextSnapshot: null,
});

function unwrapListPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.items)) return payload.items;
  return [];
}

const collapsedGroups = reactive({});
const httpMethods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"];

const moduleRows = computed(() => {
  const moduleMap = new Map();
  for (const item of props.modules || []) {
    moduleMap.set(Number(item.id), {
      id: Number(item.id),
      name: item.name || "未命名模块",
      description: item.description || null,
      parentId: item.parent_id ? Number(item.parent_id) : null,
      children: [],
      scenarios: [],
    });
  }
  const roots = [];
  for (const node of moduleMap.values()) {
    if (node.parentId && moduleMap.has(node.parentId)) moduleMap.get(node.parentId).children.push(node);
    else roots.push(node);
  }
  for (const scenario of scenarios.value || []) {
    const moduleId = Number(scenario.module_id || scenario.module || 0);
    if (moduleId && moduleMap.has(moduleId)) moduleMap.get(moduleId).scenarios.push(scenario);
  }

  const countSubtree = (node) => {
    let count = node.scenarios.length;
    for (const child of node.children) count += countSubtree(child);
    return count;
  };
  const rows = [];
  const pushNode = (node, depth = 0) => {
    const key = String(node.id);
    const expanded = !collapsedGroups[key];
    rows.push({
      type: "module",
      id: node.id,
      name: node.name,
      parent_id: node.parentId,
      description: node.description,
      depth,
      expanded,
      scenarioCount: countSubtree(node),
      hasChildren: node.children.length > 0,
      hasOwnScenarios: node.scenarios.length > 0,
    });
    if (!expanded) return;
    for (const s of node.scenarios) rows.push({ type: "scenario", id: s.id, scenario: s, depth: depth + 1 });
    for (const child of node.children) pushNode(child, depth + 1);
  };
  for (const root of roots) pushNode(root, 0);
  const ungrouped = (scenarios.value || []).filter((s) => !s.module_id && !s.module);
  if (ungrouped.length) {
    rows.push({ type: "module", id: 0, name: "未分组", depth: 0, expanded: true, scenarioCount: ungrouped.length, hasChildren: false, hasOwnScenarios: true });
    for (const s of ungrouped) rows.push({ type: "scenario", id: s.id, scenario: s, depth: 1 });
  }
  return rows;
});

const stepCaseTreeData = computed(() => {
  const moduleMap = new Map();
  for (const raw of props.modules || []) {
    const id = Number(raw.id || 0);
    if (!id) continue;
    moduleMap.set(id, {
      id: `module-${id}`,
      value: `module-${id}`,
      name: String(raw.name || `模块#${id}`),
      parentId: raw.parent_id ? Number(raw.parent_id) : null,
      sortOrder: Number(raw.sort_order || 0),
      disabled: true,
      children: [],
    });
  }
  for (const node of moduleMap.values()) {
    if (node.parentId && moduleMap.has(node.parentId)) {
      moduleMap.get(node.parentId).children.push(node);
    }
  }
  const sortNodes = (arr) =>
    arr.sort((a, b) => {
      if (a.sortOrder !== b.sortOrder) return a.sortOrder - b.sortOrder;
      return String(a.name).localeCompare(String(b.name), "zh-Hans-CN");
    });
  const roots = sortNodes(Array.from(moduleMap.values()).filter((n) => !n.parentId || !moduleMap.has(n.parentId)));

  for (const c of props.cases || []) {
    const caseId = Number(c.id || 0);
    if (!caseId) continue;
    const moduleId = Number(c.module_id || c.module || 0);
    const caseLeaf = {
      id: `case-${caseId}`,
      value: caseId,
      name: `${c.name || `接口#${caseId}`}`,
      disabled: false,
      children: [],
    };
    if (moduleId && moduleMap.has(moduleId)) {
      moduleMap.get(moduleId).children.push(caseLeaf);
    }
  }

  const ungroupedCases = (props.cases || [])
    .filter((c) => {
      const moduleId = Number(c.module_id || c.module || 0);
      return !moduleId || !moduleMap.has(moduleId);
    })
    .map((c) => {
      const caseId = Number(c.id || 0);
      return {
        id: `case-${caseId}`,
        value: caseId,
        name: `${c.name || `接口#${caseId}`}`,
        disabled: false,
        children: [],
      };
    });

  const sortTree = (nodes) => {
    sortNodes(nodes);
    for (const node of nodes) {
      if (!Array.isArray(node.children) || !node.children.length) continue;
      const moduleChildren = node.children.filter((child) => String(child.value || "").startsWith("module-"));
      const caseChildren = node.children.filter((child) => !String(child.value || "").startsWith("module-"));
      sortTree(moduleChildren);
      caseChildren.sort((a, b) => String(a.name).localeCompare(String(b.name), "zh-Hans-CN"));
      node.children = [...moduleChildren, ...caseChildren];
    }
  };
  sortTree(roots);
  if (ungroupedCases.length) {
    roots.push({
      id: "module-ungrouped",
      value: "module-ungrouped",
      name: "未分组",
      disabled: true,
      children: ungroupedCases,
    });
  }
  return roots;
});

function stepCaseFilterMethod(value, data) {
  const keyword = String(value || "").trim().toLowerCase();
  if (!keyword) return true;
  const name = String(data?.name || "").toLowerCase();
  return name.includes(keyword);
}

const executionEnvironments = computed(() => {
  return (props.environments || [])
    .filter((item) => item?.is_active !== false)
    .map((item) => ({
    id: Number(item.id),
    name: item.name || `环境#${item.id}`,
    active: item.is_active !== false,
  }));
});

const selectedModuleScenarios = computed(() => {
  const moduleId = Number(selectedModuleId.value || 0);
  if (!moduleId) return [];
  const moduleIds = new Set([moduleId]);
  const queue = [moduleId];
  while (queue.length) {
    const current = queue.shift();
    for (const item of props.modules || []) {
      const parentId = Number(item.parent_id || 0);
      const childId = Number(item.id || 0);
      if (parentId === current && childId > 0 && !moduleIds.has(childId)) {
        moduleIds.add(childId);
        queue.push(childId);
      }
    }
  }
  return (scenarios.value || []).filter((item) => moduleIds.has(Number(item.module_id || item.module || 0)));
});

const orderedSelectedModuleScenarios = computed(() => {
  const list = selectedModuleScenarios.value || [];
  const map = new Map(list.map((item) => [Number(item.id), item]));
  const baseIds = list.map((item) => Number(item.id));
  const orderedIds = (selectedModuleScenarioOrder.value || []).filter((id) => map.has(Number(id)));
  for (const id of baseIds) {
    if (!orderedIds.includes(id)) orderedIds.push(id);
  }
  return orderedIds.map((id) => map.get(id)).filter(Boolean);
});

const isAllModuleScenariosSelected = computed(() => {
  const ids = orderedSelectedModuleScenarios.value.map((item) => Number(item.id));
  if (!ids.length) return false;
  const selected = new Set((selectedModuleScenarioIds.value || []).map((item) => Number(item)));
  return ids.every((id) => selected.has(id));
});

const editingStep = computed(() => {
  return stepEditorDraft.value;
});
const editingStepCase = computed(() => {
  const caseId = Number(editingStep.value?.test_case || 0);
  if (!caseId) return null;
  return (props.cases || []).find((item) => Number(item.id) === caseId) || null;
});
const managedDataSets = computed(() => {
  const moduleId = Number(scenarioForm.module || 0) || null;
  return (scenarioDataSets.value || []).filter((item) => {
    const dsModule = Number(item?.module_id || item?.module || 0) || null;
    return dsModule === moduleId;
  });
});
const availableDataSets = computed(() => {
  const moduleId = Number(scenarioForm.module || 0) || null;
  return managedDataSets.value.filter((item) => {
    if (!item?.enabled) return false;
    const dsModule = Number(item.module_id || item.module || 0) || null;
    return dsModule === null || moduleId === null || dsModule === moduleId;
  });
});
const dataSetPreviewRows = computed(() => {
  const sourceType = String(dataSetForm.source_type || "table");
  if (sourceType === "table") {
    const cols = dataSetColumns.value.map((item) => String(item || "").trim()).filter(Boolean);
    return (dataSetRows.value || []).slice(0, 10).map((row) => {
      const out = {};
      for (const col of cols) out[col] = row?.[col] ?? "";
      return out;
    });
  }
  if (sourceType === "json") {
    try {
      const parsed = JSON.parse(dataSetForm.raw_text || "[]");
      if (Array.isArray(parsed)) return parsed.filter((item) => item && typeof item === "object").slice(0, 10);
      if (parsed && typeof parsed === "object" && Array.isArray(parsed.rows)) {
        return parsed.rows.filter((item) => item && typeof item === "object").slice(0, 10);
      }
    } catch {}
    return [];
  }
  const text = String(dataSetForm.raw_text || "").trim();
  if (!text) return [];
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((item) => item.trim());
  return lines.slice(1, 11).map((line) => {
    const cols = line.split(",");
    const row = {};
    headers.forEach((key, idx) => {
      row[key || `col_${idx + 1}`] = (cols[idx] || "").trim();
    });
    return row;
  });
});
const dataSetRawPlaceholder = computed(() => {
  if (String(dataSetForm.source_type || "") === "json") return '[{"username":"u1"}]';
  return "username,password\nu1,p1";
});

function notify(type, message) {
  emit("notify", { type, message });
}

function parseJsonText(text, fieldLabel) {
  if (!text || !text.trim()) return null;
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${fieldLabel} 不是合法 JSON`);
  }
}

function prettyJson(value) {
  if (value === null || value === undefined || value === "") return "-";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function hasPreviewContent(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return String(value).trim() !== "";
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return true;
}

function resetDataSetForm(moduleId = null) {
  dataSetForm.id = null;
  dataSetForm.name = "";
  dataSetForm.description = "";
  dataSetForm.module = moduleId ? Number(moduleId) : null;
  dataSetForm.source_type = "table";
  dataSetForm.data_rows_text = "[]";
  dataSetForm.raw_text = "";
  dataSetForm.enabled = false;
  dataSetForm.assert_enabled = false;
  dataSetForm.assert_targets = [];
  dataSetForm.assert_status_code = "";
  dataSetForm.assert_header_jsonpath = "";
  dataSetForm.assert_header_expected = "";
  dataSetForm.assert_response_jsonpath = "";
  dataSetForm.assert_response_expected = "";
  dataSetColumns.value = ["列名"];
  dataSetRows.value = [];
}

function pickPreferredDataSet(items) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return null;
  const sortByLatest = (a, b) => {
    const ta = Date.parse(a?.updated_at || a?.created_at || 0) || Number(a?.id || 0);
    const tb = Date.parse(b?.updated_at || b?.created_at || 0) || Number(b?.id || 0);
    return tb - ta;
  };
  const enabledList = list.filter((item) => item?.enabled).sort(sortByLatest);
  if (enabledList.length) return enabledList[0];
  return [...list].sort(sortByLatest)[0];
}

function applyDefaultDataSetSelection() {
  const preferred = pickPreferredDataSet(managedDataSets.value);
  if (preferred) {
    editDataSet(preferred);
    scenarioForm.data_set = Number(preferred.id);
    return;
  }
  scenarioForm.data_set = null;
  resetDataSetForm(scenarioForm.module);
}

function openCreateDataSet(moduleId = null) {
  resetDataSetForm(moduleId);
  showDataSetEditor.value = true;
}

function editDataSet(item) {
  dataSetForm.id = Number(item?.id || 0) || null;
  dataSetForm.name = String(item?.name || "");
  dataSetForm.description = String(item?.description || "");
  dataSetForm.module = item?.module_id ? Number(item.module_id) : (item?.module ? Number(item.module) : null);
  dataSetForm.source_type = String(item?.source_type || "table");
  dataSetForm.data_rows_text = JSON.stringify(Array.isArray(item?.data_rows) ? item.data_rows : [], null, 2);
  dataSetForm.raw_text = String(item?.raw_text || "");
  dataSetForm.enabled = item?.enabled !== false;
  dataSetForm.assert_enabled = item?.assert_enabled === true;
  dataSetForm.assert_targets = Array.isArray(item?.assert_targets) ? item.assert_targets.map((v) => String(v || "")) : [];
  dataSetForm.assert_status_code =
    item?.assert_status_code === undefined || item?.assert_status_code === null ? "" : String(item.assert_status_code);
  dataSetForm.assert_header_jsonpath = String(item?.assert_header_jsonpath || "");
  dataSetForm.assert_header_expected = String(item?.assert_header_expected || "");
  dataSetForm.assert_response_jsonpath = String(item?.assert_response_jsonpath || "");
  dataSetForm.assert_response_expected = String(item?.assert_response_expected || "");
  loadDataSetTableEditor(Array.isArray(item?.data_rows) ? item.data_rows : [], item?.raw_text || "");
  showDataSetEditor.value = true;
}

function loadDataSetTableEditor(rows, rawText = "") {
  const safeRows = Array.isArray(rows) ? rows.filter((item) => item && typeof item === "object") : [];
  let preferredColumns = [];
  try {
    const parsed = rawText ? JSON.parse(String(rawText)) : null;
    if (parsed && Array.isArray(parsed.columns)) {
      preferredColumns = parsed.columns.map((item) => String(item || "").trim()).filter(Boolean);
    }
  } catch {}
  const keys = new Set(preferredColumns);
  for (const row of safeRows) {
    Object.keys(row)
      .filter((key) => !String(key).startsWith("__"))
      .forEach((key) => keys.add(String(key)));
  }
  const columns = preferredColumns.length
    ? [...preferredColumns, ...Array.from(keys).filter((key) => !preferredColumns.includes(key))]
    : Array.from(keys);
  dataSetColumns.value = columns.length ? columns : ["列名"];
  dataSetRows.value = safeRows.map((row) => {
    const normalized = {};
    for (const col of dataSetColumns.value) normalized[col] = row[col] ?? "";
    if (row && row.__assertions__ && typeof row.__assertions__ === "object") {
      normalized.__assertions__ = normalizeRowAssertions(row.__assertions__);
    }
    return normalized;
  });
  syncDataSetRowsTextFromTable();
}

function syncDataSetRowsTextFromTable() {
  const cols = dataSetColumns.value
    .map((item) => String(item || "").trim())
    .filter((item) => item && !item.startsWith("__"));
  const rows = [];
  for (const row of dataSetRows.value || []) {
    const obj = {};
    for (const col of cols) obj[col] = row?.[col] ?? "";
    if (row && row.__assertions__ && typeof row.__assertions__ === "object") {
      obj.__assertions__ = JSON.parse(JSON.stringify(row.__assertions__));
    }
    rows.push(obj);
  }
  dataSetForm.data_rows_text = JSON.stringify(rows, null, 2);
}

function addDataSetColumn() {
  const next = `column_${dataSetColumns.value.length + 1}`;
  dataSetColumns.value.push(next);
  for (const row of dataSetRows.value) row[next] = "";
  syncDataSetRowsTextFromTable();
}

function removeDataSetColumn(index) {
  if (dataSetColumns.value.length <= 1) return;
  const [key] = dataSetColumns.value.splice(index, 1);
  for (const row of dataSetRows.value) delete row[key];
  syncDataSetRowsTextFromTable();
}

function uniqueColumnNames(names) {
  const seen = new Set();
  const result = [];
  for (let i = 0; i < (names || []).length; i += 1) {
    let base = String(names[i] || "").trim() || `column_${i + 1}`;
    let name = base;
    let seq = 1;
    while (seen.has(name)) {
      seq += 1;
      name = `${base}_${seq}`;
    }
    seen.add(name);
    result.push(name);
  }
  return result;
}

function reorderDataSetColumns(fromIndex, toIndex) {
  const size = dataSetColumns.value.length;
  if (fromIndex === null || toIndex === null) return;
  if (fromIndex < 0 || toIndex < 0 || fromIndex >= size || toIndex >= size || fromIndex === toIndex) return;
  const [moved] = dataSetColumns.value.splice(fromIndex, 1);
  dataSetColumns.value.splice(toIndex, 0, moved);
  syncDataSetRowsTextFromTable();
}

function onDataSetColDragStart(index) {
  dataSetDragColIndex.value = index;
}

function onDataSetColDrop(index) {
  reorderDataSetColumns(dataSetDragColIndex.value, index);
  dataSetDragColIndex.value = null;
}

function onDataSetColDragEnd() {
  dataSetDragColIndex.value = null;
}

function addDataSetRow() {
  const row = {};
  for (const col of dataSetColumns.value) row[col] = "";
  dataSetRows.value.push(row);
  syncDataSetRowsTextFromTable();
}

function removeDataSetRow(index) {
  dataSetRows.value.splice(index, 1);
  if (!dataSetRows.value.length) addDataSetRow();
  syncDataSetRowsTextFromTable();
}

function normalizeRowAssertions(assertions) {
  const source = assertions && typeof assertions === "object" ? assertions : {};
  return {
    assert_enabled: source.assert_enabled === true,
    assert_targets: Array.isArray(source.assert_targets) ? source.assert_targets.map((item) => String(item || "")) : [],
    assert_status_code:
      source.assert_status_code === undefined || source.assert_status_code === null ? "" : String(source.assert_status_code),
    assert_header_jsonpath: String(source.assert_header_jsonpath || ""),
    assert_header_expected: String(source.assert_header_expected || ""),
    assert_response_jsonpath: String(source.assert_response_jsonpath || ""),
    assert_response_expected: String(source.assert_response_expected || "")
  };
}

function rowAssertionStatus(row) {
  if (!row || !row.__assertions__ || typeof row.__assertions__ !== "object") {
    return { label: "未配置", cls: "is-empty" };
  }
  const config = normalizeRowAssertions(row.__assertions__);
  if (config.assert_enabled && Array.isArray(config.assert_targets) && config.assert_targets.length > 0) {
    return { label: "已启用", cls: "is-on" };
  }
  return { label: "已禁用", cls: "is-off" };
}

function openRowAssertEditor(rowIndex) {
  const row = dataSetRows.value?.[rowIndex];
  if (!row) return;
  const config = normalizeRowAssertions(row.__assertions__);
  rowAssertEditor.rowIndex = rowIndex;
  rowAssertEditor.assert_enabled = config.assert_enabled;
  rowAssertEditor.assert_targets = config.assert_targets;
  rowAssertEditor.assert_status_code = config.assert_status_code;
  rowAssertEditor.assert_header_jsonpath = config.assert_header_jsonpath;
  rowAssertEditor.assert_header_expected = config.assert_header_expected;
  rowAssertEditor.assert_response_jsonpath = config.assert_response_jsonpath;
  rowAssertEditor.assert_response_expected = config.assert_response_expected;
  rowAssertEditorVisible.value = true;
}

function closeRowAssertEditor() {
  rowAssertEditorVisible.value = false;
  rowAssertEditor.rowIndex = -1;
}

function saveRowAssertions() {
  const index = Number(rowAssertEditor.rowIndex);
  const row = dataSetRows.value?.[index];
  if (!row) return closeRowAssertEditor();
  const payload = {
    assert_enabled: !!rowAssertEditor.assert_enabled,
    assert_targets: Array.isArray(rowAssertEditor.assert_targets)
      ? rowAssertEditor.assert_targets.map((item) => String(item || "").trim()).filter(Boolean)
      : [],
    assert_status_code: null,
    assert_header_jsonpath: null,
    assert_header_expected: null,
    assert_response_jsonpath: null,
    assert_response_expected: null
  };
  if (payload.assert_enabled) {
    if (!payload.assert_targets.length) return notify("err", "请至少选择一种断言方式");
    if (payload.assert_targets.includes("status_code")) {
      const rawStatus = String(rowAssertEditor.assert_status_code || "").trim();
      if (!rawStatus) return notify("err", "请填写状态码断言值");
      const parsed = Number(rawStatus);
      if (!Number.isInteger(parsed) || parsed < 100 || parsed > 999) return notify("err", "状态码需为100-999整数");
      payload.assert_status_code = parsed;
    }
    if (payload.assert_targets.includes("request_headers")) {
      const path = String(rowAssertEditor.assert_header_jsonpath || "").trim();
      const expected = String(rowAssertEditor.assert_header_expected || "").trim();
      if (!path || !expected) return notify("err", "请完整填写请求头 JSONPath 与期望值");
      payload.assert_header_jsonpath = path;
      payload.assert_header_expected = expected;
    }
    if (payload.assert_targets.includes("response_body")) {
      const path = String(rowAssertEditor.assert_response_jsonpath || "").trim();
      const expected = String(rowAssertEditor.assert_response_expected || "").trim();
      if (!path || !expected) return notify("err", "请完整填写响应结果 JSONPath 与期望值");
      payload.assert_response_jsonpath = path;
      payload.assert_response_expected = expected;
    }
    row.__assertions__ = payload;
  } else {
    delete row.__assertions__;
  }
  syncDataSetRowsTextFromTable();
  closeRowAssertEditor();
}

function importPastedDataSetRows() {
  const text = String(dataSetPasteText.value || "").trim();
  if (!text) {
    notify("err", "请先粘贴 Excel 数据");
    return;
  }
  const lines = text.split(/\r?\n/).filter((line) => String(line || "").trim() !== "");
  if (!lines.length) {
    notify("err", "未识别到可导入行");
    return;
  }
  const matrix = lines.map((line) => line.split("\t"));
  const rowsStartIndex = 1;
  dataSetColumns.value = uniqueColumnNames(matrix[0] || []);
  const cols = dataSetColumns.value;
  const importRows = [];
  for (let r = rowsStartIndex; r < matrix.length; r += 1) {
    const cells = matrix[r];
    const row = {};
    for (let c = 0; c < cols.length; c += 1) row[cols[c]] = cells[c] ?? "";
    importRows.push(row);
  }
  if (!importRows.length) {
    notify("err", "没有可导入的数据行");
    return;
  }
  dataSetRows.value.push(...importRows);
  syncDataSetRowsTextFromTable();
  notify("ok", `已导入 ${importRows.length} 行`);
}

async function loadDataSets() {
  if (!props.projectId) {
    scenarioDataSets.value = [];
    return;
  }
  dataSetLoading.value = true;
  try {
    scenarioDataSets.value = (await api.listDataSets(props.projectId)).data || [];
    if (scenarioForm.data_set && !scenarioDataSets.value.some((item) => Number(item.id) === Number(scenarioForm.data_set))) {
      scenarioForm.data_set = null;
    }
  } catch (e) {
    notify("err", e?.response?.data?.detail || "加载数据集失败");
  } finally {
    dataSetLoading.value = false;
  }
}

async function openDataSetManager() {
  showDataSetEditor.value = true;
  await loadDataSets();
  applyDefaultDataSetSelection();
}

function buildDataSetUpdatePayload(item, enabledValue = false) {
  return {
    project: Number(item?.project_id || item?.project || props.projectId),
    module: item?.module_id ? Number(item.module_id) : (item?.module ? Number(item.module) : null),
    name: String(item?.name || "").trim() || `数据集-${item?.id || ""}`,
    description: String(item?.description || "").trim() || null,
    source_type: String(item?.source_type || "table"),
    data_rows: Array.isArray(item?.data_rows) ? item.data_rows : [],
    raw_text: String(item?.raw_text || ""),
    enabled: Boolean(enabledValue),
    assert_enabled: item?.assert_enabled === true,
    assert_targets: Array.isArray(item?.assert_targets) ? item.assert_targets : [],
    assert_status_code: item?.assert_status_code ?? null,
    assert_header_jsonpath: item?.assert_header_jsonpath || null,
    assert_header_expected: item?.assert_header_expected || null,
    assert_response_jsonpath: item?.assert_response_jsonpath || null,
    assert_response_expected: item?.assert_response_expected || null
  };
}

async function ensureSingleEnabledDataSet(targetId) {
  const peers = managedDataSets.value.filter((item) => Number(item.id) !== Number(targetId) && item.enabled);
  for (const peer of peers) {
    await api.updateDataSet(peer.id, buildDataSetUpdatePayload(peer, false));
  }
}

function buildDataSetPayload() {
  if (!props.projectId) throw new Error("未选择项目");
  const scenarioName = String(scenarioForm.name || "").trim() || "未命名场景";
  const autoName = `${scenarioName}-数据集`;
  const normalizedName = String(dataSetForm.name || "").trim() || autoName;
  const payload = {
    project: Number(props.projectId),
    module: scenarioForm.module ? Number(scenarioForm.module) : null,
    name: normalizedName,
    description: String(dataSetForm.description || "").trim() || null,
    source_type: String(dataSetForm.source_type || "table"),
    data_rows: [],
    raw_text: "",
    enabled: !!dataSetForm.enabled,
    assert_enabled: !!dataSetForm.assert_enabled,
    assert_targets: Array.isArray(dataSetForm.assert_targets)
      ? dataSetForm.assert_targets.map((item) => String(item || "").trim()).filter(Boolean)
      : [],
    assert_status_code: null,
    assert_header_jsonpath: null,
    assert_header_expected: null,
    assert_response_jsonpath: null,
    assert_response_expected: null
  };
  if (payload.source_type === "table") {
    const cols = dataSetColumns.value
      .map((item) => String(item || "").trim())
      .filter((item) => item && !item.startsWith("__"));
    if (!cols.length) throw new Error("请至少保留一个列名");
    payload.data_rows = (dataSetRows.value || []).map((row) => {
      const item = {};
      for (const col of cols) item[col] = row?.[col] ?? "";
      if (row && row.__assertions__ && typeof row.__assertions__ === "object") {
        item.__assertions__ = JSON.parse(JSON.stringify(row.__assertions__));
      }
      return item;
    });
    payload.raw_text = JSON.stringify({ columns: cols });
  } else if (payload.source_type === "json") {
    const text = String(dataSetForm.raw_text || "").trim();
    if (!text) throw new Error("JSON 数据不能为空");
    parseJsonText(text, "JSON 数据");
    payload.raw_text = text;
  } else if (payload.source_type === "csv") {
    payload.raw_text = String(dataSetForm.raw_text || "").trim();
    if (!payload.raw_text) throw new Error("CSV 数据不能为空");
  }
  if (payload.assert_enabled) {
    if (!payload.assert_targets.length) throw new Error("请至少选择一种断言方式");
    if (payload.assert_targets.includes("status_code")) {
      const rawStatus = String(dataSetForm.assert_status_code || "").trim();
      if (!rawStatus) throw new Error("请填写状态码断言值");
      const parsed = Number(rawStatus);
      if (!Number.isInteger(parsed) || parsed < 100 || parsed > 999) {
        throw new Error("状态码断言值必须是100-999整数");
      }
      payload.assert_status_code = parsed;
    }
    if (payload.assert_targets.includes("request_headers")) {
      const jsonpath = String(dataSetForm.assert_header_jsonpath || "").trim();
      const expected = String(dataSetForm.assert_header_expected || "").trim();
      if (!jsonpath) throw new Error("请填写请求头 JSONPath");
      if (!expected) throw new Error("请填写请求头期望值");
      payload.assert_header_jsonpath = jsonpath;
      payload.assert_header_expected = expected;
    }
    if (payload.assert_targets.includes("response_body")) {
      const jsonpath = String(dataSetForm.assert_response_jsonpath || "").trim();
      const expected = String(dataSetForm.assert_response_expected || "").trim();
      if (!jsonpath) throw new Error("请填写响应结果 JSONPath");
      if (!expected) throw new Error("请填写响应结果期望值");
      payload.assert_response_jsonpath = jsonpath;
      payload.assert_response_expected = expected;
    }
  } else {
    payload.assert_targets = [];
  }
  return payload;
}

async function saveDataSet() {
  let payload;
  try {
    payload = buildDataSetPayload();
  } catch (e) {
    notify("err", e?.message || "数据集校验失败");
    return;
  }
  try {
    let savedId = Number(dataSetForm.id || 0) || null;
    if (dataSetForm.id) {
      await api.updateDataSet(dataSetForm.id, payload);
      notify("ok", "数据集已更新");
    } else {
      const { data } = await api.createDataSet(payload);
      dataSetForm.id = Number(data?.id || 0) || null;
      savedId = dataSetForm.id;
      notify("ok", "数据集已创建");
    }
    if (payload.enabled && savedId) {
      await loadDataSets();
      await ensureSingleEnabledDataSet(savedId);
    }
    await loadDataSets();
    applyDefaultDataSetSelection();
    showDataSetEditor.value = false;
  } catch (e) {
    notify("err", e?.response?.data?.detail || "保存数据集失败");
  }
}

async function removeDataSet(item) {
  const dataSetId = Number(item?.id || 0);
  if (!dataSetId) return;
  const ok = props.confirmBox
    ? await props.confirmBox({ title: "删除数据集", message: `确认删除数据集「${item?.name || dataSetId}」吗？`, danger: true })
    : false;
  if (!ok) return;
  try {
    await api.deleteDataSet(dataSetId);
    if (Number(scenarioForm.data_set || 0) === dataSetId) scenarioForm.data_set = null;
    notify("ok", "数据集已删除");
    await loadDataSets();
    applyDefaultDataSetSelection();
  } catch (e) {
    notify("err", e?.response?.data?.detail || "删除数据集失败");
  }
}

function makeStep(index = 0) {
  return {
    step_order: index + 1,
    step_name: `步骤${index + 1}`,
    test_case: props.cases[0]?.id ?? null,
    enabled: true,
    continue_on_fail: false,
    assertions_text: "",
    assertions_enabled: false,
    assertions_expanded: false,
    assertions_mode: "table",
    assertion_rows: [],
    assert_status: "",
    assert_contains: "",
    pre_processors_text: "",
    post_processors_text: "",
    pre_processors_enabled: false,
    post_processors_enabled: false,
    pre_processors_expanded: false,
    post_processors_expanded: false,
    pre_processors_mode: "table",
    post_processors_mode: "table",
    pre_processor_rows: [],
    post_processor_rows: [],
    overrides_text: "",
    overrides_enabled: false,
    override_method: "GET",
    override_base_url: "",
    override_path: "",
    override_headers_text: "{}",
    override_params_text: "{}",
    override_body_json_text: "{}",
    override_body_text: "",
    collapsed: true
  };
}

function buildCopyName(name, existingNames = []) {
  const source = String(name || "").trim() || "未命名场景";
  const names = new Set((existingNames || []).map((item) => String(item || "").trim()));
  const base = source.replace(/（副本\d*）$/u, "").replace(/\(副本\d*\)$/u, "").trim() || source;
  let candidate = `${base}（副本）`;
  let index = 2;
  while (names.has(candidate)) {
    candidate = `${base}（副本${index}）`;
    index += 1;
  }
  return candidate;
}

function cloneStepData(step, index = 0) {
  const copy = JSON.parse(JSON.stringify(step || makeStep(index)));
  copy.step_name = buildCopyName(copy.step_name || `步骤${index + 1}`, []);
  copy.collapsed = true;
  return copy;
}

function getCaseById(caseId) {
  const id = Number(caseId || 0);
  if (!id) return null;
  return (props.cases || []).find((item) => Number(item.id) === id) || null;
}

function parseJsonLoose(text, fallback = {}) {
  const raw = String(text || "").trim();
  if (!raw) return fallback;
  try {
    const value = JSON.parse(raw);
    return value && typeof value === "object" ? value : fallback;
  } catch {
    return fallback;
  }
}

function loadStepOverridesEditor(step) {
  const base = getCaseById(step?.test_case) || {};
  const overrides = parseJsonLoose(step?.overrides_text, {});
  step.overrides_enabled = Boolean(Object.keys(overrides).length) || !!step.overrides_enabled;
  step.override_method = String(overrides.method ?? base.method ?? "GET").toUpperCase();
  step.override_base_url = String(overrides.base_url ?? base.base_url ?? "");
  step.override_path = String(overrides.path ?? base.path ?? "");
  step.override_headers_text = prettyJson(overrides.headers ?? base.headers ?? {});
  step.override_params_text = prettyJson(overrides.params ?? base.params ?? {});
  step.override_body_json_text = prettyJson(overrides.body_json ?? base.body_json ?? {});
  step.override_body_text = String(overrides.body_text ?? base.body_text ?? "");
}

function syncStepOverridesText(step) {
  if (!step?.overrides_enabled) {
    step.overrides_text = "";
    return;
  }
  const overrides = {
    method: String(step.override_method || "GET").toUpperCase(),
    base_url: String(step.override_base_url || ""),
    path: String(step.override_path || ""),
    headers: parseJsonLoose(step.override_headers_text, {}),
    params: parseJsonLoose(step.override_params_text, {}),
    body_json: parseJsonLoose(step.override_body_json_text, {}),
    body_text: String(step.override_body_text || "")
  };
  step.overrides_text = JSON.stringify(overrides, null, 2);
}

const assertionOps = [
  { value: "eq", label: "等于" },
  { value: "ne", label: "不等于" },
  { value: "contains", label: "包含" },
  { value: "not_contains", label: "不包含" },
  { value: "gt", label: "大于" },
  { value: "ge", label: "大于等于" },
  { value: "lt", label: "小于" },
  { value: "le", label: "小于等于" },
  { value: "exists", label: "存在" },
  { value: "not_exists", label: "不存在" },
  { value: "empty", label: "为空" },
  { value: "not_empty", label: "非空" }
];

function needsExpected(op) {
  return !["exists", "not_exists", "empty", "not_empty"].includes(op);
}

function defaultAssertionRow() {
  return {
    enabled: true,
    name: "",
    source: "body_json",
    op: "eq",
    path: "$.code",
    expected: "0"
  };
}

function normalizeExpectedInput(raw) {
  const text = String(raw ?? "").trim();
  if (text === "") return "";
  if (text === "true") return true;
  if (text === "false") return false;
  if (text === "null") return null;
  if (/^-?\d+(\.\d+)?$/.test(text)) return Number(text);
  if ((text.startsWith("{") && text.endsWith("}")) || (text.startsWith("[") && text.endsWith("]"))) {
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }
  return text;
}

function assertionRowsToList(rows) {
  const result = [];
  for (const row of rows || []) {
    if (!row.enabled) continue;
    const source = String(row.source || "").trim();
    const op = String(row.op || "eq").trim();
    if (!source || !op) continue;
    const item = { source, op };
    const name = String(row.name || "").trim();
    if (name) item.name = name;
    const path = String(row.path || "").trim();
    if (path) {
      if (source === "headers") item.header = path;
      else if (source === "body_json") item.jsonpath = path;
      else item.path = path;
    }
    if (needsExpected(op)) item.expected = normalizeExpectedInput(row.expected);
    result.push(item);
  }
  return result;
}

function assertionListToRows(list) {
  if (!Array.isArray(list) || !list.length) return [defaultAssertionRow()];
  return list.map((item) => ({
    enabled: true,
    name: String(item?.name || ""),
    source: String(item?.source || "body_json"),
    op: String(item?.op || "eq"),
    path: String(item?.header || item?.jsonpath || item?.path || ""),
    expected:
      item && Object.prototype.hasOwnProperty.call(item, "expected")
        ? (typeof item.expected === "string" ? item.expected : JSON.stringify(item.expected))
        : ""
  }));
}

function splitStepAssertions(step) {
  const parsed = parseJsonText(step.assertions_text, "assertions");
  const list = Array.isArray(parsed) ? parsed : [];
  const remain = [];
  step.assert_status = "";
  step.assert_contains = "";
  for (const rule of list) {
    const source = String(rule?.source || "");
    const op = String(rule?.op || "");
    if (source === "status_code" && op === "eq" && step.assert_status === "") {
      step.assert_status = rule?.expected === undefined || rule?.expected === null ? "" : String(rule.expected);
      continue;
    }
    if (source === "body_text" && op === "contains" && step.assert_contains === "") {
      step.assert_contains = rule?.expected === undefined || rule?.expected === null ? "" : String(rule.expected);
      continue;
    }
    remain.push(rule);
  }
  step.assertion_rows = assertionListToRows(remain);
}

function syncStepAssertionsText(step) {
  const customList = assertionRowsToList(step.assertion_rows);
  const finalList = [];
  if (String(step.assert_status || "").trim()) {
    finalList.push({
      name: "状态码断言",
      source: "status_code",
      op: "eq",
      expected: Number(step.assert_status)
    });
  }
  if (String(step.assert_contains || "").trim()) {
    finalList.push({
      name: "响应体包含",
      source: "body_text",
      op: "contains",
      expected: String(step.assert_contains).trim()
    });
  }
  finalList.push(...customList);
  step.assertions_text = finalList.length ? JSON.stringify(finalList, null, 2) : "";
}

function switchStepAssertionsMode(step, mode = "table") {
  step.assertions_mode = mode;
  if (mode === "table") splitStepAssertions(step);
}

function addStepAssertionRow(step) {
  step.assertion_rows.push(defaultAssertionRow());
  syncStepAssertionsText(step);
}

function removeStepAssertionRow(step, index) {
  step.assertion_rows.splice(index, 1);
  if (!step.assertion_rows.length) step.assertion_rows.push(defaultAssertionRow());
  syncStepAssertionsText(step);
}

function onProcessorEnabledChange(step, kind = "pre") {
  if (kind === "pre") {
    step.pre_processors_expanded = Boolean(step.pre_processors_enabled);
    return;
  }
  step.post_processors_expanded = Boolean(step.post_processors_enabled);
}

function onAssertionsEnabledChange(step) {
  step.assertions_expanded = Boolean(step.assertions_enabled);
}

const preProcessorTypeOptions = [
  { value: "set_var", label: "设置变量" },
  { value: "timestamp", label: "时间戳" },
  { value: "datetime", label: "日期时间" },
  { value: "random_phone", label: "随机手机号" },
  { value: "uuid", label: "UUID" },
  { value: "transform", label: "变量转换" }
];

const varTypeOptions = [
  { value: "temp", label: "临时变量" },
  { value: "global", label: "全局变量" },
  { value: "environment", label: "环境变量" }
];

const extractFromOptions = [
  { value: "response_json", label: "response json" },
  { value: "response_text", label: "response text" },
  { value: "response_xml", label: "response xml" },
  { value: "response_header", label: "response header" },
  { value: "response_cookie", label: "response cookie" }
];

const extractScopeOptions = [
  { value: "whole", label: "整个数据返回" },
  { value: "jsonpath", label: "提取部分（JSONPath）" }
];
const dataSetAssertTargetOptions = [
  { value: "status_code", label: "状态码" },
  { value: "request_headers", label: "请求头(JSONPath)" },
  { value: "response_body", label: "响应结果(JSONPath)" }
];

function defaultProcessorRow(kind = "pre") {
  return {
    enabled: true,
    name: "",
    type: kind === "pre" ? "set_var" : "extract_var",
    target: "",
    variable_type: "temp",
    extract_from: "response_json",
    extract_scope: "whole",
    extract_expr: "$.data.token",
    value: "",
    op: "base64_encode",
    arg: "",
    ms: false,
    format: "%Y-%m-%d %H:%M:%S",
    jsonpath: "$.data.token",
    header: "X-Trace-Id",
    pattern: "",
    source: "body_text",
    group: 1
  };
}

function processorListToRows(list, kind = "pre") {
  if (!Array.isArray(list) || !list.length) return [defaultProcessorRow(kind)];
  return list.map((item) => ({
    enabled: true,
    name: String(item?.name || ""),
    type: kind === "pre" ? String(item?.type || "set_var") : String(item?.type || "extract_var"),
    target: String(item?.target || item?.var || ""),
    variable_type: String(item?.variable_type || item?.var_type || "temp"),
    extract_from: String(item?.extract_from || item?.source || "response_json"),
    extract_scope: String(item?.extract_scope || item?.scope || "whole"),
    extract_expr: String(item?.extract_expr || item?.jsonpath || item?.path || ""),
    value: item?.value === undefined || item?.value === null ? "" : String(item.value),
    op: String(item?.op || "base64_encode"),
    arg: item?.arg === undefined || item?.arg === null ? "" : String(item.arg),
    ms: Boolean(item?.ms),
    format: String(item?.format || "%Y-%m-%d %H:%M:%S"),
    jsonpath: String(item?.jsonpath || item?.path || "$.data.token"),
    header: String(item?.header || item?.path || "X-Trace-Id"),
    pattern: String(item?.pattern || item?.regex || ""),
    source: String(item?.source || "body_text"),
    group: Number(item?.group || 1)
  }));
}

function processorRowsToList(rows, kind = "pre") {
  const result = [];
  for (const row of rows || []) {
    if (!row.enabled) continue;
    const type = String(row.type || "").trim();
    const target = String(row.target || "").trim();
    if (!type || !target) continue;
    const item = { type, target };
    const name = String(row.name || "").trim();
    if (kind !== "post" && name) item.name = name;

    if (type === "extract_var") {
      item.variable_type = row.variable_type || "temp";
      item.extract_from = row.extract_from || "response_json";
      item.extract_scope = row.extract_scope || "whole";
      if (String(row.extract_expr || "").trim()) {
        item.extract_expr = String(row.extract_expr || "").trim();
      }
    }
    if (type === "set_var") item.value = row.value ?? "";
    if (type === "timestamp") item.ms = Boolean(row.ms);
    if (type === "datetime") item.format = row.format || "%Y-%m-%d %H:%M:%S";
    if (type === "transform") {
      item.value = row.value ?? "";
      item.op = row.op || "base64_encode";
      if (String(row.arg || "").trim()) item.arg = row.arg;
    }
    if (type === "json_extract") item.jsonpath = row.jsonpath || "$.data.token";
    if (type === "header_extract") item.header = row.header || "X-Trace-Id";
    if (type === "regex_extract") {
      item.pattern = row.pattern || "";
      item.source = row.source || "body_text";
      item.group = Number(row.group || 1);
    }
    result.push(item);
  }
  return result;
}

function refreshStepProcessorRows(step) {
  const preParsed = parseJsonText(step.pre_processors_text, "pre_processors");
  const postParsed = parseJsonText(step.post_processors_text, "post_processors");
  step.pre_processor_rows = processorListToRows(preParsed, "pre");
  step.post_processor_rows = processorListToRows(postParsed, "post");
}

function syncStepProcessorsText(step, kind = "pre") {
  const isPre = kind === "pre";
  const rows = isPre ? step.pre_processor_rows : step.post_processor_rows;
  const list = processorRowsToList(rows, kind);
  if (isPre) step.pre_processors_text = list.length ? JSON.stringify(list, null, 2) : "";
  else step.post_processors_text = list.length ? JSON.stringify(list, null, 2) : "";
}

function switchStepProcessorMode(step, kind = "pre", mode = "table") {
  if (kind === "pre") step.pre_processors_mode = mode;
  else step.post_processors_mode = mode;
  if (mode === "table") refreshStepProcessorRows(step);
}

function addStepProcessorRow(step, kind = "pre") {
  if (kind === "pre") {
    step.pre_processor_rows.push(defaultProcessorRow("pre"));
    syncStepProcessorsText(step, "pre");
  } else {
    step.post_processor_rows.push(defaultProcessorRow("post"));
    syncStepProcessorsText(step, "post");
  }
}

function removeStepProcessorRow(step, kind = "pre", index = 0) {
  const rows = kind === "pre" ? step.pre_processor_rows : step.post_processor_rows;
  rows.splice(index, 1);
  if (!rows.length) rows.push(defaultProcessorRow(kind));
  syncStepProcessorsText(step, kind);
}

function normalizeOrders() {
  scenarioForm.steps.forEach((step, idx) => { step.step_order = idx + 1; });
}

function toggleGroup(groupId) {
  const key = String(groupId || 0);
  collapsedGroups[key] = !collapsedGroups[key];
}

function toggleModuleMore(moduleId) {
  const id = Number(moduleId || 0);
  if (!id) return;
  moreOpenModuleId.value = Number(moreOpenModuleId.value || 0) === id ? null : id;
}

function closeModuleMore() {
  moreOpenModuleId.value = null;
}

function onMoreCreateSubModule(row) {
  closeModuleMore();
  createSubModule(row);
}

function onMoreEditModule(row) {
  closeModuleMore();
  editModule(row);
}

function onMoreDeleteModule(row) {
  closeModuleMore();
  deleteModule(row);
}

function selectModule(group) {
  if (!group?.id) {
    selectedModuleId.value = null;
    return;
  }
  selectedModuleId.value = Number(group.id);
  selectedModuleScenarioIds.value = [];
  selectedScenarioId.value = null;
  scenarioEditorVisible.value = false;
  closeStepEditor();
}

function createModule() {
  emit("create-module", null);
}

function createSubModule(group) {
  if (!group?.id) return;
  emit("create-module", Number(group.id));
}

function editModule(group) {
  if (!group?.id) return;
  emit("edit-module", { id: group.id, name: group.name, parent_id: group.parent_id || null, description: group.description || null });
}

function deleteModule(group) {
  if (!group?.id) return;
  emit("delete-module", { id: group.id, name: group.name });
}

function onModuleDragStart(group) {
  if (!group?.id) return;
  moduleDragId.value = Number(group.id);
}

function onModuleDragEnd() {
  moduleDragId.value = null;
}

function onModuleDrop(targetGroup) {
  const sourceId = Number(moduleDragId.value || 0);
  const targetId = Number(targetGroup?.id || 0);
  moduleDragId.value = null;
  if (!sourceId || !targetId || sourceId === targetId) return;
  emit("move-module", { id: sourceId, parent_id: targetId });
}

function onModuleDropRoot() {
  const sourceId = Number(moduleDragId.value || 0);
  moduleDragId.value = null;
  if (!sourceId) return;
  emit("move-module", { id: sourceId, parent_id: null });
}

function scenarioModuleId(item) {
  return Number(item?.module_id || item?.module || 0) || null;
}

function onScenarioDragStart(item) {
  scenarioDrag.sourceId = Number(item?.id || 0) || null;
}

function onScenarioDragOver(item, event) {
  event.preventDefault();
  scenarioDrag.overId = Number(item?.id || 0) || null;
}

async function onScenarioDrop(targetItem) {
  const sourceId = Number(scenarioDrag.sourceId || 0);
  const targetId = Number(targetItem?.id || 0);
  scenarioDrag.sourceId = null;
  scenarioDrag.overId = null;
  if (!sourceId || !targetId || sourceId === targetId) return;

  const source = scenarios.value.find((s) => Number(s.id) === sourceId);
  const target = scenarios.value.find((s) => Number(s.id) === targetId);
  if (!source || !target) return;
  if (scenarioModuleId(source) !== scenarioModuleId(target)) {
    return notify("err", "仅支持同一模块下场景排序");
  }

  const sameModule = (scenarios.value || [])
    .filter((s) => scenarioModuleId(s) === scenarioModuleId(source))
    .slice();
  const from = sameModule.findIndex((s) => Number(s.id) === sourceId);
  const to = sameModule.findIndex((s) => Number(s.id) === targetId);
  if (from < 0 || to < 0) return;
  const [moved] = sameModule.splice(from, 1);
  sameModule.splice(to, 0, moved);
  const orderedIds = sameModule.map((s) => Number(s.id));
  try {
    await api.reorderScenarios({ ordered_ids: orderedIds });
    await loadScenarios();
    notify("ok", "场景顺序已更新");
  } catch (e) {
    notify("err", e?.response?.data?.detail || "场景排序失败");
  }
}

function onScenarioDragEnd() {
  scenarioDrag.sourceId = null;
  scenarioDrag.overId = null;
}

async function runModule(group) {
  if (!group?.id) return;
  try {
    const { data } = await api.runModuleScenarios(group.id, {
      param_enabled: !!batchParamEnabled.value,
      environment_id: batchEnvironmentId.value ? Number(batchEnvironmentId.value) : null,
    });
    const scenarioCount = Number(data?.scenario_count || 0);
    const passCount = Number(data?.pass_count || 0);
    const failCount = Number(data?.fail_count || 0);
    notify("ok", `模块执行完成：场景 ${scenarioCount}，通过 ${passCount}，失败 ${failCount}`);
    const latestHistory = Array.isArray(data?.histories) && data.histories.length ? data.histories[data.histories.length - 1] : null;
    if (latestHistory?.id) openReportPage(latestHistory.id);
  } catch (e) {
    notify("err", e?.response?.data?.detail || "执行模块失败");
  }
}

function openReportPage(historyId = null) {
  emit("open-report", {
    scenarioId: scenarioForm.id || null,
    historyId: historyId || null
  });
}

async function runScenarioDirect(item) {
  const scenarioId = Number(item?.id || 0);
  if (!scenarioId) return;
  scenarioRunLoading.value = true;
  try {
    const { data } = await api.runScenario(scenarioId);
    notify("ok", `场景执行完成：${data.history.success ? "PASS" : "FAIL"}`);
    await loadScenarioHistories(scenarioId);
    emit("open-report", {
      scenarioId,
      historyId: data?.history?.id || null
    });
  } catch (e) {
    notify("err", e?.response?.data?.detail || "场景执行失败");
  } finally {
    scenarioRunLoading.value = false;
  }
}

function resetScenarioForm(moduleId = null) {
  closeStepEditor();
  scenarioForm.id = null;
  scenarioForm.name = "";
  scenarioForm.description = "";
  scenarioForm.module = moduleId ? Number(moduleId) : (props.modules?.[0]?.id ? Number(props.modules[0].id) : null);
  scenarioForm.param_enabled = false;
  scenarioForm.data_set = null;
  scenarioForm.data_mode = "all";
  scenarioForm.data_pick = "";
  scenarioForm.param_retry_count = 0;
  scenarioForm.stop_on_failure = true;
  scenarioForm.steps = [makeStep(0)];
}

function openCreateScenario(moduleId = null) {
  closeStepEditor();
  scenarioEditorVisible.value = true;
  selectedScenarioId.value = null;
  selectedModuleId.value = moduleId ? Number(moduleId) : null;
  resetScenarioForm(moduleId);
}

function copyScenarioToEditor(item) {
  if (!item) return;
  scenarioToForm(item);
  scenarioForm.id = null;
  selectedScenarioId.value = null;
  scenarioForm.name = buildCopyName(
    scenarioForm.name,
    (scenarios.value || []).map((scenario) => scenario?.name)
  );
  notify("ok", "已复制场景到编辑器，请确认后保存为新场景");
}

function scenarioToForm(item) {
  closeStepEditor();
  scenarioEditorVisible.value = true;
  scenarioForm.id = item.id ?? null;
  scenarioForm.name = item.name || "";
  scenarioForm.description = item.description || "";
  scenarioForm.module = item.module ?? item.module_id ?? null;
  scenarioForm.param_enabled = item.param_enabled ?? false;
  scenarioForm.data_set = item.data_set ?? item.data_set_id ?? null;
  scenarioForm.data_mode = item.data_mode || "all";
  scenarioForm.data_pick = item.data_pick || "";
  scenarioForm.param_retry_count = Number(item.param_retry_count || 0);
  scenarioForm.stop_on_failure = item.stop_on_failure ?? true;
  scenarioForm.steps = (item.steps || []).map((s, idx) => ({
    step_order: s.step_order ?? idx + 1,
    step_name: s.step_name || `步骤${idx + 1}`,
    test_case: s.test_case ?? null,
    enabled: s.enabled ?? true,
    continue_on_fail: s.continue_on_fail ?? false,
    assertions_text: s.assertions ? JSON.stringify(s.assertions, null, 2) : "",
    assertions_enabled: Array.isArray(s.assertions) && s.assertions.length > 0,
    assertions_expanded: false,
    assertions_mode: "table",
    assertion_rows: [],
    assert_status: "",
    assert_contains: "",
    pre_processors_text: s.pre_processors ? JSON.stringify(s.pre_processors, null, 2) : "",
    post_processors_text: s.post_processors ? JSON.stringify(s.post_processors, null, 2) : "",
    pre_processors_enabled: Array.isArray(s.pre_processors) && s.pre_processors.length > 0,
    post_processors_enabled: Array.isArray(s.post_processors) && s.post_processors.length > 0,
    pre_processors_expanded: false,
    post_processors_expanded: false,
    pre_processors_mode: "table",
    post_processors_mode: "table",
    pre_processor_rows: [],
    post_processor_rows: [],
    overrides_text: s.overrides ? JSON.stringify(s.overrides, null, 2) : "",
    overrides_enabled: !!s.overrides,
    override_method: "GET",
    override_base_url: "",
    override_path: "",
    override_headers_text: "{}",
    override_params_text: "{}",
    override_body_json_text: "{}",
    override_body_text: "",
    collapsed: true
  }));
  if (!scenarioForm.steps.length) scenarioForm.steps = [makeStep(0)];
  scenarioForm.steps.forEach((step) => {
    refreshStepProcessorRows(step);
    splitStepAssertions(step);
    loadStepOverridesEditor(step);
  });
  normalizeOrders();
}

function addStep() {
  const step = makeStep(scenarioForm.steps.length);
  refreshStepProcessorRows(step);
  splitStepAssertions(step);
  scenarioForm.steps.push(step);
}

function copyStep(index) {
  const source = scenarioForm.steps[index];
  if (!source) return;
  const step = cloneStepData(source, index + 1);
  refreshStepProcessorRows(step);
  splitStepAssertions(step);
  loadStepOverridesEditor(step);
  scenarioForm.steps.splice(index + 1, 0, step);
  if (stepEditorIndex.value !== null && stepEditorIndex.value > index) {
    stepEditorIndex.value += 1;
  }
  normalizeOrders();
  notify("ok", "步骤已复制");
}

function removeStep(index) {
  scenarioForm.steps.splice(index, 1);
  if (stepEditorIndex.value === index) stepEditorIndex.value = null;
  if (stepEditorIndex.value !== null && stepEditorIndex.value > index) {
    stepEditorIndex.value -= 1;
  }
  if (stepEditorIndex.value === null) {
    stepEditorDraft.value = null;
  }
  if (!scenarioForm.steps.length) scenarioForm.steps.push(makeStep(0));
  normalizeOrders();
}

function openStepEditor(index) {
  stepEditorIndex.value = index;
  stepCaseEntryExpanded.value = false;
  stepCaseEntryMode.value = "view";
  const source = scenarioForm.steps[index];
  if (!source) {
    stepEditorDraft.value = null;
    return;
  }
  const draft = JSON.parse(JSON.stringify(source));
  refreshStepProcessorRows(draft);
  splitStepAssertions(draft);
  loadStepOverridesEditor(draft);
  stepEditorDraft.value = draft;
}

function closeStepEditor() {
  stepEditorIndex.value = null;
  stepEditorDraft.value = null;
  stepCaseEntryExpanded.value = false;
  stepCaseEntryMode.value = "view";
}

function openCurrentStepCase(mode = "edit") {
  stepCaseEntryExpanded.value = true;
  stepCaseEntryMode.value = mode === "edit" ? "edit" : "view";
  if (stepCaseEntryMode.value === "edit" && !Number(editingStep.value?.test_case || 0)) {
    notify("err", "当前步骤未选择引用接口");
  }
}

async function saveStepEditor() {
  if (stepEditorIndex.value === null || !stepEditorDraft.value) return;
  const draft = stepEditorDraft.value;
  try {
    if (draft.pre_processors_mode === "table") syncStepProcessorsText(draft, "pre");
    if (draft.post_processors_mode === "table") syncStepProcessorsText(draft, "post");
    if (draft.assertions_mode === "table") syncStepAssertionsText(draft);
    syncStepOverridesText(draft);
  } catch (e) {
    notify("err", e?.message || "步骤接口数据格式错误");
    return;
  }
  scenarioForm.steps.splice(stepEditorIndex.value, 1, draft);
  if (!scenarioForm.id) {
    notify("ok", "步骤配置已保存到当前编辑状态，请保存场景后生效");
    closeStepEditor();
    return;
  }
  if (stepEditorSaving.value) return;
  stepEditorSaving.value = true;
  try {
    const payload = buildScenarioPayload();
    const { data } = await api.updateScenario(scenarioForm.id, payload);
    scenarioToForm(data);
    selectedScenarioId.value = data.id;
    await loadScenarios();
    await loadScenarioHistories(selectedScenarioId.value);
    notify("ok", "步骤配置已保存");
    closeStepEditor();
  } catch (e) {
    notify("err", e?.response?.data?.detail || "保存步骤配置失败");
  } finally {
    stepEditorSaving.value = false;
  }
}

function onStepDragStart(index) { dragState.fromIndex = index; }
function onStepDragOver(index, event) { event.preventDefault(); dragState.overIndex = index; }
function onStepDragEnd() { dragState.fromIndex = null; dragState.overIndex = null; }
function onStepDrop(index) {
  const from = dragState.fromIndex;
  if (from === null || from === index) return onStepDragEnd();
  const [moved] = scenarioForm.steps.splice(from, 1);
  scenarioForm.steps.splice(index, 0, moved);
  normalizeOrders();
  onStepDragEnd();
}

function buildScenarioPayload() {
  return buildScenarioPayloadWithOptions();
}

function normalizeScenarioStepPayload(step, idx) {
  const testCaseId = Number(step.test_case);
  if (!Number.isFinite(testCaseId) || testCaseId <= 0) throw new Error(`步骤${idx + 1} 未选择有效接口`);
  if (step.pre_processors_mode === "table") syncStepProcessorsText(step, "pre");
  if (step.post_processors_mode === "table") syncStepProcessorsText(step, "post");
  if (step.assertions_mode === "table") syncStepAssertionsText(step);
  syncStepOverridesText(step);
  return {
    step_order: Number(step.step_order || idx + 1),
    step_name: step.step_name?.trim() || `步骤${idx + 1}`,
    test_case: testCaseId,
    enabled: !!step.enabled,
    continue_on_fail: !!step.continue_on_fail,
    assertions: step.assertions_enabled
      ? parseJsonText(step.assertions_text, `步骤${idx + 1} assertions`)
      : null,
    pre_processors: step.pre_processors_enabled
      ? parseJsonText(step.pre_processors_text, `步骤${idx + 1} pre_processors`)
      : null,
    post_processors: step.post_processors_enabled
      ? parseJsonText(step.post_processors_text, `步骤${idx + 1} post_processors`)
      : null,
    overrides: step.overrides_enabled
      ? parseJsonText(step.overrides_text, `步骤${idx + 1} overrides`)
      : null
  };
}

function buildScenarioPayloadWithOptions(options = {}) {
  if (!scenarioForm.name.trim()) throw new Error("场景名称不能为空");
  if (!scenarioForm.steps.length) throw new Error("至少需要一个步骤");
  if (!scenarioForm.module) throw new Error("请选择所属模块");
  if (scenarioForm.param_enabled && !scenarioForm.data_set) throw new Error("启用参数化后必须选择数据集");
  if (scenarioForm.param_enabled) {
    const retryCount = Number(scenarioForm.param_retry_count || 0);
    if (!Number.isInteger(retryCount) || retryCount < 0 || retryCount > 10) {
      throw new Error("失败重试次数必须是 0-10 的整数");
    }
  }
  const stepsSource = (scenarioForm.steps || []).map((item) => JSON.parse(JSON.stringify(item)));
  if (options.stepDraft && Number.isInteger(options.stepIndex) && options.stepIndex >= 0 && options.stepIndex < stepsSource.length) {
    stepsSource.splice(options.stepIndex, 1, JSON.parse(JSON.stringify(options.stepDraft)));
  }
  return {
    scenario_id: scenarioForm.id ? Number(scenarioForm.id) : null,
    name: scenarioForm.name.trim(),
    description: scenarioForm.description.trim() || null,
    module: scenarioForm.module ? Number(scenarioForm.module) : null,
    param_enabled: !!scenarioForm.param_enabled,
    data_set: scenarioForm.param_enabled ? (scenarioForm.data_set ? Number(scenarioForm.data_set) : null) : null,
    data_mode: scenarioForm.param_enabled ? String(scenarioForm.data_mode || "all") : "all",
    data_pick: scenarioForm.param_enabled ? (String(scenarioForm.data_pick || "").trim() || null) : null,
    param_retry_count: scenarioForm.param_enabled ? Number(scenarioForm.param_retry_count || 0) : 0,
    stop_on_failure: !!scenarioForm.stop_on_failure,
    steps: stepsSource.map((step, idx) => normalizeScenarioStepPayload(step, idx))
  };
}

async function loadScenarios() {
  scenarioLoading.value = true;
  try {
    scenarios.value = unwrapListPayload((await api.listScenarios(props.projectId)).data);
    if (selectedScenarioId.value && !scenarios.value.some((item) => item.id === selectedScenarioId.value)) {
      selectedScenarioId.value = null;
      scenarioEditorVisible.value = false;
      resetScenarioForm();
    }
  }
  catch (e) { notify("err", e?.response?.data?.detail || "加载场景失败"); }
  finally { scenarioLoading.value = false; }
}

async function saveScenario() {
  let payload;
  try { payload = buildScenarioPayload(); } catch (e) { return notify("err", e.message || "场景校验失败"); }
  try {
    if (scenarioForm.id) {
      const { data } = await api.updateScenario(scenarioForm.id, payload);
      scenarioToForm(data);
      selectedScenarioId.value = data.id;
      notify("ok", "场景已更新");
    } else {
      const { data } = await api.createScenario(payload);
      scenarioToForm(data);
      selectedScenarioId.value = data.id;
      notify("ok", "场景已创建");
    }
    await loadScenarios();
    await loadScenarioHistories(selectedScenarioId.value);
  } catch (e) { notify("err", e?.response?.data?.detail || "保存场景失败"); }
}

async function saveAsNewScenario() {
  let payload;
  try {
    payload = buildScenarioPayload();
  } catch (e) {
    return notify("err", e.message || "场景校验失败");
  }
  payload.scenario_id = null;
  payload.name = buildCopyName(payload.name, (scenarios.value || []).map((item) => item?.name));
  try {
    const { data } = await api.createScenario(payload);
    scenarioToForm(data);
    selectedScenarioId.value = data.id;
    notify("ok", "已另存为新场景");
    await loadScenarios();
    await loadScenarioHistories(selectedScenarioId.value);
  } catch (e) {
    notify("err", e?.response?.data?.detail || "另存为新场景失败");
  }
}

function selectScenario(item) {
  selectedModuleId.value = item?.module_id ? Number(item.module_id) : (item?.module ? Number(item.module) : null);
  selectedScenarioId.value = item.id;
  scenarioToForm(item);
  loadScenarioHistories(item.id);
}

function toggleSelectAllModuleScenarios() {
  if (isAllModuleScenariosSelected.value) {
    selectedModuleScenarioIds.value = [];
    return;
  }
  selectedModuleScenarioIds.value = orderedSelectedModuleScenarios.value.map((item) => Number(item.id));
}

function syncSelectedModuleScenarioOrder() {
  const ids = (selectedModuleScenarios.value || []).map((item) => Number(item.id));
  const current = (selectedModuleScenarioOrder.value || []).filter((id) => ids.includes(Number(id)));
  for (const id of ids) {
    if (!current.includes(id)) current.push(id);
  }
  selectedModuleScenarioOrder.value = current;
}

function moveSelectedModuleScenario(index, offset) {
  const order = [...(selectedModuleScenarioOrder.value || [])];
  const target = index + offset;
  if (index < 0 || target < 0 || index >= order.length || target >= order.length) return;
  const [moved] = order.splice(index, 1);
  order.splice(target, 0, moved);
  selectedModuleScenarioOrder.value = order;
}

function reorderSelectedModuleScenario(from, to) {
  const order = [...(selectedModuleScenarioOrder.value || [])];
  if (from < 0 || to < 0 || from >= order.length || to >= order.length || from === to) return;
  const [moved] = order.splice(from, 1);
  order.splice(to, 0, moved);
  selectedModuleScenarioOrder.value = order;
}

function onSelectedScenarioDragStart(index) {
  selectedModuleScenarioDrag.fromIndex = index;
}

function onSelectedScenarioDragOver(index, event) {
  event.preventDefault();
  selectedModuleScenarioDrag.overIndex = index;
}

function onSelectedScenarioDragEnd() {
  selectedModuleScenarioDrag.fromIndex = null;
  selectedModuleScenarioDrag.overIndex = null;
}

function onSelectedScenarioDrop(index) {
  const from = selectedModuleScenarioDrag.fromIndex;
  if (from === null || from === index) return onSelectedScenarioDragEnd();
  // 拖拽只更新前端顺序，真正持久化由保存排序接口处理。
  reorderSelectedModuleScenario(from, index);
  onSelectedScenarioDragEnd();
}

async function deleteScenario(id) {
  const ok = props.confirmBox
    ? await props.confirmBox({ title: "删除场景", message: "确认删除该场景吗？", danger: true })
    : false;
  if (!ok) return;
  try {
    await api.deleteScenario(id);
    if (selectedScenarioId.value === id) {
      selectedScenarioId.value = null;
      scenarioEditorVisible.value = false;
      resetScenarioForm();
    }
    notify("ok", "场景已删除");
    await loadScenarios();
    await loadScenarioHistories();
  } catch (e) { notify("err", e?.response?.data?.detail || "删除场景失败"); }
}

async function runScenariosBatch(ids) {
  // 按前端当前顺序执行，便于复现串行依赖链（如 token 透传）。
  const orderedIds = (ids || []).map((item) => Number(item)).filter((id) => id > 0);
  if (!orderedIds.length) return;
  scenarioRunLoading.value = true;
  try {
    const { data } = await api.runScenariosBatch({
      ordered_ids: orderedIds,
      param_enabled: !!batchParamEnabled.value,
      environment_id: batchEnvironmentId.value ? Number(batchEnvironmentId.value) : null,
    });
    notify("ok", `批量执行完成：场景 ${data?.scenario_count || 0}，通过 ${data?.pass_count || 0}，失败 ${data?.fail_count || 0}`);
    const histories = Array.isArray(data?.histories) ? data.histories : [];
    const last = histories.length ? histories[histories.length - 1] : null;
    emit("open-report", {
      scenarioId: null,
      historyId: Number(last?.id || 0) || null,
      clearScenarioFilter: true
    });
  } catch (e) {
    notify("err", e?.response?.data?.detail || "批量执行失败");
  } finally {
    scenarioRunLoading.value = false;
  }
}

async function runSelectedModuleScenarios() {
  const selected = new Set((selectedModuleScenarioIds.value || []).map((item) => Number(item)));
  const orderedSelected = orderedSelectedModuleScenarios.value
    .map((item) => Number(item.id))
    .filter((id) => selected.has(id));
  await runScenariosBatch(orderedSelected);
}

async function runAllModuleScenarios() {
  await runScenariosBatch(orderedSelectedModuleScenarios.value.map((item) => Number(item.id)));
}

async function runScenarioNow() {
  if (!scenarioForm.id) return notify("err", "请先保存场景");
  scenarioRunLoading.value = true;
  try {
    const payload = scenarioForm.param_enabled
      ? {
          data_mode: scenarioForm.data_mode || "all",
          data_pick: String(scenarioForm.data_pick || "").trim() || null,
          param_retry_count: Number(scenarioForm.param_retry_count || 0)
        }
      : {};
    const { data } = await api.runScenario(scenarioForm.id, payload);
    notify("ok", `场景执行完成：${data.history.success ? "PASS" : "FAIL"}`);
    await loadScenarioHistories(scenarioForm.id);
    openReportPage(data?.history?.id || null);
  } catch (e) { notify("err", e?.response?.data?.detail || "场景执行失败"); }
  finally { scenarioRunLoading.value = false; }
}

function closeRuntimeInspector() {
  runtimeInspectorVisible.value = false;
  runtimeInspector.mode = "scenario_preview";
  runtimeInspector.title = "";
  runtimeInspector.summary = null;
  runtimeInspector.steps = [];
  runtimeInspector.scenarios = [];
  runtimeInspector.prerequisiteResults = [];
  runtimeInspector.stepResult = null;
  runtimeInspector.contextSnapshot = null;
}

async function previewScenarioNow() {
  let payload;
  try {
    payload = buildScenarioPayload();
  } catch (e) {
    return notify("err", e?.message || "场景预检失败");
  }
  scenarioPreviewLoading.value = true;
  try {
    const { data } = await api.previewScenario(payload);
    runtimeInspector.mode = "scenario_preview";
    runtimeInspector.title = "场景执行预检";
    runtimeInspector.summary = data?.summary || null;
    runtimeInspector.steps = Array.isArray(data?.steps) ? data.steps : [];
    runtimeInspector.scenarios = [];
    runtimeInspector.prerequisiteResults = [];
    runtimeInspector.stepResult = null;
    runtimeInspector.contextSnapshot = null;
    runtimeInspectorVisible.value = true;
    notify("ok", `预检完成：${runtimeInspector.steps.length} 个步骤`);
  } catch (e) {
    notify("err", e?.response?.data?.detail || "场景预检失败");
  } finally {
    scenarioPreviewLoading.value = false;
  }
}

async function debugCurrentStep() {
  if (stepEditorIndex.value === null || !stepEditorDraft.value) return notify("err", "请先打开一个步骤");
  let payload;
  try {
    payload = buildScenarioPayloadWithOptions({ stepDraft: stepEditorDraft.value, stepIndex: stepEditorIndex.value });
  } catch (e) {
    return notify("err", e?.message || "步骤调试失败");
  }
  stepDebugLoading.value = true;
  try {
    const { data } = await api.debugScenarioStep({
      ...payload,
      step_index: Number(stepEditorIndex.value || 0),
      include_previous: !!stepDebugIncludePrevious.value,
    });
    runtimeInspector.mode = "step_debug";
    runtimeInspector.title = `步骤调试：${stepEditorDraft.value?.step_name || `步骤${Number(stepEditorIndex.value || 0) + 1}`}`;
    runtimeInspector.summary = data?.summary || null;
    runtimeInspector.steps = [];
    runtimeInspector.scenarios = [];
    runtimeInspector.prerequisiteResults = Array.isArray(data?.prerequisite_results) ? data.prerequisite_results : [];
    runtimeInspector.stepResult = data?.step_result || null;
    runtimeInspector.contextSnapshot = data?.context_snapshot || null;
    runtimeInspectorVisible.value = true;
    notify("ok", data?.summary?.blocked ? "步骤调试已生成拦截结果" : "步骤调试完成");
  } catch (e) {
    notify("err", e?.response?.data?.detail || "步骤调试失败");
  } finally {
    stepDebugLoading.value = false;
  }
}

async function previewScenariosBatch(ids) {
  const orderedIds = (ids || []).map((item) => Number(item)).filter((id) => id > 0);
  if (!orderedIds.length) return notify("err", "请至少选择一个场景");
  batchPreviewLoading.value = true;
  try {
    const { data } = await api.previewScenariosBatch({
      ordered_ids: orderedIds,
      param_enabled: !!batchParamEnabled.value,
      environment_id: batchEnvironmentId.value ? Number(batchEnvironmentId.value) : null,
    });
    runtimeInspector.mode = "batch_preview";
    runtimeInspector.title = data?.summary?.report_name || `批量执行预检（${orderedIds.length}个场景）`;
    runtimeInspector.summary = data?.summary || null;
    runtimeInspector.steps = [];
    runtimeInspector.scenarios = Array.isArray(data?.scenarios) ? data.scenarios : [];
    runtimeInspector.prerequisiteResults = [];
    runtimeInspector.stepResult = null;
    runtimeInspector.contextSnapshot = null;
    runtimeInspectorVisible.value = true;
    notify("ok", `批量预检完成：${runtimeInspector.scenarios.length} 个场景`);
  } catch (e) {
    notify("err", e?.response?.data?.detail || "批量预检失败");
  } finally {
    batchPreviewLoading.value = false;
  }
}

async function previewSelectedModuleScenarios() {
  const selected = new Set((selectedModuleScenarioIds.value || []).map((item) => Number(item)));
  const orderedSelected = orderedSelectedModuleScenarios.value
    .map((item) => Number(item.id))
    .filter((id) => selected.has(id));
  await previewScenariosBatch(orderedSelected);
}

async function previewAllModuleScenarios() {
  await previewScenariosBatch(orderedSelectedModuleScenarios.value.map((item) => Number(item.id)));
}

async function loadScenarioHistories(scenarioId = null) {
  scenarioHistoryLoading.value = true;
  try { scenarioHistories.value = unwrapListPayload((await api.listScenarioHistories(scenarioId ?? selectedScenarioId.value ?? null)).data); }
  catch (e) { notify("err", e?.response?.data?.detail || "加载场景执行历史失败"); }
  finally { scenarioHistoryLoading.value = false; }
}

watch(() => props.cases, () => {
  if (scenarioEditorVisible.value && !scenarioForm.steps.length) resetScenarioForm();
}, { immediate: true });

watch(() => props.modules, (val) => {
  const moduleIds = new Set((val || []).map((item) => Number(item.id)));
  if (scenarioForm.module && !moduleIds.has(Number(scenarioForm.module))) {
    scenarioForm.module = val?.[0]?.id ? Number(val[0].id) : null;
  }
}, { immediate: true, deep: true });

watch(selectedModuleScenarios, () => {
  syncSelectedModuleScenarioOrder();
}, { immediate: true, deep: true });

watch(() => scenarioForm.module, () => {
  if (scenarioForm.data_set && !availableDataSets.value.some((item) => Number(item.id) === Number(scenarioForm.data_set))) {
    scenarioForm.data_set = null;
  }
});

watch(
  () => dataSetForm.source_type,
  (value) => {
    if (String(value || "") !== "table") return;
    if (!dataSetColumns.value.length) dataSetColumns.value = ["column_1"];
    if (!dataSetRows.value.length) addDataSetRow();
    syncDataSetRowsTextFromTable();
  }
);

watch(() => props.projectId, async () => {
  selectedModuleId.value = null;
  selectedModuleScenarioIds.value = [];
  batchEnvironmentId.value = null;
  selectedScenarioId.value = null;
  scenarioEditorVisible.value = false;
  resetScenarioForm();
  await Promise.all([loadScenarios(), loadScenarioHistories(), loadDataSets()]);
}, { immediate: true });

watch(executionEnvironments, (items) => {
  const validIds = new Set((items || []).map((item) => Number(item.id)));
  if (batchEnvironmentId.value && !validIds.has(Number(batchEnvironmentId.value))) {
    batchEnvironmentId.value = null;
  }
});

onMounted(() => {
  if (scenarioEditorVisible.value && !scenarioForm.steps.length) resetScenarioForm();
  scenarioForm.steps.forEach((step) => {
    refreshStepProcessorRows(step);
    splitStepAssertions(step);
  });
});
</script>

<template>
  <section class="automation-root">
    <div class="scenario-layout">
      <section class="card">
        <div class="card-head">
          <h3>场景列表</h3>
          <div class="actions-inline">
            <el-button class="icon-btn" title="新建场景" aria-label="新建场景" @click="openCreateScenario()">
              <Plus class="ep-icon" />
            </el-button>
            <el-button class="btn" @click="createModule">新增模块</el-button>
          </div>
        </div>
        <div class="case-list">
          <div class="module-drop-root" @dragover.prevent @drop="onModuleDropRoot">
            拖拽模块到这里设为顶级模块
          </div>
          <div v-for="row in moduleRows" :key="`${row.type}-${row.id}-${row.depth}`">
            <div
              v-if="row.type === 'module'"
              class="module-head"
              :class="{ active: selectedModuleId === row.id }"
              :style="{ paddingLeft: `${row.depth * 18}px` }"
              :draggable="!!row.id"
              @dragstart="onModuleDragStart(row)"
              @dragend="onModuleDragEnd"
              @dragover.prevent
              @drop="onModuleDrop(row)"
            >
              <el-button native-type="button" class="module-toggle" @click="selectModule(row); row.id && toggleGroup(row.id)">
                <span>{{ row.id ? (collapsedGroups[String(row.id)] ? "▸" : "▾") : "•" }}</span>
                <strong>{{ row.name }}</strong>
                <span class="module-scenario-count">场景 {{ Number(row.scenarioCount || 0) }}</span>
              </el-button>
              <div class="actions-inline">
                <el-button class="icon-btn" title="新建场景" aria-label="新建场景" @click="openCreateScenario(row.id || null)">
                  <Plus class="ep-icon" />
                </el-button>
                <div v-if="row.id" class="more-wrap" @click.stop>
                  <el-button class="icon-btn" title="更多操作" aria-label="更多操作" @click="toggleModuleMore(row.id)">
                    <MoreFilled class="ep-icon" />
                  </el-button>
                  <div v-if="Number(moreOpenModuleId || 0) === Number(row.id)" class="more-menu">
                    <el-button class="more-menu-item" @click="onMoreCreateSubModule(row)">新增子模块</el-button>
                    <el-button class="more-menu-item" @click="onMoreEditModule(row)">编辑</el-button>
                    <el-button class="more-menu-item danger" @click="onMoreDeleteModule(row)">删除</el-button>
                  </div>
                </div>
              </div>
            </div>
            <div
              v-else
              class="case-item"
              :class="{ active: selectedScenarioId === row.scenario.id, 'drag-over': scenarioDrag.overId === row.scenario.id }"
              :style="{ marginLeft: `${row.depth * 18}px` }"
              draggable="true"
              @dragstart="onScenarioDragStart(row.scenario)"
              @dragover="onScenarioDragOver(row.scenario, $event)"
              @drop="onScenarioDrop(row.scenario)"
              @dragend="onScenarioDragEnd"
            >
            <div class="case-main" @click="selectScenario(row.scenario)">
              <div class="scenario-inline">
                <span class="title">{{ row.scenario.name }}</span>
                <span class="meta scenario-step-count">步骤数：{{ (row.scenario.steps || []).length }}</span>
              </div>
            </div>
            <div class="case-ops">
              <el-button class="icon-btn" title="编辑场景" aria-label="编辑场景" @click="selectScenario(row.scenario)">
                <Edit class="ep-icon" />
              </el-button>
              <el-button class="icon-btn" title="复制场景" aria-label="复制场景" @click="copyScenarioToEditor(row.scenario)">
                <DocumentCopy class="ep-icon" />
              </el-button>
              <el-button class="icon-btn danger" title="删除场景" aria-label="删除场景" @click="deleteScenario(row.scenario.id)">
                <Delete class="ep-icon" />
              </el-button>
            </div>
            </div>
          </div>
          <div v-if="!moduleRows.length" class="empty">暂无场景</div>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <template v-if="scenarioEditorVisible">
            <div><h3>测试步骤</h3><div class="sub">拖拽排序、变量提取、前置/后置处理器、业务断言</div></div>
            <div class="actions-inline">
              <el-button class="btn" :disabled="dataSetLoading" @click="openDataSetManager">
                {{ dataSetLoading ? "加载中..." : "测试集管理" }}
              </el-button>
              <el-button class="btn primary" @click="saveScenario">保存场景</el-button>
              <el-button class="btn" @click="saveAsNewScenario">另存为新场景</el-button>
              <el-button class="btn run" :disabled="scenarioPreviewLoading" @click="previewScenarioNow">{{ scenarioPreviewLoading ? "预检中..." : "执行预检" }}</el-button>
              <el-button class="btn run" :disabled="scenarioRunLoading" @click="runScenarioNow">{{ scenarioRunLoading ? "执行中..." : "执行场景" }}</el-button>
              <el-button class="btn" :disabled="!scenarioForm.id" @click="openReportPage()">查看报告</el-button>
            </div>
          </template>
          <template v-else>
            <div>
              <h3>自动化测试</h3>
              <div class="sub" style="color: #b91c1c">支持多场景自动化测试和参数化执行，可拖拽测试场景来调整执行顺序，选中根节点可以执行根节点下所有的测试场景</div>
            </div>
            <div class="actions-inline"></div>
          </template>
        </div>
        <div v-if="!scenarioEditorVisible" class="card-body">
          <template v-if="selectedModuleId">
            <div class="sub">当前已选模块：{{ (props.modules || []).find((m) => Number(m.id) === Number(selectedModuleId))?.name || "-" }}</div>
            <div style="height: 8px"></div>
            <div v-if="orderedSelectedModuleScenarios.length" class="stack">
              <div class="actions-inline">
                <label class="inline-check">
                  <el-checkbox :model-value="isAllModuleScenariosSelected" @change="toggleSelectAllModuleScenarios"  />
                </label>
                <el-button class="btn mini run" :disabled="scenarioRunLoading || !selectedModuleScenarioIds.length" @click="runSelectedModuleScenarios">
                  {{ scenarioRunLoading ? "执行中..." : `执行已选(${selectedModuleScenarioIds.length})` }}
                </el-button>
                <el-button class="btn mini run" :disabled="batchPreviewLoading || !selectedModuleScenarioIds.length" @click="previewSelectedModuleScenarios">
                  {{ batchPreviewLoading ? "预检中..." : `预检已选(${selectedModuleScenarioIds.length})` }}
                </el-button>
                <el-button class="btn mini run" :disabled="scenarioRunLoading || !orderedSelectedModuleScenarios.length" @click="runAllModuleScenarios">
                  {{ scenarioRunLoading ? "执行中..." : `执行全部(${orderedSelectedModuleScenarios.length})` }}
                </el-button>
                <el-button class="btn mini run" :disabled="batchPreviewLoading || !orderedSelectedModuleScenarios.length" @click="previewAllModuleScenarios">
                  {{ batchPreviewLoading ? "预检中..." : `预检全部(${orderedSelectedModuleScenarios.length})` }}
                </el-button>
                <label class="inline-select">
                  <span class="label">执行环境</span>
                  <el-select v-model="batchEnvironmentId" placeholder="按接口环境" clearable class="env-el-select">
                    <el-option label="按接口环境" value="" />
                    <el-option
                      v-for="env in executionEnvironments"
                      :key="env.id"
                      :label="`${env.name}${env.active ? '' : '（停用）'}`"
                      :value="env.id"
                    />
                  </el-select>
                </label>
                <div class="switch-inline">
                  <span class="label">参数化执行</span>
                  <el-switch v-model="batchParamEnabled"   />
                </div>
              </div>
              <div
                v-for="(item, idx) in orderedSelectedModuleScenarios"
                :key="item.id"
                class="rowline"
                :class="{ 'drag-over': selectedModuleScenarioDrag.overIndex === idx }"
                draggable="true"
                @dragstart="onSelectedScenarioDragStart(idx)"
                @dragover="onSelectedScenarioDragOver(idx, $event)"
                @drop="onSelectedScenarioDrop(idx)"
                @dragend="onSelectedScenarioDragEnd"
              >
                <label class="inline-check">
                  <el-checkbox :label="Number(item.id)" v-model="selectedModuleScenarioIds"  />
                </label>
                <div class="grow">
                  <div>{{ item.name }}</div>
                  <div class="muted small">{{ item.description || "无描述" }}</div>
                </div>
                <el-button class="icon-btn" title="上移" aria-label="上移" :disabled="idx === 0" @click="moveSelectedModuleScenario(idx, -1)">
                  <ArrowUp class="ep-icon" />
                </el-button>
                <el-button class="icon-btn" title="下移" aria-label="下移" :disabled="idx === orderedSelectedModuleScenarios.length - 1" @click="moveSelectedModuleScenario(idx, 1)">
                  <ArrowDown class="ep-icon" />
                </el-button>
                <el-button class="btn mini run" :disabled="scenarioRunLoading" @click="runScenarioDirect(item)">
                  {{ scenarioRunLoading ? "执行中..." : "执行" }}
                </el-button>
                <el-button class="btn mini" @click="selectScenario(item)">进入编排</el-button>
              </div>
            </div>
            <div v-else class="empty-row">该模块及下级暂无场景</div>
          </template>
          <template v-else>
            请先从左侧选择一个场景进行编排。
          </template>
        </div>
        <template v-else>
        <div class="form-grid scenario-head-grid">
          <label><span>场景名称</span><el-input v-model="scenarioForm.name" placeholder="如：购物下单主流程" /></label>
          <label>
            <span>所属模块</span>
            <el-select v-model="scenarioForm.module" placeholder="未分组" clearable>
              <el-option label="未分组" :value="null" />
              <el-option v-for="item in props.modules" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </label>
          <label>
            <span>失败策略</span>
            <el-select v-model="scenarioForm.stop_on_failure">
              <el-option label="失败即停止" :value="true" />
              <el-option label="继续执行" :value="false" />
            </el-select>
          </label>
          <div class="switch-cell">
            <span>参数化</span>
            <el-switch v-model="scenarioForm.param_enabled"   />
          </div>
          <label>
            <span>数据集</span>
            <el-select v-model="scenarioForm.data_set" :disabled="!scenarioForm.param_enabled" placeholder="不选择" clearable>
              <el-option label="不选择" :value="null" />
              <el-option v-for="item in availableDataSets" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </label>
          <label>
            <span>执行模式</span>
            <el-select v-model="scenarioForm.data_mode" :disabled="!scenarioForm.param_enabled">
              <el-option label="全部行" value="all" />
              <el-option label="按行号范围" value="range" />
              <el-option label="随机N行" value="random" />
            </el-select>
          </label>
          <label>
            <span>{{ scenarioForm.data_mode === "random" ? "随机条数" : "行号配置" }}</span>
            <el-input
              v-model="scenarioForm.data_pick"
              :disabled="!scenarioForm.param_enabled || scenarioForm.data_mode === 'all'"
              :placeholder="scenarioForm.data_mode === 'random' ? '例如：3' : '例如：1,2-4'" />
          </label>
          <label>
            <span>失败重试次数</span>
            <el-input
              v-model.number="scenarioForm.param_retry_count"
              type="number"
              min="0"
              max="10"
              :disabled="!scenarioForm.param_enabled"
              placeholder="0" />
          </label>
          <label class="full"><span>描述</span><el-input v-model="scenarioForm.description" placeholder="描述该业务场景目标" /></label>
        </div>
        <div class="steps-wrap">
          <div class="steps-head"><h3>测试步骤（拖拽排序）</h3><el-button class="btn mini" @click="addStep">新增步骤</el-button></div>
          <div
            v-for="(step, idx) in scenarioForm.steps"
            :key="idx"
            class="step-card"
            :class="{ 'drag-over': dragState.overIndex === idx }"
            draggable="true"
            @dragstart="onStepDragStart(idx)"
            @dragover="onStepDragOver(idx, $event)"
            @drop="onStepDrop(idx)"
            @dragend="onStepDragEnd"
          >
            <div class="step-row">
              <label><span>顺序</span><el-input v-model="step.step_order" type="number" min="1" /></label>
              <div class="drag-handle" title="拖拽排序">⠿⋮</div>
              <label class="grow"><span>步骤名称</span><el-input v-model="step.step_name" placeholder="如：登录" /></label>
              <label class="grow">
                <span>引用接口</span>
                <el-tree-select
                  v-model="step.test_case"
                  :data="stepCaseTreeData"
                  :props="{ label: 'name', children: 'children', value: 'value', disabled: 'disabled' }"
                  node-key="id"
                  value-key="value"
                  filterable
                  :filter-node-method="stepCaseFilterMethod"
                  check-strictly
                  clearable
                  placeholder="请选择接口"
                />
              </label>
              <div class="switch-cell">
                <span>启用</span>
                <el-switch v-model="step.enabled"   />
              </div>
              <div class="switch-cell">
                <span>失败继续</span>
                <el-switch v-model="step.continue_on_fail"   />
              </div>
              <el-button class="icon-btn" title="编辑接口" aria-label="编辑接口" @click="openStepEditor(idx)">
                <Edit class="ep-icon" />
              </el-button>
              <el-button class="icon-btn" title="复制步骤" aria-label="复制步骤" @click="copyStep(idx)">
                <DocumentCopy class="ep-icon" />
              </el-button>
              <el-button class="icon-btn danger" title="删除接口" aria-label="删除接口" @click="removeStep(idx)">
                <Delete class="ep-icon" />
              </el-button>
            </div>
            <div class="meta">点击“编辑接口”在面板中配置该步骤的接口参数、处理器与断言。</div>
          </div>
        </div>
        </template>
      </section>
    </div>
  </section>

  <div v-if="showDataSetEditor" class="history-modal-mask" @click.self="showDataSetEditor = false">
    <section class="history-modal card dataset-manage-modal">
      <div class="card-head dataset-manage-head">
        <div>
          <h3>数据集管理</h3>
          <div class="sub">支持 table/json/csv 三种数据源，场景参数化可按行执行，数据集自动关联当前场景，不需要单独填写名称和所属模块</div>
        </div>
        <div class="actions-inline">
          <el-button class="btn primary" @click="saveDataSet">保存</el-button>
          <el-button class="btn" @click="showDataSetEditor = false">关闭</el-button>
        </div>
      </div>
      <div class="dataset-manage-stack">
        <section class="detail-block">
          <h4>数据集列表</h4>
          <div v-if="managedDataSets.length" class="stack">
            <div v-for="item in managedDataSets" :key="item.id" class="rowline">
              <div class="grow">
                <div>{{ item.name || `数据集 #${item.id}` }}</div>
                <div class="muted small">{{ item.source_type }} / 行数 {{ item.row_count || 0 }}</div>
              </div>
              <el-button class="btn mini" @click="editDataSet(item)">编辑</el-button>
              <el-button class="btn mini danger" @click="removeDataSet(item)">删除</el-button>
            </div>
          </div>
          <div v-else class="empty-row">当前场景暂无数据集</div>
        </section>
        <section class="detail-block">
          <div class="form-grid dataset-form-grid">
            <label>
              <span>数据集名称</span>
              <el-input v-model="dataSetForm.name" placeholder="不填则自动使用：场景名-数据集" />
            </label>
            <label>
              <span>类型</span>
              <el-select v-model="dataSetForm.source_type">
                <el-option label="table(JSON数组)" value="table" />
                <el-option label="json(文本)" value="json" />
                <el-option label="csv(文本)" value="csv" />
              </el-select>
            </label>
            <div class="switch-cell">
              <span>启用</span>
              <el-switch v-model="dataSetForm.enabled"   />
            </div>
            <label class="full"><span>描述</span><el-input v-model="dataSetForm.description" placeholder="可选描述" /></label>
            <label v-if="dataSetForm.source_type==='table'" class="full">
              <span>表格数据（可视化编辑）</span>
              <div class="kv-table-wrap">
                <table class="kv-table">
                  <thead>
                    <tr>
                      <th
                        v-for="(col, cIdx) in dataSetColumns"
                        :key="`col-${cIdx}`"
                        class="dataset-col-head"
                        draggable="true"
                        @dragstart="onDataSetColDragStart(cIdx)"
                        @dragover.prevent
                        @drop="onDataSetColDrop(cIdx)"
                        @dragend="onDataSetColDragEnd"
                      >
                        <div class="actions-inline">
                          <span class="dataset-col-drag" title="拖拽排序">⠿</span>
                          <el-input v-model="dataSetColumns[cIdx]" @input="syncDataSetRowsTextFromTable" placeholder="列名" />
                          <el-button class="btn mini danger" native-type="button" @click="removeDataSetColumn(cIdx)">删列</el-button>
                        </div>
                      </th>
                      <th style="width: 120px">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, rIdx) in dataSetRows" :key="`row-${rIdx}`">
                      <td v-for="col in dataSetColumns" :key="`cell-${rIdx}-${col}`">
                        <el-input v-model="row[col]" @input="syncDataSetRowsTextFromTable" />
                      </td>
                      <td>
                        <div class="dataset-row-actions">
                          <el-button class="btn mini" native-type="button" @click="openRowAssertEditor(rIdx)">断言</el-button>
                          <span class="assert-badge" :class="rowAssertionStatus(row).cls">{{ rowAssertionStatus(row).label }}</span>
                          <el-button class="icon-btn danger" native-type="button" title="删行" aria-label="删行" @click="removeDataSetRow(rIdx)">
                            <Delete class="ep-icon" />
                          </el-button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
                <div class="actions-inline">
                  <el-button class="btn mini" native-type="button" @click="addDataSetColumn">新增列</el-button>
                  <el-button class="btn mini" native-type="button" @click="addDataSetRow">新增行</el-button>
                </div>
                <div v-if="!dataSetRows.length" class="muted small">暂无数据。示例：第一行为列名，第二行开始为数据行。</div>
                <div v-else class="muted small">每行可通过“断言”按钮配置独立断言，支持 <code v-pre>{{row.列名}}</code> 动态期望。</div>
                <label class="full">
                  <span>批量粘贴 Excel 行（Tab 分列，换行分行）</span>
                  <el-input type="textarea" v-model="dataSetPasteText" rows="4" placeholder="可直接粘贴 Excel 选中区域" />
                </label>
                <div class="actions-inline">
                  <el-button class="btn mini primary" native-type="button" @click="importPastedDataSetRows">导入粘贴数据</el-button>
                </div>
              </div>
            </label>
            <label v-else class="full">
              <span>{{ dataSetForm.source_type==='json' ? "JSON文本" : "CSV文本(首行header)" }}</span>
              <el-input type="textarea" v-model="dataSetForm.raw_text" rows="6" :placeholder="dataSetRawPlaceholder" />
            </label>
          </div>
        </section>
        <section class="detail-block">
          <h4>预览（前10行）</h4>
          <pre class="mono detail-pre">{{ prettyJson(dataSetPreviewRows) }}</pre>
        </section>
      </div>
    </section>
  </div>

  <div v-if="rowAssertEditorVisible" class="history-modal-mask" @click.self="closeRowAssertEditor">
    <section class="history-modal card">
      <div class="card-head">
        <div>
          <h3>行断言配置</h3>
          <div class="sub">按当前数据行生效，可使用 <code v-pre>{{row.列名}}</code> 做动态期望值。</div>
        </div>
        <div class="actions-inline">
          <el-button class="btn" @click="closeRowAssertEditor">取消</el-button>
          <el-button class="btn primary" @click="saveRowAssertions">保存</el-button>
        </div>
      </div>
      <div class="row-assert-switch-row">
        <span>启用断言</span>
        <el-switch v-model="rowAssertEditor.assert_enabled"   />
      </div>
      <div class="form-grid row-assert-grid">
        <template v-if="rowAssertEditor.assert_enabled">
          <div class="full row-assert-mode">
            <div class="row-assert-line">
              <span>断言方式（可多选）</span>
              <el-checkbox-group v-model="rowAssertEditor.assert_targets" class="assert-target-group">
                <el-checkbox v-for="opt in dataSetAssertTargetOptions" :key="opt.value" :label="opt.value">
                  {{ opt.label }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </div>
          <label v-if="rowAssertEditor.assert_targets.includes('status_code')" class="full">
            <span>状态码</span>
            <el-input v-model="rowAssertEditor.assert_status_code" type="number" min="100" max="999" placeholder="例如：200" />
          </label>
          <div v-if="rowAssertEditor.assert_targets.includes('request_headers')" class="full row-assert-pair">
            <label>
              <span>请求头 JSONPath</span>
              <el-input v-model="rowAssertEditor.assert_header_jsonpath" placeholder="例如：$.Authorization" />
            </label>
            <label>
              <span>请求头期望值</span>
              <el-input v-model="rowAssertEditor.assert_header_expected" placeholder="例如：Bearer {{row.token}}" />
            </label>
          </div>
          <div v-if="rowAssertEditor.assert_targets.includes('response_body')" class="full row-assert-pair">
            <label>
              <span>响应结果 JSONPath</span>
              <el-input v-model="rowAssertEditor.assert_response_jsonpath" placeholder="例如：$.code" />
            </label>
            <label>
              <span>响应结果期望值</span>
              <el-input v-model="rowAssertEditor.assert_response_expected" placeholder="例如：{{row.expected_code}}" />
            </label>
          </div>
        </template>
      </div>
    </section>
  </div>

  <div v-if="editingStep" class="history-modal-mask" @click.self="closeStepEditor">
    <section class="history-modal card">
      <div class="card-head">
        <div>
          <h3>步骤接口配置</h3>
          <div class="sub">步骤 {{ (stepEditorIndex ?? 0) + 1 }}：{{ editingStep.step_name || "未命名步骤" }}</div>
        </div>
        <div class="actions-inline">
          <el-button class="btn" @click="closeStepEditor">取消</el-button>
          <label class="inline-check" style="gap: 8px; align-items: center;">
            <span class="sub">带前置步骤</span>
            <el-switch v-model="stepDebugIncludePrevious"   />
          </label>
          <el-button class="btn" :disabled="stepDebugLoading" @click="debugCurrentStep">{{ stepDebugLoading ? "调试中..." : "调试当前步骤" }}</el-button>
          <el-button class="btn primary" :disabled="stepEditorSaving" @click="saveStepEditor">{{ stepEditorSaving ? "保存中..." : "保存" }}</el-button>
        </div>
      </div>
      <div class="step-config-stack">
        <div class="label-block processor-section-card">
          <div class="field-head">
            <span>接口入口</span>
            <div class="actions-inline">
              <el-button native-type="button" class="btn mini" :class="{ primary: stepCaseEntryMode === 'view' }" @click="openCurrentStepCase('view')">查看接口</el-button>
              <el-button native-type="button" class="btn mini" :class="{ primary: stepCaseEntryMode === 'edit' }" @click="openCurrentStepCase('edit')">编辑接口</el-button>
              <el-button native-type="button" class="btn mini" @click="stepCaseEntryExpanded = !stepCaseEntryExpanded">
                {{ stepCaseEntryExpanded ? "收起" : "展开" }}
              </el-button>
            </div>
          </div>
          <div v-if="!stepCaseEntryExpanded" class="empty-row">默认折叠，展开后可在当前页面查看或编辑步骤引用接口。</div>
          <div v-else-if="stepCaseEntryMode === 'view'" class="step-case-entry">
            <div class="sub">当前接口：{{ editingStepCase?.name || "未选择" }}</div>
            <pre class="json-block">{{ prettyJson(editingStepCase ? {
              id: editingStepCase.id,
              name: editingStepCase.name,
              method: editingStepCase.method,
              base_url: editingStepCase.base_url,
              path: editingStepCase.path,
              headers: editingStepCase.headers,
              params: editingStepCase.params,
              body_json: editingStepCase.body_json
            } : {}) }}</pre>
          </div>
          <div v-else class="step-case-entry">
            <div class="switch-cell">
              <span>启用接口数据覆盖</span>
              <el-switch v-model="editingStep.overrides_enabled" @change="syncStepOverridesText(editingStep)"   />
            </div>
            <div v-if="!editingStep.overrides_enabled" class="empty-row">默认关闭。开启后可在当前步骤覆盖该接口的请求数据。</div>
            <div v-else class="step-grid step-override-grid">
              <label>
                <span>Method</span>
                <el-select v-model="editingStep.override_method" @change="syncStepOverridesText(editingStep)">
                  <el-option v-for="m in httpMethods" :key="m" :label="m" :value="m" />
                </el-select>
              </label>
              <label>
                <span>Base URL</span>
                <el-input v-model="editingStep.override_base_url" placeholder="https://api.example.com" @input="syncStepOverridesText(editingStep)" />
              </label>
              <label>
                <span>Path</span>
                <el-input v-model="editingStep.override_path" placeholder="/v1/demo" @input="syncStepOverridesText(editingStep)" />
              </label>
              <div class="full step-override-pair">
                <label>
                  <span>Headers(JSON)</span>
                  <JsonEditorField v-model="editingStep.override_headers_text" height="160px" @update:model-value="syncStepOverridesText(editingStep)" />
                </label>
                <label>
                  <span>Params(JSON)</span>
                  <JsonEditorField v-model="editingStep.override_params_text" height="160px" @update:model-value="syncStepOverridesText(editingStep)" />
                </label>
              </div>
              <div class="full step-override-pair">
                <label>
                  <span>Body JSON</span>
                  <JsonEditorField v-model="editingStep.override_body_json_text" height="190px" @update:model-value="syncStepOverridesText(editingStep)" />
                </label>
                <label>
                  <span>Body Text</span>
                  <el-input type="textarea" v-model="editingStep.override_body_text" rows="4" placeholder="纯文本请求体（可选）" @input="syncStepOverridesText(editingStep)" />
                </label>
              </div>
            </div>
          </div>
        </div>
        <div class="label-block processor-section-card">
          <div class="field-head">
            <span>pre_processors（前置处理器）</span>
            <div class="actions-inline">
              <div class="switch-cell">
                <span>启用</span>
                <el-switch v-model="editingStep.pre_processors_enabled" @change="onProcessorEnabledChange(editingStep, 'pre')"   />
              </div>
              <el-button native-type="button" class="btn mini" :disabled="!editingStep.pre_processors_enabled" @click="editingStep.pre_processors_expanded = !editingStep.pre_processors_expanded">
                {{ editingStep.pre_processors_expanded ? "收起" : "展开" }}
              </el-button>
              <el-button native-type="button" class="btn mini" :class="{ primary: editingStep.pre_processors_mode === 'table' }" @click="switchStepProcessorMode(editingStep, 'pre', 'table')">可视化</el-button>
              <el-button native-type="button" class="btn mini" :class="{ primary: editingStep.pre_processors_mode === 'json' }" @click="switchStepProcessorMode(editingStep, 'pre', 'json')">JSON</el-button>
            </div>
          </div>
          <div v-if="!editingStep.pre_processors_enabled" class="empty-row">默认关闭，启用后可配置前置处理器。</div>
          <div v-else-if="!editingStep.pre_processors_expanded" class="empty-row">前置处理器已启用，点击“展开”进行编排。</div>
          <div v-else-if="editingStep.pre_processors_mode === 'table'" class="kv-table-wrap">
            <div class="processor-card-list">
              <article v-for="(row, pIdx) in editingStep.pre_processor_rows" :key="`pre-modal-${stepEditorIndex}-${pIdx}`" class="processor-card">
                <div class="processor-head">
                  <strong>前置处理器 {{ pIdx + 1 }}</strong>
                  <div class="actions-inline">
                    <label class="inline-check"><el-checkbox v-model="row.enabled" @change="syncStepProcessorsText(editingStep, 'pre')"  /> 启用</label>
                    <el-button native-type="button" class="btn mini danger" @click="removeStepProcessorRow(editingStep, 'pre', pIdx)">删除</el-button>
                  </div>
                </div>
                <div class="processor-grid">
                  <label><span>名称</span><el-input v-model="row.name" placeholder="处理器名称" @input="syncStepProcessorsText(editingStep, 'pre')" /></label>
                  <label>
                    <span>类型</span>
                    <el-select v-model="row.type" @change="syncStepProcessorsText(editingStep, 'pre')">
                      <el-option v-for="opt in preProcessorTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                  </label>
                  <label><span>目标变量</span><el-input v-model="row.target" placeholder="如：token/pwd" @input="syncStepProcessorsText(editingStep, 'pre')" /></label>
                  <label v-if="row.type==='set_var'"><span>值</span><el-input v-model="row.value" placeholder="值（支持 &变量）" @input="syncStepProcessorsText(editingStep, 'pre')" /></label>
                  <label v-else-if="row.type==='timestamp'" class="inline-check"><el-checkbox v-model="row.ms" @change="syncStepProcessorsText(editingStep, 'pre')"  /> 毫秒</label>
                  <label v-else-if="row.type==='datetime'"><span>时间格式</span><el-input v-model="row.format" placeholder="%Y-%m-%d %H:%M:%S" @input="syncStepProcessorsText(editingStep, 'pre')" /></label>
                  <div v-else-if="row.type==='transform'" class="processor-grid">
                    <label><span>源值</span><el-input v-model="row.value" placeholder="源值（如 &timems+&password）" @input="syncStepProcessorsText(editingStep, 'pre')" /></label>
                    <label><span>转换操作</span><el-input v-model="row.op" placeholder="转换操作（如 base64_encode）" @input="syncStepProcessorsText(editingStep, 'pre')" /></label>
                    <label><span>参数</span><el-input v-model="row.arg" placeholder="参数（可选）" @input="syncStepProcessorsText(editingStep, 'pre')" /></label>
                  </div>
                </div>
              </article>
            </div>
            <el-button native-type="button" class="btn mini" @click="addStepProcessorRow(editingStep, 'pre')">新增前置处理器</el-button>
          </div>
          <JsonEditorField v-else v-model="editingStep.pre_processors_text" height="220px" />
        </div>
        <div class="label-block processor-section-card">
          <div class="field-head">
            <span>post_processors（后置处理器）</span>
            <div class="actions-inline">
              <div class="switch-cell">
                <span>启用</span>
                <el-switch v-model="editingStep.post_processors_enabled" @change="onProcessorEnabledChange(editingStep, 'post')"   />
              </div>
              <el-button native-type="button" class="btn mini" :disabled="!editingStep.post_processors_enabled" @click="editingStep.post_processors_expanded = !editingStep.post_processors_expanded">
                {{ editingStep.post_processors_expanded ? "收起" : "展开" }}
              </el-button>
              <el-button native-type="button" class="btn mini" :class="{ primary: editingStep.post_processors_mode === 'table' }" @click="switchStepProcessorMode(editingStep, 'post', 'table')">可视化</el-button>
              <el-button native-type="button" class="btn mini" :class="{ primary: editingStep.post_processors_mode === 'json' }" @click="switchStepProcessorMode(editingStep, 'post', 'json')">JSON</el-button>
            </div>
          </div>
          <div v-if="!editingStep.post_processors_enabled" class="empty-row">默认关闭，启用后可配置后置处理器。</div>
          <div v-else-if="!editingStep.post_processors_expanded" class="empty-row">后置处理器已启用，点击“展开”进行编排。</div>
          <div v-else-if="editingStep.post_processors_mode === 'table'" class="kv-table-wrap">
            <div class="processor-card-list">
              <article v-for="(row, pIdx) in editingStep.post_processor_rows" :key="`post-modal-${stepEditorIndex}-${pIdx}`" class="processor-card">
                <div class="processor-head">
                  <strong>后置处理器 {{ pIdx + 1 }}</strong>
                  <div class="actions-inline">
                    <label class="inline-check"><el-checkbox v-model="row.enabled" @change="syncStepProcessorsText(editingStep, 'post')"  /> 启用</label>
                    <el-button native-type="button" class="btn mini danger" @click="removeStepProcessorRow(editingStep, 'post', pIdx)">删除</el-button>
                  </div>
                </div>
                <div class="processor-grid">
                  <label><span>变量名称</span><el-input v-model="row.target" placeholder="如：token" @input="syncStepProcessorsText(editingStep, 'post')" /></label>
                  <label>
                    <span>变量类型</span>
                    <el-select v-model="row.variable_type" @change="syncStepProcessorsText(editingStep, 'post')">
                      <el-option v-for="opt in varTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                  </label>
                  <label>
                    <span>提取来源</span>
                    <el-select v-model="row.extract_from" @change="syncStepProcessorsText(editingStep, 'post')">
                      <el-option v-for="opt in extractFromOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                  </label>
                  <label>
                    <span>提取范围</span>
                    <el-select v-model="row.extract_scope" @change="syncStepProcessorsText(editingStep, 'post')">
                      <el-option v-for="opt in extractScopeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                  </label>
                  <label class="full"><span>表达式</span><el-input v-model="row.extract_expr" placeholder="whole可留空；jsonpath如 $.data.token；header/cookie填键名" @input="syncStepProcessorsText(editingStep, 'post')" /></label>
                </div>
              </article>
            </div>
            <el-button native-type="button" class="btn mini" @click="addStepProcessorRow(editingStep, 'post')">新增后置处理器</el-button>
          </div>
          <JsonEditorField v-else v-model="editingStep.post_processors_text" height="220px" />
        </div>
        <div class="label-block processor-section-card">
          <div class="field-head">
            <span>assertions（断言）</span>
            <div class="actions-inline">
              <div class="switch-cell">
                <span>启用</span>
                <el-switch v-model="editingStep.assertions_enabled" @change="onAssertionsEnabledChange(editingStep)"   />
              </div>
              <el-button native-type="button" class="btn mini" :disabled="!editingStep.assertions_enabled" @click="editingStep.assertions_expanded = !editingStep.assertions_expanded">
                {{ editingStep.assertions_expanded ? "收起" : "展开" }}
              </el-button>
              <el-button native-type="button" class="btn mini" :class="{ primary: editingStep.assertions_mode === 'table' }" @click="switchStepAssertionsMode(editingStep, 'table')">可视化</el-button>
              <el-button native-type="button" class="btn mini" :class="{ primary: editingStep.assertions_mode === 'json' }" @click="switchStepAssertionsMode(editingStep, 'json')">JSON</el-button>
            </div>
          </div>
          <div v-if="!editingStep.assertions_enabled" class="empty-row">默认关闭，启用后可配置断言。</div>
          <div v-else-if="!editingStep.assertions_expanded" class="empty-row">断言已启用，点击“展开”进行编排。</div>
          <div v-else-if="editingStep.assertions_mode === 'table'" class="kv-table-wrap">
            <div class="pm-grid">
              <label>
                <span>断言状态码</span>
                <el-input v-model="editingStep.assert_status" type="number" placeholder="200" @input="syncStepAssertionsText(editingStep)" />
              </label>
              <label>
                <span>断言包含文本</span>
                <el-input v-model="editingStep.assert_contains" placeholder="例如 success / code" @input="syncStepAssertionsText(editingStep)" />
              </label>
            </div>
            <table class="kv-table">
              <thead><tr><th>启用</th><th>名称</th><th>数据源</th><th>操作符</th><th>路径/键</th><th>期望值</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="(row, aIdx) in editingStep.assertion_rows" :key="`assert-modal-${stepEditorIndex}-${aIdx}`">
                  <td><el-checkbox v-model="row.enabled" @change="syncStepAssertionsText(editingStep)"  /></td>
                  <td><el-input v-model="row.name" placeholder="如：code=0" @input="syncStepAssertionsText(editingStep)" /></td>
                  <td>
                    <el-select v-model="row.source" @change="syncStepAssertionsText(editingStep)">
                      <el-option label="状态码" value="status_code" />
                      <el-option label="响应头" value="headers" />
                      <el-option label="响应体(JSON)" value="body_json" />
                      <el-option label="响应体(文本)" value="body_text" />
                    </el-select>
                  </td>
                  <td>
                    <el-select v-model="row.op" @change="syncStepAssertionsText(editingStep)">
                      <el-option v-for="item in assertionOps" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </td>
                  <td><el-input v-model="row.path" placeholder="headers填Header名，json填JSONPath" @input="syncStepAssertionsText(editingStep)" /></td>
                  <td><el-input v-model="row.expected" :disabled="!needsExpected(row.op)" placeholder="期望值" @input="syncStepAssertionsText(editingStep)" /></td>
                  <td><el-button native-type="button" class="btn mini danger" @click="removeStepAssertionRow(editingStep, aIdx)">删除</el-button></td>
                </tr>
              </tbody>
            </table>
            <el-button native-type="button" class="btn mini" @click="addStepAssertionRow(editingStep)">新增断言</el-button>
          </div>
          <JsonEditorField v-else v-model="editingStep.assertions_text" height="220px" />
        </div>
      </div>
    </section>
  </div>

  <div v-if="runtimeInspectorVisible" class="history-modal-mask" @click.self="closeRuntimeInspector">
    <section class="history-modal card">
      <div class="card-head">
        <div>
          <h3>{{ runtimeInspector.title || "执行预检" }}</h3>
          <div class="sub" v-if="runtimeInspector.mode === 'scenario_preview'">
            步骤数：{{ runtimeInspector.summary?.step_count ?? 0 }}，启用步骤：{{ runtimeInspector.summary?.enabled_step_count ?? 0 }}
          </div>
          <div class="sub" v-else>
            {{ runtimeInspector.summary?.blocked ? `调试被前置步骤拦截：${runtimeInspector.summary?.blocked_reason || '-'}` : `结果：${runtimeInspector.summary?.success ? 'PASS' : 'FAIL'}` }}
          </div>
        </div>
        <div class="actions-inline">
          <el-button class="btn" @click="closeRuntimeInspector">关闭</el-button>
        </div>
      </div>
      <div class="history-detail-grid">
        <section v-if="runtimeInspector.mode === 'step_debug'" class="detail-block">
          <h4>前置步骤结果</h4>
          <pre class="mono detail-pre">{{ prettyJson(runtimeInspector.prerequisiteResults || []) }}</pre>
        </section>

        <section v-if="runtimeInspector.mode === 'step_debug'" class="detail-block full">
          <h4>当前步骤结果</h4>
          <pre class="mono detail-pre">{{ prettyJson(runtimeInspector.stepResult || {}) }}</pre>
        </section>

        <section v-if="runtimeInspector.mode === 'step_debug'" class="detail-block full">
          <h4>上下文快照</h4>
          <pre class="mono detail-pre">{{ prettyJson(runtimeInspector.contextSnapshot || {}) }}</pre>
        </section>

        <section v-if="runtimeInspector.mode === 'scenario_preview'" class="detail-block full">
          <h4>步骤预检</h4>
          <div class="step-preview-list">
            <article v-for="step in runtimeInspector.steps || []" :key="`preview-${step.step_index}`" class="step-preview-card">
              <div class="step-preview-head">
                <strong>#{{ (step.step_order ?? (step.step_index + 1)) }} {{ step.step_name || '-' }}</strong>
                <span class="tag">{{ step.test_case_name || `接口#${step.test_case_id || '-'}` }}</span>
              </div>
              <div class="step-preview-url mono">{{ step.request?.method || 'GET' }} {{ step.request?.url || '-' }}</div>
              <div class="step-preview-grid">
                <div v-if="hasPreviewContent(step.request?.headers)">
                  <div class="muted small">请求头</div>
                  <pre class="mono detail-pre">{{ prettyJson(step.request?.headers || {}) }}</pre>
                </div>
                <div v-if="hasPreviewContent(step.request?.params)">
                  <div class="muted small">Query 参数</div>
                  <pre class="mono detail-pre">{{ prettyJson(step.request?.params || {}) }}</pre>
                </div>
                <div v-if="hasPreviewContent(step.request?.body_json)">
                  <div class="muted small">JSON 请求体</div>
                  <pre class="mono detail-pre">{{ prettyJson(step.request?.body_json || {}) }}</pre>
                </div>
                <div v-if="hasPreviewContent(step.request?.body_text)">
                  <div class="muted small">文本请求体</div>
                  <pre class="mono detail-pre">{{ prettyJson(step.request?.body_text || "") }}</pre>
                </div>
                <div v-if="hasPreviewContent(step.assertions)">
                  <div class="muted small">断言计划</div>
                  <pre class="mono detail-pre">{{ prettyJson(step.assertions || []) }}</pre>
                </div>
                <div v-if="hasPreviewContent(step.unresolved_placeholders)">
                  <div class="muted small">未解析占位符</div>
                  <pre class="mono detail-pre">{{ prettyJson(step.unresolved_placeholders || []) }}</pre>
                </div>
              </div>
            </article>
            <div v-if="!(runtimeInspector.steps || []).length" class="empty-row">暂无预检结果</div>
          </div>
        </section>

        <section v-if="runtimeInspector.mode === 'batch_preview'" class="detail-block full">
          <h4>批量场景预检</h4>
          <div class="step-preview-list">
            <article v-for="scenario in runtimeInspector.scenarios || []" :key="`batch-preview-${scenario.scenario_id}`" class="step-preview-card">
              <div class="step-preview-head">
                <strong>{{ scenario.scenario_name || `场景#${scenario.scenario_id || '-'}` }}</strong>
                <span class="tag">步骤 {{ scenario.summary?.step_count ?? (scenario.steps || []).length }}</span>
              </div>
              <div class="sub" style="margin-top: 6px;">
                模块：{{ scenario.module_name || '-' }}
              </div>
              <div v-if="scenario.summary?.preview_row && Object.keys(scenario.summary.preview_row || {}).length" style="margin-top: 8px;">
                <div class="muted small">参数化预览行</div>
                <pre class="mono detail-pre">{{ prettyJson(scenario.summary.preview_row || {}) }}</pre>
              </div>
              <div class="step-preview-list" style="margin-top: 10px;">
                <article v-for="step in scenario.steps || []" :key="`batch-step-${scenario.scenario_id}-${step.step_index}`" class="step-preview-card inner">
                  <div class="step-preview-head">
                    <strong>#{{ (step.step_order ?? (step.step_index + 1)) }} {{ step.step_name || '-' }}</strong>
                    <span class="tag">{{ step.test_case_name || `接口#${step.test_case_id || '-'}` }}</span>
                  </div>
                  <div class="step-preview-url mono">{{ step.request?.method || 'GET' }} {{ step.request?.url || '-' }}</div>
                  <div class="step-preview-grid">
                    <div v-if="hasPreviewContent(step.request?.headers)">
                      <div class="muted small">请求头</div>
                      <pre class="mono detail-pre">{{ prettyJson(step.request?.headers || {}) }}</pre>
                    </div>
                    <div v-if="hasPreviewContent(step.request?.params)">
                      <div class="muted small">Query 参数</div>
                      <pre class="mono detail-pre">{{ prettyJson(step.request?.params || {}) }}</pre>
                    </div>
                    <div v-if="hasPreviewContent(step.request?.body_json)">
                      <div class="muted small">JSON 请求体</div>
                      <pre class="mono detail-pre">{{ prettyJson(step.request?.body_json || {}) }}</pre>
                    </div>
                    <div v-if="hasPreviewContent(step.request?.body_text)">
                      <div class="muted small">文本请求体</div>
                      <pre class="mono detail-pre">{{ prettyJson(step.request?.body_text || "") }}</pre>
                    </div>
                    <div v-if="hasPreviewContent(step.assertions)">
                      <div class="muted small">断言计划</div>
                      <pre class="mono detail-pre">{{ prettyJson(step.assertions || []) }}</pre>
                    </div>
                    <div v-if="hasPreviewContent(step.unresolved_placeholders)">
                      <div class="muted small">未解析占位符</div>
                      <pre class="mono detail-pre">{{ prettyJson(step.unresolved_placeholders || []) }}</pre>
                    </div>
                  </div>
                </article>
              </div>
            </article>
            <div v-if="!(runtimeInspector.scenarios || []).length" class="empty-row">暂无批量预检结果</div>
          </div>
        </section>
      </div>
    </section>
  </div>
</template>

<style scoped>
.scenario-head-grid {
  grid-template-columns: repeat(4, minmax(180px, 1fr));
}

.step-config-stack {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
.dataset-manage-stack {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
.step-preview-list {
  display: grid;
  gap: 12px;
}
.step-preview-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  background: #fff;
}
.step-preview-card.inner {
  background: #f8fafc;
  border-color: #dde6f0;
}
.step-preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.step-preview-url {
  margin-top: 8px;
}
.step-preview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 10px;
}
.dataset-manage-head {
  position: sticky;
  top: 0;
  z-index: 6;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}
.dataset-form-grid {
  grid-template-columns: minmax(260px, 2fr) minmax(180px, 1fr) auto;
}
.processor-section-card {
  border: 1px solid #dbe3ee;
  border-radius: 12px;
  background: #f8fafc;
  padding: 12px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}
.processor-card-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}
.processor-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  background: #f9fafb;
}
.processor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.processor-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.processor-grid .full {
  grid-column: 1 / -1;
}
.dataset-col-head {
  cursor: move;
  user-select: none;
}
.dataset-col-drag {
  display: inline-flex;
  align-items: center;
  color: #94a3b8;
  font-size: 12px;
}
.row-assert-grid {
  gap: 10px;
}
.row-assert-switch-row {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 0 14px;
}
.row-assert-grid > .full {
  grid-column: 1 / -1;
}
.row-assert-mode {
  display: block;
}
.row-assert-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
}
.row-assert-switch {
  display: flex;
  width: 100%;
  justify-content: flex-end;
  align-items: center;
  gap: 6px;
}
.row-assert-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.assert-target-group {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  flex: 1 1 auto;
}
.dataset-row-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
}
.assert-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid #d1d5db;
  color: #6b7280;
  background: #f3f4f6;
}
.assert-badge.is-on {
  color: #0f766e;
  border-color: #99f6e4;
  background: #f0fdfa;
}
.assert-badge.is-off {
  color: #b45309;
  border-color: #fde68a;
  background: #fffbeb;
}
.switch-cell {
  display: grid;
  grid-template-rows: auto 34px;
  gap: 3px;
  min-width: 72px;
}
.switch-cell > span {
  color: #374151;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
  margin: 0;
}
.step-row .switch-cell :deep(.el-switch) {
  height: 34px;
  display: inline-flex;
  align-items: center;
}
.inline-select {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.inline-select .label {
  font-size: 12px;
  color: #334155;
  font-weight: 700;
  white-space: nowrap;
}
.inline-select :deep(.env-el-select) {
  min-width: 190px;
}
.inline-select :deep(.env-el-select .el-select__wrapper) {
  min-height: 35px;
}
.module-scenario-count {
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
  height: 20px;
  border-radius: 999px;
  font-size: 12px;
  color: #475569;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}
.step-override-grid {
  grid-template-columns: 140px minmax(260px, 1fr) minmax(260px, 1fr);
}
.step-override-grid .full {
  grid-column: 1 / -1;
}
.step-override-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
@media (max-width: 960px) {
  .scenario-head-grid {
    grid-template-columns: 1fr;
  }
  .dataset-form-grid {
    grid-template-columns: 1fr;
  }
  .processor-grid {
    grid-template-columns: 1fr;
  }
  .row-assert-pair {
    grid-template-columns: 1fr;
  }
  .form-grid label{
    flex-direction: row !important;
  }
  .step-override-grid {
    grid-template-columns: 1fr;
  }
  .step-override-pair {
    grid-template-columns: 1fr;
  }
  .step-preview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
