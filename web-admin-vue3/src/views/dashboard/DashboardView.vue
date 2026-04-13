<template>
  <div class="dashboard-page">
    <div class="dense-grid">
      <StatCard label="线路数量" :value="summary.trunks" description="当前已接入的 SIP 线路" :icon="Connection" />
      <StatCard label="话术数量" :value="summary.scripts" description="已创建的话术主档数量" :icon="ChatLineRound" />
      <StatCard label="任务数量" :value="summary.tasks" description="平台全部外呼任务总数" :icon="Operation" />
      <StatCard label="会话数量" :value="summary.sessions" description="任务下累计通话会话数量" :icon="Phone" />
    </div>

    <div class="split-grid" style="margin-top: 22px;">
      <div class="page-card table-section">
        <div class="page-toolbar">
          <div>
            <h2 class="page-title">平台概览</h2>
            <p class="page-subtitle">根据现有接口实时聚合基础数据，便于运营快速查看当前资源状态。</p>
          </div>
          <el-button type="primary" plain @click="loadDashboardData">刷新</el-button>
        </div>

        <el-descriptions :column="1" border>
          <el-descriptions-item label="服务状态">{{ healthData.status || 'unknown' }}</el-descriptions-item>
          <el-descriptions-item label="运行环境">{{ healthData.environment || '--' }}</el-descriptions-item>
          <el-descriptions-item label="当前用户">{{ currentUser.username || '--' }}</el-descriptions-item>
          <el-descriptions-item label="角色">
            {{ (currentUser.role_codes || []).join(' / ') || '--' }}
          </el-descriptions-item>
          <el-descriptions-item label="系统配置数">{{ summary.configs }}</el-descriptions-item>
          <el-descriptions-item label="默认存储">{{ defaultStorage.profile_name || '--' }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="page-card table-section">
        <div class="page-toolbar">
          <div>
            <h2 class="page-title">资源快照</h2>
            <p class="page-subtitle">显示默认存储与最新任务，适合部署验收时快速检查。</p>
          </div>
        </div>

        <el-empty v-if="!recentTask.task_name && !defaultStorage.profile_name" description="暂无可展示数据" />

        <template v-else>
          <div class="snapshot-panel">
            <div class="snapshot-item">
              <div class="snapshot-label">默认存储</div>
              <div class="snapshot-value">{{ defaultStorage.profile_name || '--' }}</div>
              <div class="snapshot-desc mono-text">{{ defaultStorage.root_dir || defaultStorage.endpoint || '--' }}</div>
            </div>
            <div class="snapshot-item">
              <div class="snapshot-label">最近任务</div>
              <div class="snapshot-value">{{ recentTask.task_name || '--' }}</div>
              <div class="snapshot-desc">状态：{{ recentTask.task_status || '--' }}</div>
            </div>
            <div class="snapshot-item">
              <div class="snapshot-label">最近线路</div>
              <div class="snapshot-value">{{ recentTrunk.trunk_name || '--' }}</div>
              <div class="snapshot-desc">地址：{{ recentTrunk.server_host || '--' }}</div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ChatLineRound, Connection, Operation, Phone } from '@element-plus/icons-vue'
import { onMounted, reactive, ref } from 'vue'

import StatCard from '@/components/StatCard.vue'
import {
  fetchCurrentUserApi,
  fetchDefaultStorageProfileApi,
  fetchHealthApi,
  fetchScriptVersionsApi,
  fetchScriptsApi,
  fetchStorageProfilesApi,
  fetchSystemConfigsApi,
  fetchTaskSessionsApi,
  fetchTasksApi,
  fetchTrunksApi,
} from '@/api/modules'

const summary = reactive({
  trunks: 0,
  scripts: 0,
  tasks: 0,
  sessions: 0,
  configs: 0,
})
const currentUser = reactive({})
const healthData = reactive({})
const defaultStorage = reactive({})
const recentTask = reactive({})
const recentTrunk = reactive({})

/**
 * 统计全部任务对应的会话总数。
 *
 * @param {Array<object>} tasks 当前任务列表数组。
 * @returns {Promise<number>} 聚合后的会话数量。
 */
async function countAllSessions(tasks) {
  if (!tasks.length) {
    return 0
  }

  const sessionGroups = await Promise.all(tasks.map((task) => fetchTaskSessionsApi(task.id)))
  return sessionGroups.reduce((totalCount, items) => totalCount + items.length, 0)
}

/**
 * 加载控制台首页所需的全部数据。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadDashboardData() {
  const [health, configs, me, storageList, scriptList, taskList, trunkList] = await Promise.all([
    fetchHealthApi(),
    fetchSystemConfigsApi(),
    fetchCurrentUserApi(),
    fetchStorageProfilesApi(),
    fetchScriptsApi(),
    fetchTasksApi(),
    fetchTrunksApi(),
  ])

  Object.assign(healthData, health || {})
  Object.assign(currentUser, me || {})
  summary.configs = configs.length
  summary.trunks = trunkList.length
  summary.scripts = scriptList.length
  summary.tasks = taskList.length
  summary.sessions = await countAllSessions(taskList)

  const latestTask = [...taskList].sort((leftItem, rightItem) => (rightItem.id || 0) - (leftItem.id || 0))[0]
  const latestTrunk = [...trunkList].sort((leftItem, rightItem) => (rightItem.id || 0) - (leftItem.id || 0))[0]

  Object.assign(recentTask, latestTask || {})
  Object.assign(recentTrunk, latestTrunk || {})

  try {
    const defaultProfile = await fetchDefaultStorageProfileApi()
    Object.assign(defaultStorage, defaultProfile || {})
  } catch (error) {
    Object.assign(defaultStorage, {})
  }

  void fetchScriptVersionsApi
}

onMounted(loadDashboardData)
</script>

<style scoped lang="scss">
.dashboard-page {
  min-width: 0;
}

.snapshot-panel {
  display: grid;
  gap: 14px;
}

.snapshot-item {
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, #f7fbff 0%, #eef4ff 100%);
  border: 1px solid #e0ebff;
}

.snapshot-label {
  color: #7380a7;
  font-size: 13px;
}

.snapshot-value {
  margin-top: 10px;
  font-size: 20px;
  font-weight: 800;
}

.snapshot-desc {
  margin-top: 8px;
  font-size: 13px;
  color: #8a96b7;
}
</style>
