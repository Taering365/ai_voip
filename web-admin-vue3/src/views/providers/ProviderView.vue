<template>
  <div class="page-card table-section">
    <div class="page-toolbar">
      <div>
        <h2 class="page-title">ASR & TTS 接口配置</h2>
        <p class="page-subtitle">系统默认内置 ASR 与 TTS 模板，接口地址、模型、认证方式、密钥和自定义参数都支持按需修改。</p>
      </div>
      <div class="page-toolbar-right">
        <el-button type="primary" plain @click="loadProviders">刷新</el-button>
        <el-button type="primary" @click="openCreateDialog">新增接口</el-button>
      </div>
    </div>

    <el-table :data="providers" border>
      <el-table-column prop="provider_name" label="接口名称" min-width="180">
        <template #default="{ row }">
          <div class="provider-name-cell">
            <span>{{ row.provider_name }}</span>
            <el-tag v-if="row.config_json?.is_system_default" size="small" type="success">默认</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="provider_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.provider_type === 'asr' ? 'primary' : 'warning'">{{ row.provider_type.toUpperCase() }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="厂商/驱动" min-width="160">
        <template #default="{ row }">
          {{ row.config_json?.interface_name || row.driver_name }}
        </template>
      </el-table-column>
      <el-table-column label="模型" min-width="140">
        <template #default="{ row }">
          {{ row.config_json?.model || '--' }}
        </template>
      </el-table-column>
      <el-table-column label="接口地址" min-width="260" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.config_json?.endpoint || '--' }}
        </template>
      </el-table-column>
      <el-table-column label="密钥" width="110">
        <template #default="{ row }">
          <el-tag :type="hasApiKey(row) ? 'success' : 'info'">{{ hasApiKey(row) ? '已配置' : '未配置' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
          <el-button link type="success" @click="checkProviderHealth(row)">检测</el-button>
          <el-button link type="primary" @click="openDocLink(row)">查看文档</el-button>
          <el-button v-if="!row.config_json?.is_system_default" link type="danger" @click="removeProvider(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增接口' : '编辑接口'" width="840px">
      <el-form :model="formState" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="接口名称">
              <el-input v-model="formState.provider_name" maxlength="128" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="接口类型">
              <el-select v-model="formState.provider_type" :disabled="dialogMode === 'edit'" @change="handleProviderTypeChange">
                <el-option label="ASR" value="asr" />
                <el-option label="TTS" value="tts" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="formState.provider_type === 'asr'" :span="12">
            <el-form-item label="接口方案">
              <el-select v-model="formState.template_key" @change="handleAsrTemplateChange">
                <el-option
                  v-for="item in resolveAsrTemplateOptions()"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="驱动标识">
              <el-input v-model="formState.driver_name" :disabled="dialogMode === 'edit'" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="接口状态">
              <el-switch v-model="formState.is_enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-alert
              :title="resolveTemplateAlertText()"
              type="info"
              :closable="false"
            />
          </el-col>
          <el-col :span="12">
            <el-form-item label="接口地址">
              <el-input v-model="formState.endpoint" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模型名称">
              <el-input v-model="formState.model" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="认证方式">
              <el-select v-model="formState.auth_type">
                <el-option label="none" value="none" />
                <el-option label="bearer" value="bearer" />
                <el-option label="basic" value="basic" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="接口文档">
              <div class="doc-link-line">
                <el-input v-model="formState.docs_url" />
                <el-button plain @click="openDocLink(formState)">打开</el-button>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="API Key">
              <el-input
                v-model="formState.api_key"
                type="password"
                show-password
                :placeholder="formState.key_placeholder || '请输入接口密钥'"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="自定义参数">
          <JsonEditor v-model="formState.custom_params_text" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button v-if="dialogMode === 'edit'" :loading="checkingProvider" @click="checkProviderHealth(formState, true)">检测接口</el-button>
        <el-button type="primary" :loading="submitting" @click="submitProvider">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import JsonEditor from '@/components/JsonEditor.vue'
import { checkProviderHealthApi, createProviderApi, deleteProviderApi, fetchProvidersApi, updateProviderApi } from '@/api/modules'
import { parseJsonText } from '@/utils/format'

const providers = ref([])
const dialogVisible = ref(false)
const dialogMode = ref('create')
const editingId = ref(null)
const submitting = ref(false)
const checkingProvider = ref(false)
const formState = reactive(createDefaultFormState())

/**
 * 创建接口表单默认值对象。
 *
 * @returns {object} 接口表单默认值。
 */
function createDefaultFormState() {
  return buildFormStateByType('asr')
}

/**
 * 根据接口类型生成表单初始值。
 *
 * @param {'asr' | 'tts'} providerType 当前接口类型。
 * @returns {object} 指定类型对应的表单对象。
 */
function buildFormStateByType(providerType) {
  const template = resolveProviderTemplate(providerType)
  return {
    provider_code: '',
    provider_name: template.provider_name,
    provider_type: providerType,
    template_key: template.template_key || '',
    driver_name: template.driver_name,
    is_enabled: true,
    endpoint: template.config_json.endpoint,
    model: template.config_json.model,
    docs_url: template.config_json.docs_url,
    auth_type: template.config_json.auth_type,
    key_placeholder: template.config_json.key_placeholder,
    api_key: '',
    custom_params_text: JSON.stringify(template.config_json.custom_params || {}, null, 2),
    raw_config_json: template.config_json,
  }
}

/**
 * 解析指定类型对应的默认接口模板。
 *
 * @param {'asr' | 'tts'} providerType 当前接口类型。
 * @returns {object} 默认模板对象。
 */
function resolveProviderTemplate(providerType) {
  if (providerType === 'asr') {
    return resolveAsrTemplateByKey('aliyun_bailian_asr_realtime_ws')
  }
  if (providerType === 'tts') {
    return {
      template_key: 'minimax_tts_ws',
      provider_name: 'MiniMax TTS 接口',
      driver_name: 'minimax_tts_ws',
      config_json: {
        interface_name: 'MiniMax TTS',
        docs_url: 'https://platform.minimaxi.com/docs/api-reference/speech-t2a-websocket',
        endpoint: 'wss://api.minimaxi.com/ws/v1/t2a_v2',
        model: 'speech-2.8-turbo',
        auth_type: 'bearer',
        key_placeholder: '请填写 MiniMax API Key',
        custom_params: {
          language_boost: 'Chinese',
          voice_setting: {
            voice_id: 'male-qn-qingse',
            speed: 1,
            vol: 1,
            pitch: 0,
          },
          audio_setting: {
            sample_rate: 32000,
            bitrate: 128000,
            format: 'mp3',
            channel: 1,
          },
        },
        voice_profiles: [
          {
            value: 'male-qn-qingse',
            label: '青涩男声',
            voice_id: 'male-qn-qingse',
            voice_name: '青涩男声',
            speed: 1,
          },
        ],
        default_voice_profile: 'male-qn-qingse',
      },
    }
  }
  return resolveAsrTemplateByKey('aliyun_bailian_asr_realtime_ws')
}

/**
 * 返回页面支持创建的 ASR 模板列表。
 *
 * @returns {Array<{label: string, value: string}>} ASR 模板选项列表。
 */
function resolveAsrTemplateOptions() {
  return [
    { label: '阿里百炼实时 ASR', value: 'aliyun_bailian_asr_realtime_ws' },
    { label: '本地流式 ASR', value: 'qwen_stream_asr_http' },
  ]
}

/**
 * 根据模板标识返回对应的 ASR 模板。
 *
 * @param {string} templateKey 当前选中的模板标识。
 * @returns {object} ASR 模板对象。
 */
function resolveAsrTemplateByKey(templateKey) {
  if (templateKey === 'qwen_stream_asr_http') {
    return {
      template_key: 'qwen_stream_asr_http',
      provider_name: '本地流式 ASR 接口',
      driver_name: 'qwen_stream_asr_http',
      config_json: {
        interface_name: '本地流式 ASR',
        docs_url: '',
        endpoint: 'http://127.0.0.1:8000/api/asr/stream',
        model: 'qwen-stream-asr',
        auth_type: 'none',
        key_placeholder: '本地流式 ASR 默认无需 API Key',
        custom_params: {
          language: 'zh',
          context: '',
          chunk_size_sec: 0.24,
          client_chunk_size_sec: 0.06,
          unfixed_chunk_num: 1,
          unfixed_token_num: 2,
          vad: true,
          denoise: true,
          noise_threshold: 0.015,
          sample_rate: 16000,
          max_sentence_silence: 280,
        },
      },
    }
  }
  return {
    template_key: 'aliyun_bailian_asr_realtime_ws',
    provider_name: '阿里百炼 ASR 接口',
    driver_name: 'aliyun_bailian_asr_realtime_ws',
    config_json: {
      interface_name: '阿里百炼 ASR',
      docs_url: 'https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-interaction-process',
      endpoint: 'wss://dashscope.aliyuncs.com/api-ws/v1/inference',
      model: 'paraformer-realtime-8k-v2',
      auth_type: 'bearer',
      key_placeholder: '请填写阿里云百炼 API Key',
      custom_params: {
        format: 'pcm',
        sample_rate: 8000,
        language_hints: ['zh'],
        semantic_punctuation_enabled: true,
        max_sentence_silence_ms: 500,
      },
    },
  }
}

/**
 * 根据当前表单状态生成模板提示文案。
 *
 * @returns {string} 接口模板提示文本。
 */
function resolveTemplateAlertText() {
  if (formState.provider_type === 'tts') {
    return 'TTS 默认模板：MiniMax WebSocket 接口'
  }
  if (formState.driver_name === 'qwen_stream_asr_http') {
    return 'ASR 默认模板：本地流式 ASR 接口；接口地址以后端服务器访问视角为准，ASR 不在同机时不要填写 127.0.0.1'
  }
  return 'ASR 默认模板：阿里百炼实时 WebSocket 接口'
}

/**
 * 加载接口配置列表。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadProviders() {
  providers.value = await fetchProvidersApi()
}

/**
 * 打开新增接口弹窗。
 *
 * @returns {void} 无返回值。
 */
function openCreateDialog() {
  dialogMode.value = 'create'
  editingId.value = null
  Object.assign(formState, createDefaultFormState())
  dialogVisible.value = true
}

/**
 * 根据选择的新接口类型同步表单模板。
 *
 * @param {'asr' | 'tts'} providerType 当前选中的接口类型。
 * @returns {void} 无返回值。
 */
function handleProviderTypeChange(providerType) {
  if (dialogMode.value !== 'create') {
    return
  }
  Object.assign(formState, buildFormStateByType(providerType))
}

/**
 * 根据当前选中的 ASR 模板更新表单默认值。
 *
 * @param {string} templateKey 当前选中的 ASR 模板标识。
 * @returns {void} 无返回值。
 */
function handleAsrTemplateChange(templateKey) {
  if (formState.provider_type !== 'asr') {
    return
  }
  const template = resolveAsrTemplateByKey(templateKey)
  Object.assign(formState, {
    template_key: template.template_key,
    provider_name: template.provider_name,
    driver_name: template.driver_name,
    endpoint: template.config_json.endpoint,
    model: template.config_json.model,
    docs_url: template.config_json.docs_url,
    auth_type: template.config_json.auth_type,
    key_placeholder: template.config_json.key_placeholder,
    api_key: formState.api_key,
    custom_params_text: JSON.stringify(template.config_json.custom_params || {}, null, 2),
    raw_config_json: template.config_json,
  })
}

/**
 * 打开编辑接口弹窗。
 *
 * @param {object} row 当前选中的接口配置对象。
 * @returns {void} 无返回值。
 */
function openEditDialog(row) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  Object.assign(formState, {
    provider_code: row.provider_code,
    provider_name: row.provider_name,
    provider_type: row.provider_type,
    template_key: row.driver_name || '',
    driver_name: row.driver_name,
    is_enabled: row.is_enabled,
    endpoint: row.config_json?.endpoint || '',
    model: row.config_json?.model || '',
    docs_url: row.config_json?.docs_url || '',
    auth_type: row.config_json?.auth_type || 'bearer',
    key_placeholder: row.config_json?.key_placeholder || '请输入接口密钥',
    api_key: row.config_json?.api_key || '',
    custom_params_text: JSON.stringify(row.config_json?.custom_params || {}, null, 2),
    raw_config_json: row.config_json || {},
  })
  dialogVisible.value = true
}

/**
 * 判断当前接口是否已经配置密钥。
 *
 * @param {object} row 当前接口配置对象。
 * @returns {boolean} 已配置密钥返回 true，否则返回 false。
 */
function hasApiKey(row) {
  return Boolean(String(row.config_json?.api_key || '').trim())
}

/**
 * 构造接口保存请求体。
 *
 * @returns {object} 可直接提交给后端的接口请求体。
 */
function buildSubmitPayload() {
  const providerType = formState.provider_type
  const template = resolveProviderTemplate(providerType)
  const rawConfig = formState.raw_config_json || {}
  return {
    provider_code: formState.provider_code || `${providerType}_${Date.now()}`,
    provider_name: formState.provider_name.trim(),
    provider_type: providerType,
    driver_name: formState.driver_name || template.driver_name,
    is_enabled: formState.is_enabled,
    config_json: {
      ...template.config_json,
      ...rawConfig,
      endpoint: formState.endpoint,
      model: formState.model,
      docs_url: formState.docs_url,
      auth_type: formState.auth_type,
      key_placeholder: formState.key_placeholder,
      api_key: formState.api_key.trim(),
      custom_params: parseJsonText(formState.custom_params_text, template.config_json.custom_params || {}),
    },
  }
}

/**
 * 校验并解析当前表单里的自定义参数 JSON。
 *
 * @returns {object} 解析成功后的自定义参数对象。
 * @throws {Error} 当 JSON 文本格式不正确时抛出异常，供保存逻辑统一提示。
 */
function parseProviderCustomParams() {
  const providerType = formState.provider_type
  const template = resolveProviderTemplate(providerType)
  return parseJsonText(formState.custom_params_text, template.config_json.custom_params || {})
}

/**
 * 提交接口新增或编辑操作。
 *
 * @returns {Promise<void>} 保存完成后的 Promise。
 */
async function submitProvider() {
  if (!formState.provider_name.trim()) {
    ElMessage.warning('请输入接口名称')
    return
  }
  try {
    parseProviderCustomParams()
  } catch (error) {
    ElMessage.error(`自定义参数 JSON 格式不正确：${error.message || '请检查逗号、引号和括号'}`)
    return
  }
  submitting.value = true
  try {
    const payload = buildSubmitPayload()
    if (dialogMode.value === 'create') {
      await createProviderApi(payload)
      ElMessage.success('接口已创建')
    } else {
      delete payload.provider_code
      await updateProviderApi(editingId.value, payload)
      ElMessage.success('接口已更新')
    }
    dialogVisible.value = false
    await loadProviders()
  } catch (error) {
    ElMessage.error(error?.message || '接口保存失败，请检查配置后重试')
  } finally {
    submitting.value = false
  }
}

/**
 * 检测当前接口的连通状态。
 *
 * @param {object} row 当前接口配置对象或表单对象。
 * @param {boolean} useEditingId 是否使用当前编辑中的接口主键。
 * @returns {Promise<void>} 检测完成后的 Promise。
 */
async function checkProviderHealth(row, useEditingId = false) {
  const providerId = useEditingId ? editingId.value : row.id
  if (!providerId) {
    ElMessage.warning('请先保存接口后再检测')
    return
  }
  checkingProvider.value = true
  try {
    const result = await checkProviderHealthApi(providerId)
    ElMessage.success(result?.message || '接口检测成功')
  } finally {
    checkingProvider.value = false
  }
}

/**
 * 打开当前接口关联的官方文档链接。
 *
 * @param {object} row 当前接口配置对象或表单对象。
 * @returns {void} 无返回值。
 */
function openDocLink(row) {
  const docsUrl = row.config_json?.docs_url || row.docs_url
  if (!docsUrl) {
    ElMessage.warning('当前接口未配置文档地址')
    return
  }
  window.open(docsUrl, '_blank', 'noopener,noreferrer')
}

/**
 * 删除指定接口配置。
 *
 * @param {object} row 当前选中的接口配置对象。
 * @returns {Promise<void>} 删除完成后的 Promise。
 */
async function removeProvider(row) {
  await ElMessageBox.confirm(`确定删除接口「${row.provider_name}」吗？`, '删除确认', {
    type: 'warning',
  })
  await deleteProviderApi(row.id)
  ElMessage.success('接口已删除')
  await loadProviders()
}

onMounted(loadProviders)
</script>

<style scoped>
.provider-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.doc-link-line {
  display: flex;
  gap: 10px;
  width: 100%;
}

.doc-link-line :deep(.el-input) {
  flex: 1;
}
</style>
