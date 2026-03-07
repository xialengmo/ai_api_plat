<!-- 作者: lxl -->
<!-- 说明: 前端页面/组件模块。 -->
<script setup>
import { computed, ref, watch } from 'vue';
import JsonEditorField from './JsonEditorField.vue';

const props = defineProps({
  form: { type: Object, required: true },
  selectedCase: { type: Object, default: null },
  saving: { type: Boolean, default: false },
  environments: { type: Array, default: () => [] },
  modules: { type: Array, default: () => [] }
});

const emit = defineEmits(['save']);

const submitted = ref(false);
const activeTab = ref('params');
const paramsMode = ref('table');
const headersMode = ref('table');
const bodyMode = ref('none');
const assertionsMode = ref('table');
const assertionsExpanded = ref(false);

const jsonErrors = ref({
  headers_text: '',
  params_text: '',
  body_json_text: '',
  custom_assertions_text: ''
});

const paramsRows = ref([]);
const headersRows = ref([]);
const assertionRows = ref([]);
const preview = ref({
  url: '',
  params: '',
  headers: '',
  body: ''
});
const selectableEnvironments = computed(() =>
  (props.environments || []).filter((item) => item?.is_active !== false)
);
const moduleTreeData = computed(() => {
  const nodes = new Map();
  for (const raw of props.modules || []) {
    const id = Number(raw.id || 0);
    if (!id) continue;
    nodes.set(id, {
      id,
      name: String(raw.name || `模块#${id}`),
      parent_id: raw.parent_id ? Number(raw.parent_id) : null,
      sort_order: Number(raw.sort_order || 0),
      children: []
    });
  }
  for (const node of nodes.values()) {
    if (node.parent_id && nodes.has(node.parent_id)) {
      nodes.get(node.parent_id).children.push(node);
    }
  }
  const sortTree = (list) => {
    list.sort((a, b) => {
      if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
      return a.id - b.id;
    });
    for (const item of list) sortTree(item.children);
    return list;
  };
  const roots = Array.from(nodes.values()).filter((n) => !n.parent_id || !nodes.has(n.parent_id));
  return sortTree(roots);
});

function moduleFilterMethod(query, nodeData) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return true;
  const name = String(nodeData?.name || "").toLowerCase();
  return name.includes(q);
}

function requiredError(field) {
  if (!submitted.value) return '';
  if (field === 'name' && !String(props.form.name || '').trim()) return '名称不能为空';
  if (field === 'base_url' && !String(props.form.base_url || '').trim()) return 'Base URL 不能为空';
  if (field === 'path' && !String(props.form.path || '').trim()) return 'Path 不能为空';
  return '';
}

function onEnvironmentChange() {
  const envId = Number(props.form.environment || 0);
  const env = selectableEnvironments.value.find((item) => Number(item.id) === envId);
  if (env && String(env.base_url || '').trim()) {
    props.form.base_url = String(env.base_url || '').trim();
  }
  const isCreateMode = !props.form.id;
  const hasCustomHeaders = String(props.form.headers_text || '').trim();
  const defaultHeaders = env && env.default_headers && typeof env.default_headers === 'object'
    ? env.default_headers
    : {};
  if (isCreateMode && !hasCustomHeaders && Object.keys(defaultHeaders).length) {
    props.form.headers_text = JSON.stringify(defaultHeaders, null, 2);
    loadRowsFromField('headers_text', 'Headers', headersRows);
  }
  refreshPreview();
}

watch(
  () => props.environments,
  () => {
    const currentId = Number(props.form.environment || 0);
    if (!currentId) return;
    const active = selectableEnvironments.value.some((item) => Number(item.id) === currentId);
    if (!active) props.form.environment = '';
  },
  { deep: true }
);

function parseObjectText(fieldKey, fieldLabel) {
  const raw = String(props.form[fieldKey] || '').trim();
  if (!raw) {
    jsonErrors.value[fieldKey] = '';
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      jsonErrors.value[fieldKey] = '';
      return parsed;
    }
    jsonErrors.value[fieldKey] = `${fieldLabel} 必须是 JSON 对象`;
    return null;
  } catch {
    jsonErrors.value[fieldKey] = `${fieldLabel} 不是合法 JSON`;
    return null;
  }
}

