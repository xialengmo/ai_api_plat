<!-- 作者: lxl -->
<!-- 说明: 前端页面/组件模块。 -->
<script setup>
defineProps({
  loadingSave: { type: Boolean, default: false },
  projectName: { type: String, default: '-' },
  passRate7d: { type: Number, default: 0 },
  projects: { type: Array, default: () => [] },
  selectedProjectId: { type: Number, default: null },
  authUser: { type: Object, default: null }
});

const emit = defineEmits(['open-ai', 'project-change', 'change-password', 'logout']);

function onProjectChange(value) {
  if (value === null || value === "") {
    emit('project-change', null);
    return;
  }
  const next = Number(value);
  emit('project-change', Number.isFinite(next) ? next : null);
}

function onUserAction(cmd) {
  if (cmd === "change-password") emit("change-password");
  if (cmd === "logout") emit("logout");
}
</script>

<template>
  <header class="topbar">
    <div class="brand">
      <div class="brand-badge"></div>
      <div class="brand-title-wrap">
        <div class="brand-title">接口测试平台</div>
      </div>
    </div>

    <div class="project-select" title="项目">
      <strong>项目：</strong>
      <el-select
        :model-value="selectedProjectId"
        placeholder="请选择项目"
        class="header-project-select"
        @update:model-value="onProjectChange"
      >
        <el-option v-if="!projects.length" label="暂无项目" :value="null" disabled />
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
    </div>

    <div class="actions">
      <span class="badge good">近7天通过率 {{ passRate7d }}%</span>
      <el-button class="btn primary" @click="$emit('open-ai')">AI 生成</el-button>
      <el-dropdown trigger="click" @command="onUserAction">
        <div class="user-trigger">
          <div class="avatar">{{ (authUser?.username || "U").slice(0, 1).toUpperCase() }}</div>
          <span class="user-name">{{ authUser?.username || "未登录" }}</span>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="change-password">修改密码</el-dropdown-item>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>
