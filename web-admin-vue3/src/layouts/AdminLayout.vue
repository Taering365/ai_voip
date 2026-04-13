<template>
  <div class="app-shell admin-layout">
    <AppSidebar :collapsed="sidebarCollapsed" @toggle="toggleSidebar" />
    <main class="admin-main">
      <AppHeader :title="pageTitle" :subtitle="pageSubtitle" />
      <section class="admin-content">
        <router-view />
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { useAuthStore } from '@/stores/auth'

const ADMIN_SIDEBAR_COLLAPSED_KEY = 'ai_voip_admin_sidebar_collapsed'
const route = useRoute()
const authStore = useAuthStore()
const sidebarCollapsed = ref(false)

const pageTitle = computed(() => route.meta?.title || '控制台')
const pageSubtitle = computed(() => '智能呼叫、线路管理、话术配置、质检复核一体化后台')

/**
 * 初始化后台布局依赖的用户信息。
 *
 * @returns {Promise<void>} 用户信息同步完成后的 Promise。
 */
async function initializeLayout() {
  if (!authStore.userInfo && authStore.isAuthenticated) {
    await authStore.refreshUser()
  }
  sidebarCollapsed.value = window.localStorage.getItem(ADMIN_SIDEBAR_COLLAPSED_KEY) === '1'
}

/**
 * 切换全局左侧菜单栏的展开与收起状态，并写入本地缓存。
 *
 * @returns {void}
 */
function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  window.localStorage.setItem(ADMIN_SIDEBAR_COLLAPSED_KEY, sidebarCollapsed.value ? '1' : '0')
}

onMounted(initializeLayout)
</script>

<style scoped lang="scss">
.admin-layout {
  display: flex;
}

.admin-main {
  flex: 1;
  min-width: 0;
  padding: 22px;
  transition: padding 0.18s ease;
}

.admin-content {
  min-height: calc(100vh - 120px);
}
</style>
