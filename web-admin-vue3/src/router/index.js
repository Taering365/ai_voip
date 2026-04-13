import { createRouter, createWebHistory } from 'vue-router'

import AdminLayout from '@/layouts/AdminLayout.vue'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/auth/LoginView.vue'
import ContactView from '@/views/contacts/ContactView.vue'
import DashboardView from '@/views/dashboard/DashboardView.vue'
import MediaView from '@/views/media/MediaView.vue'
import ProviderView from '@/views/providers/ProviderView.vue'
import QcView from '@/views/qc/QcView.vue'
import RuntimeView from '@/views/runtime/RuntimeView.vue'
import ScriptView from '@/views/scripts/ScriptView.vue'
import StorageProfileView from '@/views/storage/StorageProfileView.vue'
import SystemConfigView from '@/views/system/SystemConfigView.vue'
import TaskView from '@/views/tasks/TaskView.vue'
import TrunkView from '@/views/trunks/TrunkView.vue'
import UserManagementView from '@/views/users/UserManagementView.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: {
      public: true,
      title: '登录',
    },
  },
  {
    path: '/',
    component: AdminLayout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: DashboardView, meta: { title: '控制台' } },
      { path: 'storage', name: 'storage', component: StorageProfileView, meta: { title: '存储配置', adminOnly: true } },
      { path: 'providers', name: 'providers', component: ProviderView, meta: { title: '语音接口', adminOnly: true } },
      { path: 'trunks', name: 'trunks', component: TrunkView, meta: { title: '线路管理', adminOnly: true } },
      { path: 'scripts', name: 'scripts', component: ScriptView, meta: { title: '话术管理' } },
      { path: 'contacts', name: 'contacts', component: ContactView, meta: { title: '名单与联系人' } },
      { path: 'tasks', name: 'tasks', component: TaskView, meta: { title: '任务与会话' } },
      { path: 'qc', name: 'qc', component: QcView, meta: { title: '质检中心', adminOnly: true } },
      { path: 'media', name: 'media', component: MediaView, meta: { title: '录音管理' } },
      { path: 'system', name: 'system', component: SystemConfigView, meta: { title: '系统信息', adminOnly: true } },
      { path: 'users', name: 'users', component: UserManagementView, meta: { title: '用户管理', adminOnly: true } },
      { path: 'runtime', name: 'runtime', component: RuntimeView, meta: { title: '运行调试' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/**
 * 在路由切换前校验用户登录态并同步页面标题。
 *
 * @param {import('vue-router').RouteLocationNormalized} to 即将进入的目标路由。
 * @param {import('vue-router').RouteLocationNormalized} from 当前离开的路由。
 * @param {Function} next 路由放行回调函数。
 * @returns {void}
 */
function handleRouteGuard(to, from, next) {
  const authStore = useAuthStore()
  const pageTitle = to.meta?.title ? `${to.meta.title} - AI 智能语音平台` : 'AI 智能语音平台'
  document.title = pageTitle

  if (to.meta?.public) {
    if (to.path === '/login' && authStore.isAuthenticated) {
      next('/dashboard')
      return
    }
    next()
    return
  }

  if (!authStore.isAuthenticated) {
    next('/login')
    return
  }

  if (to.meta?.adminOnly && !authStore.isAdmin) {
    next('/dashboard')
    return
  }

  void from
  next()
}

router.beforeEach(handleRouteGuard)

export default router
