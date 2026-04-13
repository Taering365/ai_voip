<template>
  <div class="page-card table-section trunk-page">
    <div class="page-toolbar">
      <div>
        <h2 class="page-title">线路管理</h2>
        <p class="page-subtitle">管理员可统一维护 SIP 账号线路和网关对接线路，再分配给业务用户使用。</p>
      </div>
      <div class="page-toolbar-right">
        <el-button type="primary" plain @click="loadTrunks">刷新</el-button>
        <el-button type="primary" @click="openCreateDialog">新增线路</el-button>
      </div>
    </div>

    <div class="trunk-summary-grid">
      <div class="trunk-summary-card">
        <span class="summary-label">总线路数</span>
        <strong class="summary-value">{{ trunks.length }}</strong>
      </div>
      <div class="trunk-summary-card">
        <span class="summary-label">SIP 账号</span>
        <strong class="summary-value">{{ sipCount }}</strong>
      </div>
      <div class="trunk-summary-card">
        <span class="summary-label">网关对接</span>
        <strong class="summary-value">{{ gatewayCount }}</strong>
      </div>
      <div class="trunk-summary-card">
        <span class="summary-label">已启用</span>
        <strong class="summary-value">{{ enabledCount }}</strong>
      </div>
    </div>

    <el-table :data="trunks" border>
      <el-table-column prop="trunk_name" label="线路名称" min-width="180" />
      <el-table-column label="线路类型" width="120">
        <template #default="{ row }">
          <span class="type-chip" :class="row.trunk_type === 'gateway' ? 'is-gateway' : 'is-sip'">
            {{ row.trunk_type === 'gateway' ? '网关对接' : 'SIP账号' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="接入信息" min-width="220">
        <template #default="{ row }">
          <div class="endpoint-block">
            <strong>{{ row.trunk_type === 'gateway' ? row.ip_address : row.domain }}</strong>
            <span>{{ row.port }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="账号/主叫" min-width="220">
        <template #default="{ row }">
          <div class="trunk-meta">
            <span v-if="row.trunk_type === 'sip_account'">Full Name：{{ row.full_name || '--' }}</span>
            <span v-if="row.trunk_type === 'sip_account'">Username：{{ row.username || '--' }}</span>
            <span v-else>主叫：{{ row.caller_id_number || '--' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="并发" width="140">
        <template #default="{ row }">
          {{ row.support_concurrency ? `启用 / ${row.max_concurrency}` : '关闭 / 1' }}
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="180" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <span class="status-chip" :class="resolveStatusClass(row.trunk_status)">{{ row.trunk_status }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="320" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
          <el-button link type="info" :loading="probingId === row.id" @click="probeTrunk(row)">检测</el-button>
          <el-button link type="success" @click="updateStatus(row, 'enabled')">启用</el-button>
          <el-button link type="warning" @click="updateStatus(row, 'disabled')">停用</el-button>
          <el-button link type="danger" @click="removeTrunk(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增线路' : '编辑线路'" width="900px">
      <div class="line-type-switcher">
        <button
          v-for="typeOption in trunkTypeOptions"
          :key="typeOption.value"
          type="button"
          class="line-type-card"
          :class="{ 'is-active': formState.trunk_type === typeOption.value }"
          @click="switchTrunkType(typeOption.value)"
        >
          <strong>{{ typeOption.label }}</strong>
          <span>{{ typeOption.description }}</span>
        </button>
      </div>

      <el-form :model="formState" label-width="110px">
        <el-row :gutter="18">
          <el-col :span="24">
            <el-form-item label="线路名称">
              <el-input v-model="formState.trunk_name" />
            </el-form-item>
          </el-col>
        </el-row>

        <template v-if="formState.trunk_type === 'sip_account'">
          <el-row :gutter="18">
            <el-col :span="12">
              <el-form-item label="Domain">
                <el-input v-model="formState.domain" placeholder="例如 10.2.1.10 或 10.2.1.10:5080" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Full Name">
                <el-input v-model="formState.full_name" placeholder="相当于显示用户名" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Username">
                <el-input v-model="formState.username" placeholder="SIP 用户名" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Password">
                <el-input
                  v-model="formState.password_cipher"
                  type="password"
                  show-password
                  :placeholder="dialogMode === 'edit' ? '留空表示不修改密码' : '请输入 SIP 密码'"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <template v-else>
          <el-row :gutter="18">
            <el-col :span="12">
              <el-form-item label="IP地址">
                <el-input v-model="formState.ip_address" placeholder="请输入网关 IP" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="端口">
                <el-input-number v-model="formState.port" :min="1" :max="65535" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="主叫">
                <el-input v-model="formState.caller_id_number" placeholder="例如 02112345678" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <el-row :gutter="18">
          <el-col :span="12">
            <el-form-item label="支持并发">
              <el-switch v-model="formState.support_concurrency" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="并发数量">
              <div class="concurrency-field">
                <el-select
                  v-model="selectedConcurrencyOption"
                  :disabled="!formState.support_concurrency"
                  clearable
                  placeholder="先选常用值"
                  style="flex: 1"
                  @change="handleConcurrencySelect"
                >
                  <el-option v-for="option in concurrencyOptions" :key="option" :label="`${option} 路`" :value="option" />
                </el-select>
                <el-input-number
                  v-model="formState.max_concurrency"
                  :disabled="!formState.support_concurrency"
                  :min="1"
                  :max="99"
                  controls-position="right"
                  style="width: 140px"
                />
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="描述">
              <el-input v-model="formState.description" type="textarea" :rows="3" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitTrunk">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createTrunkApi, deleteTrunkApi, fetchTrunksApi, probeTrunkApi, updateTrunkApi, updateTrunkStatusApi } from '@/api/modules'
import { resolveStatusClass } from '@/utils/format'

const trunks = ref([])
const dialogVisible = ref(false)
const dialogMode = ref('create')
const editingId = ref(null)
const submitting = ref(false)
const probingId = ref(null)
const selectedConcurrencyOption = ref(null)
const formState = reactive(createDefaultFormState())
const concurrencyOptions = Array.from({ length: 99 }, (_, index) => index + 1)
const trunkTypeOptions = [
  {
    value: 'sip_account',
    label: 'SIP账号',
    description: '适合第三方直接提供注册账号、密码和 Domain 的线路。',
  },
  {
    value: 'gateway',
    label: '网关对接',
    description: '适合通过固定 IP、端口和主叫接入网关设备的线路。',
  },
]

const sipCount = computed(() => trunks.value.filter((item) => item.trunk_type === 'sip_account').length)
const gatewayCount = computed(() => trunks.value.filter((item) => item.trunk_type === 'gateway').length)
const enabledCount = computed(() => trunks.value.filter((item) => item.trunk_status === 'enabled').length)

/**
 * 创建线路表单默认值。
 *
 * @returns {object} 返回初始化后的线路表单对象。
 */
function createDefaultFormState() {
  return {
    trunk_name: '',
    trunk_type: 'sip_account',
    description: '',
    support_concurrency: false,
    max_concurrency: 1,
    trunk_status: 'draft',
    transport: 'udp',
    domain: '',
    full_name: '',
    username: '',
    password_cipher: '',
    ip_address: '',
    port: 5060,
    caller_id_number: '',
  }
}

/**
 * 重置线路表单状态。
 *
 * @returns {void}
 */
function resetFormState() {
  Object.assign(formState, createDefaultFormState())
  selectedConcurrencyOption.value = null
}

/**
 * 切换当前表单中的线路类型。
 *
 * @param {string} trunkType 目标线路类型值。
 * @returns {void}
 */
function switchTrunkType(trunkType) {
  formState.trunk_type = trunkType
  formState.support_concurrency = false
  formState.max_concurrency = 1
  if (trunkType === 'sip_account') {
    formState.ip_address = ''
    formState.port = 5060
    formState.caller_id_number = ''
  } else {
    formState.domain = ''
    formState.full_name = ''
    formState.username = ''
    formState.password_cipher = ''
  }
}

/**
 * 加载线路列表。
 *
 * @returns {Promise<void>} 返回线路加载完成后的 Promise。
 */
async function loadTrunks() {
  trunks.value = await fetchTrunksApi()
}

/**
 * 打开新增线路弹窗。
 *
 * @returns {void}
 */
function openCreateDialog() {
  dialogMode.value = 'create'
  editingId.value = null
  resetFormState()
  dialogVisible.value = true
}

/**
 * 打开编辑线路弹窗。
 *
 * @param {object} row 当前选中的线路对象。
 * @returns {void}
 */
function openEditDialog(row) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  selectedConcurrencyOption.value = row.max_concurrency
  Object.assign(formState, {
    trunk_name: row.trunk_name,
    trunk_type: row.trunk_type,
    description: row.description || '',
    support_concurrency: row.support_concurrency,
    max_concurrency: row.max_concurrency,
    trunk_status: row.trunk_status,
    transport: row.transport || 'udp',
    domain: row.domain || '',
    full_name: row.full_name || '',
    username: row.username || '',
    password_cipher: '',
    ip_address: row.ip_address || '',
    port: row.port || 5060,
    caller_id_number: row.caller_id_number || '',
  })
  dialogVisible.value = true
}

/**
 * 构造线路保存请求体。
 *
 * @returns {object} 返回可提交给后端的线路请求对象。
 */
function buildSubmitPayload() {
  return {
    trunk_code: dialogMode.value === 'create' ? buildAutoTrunkCode(formState.trunk_type) : undefined,
    trunk_name: formState.trunk_name.trim(),
    trunk_type: formState.trunk_type,
    description: formState.description?.trim() || null,
    support_concurrency: formState.support_concurrency,
    max_concurrency: Number(formState.max_concurrency || 1),
    trunk_status: formState.trunk_status,
    transport: 'udp',
    domain: formState.trunk_type === 'sip_account' ? formState.domain.trim() : null,
    full_name: formState.trunk_type === 'sip_account' ? formState.full_name.trim() || null : null,
    username: formState.trunk_type === 'sip_account' ? formState.username.trim() || null : null,
    password_cipher: formState.trunk_type === 'sip_account' ? formState.password_cipher || undefined : null,
    ip_address: formState.trunk_type === 'gateway' ? formState.ip_address.trim() : null,
    port: Number(formState.port || 5060),
    caller_id_number: formState.caller_id_number?.trim() || null,
  }
}

/**
 * 根据线路类型生成后台使用的线路编码。
 *
 * @param {string} trunkType 当前线路类型值。
 * @returns {string} 返回自动生成的线路编码。
 */
function buildAutoTrunkCode(trunkType) {
  const prefix = trunkType === 'gateway' ? 'gateway' : 'sip'
  return `${prefix}_${Date.now()}`
}

/**
 * 处理并发预设值选择行为。
 *
 * @param {number | null} value 当前选中的并发值。
 * @returns {void}
 */
function handleConcurrencySelect(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    formState.max_concurrency = value
  }
}

/**
 * 校验线路表单是否填写完整。
 *
 * @returns {boolean} 校验通过返回 `true`，否则返回 `false`。
 */
function validateTrunkForm() {
  if (!formState.trunk_name.trim()) {
    ElMessage.warning('请输入线路名称')
    return false
  }

  if (formState.trunk_type === 'sip_account') {
    if (!formState.domain.trim()) {
      ElMessage.warning('请输入 Domain')
      return false
    }
    if (!formState.full_name.trim()) {
      ElMessage.warning('请输入 Full Name')
      return false
    }
    if (!formState.username.trim()) {
      ElMessage.warning('请输入 Username')
      return false
    }
    if (dialogMode.value === 'create' && !formState.password_cipher) {
      ElMessage.warning('请输入 Password')
      return false
    }
  } else {
    if (!formState.ip_address.trim()) {
      ElMessage.warning('请输入网关 IP 地址')
      return false
    }
    if (!formState.caller_id_number.trim()) {
      ElMessage.warning('请输入主叫号码')
      return false
    }
  }

  if (formState.support_concurrency) {
    if (!Number.isInteger(Number(formState.max_concurrency))) {
      ElMessage.warning('并发数量必须为纯数字')
      return false
    }
    if (Number(formState.max_concurrency) < 1 || Number(formState.max_concurrency) > 99) {
      ElMessage.warning('并发数量只能在 1 到 99 之间')
      return false
    }
  }

  return true
}

/**
 * 提交线路表单。
 *
 * @returns {Promise<void>} 返回保存完成后的 Promise。
 */
async function submitTrunk() {
  if (!validateTrunkForm()) {
    return
  }
  submitting.value = true
  try {
    const payload = buildSubmitPayload()
    if (dialogMode.value === 'create') {
      await createTrunkApi(payload)
      ElMessage.success('线路已创建')
    } else {
      await updateTrunkApi(editingId.value, payload)
      ElMessage.success('线路已更新')
    }
    dialogVisible.value = false
    await loadTrunks()
  } finally {
    submitting.value = false
  }
}

/**
 * 更新线路状态。
 *
 * @param {object} row 当前选中的线路对象。
 * @param {string} targetStatus 目标状态值。
 * @returns {Promise<void>} 返回状态更新完成后的 Promise。
 */
async function updateStatus(row, targetStatus) {
  await updateTrunkStatusApi(row.id, { trunk_status: targetStatus })
  ElMessage.success('线路状态已更新')
  await loadTrunks()
}

/**
 * 触发线路检测并展示检测结果。
 *
 * @param {object} row 当前要检测的线路对象。
 * @returns {Promise<void>} 返回检测完成后的 Promise。
 */
async function probeTrunk(row) {
  probingId.value = row.id
  try {
    const result = await probeTrunkApi(row.id)
    const connectStatusText = resolveProbeStatusText(result.connect_status, '连通')
    const registerStatusText = resolveProbeStatusText(result.register_status, '注册')
    const lines = [
      `线路：${result.trunk_name}`,
      `类型：${result.trunk_type === 'gateway' ? '网关对接' : 'SIP账号'}`,
      `目标：${result.host}:${result.port}`,
      `连通状态：${connectStatusText}`,
      `注册状态：${registerStatusText}`,
      `耗时：${result.latency_ms}ms`,
      `说明：${result.message}`,
    ]
    await ElMessageBox.alert(
      `<div class="probe-result-pre">${lines.join('<br>')}</div>`,
      '线路检测结果',
      {
        confirmButtonText: '知道了',
        dangerouslyUseHTMLString: true,
      },
    )
  } finally {
    probingId.value = null
  }
}

/**
 * 删除指定线路。
 *
 * @param {object} row 当前要删除的线路对象。
 * @returns {Promise<void>} 返回删除完成后的 Promise。
 */
async function removeTrunk(row) {
  await ElMessageBox.confirm(`确定删除线路「${row.trunk_name}」吗？`, '删除确认', { type: 'warning' })
  await deleteTrunkApi(row.id)
  ElMessage.success('线路已删除')
  await loadTrunks()
}

/**
 * 将线路检测状态值转换为更易理解的中文文本。
 *
 * @param {string} status 原始状态值。
 * @param {string} scene 当前展示场景，用于细化文案。
 * @returns {string} 返回中文说明文本。
 */
function resolveProbeStatusText(status, scene) {
  if (status === 'success') {
    return scene === '注册' ? '基础信息完整，可继续做注册验证' : '连通正常'
  }
  if (status === 'warning') {
    return scene === '注册' ? '暂未做真实注册，仅完成基础条件检查' : '已完成地址检测，建议继续人工确认'
  }
  if (status === 'not_applicable') {
    return '当前线路类型无需注册'
  }
  if (status === 'failed') {
    return scene === '注册' ? '注册前置信息不完整' : '连通失败'
  }
  return status || '--'
}

onMounted(loadTrunks)
</script>

<style scoped lang="scss">
.trunk-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.trunk-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.trunk-summary-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px 20px;
  border-radius: 20px;
  background: linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
  border: 1px solid #dbe8ff;
}

.summary-label {
  font-size: 13px;
  color: var(--app-text-soft);
}

.summary-value {
  font-size: 28px;
  color: #2359c9;
}

.type-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 74px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.type-chip.is-sip {
  color: #125fd6;
  background: #eaf2ff;
}

.type-chip.is-gateway {
  color: #7b4acb;
  background: #f1e8ff;
}

.endpoint-block,
.trunk-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.endpoint-block strong {
  color: #2b3f71;
}

.endpoint-block span,
.trunk-meta span {
  font-size: 12px;
  color: var(--app-text-soft);
}

.line-type-switcher {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 22px;
}

.line-type-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 18px 20px;
  border: 1px solid #d8e6ff;
  border-radius: 20px;
  background: linear-gradient(180deg, #fafdff 0%, #eff4ff 100%);
  color: #31518f;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.line-type-card span {
  font-size: 13px;
  line-height: 1.6;
  color: #7381a6;
}

.line-type-card.is-active {
  border-color: #4b82ff;
  box-shadow: 0 14px 28px rgba(44, 103, 220, 0.12);
  transform: translateY(-2px);
}

.concurrency-field {
  display: flex;
  gap: 10px;
  width: 100%;
}

:deep(.probe-result-pre) {
  line-height: 1.9;
  font-size: 14px;
  color: #33456f;
  white-space: normal;
}

@media (max-width: 1080px) {
  .trunk-summary-grid,
  .line-type-switcher {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 720px) {
  .trunk-summary-grid,
  .line-type-switcher {
    grid-template-columns: 1fr;
  }
}
</style>