function parseArrayText(fieldKey, fieldLabel) {
  const raw = String(props.form[fieldKey] || '').trim();
  if (!raw) {
    jsonErrors.value[fieldKey] = '';
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      jsonErrors.value[fieldKey] = '';
      return parsed;
    }
    jsonErrors.value[fieldKey] = `${fieldLabel} 必须是 JSON 数组`;
    return null;
  } catch {
    jsonErrors.value[fieldKey] = `${fieldLabel} 不是合法 JSON`;
    return null;
  }
}

function parseJsonText(fieldKey, fieldLabel) {
  const raw = String(props.form[fieldKey] || '').trim();
  if (!raw) {
    jsonErrors.value[fieldKey] = '';
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    jsonErrors.value[fieldKey] = '';
    return parsed;
  } catch {
    jsonErrors.value[fieldKey] = `${fieldLabel} 不是合法 JSON`;
    return null;
  }
}

function beautifyJson(fieldKey, fieldLabel) {
  const raw = String(props.form[fieldKey] || '').trim();
  if (!raw) {
    jsonErrors.value[fieldKey] = '';
    return;
  }
  const parsed = parseObjectText(fieldKey, fieldLabel);
  if (parsed !== null) {
    props.form[fieldKey] = JSON.stringify(parsed, null, 2);
  }
}

function beautifyAnyJson(fieldKey, fieldLabel) {
  const parsed = parseJsonText(fieldKey, fieldLabel);
  if (parsed !== null) {
    props.form[fieldKey] = JSON.stringify(parsed, null, 2);
  }
}

function beautifyJsonArray(fieldKey, fieldLabel) {
  const raw = String(props.form[fieldKey] || '').trim();
  if (!raw) {
    jsonErrors.value[fieldKey] = '';
    return;
  }
  const parsed = parseArrayText(fieldKey, fieldLabel);
  if (parsed !== null) {
    props.form[fieldKey] = JSON.stringify(parsed, null, 2);
  }
}

function rowsToObject(rows) {
  const obj = {};
  for (const row of rows) {
    if (!row.enabled) continue;
    const key = String(row.key || '').trim();
    if (!key) continue;
    obj[key] = String(row.value ?? '');
  }
  return obj;
}

function asRows(targetRows) {
  return Array.isArray(targetRows) ? targetRows : targetRows.value;
}

function objectToRows(obj) {
  const rows = Object.entries(obj || {}).map(([k, v]) => ({
    enabled: true,
    key: String(k),
    value: typeof v === 'string' ? v : JSON.stringify(v)
  }));
  return rows.length ? rows : [{ enabled: true, key: '', value: '' }];
}

function syncFieldFromRows(fieldKey, rows) {
  const obj = rowsToObject(rows);
  props.form[fieldKey] = Object.keys(obj).length ? JSON.stringify(obj, null, 2) : '';
  jsonErrors.value[fieldKey] = '';
}

function loadRowsFromField(fieldKey, fieldLabel, targetRows) {
  const rows = asRows(targetRows);
  const parsed = parseObjectText(fieldKey, fieldLabel);
  if (parsed === null) {
    const hasRaw = String(props.form[fieldKey] || '').trim().length > 0;
    if (!hasRaw) {
      rows.splice(0, rows.length, { enabled: true, key: '', value: '' });
      jsonErrors.value[fieldKey] = '';
    }
    return;
  }
  rows.splice(0, rows.length, ...objectToRows(parsed));
}

function addRow(targetRows, fieldKey) {
  const rows = asRows(targetRows);
  rows.push({ enabled: true, key: '', value: '' });
  syncFieldFromRows(fieldKey, rows);
}

function removeRow(targetRows, index, fieldKey) {
  const rows = asRows(targetRows);
  rows.splice(index, 1);
  if (!rows.length) rows.push({ enabled: true, key: '', value: '' });
  syncFieldFromRows(fieldKey, rows);
}

const assertionOps = [
  { value: 'eq', label: '等于' },
  { value: 'ne', label: '不等于' },
  { value: 'contains', label: '包含' },
  { value: 'not_contains', label: '不包含' },
  { value: 'gt', label: '大于' },
  { value: 'ge', label: '大于等于' },
  { value: 'lt', label: '小于' },
  { value: 'le', label: '小于等于' },
  { value: 'exists', label: '存在' },
  { value: 'not_exists', label: '不存在' },
  { value: 'empty', label: '为空' },
  { value: 'not_empty', label: '非空' }
];

