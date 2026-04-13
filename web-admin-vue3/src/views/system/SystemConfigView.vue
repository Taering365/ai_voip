<template>
  <div class="split-grid">
    <div class="page-card table-section">
      <div class="page-toolbar">
        <div>
          <h2 class="page-title">当前登录信息</h2>
          <p class="page-subtitle">展示当前 token 对应的用户主体信息。</p>
        </div>
        <el-button type="primary" plain @click="loadSystemData">刷新</el-button>
      </div>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="用户 ID">{{ userInfo.id || '--' }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ userInfo.username || '--' }}</el-descriptions-item>
        <el-descriptions-item label="显示名称">{{ userInfo.display_name || '--' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ userInfo.status || '--' }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ (userInfo.role_codes || []).join(' / ') || '--' }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="page-card table-section">
      <div class="page-toolbar">
        <div>
          <h2 class="page-title">系统配置</h2>
          <p class="page-subtitle">读取后端 `sys_config` 配置项，便于部署后逐项核验。</p>
        </div>
      </div>

      <el-table :data="configs" border>
        <el-table-column prop="config_key" label="配置键" min-width="220" />
        <el-table-column prop="config_value" label="配置值" min-width="220" show-overflow-tooltip />
        <el-table-column prop="config_type" label="类型" width="120" />
        <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { fetchCurrentUserApi, fetchSystemConfigsApi } from '@/api/modules'

const configs = ref([])
const userInfo = ref({})

/**
 * 加载系统配置页所需的数据。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadSystemData() {
  const [currentUser, configItems] = await Promise.all([fetchCurrentUserApi(), fetchSystemConfigsApi()])
  userInfo.value = currentUser || {}
  configs.value = configItems || []
}

onMounted(loadSystemData)
</script>
