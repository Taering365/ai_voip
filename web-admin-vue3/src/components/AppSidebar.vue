<template>
  <aside class="sidebar" :class="{ 'is-collapsed': collapsed }">
    <div class="sidebar-topbar">
      <el-button class="collapse-button" plain type="primary" @click="$emit('toggle')">
        {{ collapsed ? '展开' : '收起' }}
      </el-button>
    </div>

    <div class="brand" :class="{ 'is-collapsed': collapsed }">
      <img :src="logoImage" alt="logo" class="brand-logo" />
      <div v-if="!collapsed">
        <div class="brand-title">AI 智能语音</div>
        <div class="brand-subtitle">INTELLIGENT SPEECH</div>
      </div>
    </div>

    <nav class="menu-list">
      <RouterLink
        v-for="item in visibleMenus"
        :key="item.path"
        :to="item.path"
        class="menu-item"
        :class="{ 'is-active': isActiveMenu(item.path) }"
        :title="collapsed ? item.label : ''"
      >
        <img :src="getMenuIcon(item)" :alt="item.label" class="menu-icon" />
        <span v-if="!collapsed">{{ item.label }}</span>
      </RouterLink>
    </nav>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import logoImage from '@/assets/images/logo@2x.png'
import { useAuthStore } from '@/stores/auth'

defineProps({
  collapsed: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['toggle'])

const route = useRoute()
const authStore = useAuthStore()
const visibleMenus = computed(() => authStore.availableMenus)

/**
 * 判断指定菜单路径是否为当前激活菜单。
 *
 * @param {string} path 菜单目标路由路径。
 * @returns {boolean} 当前路由匹配时返回 `true`。
 */
function isActiveMenu(path) {
  return route.path === path
}

/**
 * 根据菜单激活状态返回对应的图标资源。
 *
 * @param {{icon: string, activeIcon: string, path: string}} item 菜单配置对象。
 * @returns {string} 当前菜单应展示的图标路径。
 */
function getMenuIcon(item) {
  return isActiveMenu(item.path) ? item.activeIcon : item.icon
}
</script>

<style scoped lang="scss">
.sidebar {
  width: 248px;
  min-height: 100vh;
  padding: 28px 18px 22px;
  background: linear-gradient(180deg, #ffffff 0%, #f6faff 100%);
  border-right: 1px solid rgba(214, 229, 253, 0.8);
  transition: width 0.18s ease, padding 0.18s ease;
}

.sidebar.is-collapsed {
  width: 92px;
  padding: 24px 12px 20px;
}

.sidebar-topbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.collapse-button {
  width: 100%;
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 12px 26px;
}

.brand.is-collapsed {
  justify-content: center;
  padding: 10px 0 22px;
}

.brand-logo {
  width: 52px;
  height: 52px;
  object-fit: contain;
}

.brand-title {
  font-size: 24px;
  font-weight: 800;
  color: #1f7fff;
}

.brand-subtitle {
  margin-top: 4px;
  font-size: 11px;
  letter-spacing: 0.15em;
  color: #8aa1cb;
}

.menu-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 54px;
  padding: 0 18px;
  border-radius: 16px;
  color: #647094;
  transition: all 0.18s ease;
}

.sidebar.is-collapsed .menu-item {
  justify-content: center;
  padding: 0;
}

.menu-item:hover {
  color: #0b7cff;
  background: #edf5ff;
}

.menu-item.is-active {
  color: #0b7cff;
  background: #ebf3ff;
  box-shadow: inset 0 0 0 1px rgba(11, 124, 255, 0.08);
}

.menu-icon {
  width: 20px;
  height: 20px;
}
</style>