const assertionTemplates = [
  {
    key: 'status_200',
    label: '状态码=200',
    build: () => ({ enabled: true, name: '状态码为 200', source: 'status_code', op: 'eq', path: '', expected: '200' })
  },
  {
    key: 'header_trace',
    label: '响应头存在',
    build: () => ({ enabled: true, name: '响应头 X-Trace-Id 存在', source: 'headers', op: 'exists', path: 'X-Trace-Id', expected: '' })
  },
  {
    key: 'body_code',
    label: 'JSON字段=0',
    build: () => ({ enabled: true, name: 'code 等于 0', source: 'body_json', op: 'eq', path: '$.code', expected: '0' })
  },
  {
    key: 'body_contains',
    label: '文本包含',
    build: () => ({ enabled: true, name: '响应文本包含 success', source: 'body_text', op: 'contains', path: '', expected: 'success' })
  }
];

function needsExpected(op) {
  return !['exists', 'not_exists', 'empty', 'not_empty'].includes(op);
}

function defaultAssertionRow() {
  return {
    enabled: true,
    name: '',
    source: 'body_json',
    op: 'eq',
    path: '$.code',
    expected: '0'
  };
}

function getPathPlaceholder(source) {
  if (source === 'headers') return '如：X-Trace-Id';
  if (source === 'body_json') return '如：$.data.id';
  if (source === 'body_text') return '可留空';
  if (source === 'status_code') return '状态码无需路径';
  return '';
}

function getSourceHint(source) {
  if (source === 'status_code') return '状态码断言直接对 HTTP 状态码比较，通常无需填写路径。';
  if (source === 'headers') return '响应头断言请填写 Header 名称，大小写不敏感。';
  if (source === 'body_json') return 'JSON 断言建议使用 JSONPath，例如 $.code / $.data.items[0].id。';
  if (source === 'body_text') return '文本断言会基于响应原文进行比较，可用于 contains/正则预处理后的结果。';
  return '';
}

function getExpectedPlaceholder(op, source) {
  if (!needsExpected(op)) return '当前操作符无需期望值';
  if (source === 'status_code') return '如：200';
  if (source === 'body_json') return '如：0 / true / success';
  if (source === 'headers') return '如：application/json';
  return '如：success';
}

function onAssertionSourceChange(row) {
  if (row.source === 'status_code') row.path = '';
  if (row.source === 'body_json' && !String(row.path || '').trim()) row.path = '$.code';
  if (row.source === 'headers' && !String(row.path || '').trim()) row.path = 'Content-Type';
  syncAssertionsFromRows();
}

function onAssertionOpChange(row) {
  if (!needsExpected(row.op)) row.expected = '';
  syncAssertionsFromRows();
}

function addAssertionByTemplate(templateKey) {
  const template = assertionTemplates.find((item) => item.key === templateKey);
  if (!template) return;
  assertionRows.value.push(template.build());
  syncAssertionsFromRows();
}

function normalizeExpectedInput(raw) {
  const text = String(raw ?? '').trim();
  if (text === '') return '';
  if (text === 'true') return true;
  if (text === 'false') return false;
  if (text === 'null') return null;
  if (/^-?\d+(\.\d+)?$/.test(text)) return Number(text);
  if ((text.startsWith('{') && text.endsWith('}')) || (text.startsWith('[') && text.endsWith(']'))) {
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
  for (const row of rows) {
    if (!row.enabled) continue;
    const source = String(row.source || '').trim();
    const op = String(row.op || 'eq').trim();
    if (!source || !op) continue;
    const item = { source, op };
    const name = String(row.name || '').trim();
    if (name) item.name = name;
    const path = String(row.path || '').trim();
    if (path) {
      if (source === 'headers') item.header = path;
      else if (source === 'body_json') item.jsonpath = path;
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
    name: String(item?.name || ''),
    source: String(item?.source || item?.from || 'body_json'),
    op: String(item?.op || 'eq'),
    path: String(item?.header || item?.jsonpath || item?.path || ''),
    expected:
      item && Object.prototype.hasOwnProperty.call(item, 'expected')
        ? (typeof item.expected === 'string' ? item.expected : JSON.stringify(item.expected))
        : ''
  }));
}

function syncAssertionsFromRows() {
  const list = assertionRowsToList(assertionRows.value);
  props.form.custom_assertions_text = list.length ? JSON.stringify(list, null, 2) : '';
  jsonErrors.value.custom_assertions_text = '';
}

