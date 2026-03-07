<!-- 作者: lxl -->
<!-- 说明: 前端页面/组件模块。 -->
<script setup>
import { computed, reactive, ref, watch } from "vue";

const props = defineProps({
  loading: { type: Boolean, default: false },
  generatedCases: { type: Array, default: () => [] },
  openapiSummary: { type: Object, default: null },
  aiConfig: {
    type: Object,
    default: () => ({
      apiBaseUrl: "https://api.openai.com/v1",
      apiKey: "",
      model: "gpt-4o-mini",
      timeoutSeconds: 60
    })
  }
});

const emit = defineEmits([
  "generate",
  "generate-from-openapi",
  "load-to-form",
  "batch-create",
  "save-ai-config"
]);

const aiForm = reactive({
  baseUrlHint: "",
  prompt: ""
});

const openapiForm = reactive({
  schemaUrl: "",
  schemaText: "",
  extraRequirements: ""
});

const configForm = reactive({
  apiBaseUrl: "https://api.openai.com/v1",
  apiKey: "",
  model: "gpt-4o-mini",
  timeoutSeconds: 60
});
const showConfigDialog = ref(false);
const savingConfig = ref(false);
const aiConfigured = computed(() => String(props.aiConfig?.apiKey || "").trim().length > 0);

watch(
  () => props.aiConfig,
  (next) => {
    configForm.apiBaseUrl = String(next?.apiBaseUrl || "https://api.openai.com/v1");
    configForm.apiKey = String(next?.apiKey || "");
    configForm.model = String(next?.model || "gpt-4o-mini");
    const timeoutNum = Number(next?.timeoutSeconds || 60);
    configForm.timeoutSeconds = Number.isFinite(timeoutNum) && timeoutNum > 0 ? timeoutNum : 60;
  },
  { immediate: true, deep: true }
);

function openConfigDialog() {
  configForm.apiBaseUrl = String(props.aiConfig?.apiBaseUrl || "https://api.openai.com/v1");
  configForm.apiKey = String(props.aiConfig?.apiKey || "");
  configForm.model = String(props.aiConfig?.model || "gpt-4o-mini");
  const timeoutNum = Number(props.aiConfig?.timeoutSeconds || 60);
  configForm.timeoutSeconds = Number.isFinite(timeoutNum) && timeoutNum > 0 ? timeoutNum : 60;
  showConfigDialog.value = true;
}

function saveAiConfig() {
  const payload = {
    apiBaseUrl: String(configForm.apiBaseUrl || "").trim(),
    apiKey: String(configForm.apiKey || "").trim(),
    model: String(configForm.model || "").trim(),
    timeoutSeconds: Number(configForm.timeoutSeconds || 60)
  };
  savingConfig.value = true;
  emit("save-ai-config", payload, (ok) => {
    savingConfig.value = false;
    if (ok) {
      showConfigDialog.value = false;
    }
  });
}

function submitGenerate() {
  emit("generate", {
    prompt: aiForm.prompt,
    baseUrlHint: aiForm.baseUrlHint,
    aiConfig: {
      apiBaseUrl: configForm.apiBaseUrl,
      apiKey: configForm.apiKey,
      model: configForm.model,
      timeoutSeconds: configForm.timeoutSeconds
    }
  });
}

function submitOpenapiGenerate() {
  emit("generate-from-openapi", {
    schemaUrl: openapiForm.schemaUrl,
    schemaText: openapiForm.schemaText,
    extraRequirements: openapiForm.extraRequirements,
    aiConfig: {
      apiBaseUrl: configForm.apiBaseUrl,
      apiKey: configForm.apiKey,
      model: configForm.model,
      timeoutSeconds: configForm.timeoutSeconds
    }
  });
}
</script>

