<!-- 作者: lxl -->
<!-- 说明: 前端页面/组件模块。 -->
<script setup>
import { Delete, Edit, Plus, Search } from "@element-plus/icons-vue";
import { computed, ref } from "vue";

const props = defineProps({
  items: { type: Array, default: () => [] },
  modules: { type: Array, default: () => [] },
  selectedId: { type: Number, default: null },
  loading: { type: Boolean, default: false }
});

const emit = defineEmits([
  "refresh",
  "select",
  "delete",
  "create-module",
  "create-in-module",
  "edit-module",
  "delete-module",
  "select-module"
]);

const collapsedMap = ref({});
const selectedModuleId = ref(null);
const caseKeyword = ref("");
const isSearching = computed(() => Boolean(String(caseKeyword.value || "").trim()));

function getCaseModuleId(item) {
  const raw = item?.module_id ?? item?.module;
  if (raw && typeof raw === "object") return Number(raw.id || 0);
  return Number(raw || 0);
}

const filteredItems = computed(() => {
  const keyword = String(caseKeyword.value || "").trim().toLowerCase();
  if (!keyword) return props.items || [];
  return (props.items || []).filter((item) => {
    const name = String(item?.name || "").toLowerCase();
    const path = String(item?.path || "").toLowerCase();
    return name.includes(keyword) || path.includes(keyword);
  });
});

const moduleRows = computed(() => {
  const map = new Map();
  for (const raw of props.modules || []) {
    const id = Number(raw.id);
    if (!id) continue;
    map.set(id, {
      id,
      name: raw.name || `模块#${id}`,
      parentId: raw.parent_id ? Number(raw.parent_id) : null,
      sortOrder: Number(raw.sort_order || 0),
      children: [],
      items: []
    });
  }

  for (const node of map.values()) {
    if (node.parentId && map.has(node.parentId)) {
      map.get(node.parentId).children.push(node);
    }
  }

  for (const item of filteredItems.value || []) {
    const moduleId = getCaseModuleId(item);
    if (moduleId && map.has(moduleId)) {
      map.get(moduleId).items.push(item);
    }
  }

  const sortNodes = (nodes) =>
    nodes.sort((a, b) => {
      if (a.sortOrder !== b.sortOrder) return a.sortOrder - b.sortOrder;
      return a.id - b.id;
    });

  const roots = sortNodes(Array.from(map.values()).filter((n) => !n.parentId || !map.has(n.parentId)));
  const rows = [];
  const walk = (node, depth = 0) => {
    rows.push({
      id: node.id,
      name: node.name,
      depth,
      parentId: node.parentId,
      items: node.items
    });
    const children = sortNodes(node.children.slice());
    for (const child of children) walk(child, depth + 1);
  };
  for (const root of roots) walk(root, 0);
  return rows;
});

const ungroupedItems = computed(() => {
  const moduleIds = new Set((props.modules || []).map((m) => Number(m.id)));
  return (filteredItems.value || []).filter((item) => {
    const moduleId = getCaseModuleId(item);
    return !moduleId || !moduleIds.has(moduleId);
  });
});

function isCollapsed(groupId) {
  const key = String(groupId);
  if (!(key in collapsedMap.value)) return true;
  return Boolean(collapsedMap.value[key]);
}

function toggleGroup(groupId) {
  const key = String(groupId);
  collapsedMap.value[key] = !isCollapsed(groupId);
}

function getDescendantModuleIds(moduleId) {
  const ids = new Set();
  const queue = [Number(moduleId)];
  const list = props.modules || [];
  while (queue.length) {
    const current = queue.shift();
    if (!current || ids.has(current)) continue;
    ids.add(current);
    for (const item of list) {
      if (Number(item.parent_id || 0) === current) queue.push(Number(item.id));
    }
  }
  return Array.from(ids);
}

function selectModule(moduleId) {
  const normalized = Number(moduleId || 0);
  if (!normalized) return;
  if (Number(selectedModuleId.value || 0) === normalized) {
    selectedModuleId.value = null;
    emit("select-module", null);
    return;
  }
  selectedModuleId.value = normalized;
  collapsedMap.value[String(normalized)] = false;
  emit("select-module", normalized);
}

function clearModuleFilter() {
  selectedModuleId.value = null;
  emit("select-module", null);
}

function selectUngrouped() {
  if (Number(selectedModuleId.value || 0) === -1) {
    clearModuleFilter();
    return;
  }
  selectedModuleId.value = -1;
  emit("select-module", -1);
}

const visibleModuleRows = computed(() => {
  const selected = Number(selectedModuleId.value || 0);
  if (!selected) return moduleRows.value;
  if (selected === -1) return [];
  return moduleRows.value.filter((row) => Number(row.id) === selected);
});

function getVisibleItemsByRow(row) {
  const selected = Number(selectedModuleId.value || 0);
  if (!selected || Number(row.id) !== selected) return row.items || [];
  const moduleIds = new Set(getDescendantModuleIds(selected));
  return (filteredItems.value || []).filter((item) => moduleIds.has(getCaseModuleId(item)));
}

function getVisibleCountByRow(row) {
  const selected = Number(selectedModuleId.value || 0);
  if (!selected || Number(row.id) !== selected) return (row.items || []).length;
  return getVisibleItemsByRow(row).length;
}