function loadAssertionRowsFromField() {
  const parsed = parseArrayText('custom_assertions_text', '高级断言');
  if (parsed === null) {
    const hasRaw = String(props.form.custom_assertions_text || '').trim().length > 0;
    if (!hasRaw) {
      assertionRows.value = [defaultAssertionRow()];
      jsonErrors.value.custom_assertions_text = '';
    }
    return;
  }
  assertionRows.value = assertionListToRows(parsed);
}

function addAssertionRow() {
  assertionRows.value.push(defaultAssertionRow());
  syncAssertionsFromRows();
}

function removeAssertionRow(index) {
  assertionRows.value.splice(index, 1);
  if (!assertionRows.value.length) assertionRows.value.push(defaultAssertionRow());
  syncAssertionsFromRows();
}

function switchParamsMode(mode) {
  paramsMode.value = mode;
  if (mode === 'table') loadRowsFromField('params_text', 'Query Params', paramsRows);
}

function switchHeadersMode(mode) {
  headersMode.value = mode;
  if (mode === 'table') loadRowsFromField('headers_text', 'Headers', headersRows);
}

function switchAssertionsMode(mode) {
  assertionsMode.value = mode;
  if (mode === 'table') loadAssertionRowsFromField();
}

function hasAnyAssertionConfig() {
  return Boolean(
    props.form.assert_status !== '' && props.form.assert_status !== null && props.form.assert_status !== undefined
    || String(props.form.assert_contains || '').trim()
    || String(props.form.custom_assertions_text || '').trim()
  );
}

function onAssertionToggleChange() {
  assertionsExpanded.value = Boolean(props.form.assert_enabled);
  if (!props.form.assert_enabled) {
    jsonErrors.value.custom_assertions_text = '';
  }
}

function initBodyMode() {
  if (String(props.form.body_json_text || '').trim()) return 'json';
  if (String(props.form.body_text || '').trim()) return 'text';
  return 'none';
}

function setBodyMode(mode) {
  bodyMode.value = mode;
  if (mode === 'none') {
    props.form.body_json_text = '';
    props.form.body_text = '';
    jsonErrors.value.body_json_text = '';
  } else if (mode === 'json') {
    props.form.body_text = '';
  } else if (mode === 'text') {
    props.form.body_json_text = '';
    jsonErrors.value.body_json_text = '';
  }
}

function handleSave() {
  submitted.value = true;

  parseObjectText('headers_text', 'Headers');
  parseObjectText('params_text', 'Query Params');
  if (bodyMode.value === 'json') {
    parseJsonText('body_json_text', 'Body JSON');
  } else {
    jsonErrors.value.body_json_text = '';
  }
  if (props.form.assert_enabled) {
    parseArrayText('custom_assertions_text', '高级断言');
  } else {
    jsonErrors.value.custom_assertions_text = '';
  }
  const hasRequired = !!requiredError('name') || !!requiredError('base_url') || !!requiredError('path');
  const hasJsonError = Object.values(jsonErrors.value).some(Boolean);
  if (hasRequired || hasJsonError) return;

  emit('save');
}