<template>
  <section class="card ai-layout">
    <div class="ai-left">
      <div class="card-head">
        <div style="width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 12px;">
          <div>
            <h3>AI 助手</h3>
            <div class="sub">支持业务描述生成与 OpenAPI 文档生成。</div>
          </div>
          <el-button :class="['btn', aiConfigured ? 'primary' : 'warn']" native-type="button" @click="openConfigDialog">
            AI配置（{{ aiConfigured ? "已配置" : "未配置" }}）
          </el-button>
        </div>
      </div>

      <div class="card-head">
        <div>
          <h3>AI 生成接口草稿</h3>
          <div class="sub">基于业务描述生成接口定义草稿（审核后导入）。</div>
        </div>
      </div>
      <div class="ai-form">
        <label>
          <span>Base URL 提示（可选）</span>
          <el-input v-model="aiForm.baseUrlHint" placeholder="https://api.example.com" />
        </label>
        <label>
          <span>业务需求 / 接口描述</span>
          <el-input type="textarea" v-model="aiForm.prompt" rows="8" placeholder="请输入业务场景、接口用途、鉴权方式、预期断言..." />
        </label>
        <div class="ai-actions">
          <el-button class="btn primary" :disabled="loading || !aiForm.prompt.trim()" @click="submitGenerate">
            {{ loading ? "生成中..." : "开始生成" }}
          </el-button>
          <el-button class="btn" :disabled="loading || !generatedCases.length" @click="$emit('batch-create', generatedCases)">
            批量导入接口
          </el-button>
        </div>
      </div>

      <div class="split-line"></div>

      <div class="card-head">
        <div>
          <h3>Swagger / OpenAPI 文档生成</h3>
          <div class="sub">支持文档 URL 或粘贴 JSON/YAML 文本。</div>
        </div>
      </div>
      <div class="ai-form">
        <label>
          <span>文档 URL（可选）</span>
          <el-input v-model="openapiForm.schemaUrl" placeholder="https://example.com/openapi.json" />
        </label>
        <label>
          <span>文档文本（JSON/YAML，可选）</span>
          <el-input type="textarea" v-model="openapiForm.schemaText" rows="8" placeholder='{"openapi":"3.0.0","paths":{...}}' />
        </label>
        <label>
          <span>额外要求（可选）</span>
          <el-input type="textarea" v-model="openapiForm.extraRequirements" rows="4" placeholder="如：优先覆盖边界值、异常场景、鉴权失败" />
        </label>
        <div class="ai-actions">
          <el-button
            class="btn primary"
            :disabled="loading || (!openapiForm.schemaUrl.trim() && !openapiForm.schemaText.trim())"
            @click="submitOpenapiGenerate"
          >
            {{ loading ? "生成中..." : "解析文档并生成" }}
          </el-button>
        </div>
      </div>
    </div>

    <div class="ai-right">
      <div class="card-head"><h3>生成结果（{{ generatedCases.length }}）</h3></div>
      <div v-if="openapiSummary" class="openapi-summary">
        <div><strong>文档：</strong>{{ openapiSummary.title || "未命名" }}</div>
        <div><strong>版本：</strong>{{ openapiSummary.version || "-" }}</div>
        <div><strong>Base URL：</strong>{{ openapiSummary.base_url || "-" }}</div>
        <div><strong>接口数量：</strong>{{ openapiSummary.operation_count ?? "-" }}</div>
      </div>
      <div class="ai-result-list">
        <div v-for="(item, idx) in generatedCases" :key="idx" class="ai-case-card">
          <div class="row">
            <strong>{{ item.name }}</strong>
            <span class="method">{{ item.method }}</span>
          </div>
          <div class="desc">{{ item.description || "无描述" }}</div>
          <div class="url">{{ item.base_url }}{{ item.path }}</div>
          <div class="asserts">
            <span>状态码：{{ item.assert_status ?? "-" }}</span>
            <span>包含：{{ item.assert_contains || "-" }}</span>
          </div>
          <div class="ops"><el-button class="btn mini" @click="$emit('load-to-form', item)">载入接口表单</el-button></div>
        </div>
        <div v-if="!generatedCases.length" class="empty">暂无生成结果</div>
      </div>
    </div>

    <el-dialog
      v-model="showConfigDialog"
      title="AI 配置"
      width="560px"
      append-to-body
      destroy-on-close
    >
      <div class="ai-form">
        <label>
          <span>API Base URL</span>
          <el-input v-model="configForm.apiBaseUrl" placeholder="https://api.openai.com/v1" />
        </label>
        <label>
          <span>API Key</span>
          <el-input v-model="configForm.apiKey" type="password" show-password placeholder="sk-..." />
        </label>
        <label>
          <span>模型名称</span>
          <el-input v-model="configForm.model" placeholder="gpt-4o-mini" />
        </label>
        <label>
          <span>超时秒数</span>
          <el-input v-model.number="configForm.timeoutSeconds" type="number" min="1" max="300" />
        </label>
      </div>
      <template #footer>
        <div class="ai-actions" style="justify-content: flex-end;">
          <el-button class="btn" native-type="button" :disabled="savingConfig" @click="showConfigDialog = false">取消</el-button>
          <el-button class="btn primary" native-type="button" :disabled="savingConfig" @click="saveAiConfig">
            {{ savingConfig ? "检测中..." : "保存" }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>
