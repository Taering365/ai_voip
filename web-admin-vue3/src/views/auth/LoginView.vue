<template>
  <div class="login-page">
    <div class="login-overlay"></div>
    <div class="login-panel page-card">
      <div class="login-brand">
        <img :src="logoImage" alt="logo" class="login-logo" />
        <div>
          <div class="login-title">AI 智能呼叫平台</div>
          <div class="login-subtitle">对接 SIP 线路、话术编排、任务外呼、录音质检</div>
        </div>
      </div>

      <el-form :model="formState" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="用户名">
          <el-input v-model="formState.username" placeholder="请输入管理员账号" size="large" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="formState.password"
            type="password"
            show-password
            placeholder="请输入密码"
            size="large"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item label="验证码">
          <div class="captcha-row">
            <el-input v-model="formState.captcha_code" placeholder="请输入图片数字" size="large" />
            <img :src="captchaImageDataUrl" alt="captcha" class="captcha-image" @click="loadCaptcha" />
          </div>
        </el-form-item>
        <el-button type="primary" size="large" class="login-button" :loading="submitting" @click="handleLogin">
          登录后台
        </el-button>
      </el-form>

      <div class="login-footer">
        <span>首次登录前请先执行后端管理员初始化命令。</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import logoImage from '@/assets/images/logo@2x.png'
import { fetchCaptchaApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const submitting = ref(false)
const captchaImageDataUrl = ref('')
const formState = reactive({
  username: '',
  password: '',
  captcha_key: '',
  captcha_code: '',
})

/**
 * 从后端加载最新验证码图片。
 *
 * @returns {Promise<void>} 验证码加载完成后的 Promise。
 */
async function loadCaptcha() {
  const captchaData = await fetchCaptchaApi()
  formState.captcha_key = captchaData.captcha_key
  formState.captcha_code = ''
  captchaImageDataUrl.value = `data:${captchaData.image_mime_type};base64,${captchaData.image_base64}`
}

/**
 * 执行登录并跳转到控制台首页。
 *
 * @returns {Promise<void>} 登录完成后的 Promise。
 */
async function handleLogin() {
  if (!formState.username || !formState.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (!formState.captcha_code) {
    ElMessage.warning('请输入验证码')
    return
  }

  submitting.value = true
  try {
    await authStore.login({
      username: formState.username,
      password: formState.password,
      captcha_key: formState.captcha_key,
      captcha_code: formState.captcha_code,
    })
    ElMessage.success('登录成功')
    await router.push('/dashboard')
  } catch (error) {
    await loadCaptcha()
  } finally {
    submitting.value = false
  }
}

loadCaptcha()
</script>

<style scoped lang="scss">
.login-page {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 100vh;
  padding: 24px;
  background: url('@/assets/images/login-bg.jpg') center center / cover no-repeat;
}

.login-overlay {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at top right, rgba(10, 124, 255, 0.28), transparent 35%),
    linear-gradient(135deg, rgba(12, 28, 80, 0.72) 0%, rgba(13, 61, 165, 0.48) 100%);
}

.login-panel {
  position: relative;
  z-index: 1;
  width: min(520px, 100%);
  padding: 34px 34px 28px;
  backdrop-filter: blur(12px);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 26px;
}

.login-logo {
  width: 64px;
  height: 64px;
}

.login-title {
  font-size: 28px;
  font-weight: 800;
}

.login-subtitle {
  margin-top: 6px;
  font-size: 14px;
  color: #6f7ea8;
}

.captcha-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px;
  gap: 12px;
  width: 100%;
}

.captcha-image {
  width: 140px;
  height: 52px;
  border-radius: 12px;
  border: 1px solid #dbe8ff;
  background: #f4f8ff;
  cursor: pointer;
}

.login-button {
  width: 100%;
  height: 48px;
  margin-top: 8px;
}

.login-footer {
  margin-top: 18px;
  color: #7f8baa;
  font-size: 13px;
}
</style>
