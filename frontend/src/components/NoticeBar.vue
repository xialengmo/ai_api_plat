<!-- 作者: lxl -->
<!-- 说明: 前端页面/组件模块。 -->
<script setup>
defineProps({
  message: { type: String, default: "" },
  error: { type: String, default: "" }
});
defineEmits(["clear"]);
</script>

<template>
  <div v-if="message || error" class="notice-wrap">
    <div v-if="message" class="notice ok" @click="$emit('clear')">{{ message }}</div>
    <div v-if="error" class="notice err" @click="$emit('clear')">{{ error }}</div>
  </div>
</template>

