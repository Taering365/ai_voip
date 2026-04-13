<template>
  <header class="header">
    <div>
      <div class="header-title">{{ title }}</div>
      <div class="header-subtitle">{{ subtitle }}</div>
    </div>

    <div class="header-right">
      <div class="clock">{{ clock.date }} {{ clock.time }} {{ clock.week }}</div>
      <img :src="avatarImage" alt="avatar" class="avatar" />
      <div class="user-block">
        <div class="username">{{ userName }}</div>
        <div class="role">{{ roleText }}</div>
      </div>
      <el-button plain type="primary" @click="handleLogout">退出</el-button>
    </div>
  </header>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import avatarImage from '@/assets/images/header_image.png'
import { useAuthStore } from '@/stores/auth'
import { getCurrentClock } from '@/utils/format'

const props = defineProps({
  title: {
    type: String,
    default: 'AI 智能语音平台',
  },
  subtitle: {
    type: String,
    default: '开源智能呼叫控制台',
  },
})

const router = useRouter()
const authStore = useAuthStore()
const clock = ref(getCurrentClock())
let timerId = null

const userName = computed(() => authStore.userInfo?.display_name || authStore.userInfo?.username || '未登录')
const roleText = computed(() => (authStore.userInfo?.role_codes || []).join(' / ') || 'operator')

/**
 * 刷新头部时钟显示内容。
 *
 * @returns {void}
 */
function refreshClock() {
  clock.value = getCurrentClock()
}

/**
 * 执行退出登录逻辑并跳转到登录页。
 *
 * @returns {Promise<void>} 异步退出完成后的 Promise。
 */
async function handleLogout() {
  authStore.logout()
  await router.push('/login')
}

/**
 * 启动头部时钟定时器。
 *
 * @returns {void}
 */
function startClockTimer() {
  refreshClock()
  timerId = window.setInterval(refreshClock, 1000)
}

/**
 * 清理头部时钟定时器。
 *
 * @returns {void}
 */
function stopClockTimer() {
  if (timerId) {
    window.clearInterval(timerId)
    timerId = null
  }
}

onMounted(startClockTimer)
onBeforeUnmount(stopClockTimer)
</script>

<style scoped lang="scss">
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 30px;
  margin-bottom: 22px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(218, 232, 252, 0.9);
  border-radius: 24px;
  box-shadow: 0 16px 36px rgba(59, 108, 196, 0.08);
}

.header-title {
  font-size: 28px;
  font-weight: 800;
  color: #364064;
}

.header-subtitle {
  margin-top: 6px;
  color: #7b8ab2;
  font-size: 14px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.clock {
  color: #6c779e;
  font-size: 14px;
}

.avatar {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  border: 3px solid #eef5ff;
}

.user-block {
  min-width: 120px;
}

.username {
  font-size: 16px;
  font-weight: 700;
}

.role {
  margin-top: 4px;
  color: #8a96b8;
  font-size: 12px;
}
</style>
