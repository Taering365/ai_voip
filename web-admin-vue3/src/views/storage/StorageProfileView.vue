<template>
  <div class="page-card table-section">
    <div class="page-toolbar">
      <div>
        <h2 class="page-title">存储配置</h2>
        <p class="page-subtitle">默认可落到项目内 `data/recorder`，也支持配置 MinIO / S3 兼容存储并即时检测连通性。</p>
      </div>
      <div class="page-toolbar-right">
        <el-button type="primary" plain @click="loadStorageProfiles">刷新</el-button>
        <el-button type="primary" @click="openCreateDialog">新增配置</el-button>
      </div>
    </div>

    <el-table :data="profiles" border>
      <el-table-column prop="profile_name" label="配置名称" min-width="180" />
      <el-table-column prop="storage_backend" label="后端" width="120" />
      <el-table-column label="默认" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_default ? 'success' : 'info'">{{ row.is_default ? '是' : '否' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="root_dir" label="本地目录" min-width="220" show-overflow-tooltip />
      <el-table-column prop="endpoint" label="Endpoint" min-width="220" show-overflow-tooltip />
      <el-table-column prop="bucket_name" label="Bucket" min-width="150" show-overflow-tooltip />
      <el-table-column label="最近检测" min-width="200">
        <template #default="{ row }">
          <span :class="row.extra_config?.probe_status === 'success' ? 'probe-success' : 'probe-failed'">
            {{ row.extra_config?.probe_message || '未检测' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
          <el-button link type="success" @click="probeExistingProfile(row)">检测</el-button>
          <el-button link type="primary" @click="setDefaultProfile(row)">设为默认</el-button>
          <el-button link type="danger" @click="removeProfile(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增存储配置' : '编辑存储配置'" width="780px">
      <el-form :model="formState" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="配置名称">
              <el-input v-model="formState.profile_name" maxlength="128" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="存储后端">
              <el-select v-model="formState.storage_backend" @change="handleStorageBackendChange">
                <el-option label="本地落盘" value="local" />
                <el-option label="S3 兼容 / MinIO" value="s3_compatible" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认配置">
              <el-switch v-model="formState.is_default" />
            </el-form-item>
          </el-col>
        </el-row>

        <template v-if="formState.storage_backend === 'local'">
          <el-form-item label="本地根目录">
            <el-input v-model="formState.root_dir" placeholder="data/recorder" />
          </el-form-item>
          <el-alert title="录音、TTS 缓存、转写结果会按子目录自动分层落到该目录下。" type="info" :closable="false" />
        </template>

        <template v-else>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="Endpoint">
                <el-input v-model="formState.endpoint" placeholder="127.0.0.1:9000 或 https://minio.example.com" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Bucket">
                <el-input v-model="formState.bucket_name" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Access Key">
                <el-input v-model="formState.access_key" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Secret Key">
                <el-input v-model="formState.secret_key" type="password" show-password />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="区域">
                <el-input v-model="formState.region_name" placeholder="us-east-1" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="对象前缀">
                <el-input v-model="formState.object_prefix" placeholder="ai-voip" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="使用 HTTPS">
                <el-switch v-model="formState.use_ssl" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Path Style">
                <el-switch v-model="formState.force_path_style" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="自动建桶">
                <el-switch v-model="formState.auto_create_bucket" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="公共访问地址">
                <el-input v-model="formState.public_base_url" placeholder="可选，用于生成外链 URL" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <el-form-item label="扩展配置">
          <JsonEditor v-model="formState.extra_config_text" />
        </el-form-item>

        <div v-if="probeResult.message" class="probe-result-box">
          <el-alert :title="probeResult.message" :type="probeResult.status === 'success' ? 'success' : 'error'" :closable="false" />
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="success" plain :loading="probing" @click="probeCurrentForm">检测配置</el-button>
        <el-button type="primary" :loading="submitting" @click="submitProfile">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import JsonEditor from '@/components/JsonEditor.vue'
import {
  createStorageProfileApi,
  deleteStorageProfileApi,
  fetchStorageProfilesApi,
  probeStorageProfileApi,
  setDefaultStorageProfileApi,
  updateStorageProfileApi,
} from '@/api/modules'
import { parseJsonText } from '@/utils/format'

const profiles = ref([])
const dialogVisible = ref(false)
const dialogMode = ref('create')
const editingId = ref(null)
const submitting = ref(false)
const probing = ref(false)
const probeResult = reactive(createDefaultProbeResult())
const formState = reactive(createDefaultFormState())

/**
 * 创建存储配置表单的默认值对象。
 *
 * @returns {object} 适用于新增与编辑弹窗的默认表单对象。
 */
function createDefaultFormState() {
  return {
    profile_name: '',
    storage_backend: 'local',
    is_default: false,
    root_dir: 'data/recorder',
    endpoint: '',
    bucket_name: '',
    access_key: '',
    secret_key: '',
    region_name: 'us-east-1',
    object_prefix: 'ai-voip',
    public_base_url: '',
    use_ssl: false,
    force_path_style: true,
    auto_create_bucket: false,
    extra_config_text: '{}',
  }
}

/**
 * 创建检测结果默认对象。
 *
 * @returns {{status: string, message: string}} 默认检测结果对象。
 */
function createDefaultProbeResult() {
  return {
    status: '',
    message: '',
  }
}

/**
 * 将表单状态重置为默认值。
 *
 * @returns {void} 无返回值。
 */
function resetFormState() {
  Object.assign(formState, createDefaultFormState())
  Object.assign(probeResult, createDefaultProbeResult())
}

/**
 * 加载存储配置列表。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadStorageProfiles() {
  profiles.value = await fetchStorageProfilesApi()
}

/**
 * 根据后端类型切换同步默认表单值。
 *
 * @param {string} storageBackend 当前选中的存储后端类型。
 * @returns {void} 无返回值。
 */
function handleStorageBackendChange(storageBackend) {
  if (storageBackend === 'local') {
    formState.root_dir = formState.root_dir || 'data/recorder'
  } else {
    formState.region_name = formState.region_name || 'us-east-1'
    formState.object_prefix = formState.object_prefix || 'ai-voip'
    formState.force_path_style = true
  }
}

/**
 * 打开新增配置弹窗。
 *
 * @returns {void} 无返回值。
 */
function openCreateDialog() {
  dialogMode.value = 'create'
  editingId.value = null
  resetFormState()
  dialogVisible.value = true
}

/**
 * 打开编辑配置弹窗并填充表单。
 *
 * @param {object} row 当前选中的存储配置对象。
 * @returns {void} 无返回值。
 */
function openEditDialog(row) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  Object.assign(formState, {
    profile_name: row.profile_name,
    storage_backend: row.storage_backend,
    is_default: row.is_default,
    root_dir: row.root_dir || 'data/recorder',
    endpoint: row.endpoint || '',
    bucket_name: row.bucket_name || '',
    access_key: row.access_key || '',
    secret_key: row.secret_key || '',
    region_name: row.region_name || 'us-east-1',
    object_prefix: row.extra_config?.object_prefix || 'ai-voip',
    public_base_url: row.extra_config?.public_base_url || '',
    use_ssl: Boolean(row.extra_config?.use_ssl),
    force_path_style: row.extra_config?.force_path_style !== false,
    auto_create_bucket: Boolean(row.extra_config?.auto_create_bucket),
    extra_config_text: JSON.stringify(row.extra_config || {}, null, 2),
  })
  Object.assign(probeResult, {
    status: row.extra_config?.probe_status || '',
    message: row.extra_config?.probe_message || '',
  })
  dialogVisible.value = true
}

/**
 * 构造提交给后端的存储配置请求体。
 *
 * @returns {object} 已转换完成的请求体对象。
 */
function buildSubmitPayload() {
  const parsedExtraConfig = parseJsonText(formState.extra_config_text, {})
  return {
    profile_name: formState.profile_name.trim(),
    storage_backend: formState.storage_backend,
    is_default: formState.is_default,
    root_dir: formState.storage_backend === 'local' ? formState.root_dir.trim() || 'data/recorder' : null,
    endpoint: formState.storage_backend === 's3_compatible' ? formState.endpoint.trim() || null : null,
    bucket_name: formState.storage_backend === 's3_compatible' ? formState.bucket_name.trim() || null : null,
    access_key: formState.storage_backend === 's3_compatible' ? formState.access_key.trim() || null : null,
    secret_key: formState.storage_backend === 's3_compatible' ? formState.secret_key.trim() || null : null,
    region_name: formState.storage_backend === 's3_compatible' ? formState.region_name.trim() || 'us-east-1' : null,
    extra_config: {
      ...parsedExtraConfig,
      object_prefix: formState.object_prefix.trim() || 'ai-voip',
      public_base_url: formState.public_base_url.trim() || null,
      use_ssl: formState.use_ssl,
      force_path_style: formState.force_path_style,
      auto_create_bucket: formState.auto_create_bucket,
      ...(probeResult.message
        ? {
            probe_status: probeResult.status,
            probe_message: probeResult.message,
          }
        : {}),
    },
  }
}

/**
 * 检测当前表单里的存储配置。
 *
 * @returns {Promise<void>} 检测完成后的 Promise。
 */
async function probeCurrentForm() {
  probing.value = true
  try {
    const result = await probeStorageProfileApi(buildSubmitPayload())
    Object.assign(probeResult, {
      status: result.status,
      message: result.message,
    })
    ElMessage.success(result.message)
  } finally {
    probing.value = false
  }
}

/**
 * 检测列表中已有的存储配置。
 *
 * @param {object} row 当前选中的存储配置对象。
 * @returns {Promise<void>} 检测完成后的 Promise。
 */
async function probeExistingProfile(row) {
  const payload = {
    profile_name: row.profile_name,
    storage_backend: row.storage_backend,
    is_default: row.is_default,
    root_dir: row.root_dir || null,
    endpoint: row.endpoint || null,
    bucket_name: row.bucket_name || null,
    access_key: row.access_key || null,
    secret_key: row.secret_key || null,
    region_name: row.region_name || null,
    extra_config: row.extra_config || {},
  }
  const result = await probeStorageProfileApi(payload)
  ElMessage.success(result.message)
}

/**
 * 提交新增或编辑的存储配置。
 *
 * @returns {Promise<void>} 保存完成后的 Promise。
 */
async function submitProfile() {
  if (!formState.profile_name.trim()) {
    ElMessage.warning('请输入配置名称')
    return
  }
  submitting.value = true
  try {
    const payload = buildSubmitPayload()
    if (dialogMode.value === 'create') {
      await createStorageProfileApi(payload)
      ElMessage.success('存储配置已创建')
    } else {
      await updateStorageProfileApi(editingId.value, payload)
      ElMessage.success('存储配置已更新')
    }

    dialogVisible.value = false
    await loadStorageProfiles()
  } finally {
    submitting.value = false
  }
}

/**
 * 将指定存储配置设置为默认配置。
 *
 * @param {object} row 当前选中的存储配置对象。
 * @returns {Promise<void>} 设置完成后的 Promise。
 */
async function setDefaultProfile(row) {
  await setDefaultStorageProfileApi(row.id)
  ElMessage.success('默认存储已更新')
  await loadStorageProfiles()
}

/**
 * 删除指定存储配置。
 *
 * @param {object} row 当前选中的存储配置对象。
 * @returns {Promise<void>} 删除完成后的 Promise。
 */
async function removeProfile(row) {
  await ElMessageBox.confirm(`确定删除存储配置「${row.profile_name}」吗？`, '删除确认', {
    type: 'warning',
  })
  await deleteStorageProfileApi(row.id)
  ElMessage.success('存储配置已删除')
  await loadStorageProfiles()
}

onMounted(loadStorageProfiles)
</script>

<style scoped>
.probe-success {
  color: #1f9d55;
}

.probe-failed {
  color: #d03050;
}

.probe-result-box {
  margin-top: 12px;
}
</style>
