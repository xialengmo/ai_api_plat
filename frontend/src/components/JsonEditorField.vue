<!-- 作者: lxl -->
<!-- 说明: JSON 编辑器统一封装（基于 vue-codemirror）。 -->
<script setup>
import { computed, reactive, watch } from "vue";
import { Codemirror } from "vue-codemirror";
import { json } from "@codemirror/lang-json";

const props = defineProps({
  modelValue: { type: String, default: "" },
  height: { type: String, default: "220px" },
  menu: { type: Boolean, default: true },
  readOnly: { type: Boolean, default: false },
  statusBar: { type: Boolean, default: false },
  navigationBar: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "validation-change"]);

const validation = reactive({
  valid: true,
  error: "",
});

const editorValue = computed({
  get() {
    return String(props.modelValue || "");
  },
  set(next) {
    const text = String(next || "");
    emit("update:modelValue", text);
    validateJsonText(text);
  },
});

function validateJsonText(text) {
  const raw = String(text || "");
  const trimmed = raw.trim();
  if (!trimmed) {
    validation.valid = true;
    validation.error = "";
    emit("validation-change", { valid: true, error: "" });
    return;
  }
  try {
    JSON.parse(trimmed);
    validation.valid = true;
    validation.error = "";
    emit("validation-change", { valid: true, error: "" });
  } catch (error) {
    validation.valid = false;
    validation.error = String(error?.message || "JSON 语法错误");
    emit("validation-change", { valid: false, error: validation.error });
  }
}

function formatJson() {
  if (props.readOnly) return;
  try {
    const raw = String(editorValue.value || "").trim();
    if (!raw) return;
    editorValue.value = JSON.stringify(JSON.parse(raw), null, 2);
  } catch (error) {
    validation.valid = false;
    validation.error = String(error?.message || "JSON 语法错误，无法格式化");
    emit("validation-change", { valid: false, error: validation.error });
  }
}

watch(() => props.modelValue, (next) => {
  validateJsonText(String(next || ""));
});

validateJsonText(editorValue.value);
</script>

<template>
  <div class="json-editor-field">
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <button
          v-if="menu"
          type="button"
          class="tool-btn"
          :disabled="readOnly"
          @click="formatJson"
        >
          美化 JSON
        </button>
      </div>
      <div v-if="statusBar || !validation.valid" class="toolbar-status">
        <span v-if="validation.valid" class="status-ok">JSON 合法</span>
        <span v-else class="status-err">JSON 错误：{{ validation.error }}</span>
      </div>
    </div>

    <Codemirror
      v-model="editorValue"
      :extensions="[json()]"
      :style="{ height: height }"
      :disabled="readOnly"
      :autofocus="false"
      :indent-with-tab="true"
      :tab-size="2"
    />
  </div>
</template>

<style scoped>
.json-editor-field {
  width: 100%;
}
.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.toolbar-status {
  min-width: 0;
  text-align: right;
  flex: 1;
}
.status-ok {
  font-size: 12px;
  color: #15803d;
}
.status-err {
  font-size: 12px;
  color: #dc2626;
  word-break: break-all;
}
.tool-btn {
  height: 28px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #ffffff;
  color: #303133;
  padding: 0 10px;
  cursor: pointer;
}
.tool-btn:hover {
  border-color: #409eff;
  color: #409eff;
}
.tool-btn:disabled {
  cursor: not-allowed;
  color: #a8abb2;
  border-color: #e4e7ed;
}
.json-editor-field :deep(.cm-editor) {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
}
.json-editor-field :deep(.cm-scroller) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
.json-editor-field :deep(.cm-editor.cm-focused) {
  border-color: #409eff;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.2);
}
</style>