function isRowVisible(row) {
  const selected = Number(selectedModuleId.value || 0);
  if (selected && selected !== -1) return Number(row.id) === selected;
  let cursor = Number(row.parentId || 0);
  while (cursor) {
    if (isCollapsed(cursor)) return false;
    const parent = (props.modules || []).find((item) => Number(item.id) === cursor);
    cursor = Number(parent?.parent_id || 0);
  }
  return true;
}
</script>

<template>
  <section class="card">
    <div class="card-head">
      <h3>接口列表</h3>
      <div class="actions-inline">
        <el-input
          v-model="caseKeyword"
          placeholder="搜索接口 / Path"
          clearable
          style="width: 180px;"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" @click="emit('create-module')">新增模块</el-button>
      </div>
    </div>
    <div class="case-list">
      <div v-if="selectedModuleId && !isSearching" class="sub">
        已筛选模块 {{ Number(selectedModuleId) === -1 ? "未分组" : `#${selectedModuleId}` }}
        <el-button size="small" @click="clearModuleFilter">清除筛选</el-button>
      </div>
      <template v-if="!isSearching">
        <div v-for="row in visibleModuleRows" v-show="isRowVisible(row)" :key="`group-${row.id}`" class="module-group">
          <div
            class="module-head tree-node"
            :class="{ active: Number(selectedModuleId || 0) === Number(row.id) }"
            :style="{ paddingLeft: `${12 + row.depth * 18}px`, '--depth': row.depth }"
          >
            <el-button native-type="button" class="module-toggle" @click="selectModule(row.id)">
              <span class="fold-icon" @click.stop="toggleGroup(row.id)">{{ isCollapsed(row.id) ? "▸" : "▾" }}</span>
              <strong>{{ row.name }}</strong>
            </el-button>
            <div class="actions-inline">
              <span class="badge">{{ getVisibleCountByRow(row) }}</span>
              <el-button class="icon-btn" title="新增接口" aria-label="新增接口" @click="emit('create-in-module', row.id || null)">
                <Plus class="ep-icon" />
              </el-button>
              <el-button class="icon-btn" title="编辑模块" aria-label="编辑模块" @click="emit('edit-module', row)">
                <Edit class="ep-icon" />
              </el-button>
              <el-button class="icon-btn danger" title="删除模块" aria-label="删除模块" @click="emit('delete-module', row)">
                <Delete class="ep-icon" />
              </el-button>
            </div>
          </div>
          <div v-if="getVisibleCountByRow(row) && !isCollapsed(row.id)">
            <div
              v-for="item in getVisibleItemsByRow(row)"
              :key="item.id"
              class="case-item tree-leaf"
              :class="{ active: selectedId === item.id }"
              :style="{ marginLeft: `${20 + row.depth * 18}px`, '--depth': row.depth }"
            >
              <div class="case-main" @click="$emit('select', item)">
                <div class="title">{{ item.name }}</div>
              </div>
              <div class="case-ops">
                <el-button class="icon-btn" title="编辑接口" aria-label="编辑接口" @click="$emit('select', item)">
                  <Edit class="ep-icon" />
                </el-button>
                <el-button class="icon-btn danger" title="删除接口" aria-label="删除接口" @click="$emit('delete', item.id)">
                  <Delete class="ep-icon" />
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="ungroupedItems.length && (!selectedModuleId || Number(selectedModuleId) === -1)" class="module-group">
          <div class="module-head tree-node" :class="{ active: Number(selectedModuleId || 0) === -1 }" :style="{ paddingLeft: '12px', '--depth': 0 }">
            <el-button native-type="button" class="module-toggle" @click="selectUngrouped">
              <span class="fold-icon" @click.stop="toggleGroup(0)">{{ isCollapsed(0) ? "▸" : "▾" }}</span>
              <strong>未分组</strong>
            </el-button>
            <div class="actions-inline">
              <span class="badge">{{ ungroupedItems.length }}</span>
              <el-button class="icon-btn" title="新增接口" aria-label="新增接口" @click="emit('create-in-module', null)">
                <Plus class="ep-icon" />
              </el-button>
            </div>
          </div>
          <div v-if="!isCollapsed(0)">
            <div
              v-for="item in ungroupedItems"
              :key="`ungrouped-${item.id}`"
              class="case-item tree-leaf"
              :class="{ active: selectedId === item.id }"
              :style="{ marginLeft: '20px', '--depth': 0 }"
            >
              <div class="case-main" @click="$emit('select', item)">
                <div class="title">{{ item.name }}</div>
              </div>
              <div class="case-ops">
                <el-button class="icon-btn" title="编辑接口" aria-label="编辑接口" @click="$emit('select', item)">
                  <Edit class="ep-icon" />
                </el-button>
                <el-button class="icon-btn danger" title="删除接口" aria-label="删除接口" @click="$emit('delete', item.id)">
                  <Delete class="ep-icon" />
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <div
          v-for="item in filteredItems"
          :key="`search-${item.id}`"
          class="case-item"
          :class="{ active: selectedId === item.id }"
        >
          <div class="case-main" @click="$emit('select', item)">
            <div class="title">{{ item.name }}</div>
          </div>
          <div class="case-ops">
            <el-button class="icon-btn" title="编辑接口" aria-label="编辑接口" @click="$emit('select', item)">
              <Edit class="ep-icon" />
            </el-button>
            <el-button class="icon-btn danger" title="删除接口" aria-label="删除接口" @click="$emit('delete', item.id)">
              <Delete class="ep-icon" />
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="!filteredItems.length" class="empty">暂无接口</div>
    </div>
  </section>
</template>