function safePrettyJson(text) {
  const raw = String(text || '').trim();
  if (!raw) return '-';
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function refreshPreview() {
  const base = String(props.form.base_url || '').trim();
  const path = String(props.form.path || '').trim();
  preview.value.url = `${base}${path}`;
  preview.value.params = safePrettyJson(props.form.params_text);
  preview.value.headers = safePrettyJson(props.form.headers_text);
  if (bodyMode.value === 'json') preview.value.body = safePrettyJson(props.form.body_json_text);
  else if (bodyMode.value === 'text') preview.value.body = String(props.form.body_text || '').trim() || '-';
  else preview.value.body = '-';
}

loadRowsFromField('params_text', 'Query Params', paramsRows);
loadRowsFromField('headers_text', 'Headers', headersRows);
loadAssertionRowsFromField();
bodyMode.value = initBodyMode();
if (typeof props.form.assert_enabled !== 'boolean') {
  props.form.assert_enabled = hasAnyAssertionConfig();
}
assertionsExpanded.value = Boolean(props.form.assert_enabled);
refreshPreview();

watch(
  () => [props.form.id, props.form.base_url, props.form.path, props.form.method],
  () => {
    refreshPreview();
  }
);

watch(
  () => props.form.environment,
  () => {
    onEnvironmentChange();
  }
);

watch(
  () => props.form.id,
  () => {
    // 切换接口时，根据已保存内容初始化 Body 展示模式。
    bodyMode.value = initBodyMode();
    if (typeof props.form.assert_enabled !== 'boolean') {
      props.form.assert_enabled = hasAnyAssertionConfig();
    }
    assertionsExpanded.value = Boolean(props.form.assert_enabled);
    refreshPreview();
  }
);

watch(
  () => props.form.params_text,
  () => {
    if (paramsMode.value === 'table') {
      loadRowsFromField('params_text', 'Query Params', paramsRows);
    }
    refreshPreview();
  }
);

watch(
  () => props.form.headers_text,
  () => {
    if (headersMode.value === 'table') {
      loadRowsFromField('headers_text', 'Headers', headersRows);
    }
    refreshPreview();
  }
);

watch(
  () => [props.form.body_json_text, props.form.body_text],
  ([nextJson, nextText]) => {
    const hasJson = Boolean(String(nextJson || '').trim());
    const hasText = Boolean(String(nextText || '').trim());
    // 用户已手动切到 json/text 且当前内容为空时，不要回退到 none，避免编辑器被卸载导致无法输入。
    if (hasJson && bodyMode.value !== 'json') {
      bodyMode.value = 'json';
    } else if (!hasJson && hasText && bodyMode.value !== 'text') {
      bodyMode.value = 'text';
    } else if (!hasJson && !hasText && !['json', 'text', 'none'].includes(bodyMode.value)) {
      bodyMode.value = 'none';
    }
    refreshPreview();
  }
);

watch(
  () => props.form.custom_assertions_text,
  () => {
    if (assertionsMode.value === 'table') loadAssertionRowsFromField();
  }
);
</script>

<template>
  <section class="card">
    <div class="card-head">
      <div>
        <h3>接口配置</h3>
        <div class="sub">{{ selectedCase ? `正在编辑接口 #${selectedCase.id}` : '新建接口定义（供自动化测试复用）' }}</div>
      </div>
      <el-button type="primary" :loading="saving" @click="handleSave">
        {{ saving ? '保存中...' : '保存接口' }}
      </el-button>
    </div>

    <div class="pm-layout">
      <section class="pm-block">
        <div class="pm-block-head">Request</div>
        <div class="pm-block-body pm-grid">
          <div class="full request-row request-row-top" style="display:flex;flex-wrap:nowrap;gap:50px;align-items:center;grid-column:1 / -1;">
            <label style="flex:0 0 430px;display:grid;grid-template-columns:72px minmax(0,1fr);align-items:center;column-gap:8px;row-gap:4px;min-width:0;">
              <span>接口名称 *</span>
              <el-input v-model="props.form.name" :class="{ 'input-error': !!requiredError('name') }" placeholder="例如：获取用户详情-成功" />
              <small v-if="requiredError('name')" class="field-error" style="grid-column:1 / -1;">{{ requiredError('name') }}</small>
            </label>

            <label style="flex:0 0 280px;display:grid;grid-template-columns:72px minmax(0,1fr);align-items:center;column-gap:8px;row-gap:4px;min-width:0;">
              <span>关联环境</span>
              <el-select v-model="props.form.environment" @change="onEnvironmentChange" clearable placeholder="不绑定环境">
                <el-option label="不绑定环境" value="" />
                <el-option v-for="env in selectableEnvironments" :key="env.id" :label="env.name" :value="env.id" />
              </el-select>
            </label>

            <label style="flex:0 0 280px;display:grid;grid-template-columns:72px minmax(0,1fr);align-items:center;column-gap:8px;row-gap:4px;min-width:0;">
              <span>所属模块</span>
              <el-tree-select
                v-model="props.form.module"
                :data="moduleTreeData"
                :props="{ label: 'name', children: 'children' }"
                node-key="id"
                value-key="id"
                filterable
                :filter-node-method="moduleFilterMethod"
                check-strictly
                clearable
                placeholder="未分组"
              />
            </label>
          </div>

          <div class="full request-row request-row-bottom" style="display:flex;flex-wrap:nowrap;gap:70px;align-items:center;grid-column:1 / -1;">
            <label style="flex:0 0 170px;display:grid;grid-template-columns:60px minmax(0,1fr);align-items:center;column-gap:18px;row-gap:4px;min-width:0;">
              <span>Method *</span>
              <el-select v-model="props.form.method" @change="refreshPreview">
                <el-option label="GET" value="GET" />
                <el-option label="POST" value="POST" />
                <el-option label="PUT" value="PUT" />
                <el-option label="PATCH" value="PATCH" />
                <el-option label="DELETE" value="DELETE" />
              </el-select>
            </label>

            <label style="flex:0 0 380px;display:grid;grid-template-columns:80px minmax(0,1fr);align-items:center;column-gap:8px;row-gap:4px;min-width:0;">
              <span>Base URL *</span>
              <el-input v-model="props.form.base_url" :class="{ 'input-error': !!requiredError('base_url') }" placeholder="https://api.example.com" @input="refreshPreview" />
              <small v-if="requiredError('base_url')" class="field-error" style="grid-column:1 / -1;">{{ requiredError('base_url') }}</small>
            </label>

            <label style="flex:0 0 430px;display:grid;grid-template-columns:50px minmax(0,1fr);align-items:center;column-gap:8px;row-gap:4px;min-width:0;">
              <span>Path *</span>
              <el-input v-model="props.form.path" :class="{ 'input-error': !!requiredError('path') }" placeholder="/v1/users/1" @input="refreshPreview" />
              <small v-if="requiredError('path')" class="field-error" style="grid-column:1 / -1;">{{ requiredError('path') }}</small>
            </label>
          </div>

          <div class="full request-row request-row-extra" style="display:flex;flex-wrap:nowrap;gap:22px;align-items:center;grid-column:1 / -1;">
            <label style="flex:1 1 auto;display:grid;grid-template-columns:50px minmax(0,1fr);align-items:center;column-gap:8px;row-gap:4px;min-width:0;">
              <span>描述</span>
              <el-input v-model="props.form.description" placeholder="接口说明（可选）" @input="refreshPreview" />
            </label>
            <label style="flex:0 0 170px;display:grid;grid-template-columns:62px minmax(0,1fr);align-items:center;column-gap:8px;row-gap:4px;min-width:0;">
              <span>超时</span>
              <el-input-number v-model="props.form.timeout_seconds" :min="1" :max="120" style="width:100%;" />
            </label>
            <div class="switch-inline" style="flex:0 0 220px;justify-content:flex-start;">
              <span class="label">SSL 证书</span>
              <el-switch v-model="props.form.verify_ssl" inline-prompt active-text="开" inactive-text="关" />
            </div>
          </div>
          <label class="full">
            <small class="sub">绑定环境后可用 `&变量名` 引用变量，支持转换链：`&password|sha256`、`&token|base64_encode`、`&ts|timestamp_ms`。</small>
          </label>
        </div>
      </section>

      <section class="pm-block">
        <div class="pm-block-head">请求预览</div>
        <div class="pm-block-body">
          <div class="mono">{{ props.form.method || 'GET' }} {{ preview.url || '-' }}</div>
          <div class="pm-preview-grid">
            <div>
              <div class="sub">Params</div>
              <pre class="pm-preview">{{ preview.params }}</pre>
            </div>
            <div>
              <div class="sub">Headers</div>
              <pre class="pm-preview">{{ preview.headers }}</pre>
            </div>
            <div class="full">
              <div class="sub">Body</div>
              <pre class="pm-preview">{{ preview.body }}</pre>
            </div>
          </div>
        </div>
      </section>

      <section class="pm-block">
        <div class="pm-block-head">Request Config</div>
        <div class="pm-tabs">
          <el-button size="small" :type="activeTab === 'params' ? 'primary' : 'default'" @click="activeTab = 'params'">Params</el-button>
          <el-button size="small" :type="activeTab === 'headers' ? 'primary' : 'default'" @click="activeTab = 'headers'">Headers</el-button>
          <el-button size="small" :type="activeTab === 'body' ? 'primary' : 'default'" @click="activeTab = 'body'">Body</el-button>
        </div>
        <div class="pm-block-body">
          <div v-show="activeTab === 'params'">
            <div class="pm-subtabs">
              <el-button size="small" :type="paramsMode === 'table' ? 'primary' : 'default'" @click="switchParamsMode('table')">可视化</el-button>
              <el-button size="small" :type="paramsMode === 'json' ? 'primary' : 'default'" @click="switchParamsMode('json')">JSON</el-button>
            </div>

            <div v-if="paramsMode === 'table'" class="kv-table-wrap">
              <table class="kv-table">
                <thead>
                  <tr>
                    <th>启用</th>
                    <th>Key</th>
                    <th>Value</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in paramsRows" :key="`params-${idx}`">
                    <td><el-checkbox v-model="row.enabled" @change="syncFieldFromRows('params_text', paramsRows); refreshPreview()" /></td>
                    <td><el-input v-model="row.key" placeholder="page" @input="syncFieldFromRows('params_text', paramsRows); refreshPreview()" /></td>
                    <td><el-input v-model="row.value" placeholder="1 或 &username|url_encode" @input="syncFieldFromRows('params_text', paramsRows); refreshPreview()" /></td>
                    <td><el-button type="danger" plain size="small" @click="removeRow(paramsRows, idx, 'params_text')">删除</el-button></td>
                  </tr>
                </tbody>
              </table>
              <el-button size="small" @click="addRow(paramsRows, 'params_text'); refreshPreview()">新增参数</el-button>
            </div>

            <div v-else>
              <div class="field-head">
                <span>Query Params (JSON)</span>
              </div>
              <JsonEditorField
                v-model="props.form.params_text"
                height="220px"
                @update:model-value="refreshPreview"
              />
              <small v-if="jsonErrors.params_text" class="field-error">{{ jsonErrors.params_text }}</small>
            </div>
          </div>

          <div v-show="activeTab === 'headers'">
            <div class="pm-subtabs">
              <el-button size="small" :type="headersMode === 'table' ? 'primary' : 'default'" @click="switchHeadersMode('table')">可视化</el-button>
              <el-button size="small" :type="headersMode === 'json' ? 'primary' : 'default'" @click="switchHeadersMode('json')">JSON</el-button>
            </div>

            <div v-if="headersMode === 'table'" class="kv-table-wrap">
              <table class="kv-table">
                <thead>
                  <tr>
                    <th>启用</th>
                    <th>Key</th>
                    <th>Value</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in headersRows" :key="`headers-${idx}`">
                    <td><el-checkbox v-model="row.enabled" @change="syncFieldFromRows('headers_text', headersRows); refreshPreview()" /></td>
                    <td><el-input v-model="row.key" placeholder="Authorization" @input="syncFieldFromRows('headers_text', headersRows); refreshPreview()" /></td>
                    <td><el-input v-model="row.value" placeholder="Bearer &token|base64_encode" @input="syncFieldFromRows('headers_text', headersRows); refreshPreview()" /></td>
                    <td><el-button type="danger" plain size="small" @click="removeRow(headersRows, idx, 'headers_text')">删除</el-button></td>
                  </tr>
                </tbody>
              </table>
              <el-button size="small" @click="addRow(headersRows, 'headers_text'); refreshPreview()">新增请求头</el-button>
            </div>

            <div v-else>
              <div class="field-head">
                <span>Headers (JSON)</span>
              </div>
              <JsonEditorField
                v-model="props.form.headers_text"
                height="220px"
                @update:model-value="refreshPreview"
              />
              <small v-if="jsonErrors.headers_text" class="field-error">{{ jsonErrors.headers_text }}</small>
            </div>
          </div>

          <div v-show="activeTab === 'body'" class="pm-grid">
            <div class="pm-subtabs full">
              <el-button size="small" :type="bodyMode === 'none' ? 'primary' : 'default'" @click="setBodyMode('none'); refreshPreview()">none</el-button>
              <el-button size="small" :type="bodyMode === 'json' ? 'primary' : 'default'" @click="setBodyMode('json'); refreshPreview()">raw(JSON)</el-button>
              <el-button size="small" :type="bodyMode === 'text' ? 'primary' : 'default'" @click="setBodyMode('text'); refreshPreview()">raw(text)</el-button>
            </div>

            <div v-if="bodyMode === 'json'" class="full body-editor">
              <div class="field-head">
                <span>Body JSON (JSON)</span>
              </div>
              <JsonEditorField
                v-model="props.form.body_json_text"
                height="280px"
                @update:model-value="refreshPreview"
              />
              <small v-if="jsonErrors.body_json_text" class="field-error">{{ jsonErrors.body_json_text }}</small>
            </div>

            <div v-if="bodyMode === 'text'" class="full body-editor">
              <span>Body Text</span>
              <el-input v-model="props.form.body_text" type="textarea" :rows="6" placeholder="raw text / xml / form-data... 支持 &username 引用环境变量" @input="refreshPreview" />
            </div>

            <div v-if="bodyMode === 'none'" class="empty-row">当前不发送请求体</div>
          </div>
        </div>
      </section>

      <section class="pm-block">
        <div class="pm-block-head assertion-head">
          <span>Assertions</span>
          <div class="actions-inline">
            <div class="switch-inline">
              <span class="label">启用断言</span>
              <el-switch v-model="props.form.assert_enabled" inline-prompt active-text="开" inactive-text="关" @change="onAssertionToggleChange" />
            </div>
            <el-button
              size="small"
              :disabled="!props.form.assert_enabled"
              @click="assertionsExpanded = !assertionsExpanded"
            >
              {{ assertionsExpanded ? '收起' : '展开' }}
            </el-button>
          </div>
        </div>
        <div v-if="!props.form.assert_enabled" class="pm-block-body">
          <div class="empty-row">断言默认不启用。开启后可配置状态码、响应头、响应体等断言规则。</div>
        </div>
        <div v-else-if="!assertionsExpanded" class="pm-block-body">
          <div class="empty-row">断言已启用，点击“展开”进行配置。</div>
        </div>
        <div v-else class="pm-block-body">
          <div class="pm-tabs">
            <el-button size="small" :type="assertionsMode === 'table' ? 'primary' : 'default'" @click="switchAssertionsMode('table')">可视化规则</el-button>
            <el-button size="small" :type="assertionsMode === 'json' ? 'primary' : 'default'" @click="switchAssertionsMode('json')">JSON 规则</el-button>
          </div>
          <div class="pm-grid">
            <label>
              <span>断言状态码</span>
              <el-input-number v-model="props.form.assert_status" :min="100" :max="599" style="width:100%;" placeholder="200" />
            </label>

            <label class="full">
              <span>断言包含文本</span>
              <el-input v-model="props.form.assert_contains" placeholder="例如：success / code / message" />
            </label>
          </div>

          <div v-if="assertionsMode === 'table'" class="kv-table-wrap">
            <div class="assertion-toolbar">
              <span class="sub">快捷模板：</span>
              <el-button
                v-for="tpl in assertionTemplates"
                :key="tpl.key"
                size="small"
                @click="addAssertionByTemplate(tpl.key)"
              >
                {{ tpl.label }}
              </el-button>
            </div>
            <table class="kv-table">
              <thead>
                <tr>
                  <th>启用</th>
                  <th>名称</th>
                  <th>数据源</th>
                  <th>操作符</th>
                  <th>路径/键</th>
                  <th>期望值</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in assertionRows" :key="`assert-${idx}`">
                  <td><el-checkbox v-model="row.enabled" @change="syncAssertionsFromRows" /></td>
                  <td><el-input v-model="row.name" placeholder="如：code=0" @input="syncAssertionsFromRows" /></td>
                  <td>
                    <el-select v-model="row.source" @change="onAssertionSourceChange(row)">
                      <el-option label="状态码" value="status_code" />
                      <el-option label="响应头" value="headers" />
                      <el-option label="响应体(JSON)" value="body_json" />
                      <el-option label="响应体(文本)" value="body_text" />
                    </el-select>
                  </td>
                  <td>
                    <el-select v-model="row.op" @change="onAssertionOpChange(row)">
                      <el-option v-for="item in assertionOps" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </td>
                  <td>
                    <el-input
                      v-model="row.path"
                      :placeholder="getPathPlaceholder(row.source)"
                      @input="syncAssertionsFromRows"
                    />
                    <small class="sub">{{ getSourceHint(row.source) }}</small>
                  </td>
                  <td>
                    <el-input
                      v-model="row.expected"
                      :disabled="!needsExpected(row.op)"
                      :placeholder="getExpectedPlaceholder(row.op, row.source)"
                      @input="syncAssertionsFromRows"
                    />
                  </td>
                  <td><el-button type="danger" plain size="small" @click="removeAssertionRow(idx)">删除</el-button></td>
                </tr>
              </tbody>
            </table>
            <el-button size="small" @click="addAssertionRow">新增断言</el-button>
          </div>

          <div v-else>
            <div class="field-head">
              <span>高级断言 (JSON Array)</span>
            </div>
            <JsonEditorField
              v-model="props.form.custom_assertions_text"
              height="300px"
            />
            <small v-if="jsonErrors.custom_assertions_text" class="field-error">{{ jsonErrors.custom_assertions_text }}</small>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>
