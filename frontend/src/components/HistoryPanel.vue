<!-- 作者: lxl -->
<!-- 说明: 前端页面/组件模块。 -->
<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  histories: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  selectedCaseId: { type: Number, default: null },
  query: { type: Object, default: () => ({ keyword: "", ordering: "-created_at", page: 1, pageSize: 20 }) },
  total: { type: Number, default: 0 }
});

const emit = defineEmits(["refresh", "query-change"]);

const activeHistory = ref(null);
const keywordDraft = ref("");

watch(
  () => props.query,
  (next) => {
    keywordDraft.value = String(next?.keyword || "");
  },
  { immediate: true, deep: true }
);

const currentOrdering = computed({
  get: () => String(props.query?.ordering || "-created_at"),
  set: (value) => emit("query-change", { ordering: String(value || "-created_at") })
});

const currentPage = computed({
  get: () => Number(props.query?.page || 1),
  set: (value) => emit("query-change", { page: Number(value || 1) })
});

const currentPageSize = computed({
  get: () => Number(props.query?.pageSize || 20),
  set: (value) => emit("query-change", { pageSize: Number(value || 20) })
});

const requestPreview = computed(() => {
  const item = activeHistory.value;
  if (!item) return "-";
  return prettyJson(item.request_snapshot || {});
});

const responseHeaderPreview = computed(() => {
  const item = activeHistory.value;
  if (!item) return "-";
  return prettyJson(item.response_headers || {});
});

const responseBodyPreview = computed(() => {
  const item = activeHistory.value;
  if (!item) return "-";
  const raw = item.response_body;
  if (raw === null || raw === undefined || raw === "") return "-";
  const text = String(raw);
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
});

function prettyJson(value) {
  if (value === null || value === undefined || value === "") return "-";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function openHistoryDetail(item) {
  activeHistory.value = item;
}

function closeHistoryDetail() {
  activeHistory.value = null;
}

function applyKeyword() {
  emit("query-change", { keyword: String(keywordDraft.value || "") });
}
</script>

<template>
  <section class="card">
    <div class="card-head">
      <div>
        <h3>执行历史</h3>
        <div class="sub">{{ selectedCaseId ? `当前筛选接口 ID: ${selectedCaseId}` : `共 ${total} 条记录` }}</div>
      </div>
      <div class="actions-inline">
        <el-input
          v-model="keywordDraft"
          clearable
          placeholder="搜索断言 / 错误 / 接口名"
          style="width: 220px"
          @keyup.enter="applyKeyword"
          @clear="applyKeyword"
        />
        <el-select v-model="currentOrdering" style="width: 160px">
          <el-option label="最新执行" value="-created_at" />
          <el-option label="最早执行" value="created_at" />
          <el-option label="最慢优先" value="-response_time_ms" />
          <el-option label="最快优先" value="response_time_ms" />
          <el-option label="状态码降序" value="-status_code" />
          <el-option label="状态码升序" value="status_code" />
        </el-select>
        <el-button @click="applyKeyword">搜索</el-button>
        <el-button @click="emit('refresh')">刷新</el-button>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>接口ID</th>
            <th>结果</th>
            <th>状态码</th>
            <th>耗时</th>
            <th>断言</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in histories" :key="h.id" class="clickable-row" @click="openHistoryDetail(h)">
            <td>{{ h.id }}</td>
            <td>{{ h.test_case_id }}</td>
            <td><span :class="h.success ? 'tag pass' : 'tag fail'">{{ h.success ? "PASS" : "FAIL" }}</span></td>
            <td>{{ h.status_code ?? "-" }}</td>
            <td>{{ h.response_time_ms ?? "-" }}ms</td>
            <td :title="h.assertion_result">{{ h.assertion_result || "-" }}</td>
            <td>{{ (h.created_at || "").replace("T", " ").slice(0, 19) }}</td>
          </tr>
          <tr v-if="!histories.length">
            <td colspan="7" class="empty-row">暂无执行历史</td>
          </tr>
        </tbody>
      </table>
      <div v-if="total > 0" class="actions-inline" style="justify-content:flex-end; margin-top: 10px;">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="currentPageSize"
          :total="total"
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
          <h3>执行详情 #{{ activeHistory.id }}</h3>
          <div class="sub">
            结果：
            <span :class="activeHistory.success ? 'tag pass' : 'tag fail'">
              {{ activeHistory.success ? "PASS" : "FAIL" }}
            </span>
            ，状态码：{{ activeHistory.status_code ?? "-" }}，耗时：{{ activeHistory.response_time_ms ?? "-" }}ms
          </div>
        </div>
        <el-button class="btn" @click="closeHistoryDetail">关闭</el-button>
      </div>

      <div class="history-detail-grid">
        <section class="detail-block">
          <h4>请求信息</h4>
          <pre class="mono detail-pre">{{ requestPreview }}</pre>
        </section>

        <section class="detail-block">
          <h4>响应摘要</h4>
          <div class="stack">
            <div class="rowline">
              <strong>断言结果：</strong>
              <span class="grow">{{ activeHistory.assertion_result || "-" }}</span>
            </div>
            <div class="rowline">
              <strong>错误信息：</strong>
              <span class="grow">{{ activeHistory.error_message || "-" }}</span>
            </div>
            <div class="rowline">
              <strong>Content-Type：</strong>
              <span class="grow">{{ activeHistory.response_content_type || "-" }}</span>
            </div>
          </div>
        </section>

        <section class="detail-block full">
          <h4>响应头</h4>
          <pre class="mono detail-pre">{{ responseHeaderPreview }}</pre>
        </section>

        <section class="detail-block full">
          <h4>响应体</h4>
          <pre class="mono detail-pre">{{ responseBodyPreview }}</pre>
        </section>
      </div>
    </section>
  </div>
</template>
