<template>
  <div ref="taskPageContainerRef" class="task-page-stack" :class="{ 'is-resizing': panelResizeDragging }">
    <div class="task-page-panel task-page-panel-top" :style="{ height: `${topPanelHeight}px` }">
      <div class="page-card table-section task-page-card">
      <div class="page-toolbar">
        <div>
          <h2 class="page-title">外呼任务</h2>
          <p class="page-subtitle">配置任务与线路、话术、名单之间的关系，并维护运行状态。</p>
        </div>
        <div class="page-toolbar-right">
          <el-button type="primary" plain @click="loadTaskData">刷新</el-button>
          <el-button type="primary" @click="openTaskDialog('create')">新增任务</el-button>
        </div>
      </div>

      <div class="runtime-dependency-panel">
        <div class="runtime-dependency-card">
          <span class="runtime-dependency-label">ASR 接口</span>
          <strong>{{ runtimeAsrStatus.label }}</strong>
          <small>{{ runtimeAsrStatus.detail }}</small>
        </div>
        <div class="runtime-dependency-card">
          <span class="runtime-dependency-label">在线 TTS</span>
          <strong>{{ runtimeTtsStatus.label }}</strong>
          <small>{{ runtimeTtsStatus.detail }}</small>
        </div>
      </div>

      <div class="task-table-wrap">
        <el-table
          ref="taskTableRef"
          :data="tasks"
          border
          height="100%"
          highlight-current-row
          row-key="id"
          :current-row-key="activeTask?.id || undefined"
          @current-change="handleTaskChange"
        >
          <el-table-column label="操作" width="240" fixed="left">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="openTaskDialog('edit', row)">编辑</el-button>
              <el-button link type="success" @click.stop="updateTaskStatus(row, 'running')">运行</el-button>
              <el-button link type="warning" @click.stop="updateTaskStatus(row, 'terminated')">停止</el-button>
              <el-button link type="danger" @click.stop="removeTask(row)">删除</el-button>
            </template>
          </el-table-column>
          <el-table-column prop="task_code" label="任务编码" min-width="150" />
          <el-table-column prop="task_name" label="任务名称" min-width="160" />
          <el-table-column label="所属批次" min-width="140">
            <template #default="{ row }">
              {{ resolveBatchName(row.batch_id) }}
            </template>
          </el-table-column>
          <el-table-column prop="task_type" label="类型" width="100" />
          <el-table-column prop="max_concurrency" label="并发" width="80" />
          <el-table-column prop="retry_limit" label="重试" width="80" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <span class="status-chip" :class="resolveStatusClass(row.task_status)">
                {{ formatStatusLabel(row.task_status, 'task') }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      </div>
    </div>

    <div
      class="task-page-resize-handle"
      role="separator"
      aria-orientation="horizontal"
      title="拖动调整上下区域高度"
      @mousedown="startPanelResize"
    >
      <span class="task-page-resize-grip"></span>
    </div>

    <div class="task-page-panel task-page-panel-bottom">
      <div class="page-card table-section task-page-card task-page-card-bottom">
        <div class="page-toolbar">
          <div>
            <h2 class="page-title">任务会话</h2>
            <p class="page-subtitle">
              {{ activeTask ? `当前任务：${activeTask.task_name}` : '选择左侧任务后查看通话会话。' }}
            </p>
          </div>
          <div class="page-toolbar-right" v-if="activeTask">
            <el-button type="primary" plain @click="loadSessions">刷新会话</el-button>
          <el-button type="primary" @click="queueTask(activeTask)">生成分发表</el-button>
        </div>
      </div>

      <el-empty v-if="!activeTask" description="请选择左侧任务" />

      <template v-else>
        <div class="task-progress-panel">
          <div class="task-run-banner">
            <div>
              <h3>{{ currentTaskRun ? resolveRunTitle(currentTaskRun) : '当前还没有执行批次' }}</h3>
              <p>
                {{
                  currentTaskRun
                    ? `批次状态：${formatStatusLabel(currentTaskRun.run_status, 'run')}，开始时间：${currentTaskRun.started_at || '--'}`
                    : '任务尚未真正开始外呼，点击运行后会生成新的执行批次。'
                }}
              </p>
            </div>
            <span v-if="currentTaskRun" class="status-chip" :class="resolveStatusClass(currentTaskRun.run_status)">
              {{ formatStatusLabel(currentTaskRun.run_status, 'run') }}
            </span>
          </div>

          <div class="task-progress-grid">
            <div class="task-progress-card">
              <span class="task-progress-label">所属批次</span>
              <strong :title="currentTaskBatch?.batch_name || '未绑定批次'" class="batch-name-text">
                {{ currentTaskBatch?.batch_name || '未绑定批次' }}
              </strong>
              <small>总联系人：{{ currentTaskBatch?.import_total || 0 }}</small>
            </div>
            <div class="task-progress-card">
              <span class="task-progress-label">已拨联系人</span>
              <strong>{{ handledContactCount }}</strong>
              <small>估算进度：{{ progressPercent }}%</small>
            </div>
            <div class="task-progress-card">
              <span class="task-progress-label">进行中</span>
              <strong>{{ activeSessions.length }}</strong>
              <small>拨号 / 振铃 / 已接通</small>
            </div>
            <div class="task-progress-card">
              <span class="task-progress-label">已结束</span>
              <strong>{{ finishedSessions.length }}</strong>
              <small>完成 / 失败 / 取消</small>
            </div>
            <div class="task-progress-card">
              <span class="task-progress-label">待处理</span>
              <strong>{{ pendingContactEstimate }}</strong>
              <small>按批次总数估算剩余</small>
            </div>
          </div>

            <div class="current-call-card">
              <div>
                <h3>当前拨打</h3>
                <p>任务运行中会自动刷新，不影响继续外呼。</p>
              </div>
              <div v-if="activeSessions.length" class="current-call-list">
              <div v-for="session in activeSessions" :key="session.id" class="current-call-item">
                <strong>{{ session.callee_number }}</strong>
                <span>
                  状态：{{ formatStatusLabel(session.session_status, 'session') }} / {{ formatStatusLabel(session.answer_status, 'answer') }}
                </span>
                <span>意向：{{ formatIntentLevel(session.intent_level) }}</span>
                <span>节点：{{ session.current_node_code || '--' }}</span>
              </div>
            </div>
            <el-empty v-else description="当前没有正在拨打中的会话" />
          </div>
        </div>

        <el-table :data="currentRunSessions" border>
          <el-table-column label="意向" width="110" fixed="left">
            <template #default="{ row }">
              <span class="status-chip" :class="resolveIntentClass(row.intent_level)">
                {{ formatIntentLevel(row.intent_level) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="contact_record_id" label="联系人 ID" width="100" />
          <el-table-column prop="callee_number" label="被叫号码" min-width="130" />
          <el-table-column prop="session_code" label="会话编码" min-width="170" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              {{ formatStatusLabel(row.session_status, 'session') }}
            </template>
          </el-table-column>
          <el-table-column label="应答" width="110">
            <template #default="{ row }">
              {{ formatStatusLabel(row.answer_status, 'answer') }}
            </template>
          </el-table-column>
          <el-table-column prop="current_node_code" label="当前节点" min-width="130" />
          <el-table-column label="结果" width="110">
            <template #default="{ row }">
              {{ formatStatusLabel(row.result_code, 'result') }}
            </template>
          </el-table-column>
          <el-table-column prop="duration" label="总时长" width="90" />
          <el-table-column prop="billsec" label="计费时长" width="100" />
        </el-table>

        <div class="task-history-card" v-if="historyRuns.length">
          <div class="task-history-header">
            <h3>历史执行批次</h3>
            <p>历史呼叫会话会折叠展示，便于查看当前状态又不丢历史记录。</p>
          </div>
          <el-collapse>
            <el-collapse-item
              v-for="run in historyRuns"
              :key="run.id"
              :title="`${resolveRunTitle(run)} ｜ 状态：${formatStatusLabel(run.run_status, 'run')} ｜ 会话数：${run.session_count}`"
              :name="String(run.id)"
            >
              <el-table :data="resolveRunSessions(run.id)" border>
                <el-table-column label="意向" width="110" fixed="left">
                  <template #default="{ row }">
                    <span class="status-chip" :class="resolveIntentClass(row.intent_level)">
                      {{ formatIntentLevel(row.intent_level) }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="callee_number" label="被叫号码" min-width="130" />
                <el-table-column prop="session_code" label="会话编码" min-width="170" />
                <el-table-column label="状态" width="110">
                  <template #default="{ row }">
                    {{ formatStatusLabel(row.session_status, 'session') }}
                  </template>
                </el-table-column>
                <el-table-column label="应答" width="110">
                  <template #default="{ row }">
                    {{ formatStatusLabel(row.answer_status, 'answer') }}
                  </template>
                </el-table-column>
                <el-table-column label="结果" width="110">
                  <template #default="{ row }">
                    {{ formatStatusLabel(row.result_code, 'result') }}
                  </template>
                </el-table-column>
                <el-table-column prop="started_at" label="开始时间" min-width="170" />
                <el-table-column prop="ended_at" label="结束时间" min-width="170" />
              </el-table>
            </el-collapse-item>
          </el-collapse>
        </div>
      </template>
      </div>
    </div>

    <el-dialog v-model="taskDialogVisible" :title="taskDialogMode === 'create' ? '新增任务' : '编辑任务'" width="840px">
      <el-form :model="taskForm" label-width="110px">
        <el-alert
          :title="`运行前检查：ASR接口 ${runtimeAsrStatus.label}，TTS接口 ${runtimeTtsStatus.label}`"
          :type="runtimeDependencyAlertType"
          :closable="false"
          class="task-runtime-alert"
        />
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="任务编码">
              <el-input v-model="taskForm.task_code" :disabled="taskDialogMode === 'edit'" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="任务名称">
              <el-input v-model="taskForm.task_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="任务类型">
              <el-select v-model="taskForm.task_type">
                <el-option label="outbound" value="outbound" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="线路池">
              <el-select v-model="taskForm.trunk_ids" multiple collapse-tags collapse-tags-tooltip clearable>
                <el-option
                  v-for="trunk in trunks"
                  :key="trunk.id"
                  :label="`${trunk.trunk_name} (#${trunk.id})`"
                  :value="trunk.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="话术">
              <el-select v-model="taskForm.script_id" @change="handleTaskScriptChange">
                <el-option v-for="script in scripts" :key="script.id" :label="script.script_name" :value="script.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="话术版本">
              <el-select v-model="taskForm.script_version_id">
                <el-option
                  v-for="version in currentTaskVersions"
                  :key="version.id"
                  :label="`${version.version_label} (#${version.version_no})`"
                  :value="version.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名单批次">
              <el-select v-model="taskForm.batch_id" clearable>
                <el-option v-for="batch in batches" :key="batch.id" :label="batch.batch_name" :value="batch.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="并发">
              <el-input v-model.number="taskForm.max_concurrency" type="number" min="1" placeholder="请输入并发数" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="CPS">
              <el-input v-model.number="taskForm.cps_limit" type="number" min="1" placeholder="请输入 CPS" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="重试次数">
              <el-input v-model.number="taskForm.retry_limit" type="number" min="0" placeholder="请输入重试次数" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="重试间隔">
              <el-input v-model.number="taskForm.retry_interval_seconds" type="number" min="0" placeholder="请输入秒数" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="时间窗口">
          <JsonEditor v-model="taskForm.call_time_range_text" />
        </el-form-item>
        <el-form-item label="扩展配置">
          <JsonEditor v-model="taskForm.extra_config_text" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingTask" @click="submitTask">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import JsonEditor from '@/components/JsonEditor.vue'
import {
  createTaskApi,
  deleteTaskApi,
  fetchBatchesApi,
  fetchProvidersApi,
  fetchScriptsApi,
  fetchScriptVersionsApi,
  fetchTasksApi,
  fetchTaskSessionsApi,
  fetchTrunksApi,
  queueTaskApi,
  updateTaskApi,
  fetchTaskRunsApi,
  updateTaskStatusApi,
} from '@/api/modules'
import { formatStatusLabel, parseJsonText, resolveStatusClass } from '@/utils/format'

const tasks = ref([])
const sessions = ref([])
const taskRuns = ref([])
const scripts = ref([])
const trunks = ref([])
const batches = ref([])
const providers = ref([])
const activeTask = ref(null)
const taskTableRef = ref(null)
const taskDialogVisible = ref(false)
const taskDialogMode = ref('create')
const editingTaskId = ref(null)
const submittingTask = ref(false)
const currentTaskVersions = ref([])
const taskForm = reactive(createDefaultTaskForm())
const autoRefreshTimer = ref(null)
const taskPageContainerRef = ref(null)
const topPanelHeight = ref(360)
const panelResizeDragging = ref(false)
const panelResizeState = reactive({
  startY: 0,
  startHeight: 360,
})

/**
 * 创建任务表单默认值对象。
 *
 * @returns {object} 任务表单默认值。
 */
function createDefaultTaskForm() {
  return {
    task_code: '',
    task_name: '',
    task_type: 'outbound',
    script_id: null,
    script_version_id: null,
    trunk_id: null,
    trunk_ids: [],
    batch_id: null,
    max_concurrency: 10,
    cps_limit: 2,
    retry_limit: 0,
    retry_interval_seconds: 300,
    call_time_range_text: '{\n  "start": "09:00",\n  "end": "18:00"\n}',
    extra_config_text: '{}',
    task_status: 'draft',
  }
}

/**
 * 根据批次主键解析批次名称。
 *
 * @param {number | null} batchId 当前任务绑定的批次主键。
 * @returns {string} 返回批次名称，未绑定时返回提示文本。
 */
function resolveBatchName(batchId) {
  if (!batchId) {
    return '未绑定批次'
  }
  return batches.value.find((item) => item.id === batchId)?.batch_name || `批次#${batchId}`
}

/**
 * 根据当前容器高度约束顶部面板的最终高度，避免拖拽后把上下区域压得过小。
 *
 * @param {number} targetHeight 当前希望设置的顶部区域高度。
 * @returns {number} 经过最小值与最大值限制后的顶部区域高度。
 */
function clampTopPanelHeight(targetHeight) {
  const containerElement = taskPageContainerRef.value
  const minimumTopHeight = 420
  const minimumBottomHeight = 360
  const resizeHandleHeight = 18
  if (!containerElement) {
    return Math.max(minimumTopHeight, Number(targetHeight) || minimumTopHeight)
  }

  const containerHeight = Math.max(containerElement.clientHeight, minimumTopHeight + minimumBottomHeight + resizeHandleHeight)
  const maximumTopHeight = Math.max(minimumTopHeight, containerHeight - minimumBottomHeight - resizeHandleHeight)
  return Math.min(maximumTopHeight, Math.max(minimumTopHeight, Number(targetHeight) || minimumTopHeight))
}

/**
 * 初始化上下布局的默认高度，优先让下方任务会话区域获得更大空间。
 *
 * @returns {void}
 */
function syncInitialPanelHeight() {
  const containerElement = taskPageContainerRef.value
  if (!containerElement) {
    return
  }

  // 默认将上方任务列表控制在整体高度约 38%，让下方会话区域更贴近客服高频使用场景。
  const suggestedHeight = Math.round(containerElement.clientHeight * 0.38)
  topPanelHeight.value = clampTopPanelHeight(suggestedHeight)
}

/**
 * 开始拖拽上下分隔条，并记录拖拽起点与初始高度。
 *
 * @param {MouseEvent} event 当前鼠标按下事件对象。
 * @returns {void}
 */
function startPanelResize(event) {
  panelResizeDragging.value = true
  panelResizeState.startY = event.clientY
  panelResizeState.startHeight = topPanelHeight.value

  // 拖拽过程中统一由 document 监听鼠标移动，保证鼠标移出分隔条后仍可继续调整高度。
  document.addEventListener('mousemove', handlePanelResizeMove)
  document.addEventListener('mouseup', stopPanelResize)
}

/**
 * 在拖拽过程中根据鼠标位移实时调整顶部区域高度。
 *
 * @param {MouseEvent} event 当前鼠标移动事件对象。
 * @returns {void}
 */
function handlePanelResizeMove(event) {
  if (!panelResizeDragging.value) {
    return
  }

  const offsetY = event.clientY - panelResizeState.startY
  topPanelHeight.value = clampTopPanelHeight(panelResizeState.startHeight + offsetY)
}

/**
 * 结束上下分隔条拖拽，并移除全局鼠标监听。
 *
 * @returns {void}
 */
function stopPanelResize() {
  panelResizeDragging.value = false
  document.removeEventListener('mousemove', handlePanelResizeMove)
  document.removeEventListener('mouseup', stopPanelResize)
}

/**
 * 解析当前可用的实时 ASR 接口状态。
 *
 * @returns {{label: string, detail: string, ok: boolean}} 当前实时 ASR 状态对象。
 */
function resolveRuntimeAsrStatus() {
  const enabledAsrItems = providers.value.filter((item) => item.provider_type === 'asr' && item.is_enabled)
  if (!enabledAsrItems.length) {
    return { label: '未配置', detail: '未找到已启用的 ASR 接口', ok: false }
  }
  const availableAsrItem = enabledAsrItems.find((item) => {
    const configJson = item.config_json || {}
    const driverName = String(item.driver_name || '').trim()
    const isSupportedDriver = ['aliyun_bailian_asr_realtime_ws', 'aliyun_bailian_asr_file_transcription', 'aliyun_bailian_asr_ws', 'qwen_stream_asr_http'].includes(driverName)
    if (!isSupportedDriver || !String(configJson.endpoint || '').trim()) {
      return false
    }
    if (driverName === 'qwen_stream_asr_http') {
      return true
    }
    return Boolean(String(configJson.api_key || '').trim())
  })
  if (!availableAsrItem) {
    return { label: '待完善', detail: 'ASR 接口缺少 endpoint、API Key，或驱动尚未启用实时识别模板', ok: false }
  }
  return {
    label: '可运行',
    detail: `${availableAsrItem.provider_name} / ${availableAsrItem.driver_name}`,
    ok: true,
  }
}

/**
 * 解析当前可用的在线 TTS 接口状态。
 *
 * @returns {{label: string, detail: string, ok: boolean}} 当前在线 TTS 状态对象。
 */
function resolveRuntimeTtsStatus() {
  const enabledTtsItems = providers.value.filter((item) => item.provider_type === 'tts' && item.is_enabled)
  if (!enabledTtsItems.length) {
    return { label: '未配置', detail: '未找到已启用的 TTS 接口', ok: false }
  }
  const availableTtsItem = enabledTtsItems.find((item) => {
    const configJson = item.config_json || {}
    return Boolean(String(configJson.api_key || '').trim() && String(configJson.endpoint || '').trim())
  })
  if (!availableTtsItem) {
    return { label: '待完善', detail: 'TTS 接口缺少 API Key 或 endpoint', ok: false }
  }
  return {
    label: '可运行',
    detail: `${availableTtsItem.provider_name} / ${availableTtsItem.driver_name}`,
    ok: true,
  }
}

const currentTaskBatch = computed(() =>
  batches.value.find((item) => item.id === activeTask.value?.batch_id) || null,
)
const runtimeAsrStatus = computed(() => resolveRuntimeAsrStatus())
const runtimeTtsStatus = computed(() => resolveRuntimeTtsStatus())
const runtimeDependencyAlertType = computed(() => {
  if (runtimeAsrStatus.value.ok && runtimeTtsStatus.value.ok) {
    return 'success'
  }
  return 'warning'
})
const currentTaskRun = computed(() => {
  if (!activeTask.value) {
    return null
  }
  if (activeTask.value.current_run_id) {
    return taskRuns.value.find((item) => item.id === activeTask.value.current_run_id) || taskRuns.value[0] || null
  }
  return taskRuns.value[0] || null
})
const runSessionsMap = computed(() => {
  const groupedMap = new Map()
  sessions.value.forEach((item) => {
    const runId = item.task_run_id || 0
    if (!groupedMap.has(runId)) {
      groupedMap.set(runId, [])
    }
    groupedMap.get(runId).push(item)
  })
  groupedMap.forEach((sessionItems, runId) => {
    groupedMap.set(runId, sortSessionsByIntentPriority(sessionItems))
  })
  return groupedMap
})
const currentRunSessions = computed(() => {
  if (!currentTaskRun.value) {
    return []
  }
  return runSessionsMap.value.get(currentTaskRun.value.id) || []
})
const historyRuns = computed(() =>
  taskRuns.value.filter((item) => item.id !== currentTaskRun.value?.id && item.session_count > 0),
)
const activeSessionStatuses = new Set(['dialing', 'ringing', 'answered'])
const finishedSessionStatuses = new Set(['completed', 'failed', 'cancelled'])
const activeSessions = computed(() =>
  currentRunSessions.value.filter((item) => activeSessionStatuses.has(item.session_status)),
)
const finishedSessions = computed(() =>
  currentRunSessions.value.filter((item) => finishedSessionStatuses.has(item.session_status)),
)
const handledContactCount = computed(() => {
  const contactIdSet = new Set(
    currentRunSessions.value
      .map((item) => item.contact_record_id)
      .filter((item) => item !== null && item !== undefined),
  )
  return contactIdSet.size
})
const pendingContactEstimate = computed(() => {
  const totalCount = Number(currentTaskBatch.value?.import_total || 0)
  return Math.max(totalCount - handledContactCount.value, 0)
})
const progressPercent = computed(() => {
  const totalCount = Number(currentTaskBatch.value?.import_total || 0)
  if (!totalCount) {
    return 0
  }
  return Math.min(100, Math.round((handledContactCount.value / totalCount) * 100))
})

/**
 * 加载任务页依赖的基础数据。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadTaskData() {
  const [taskItems, scriptItems, trunkItems, batchItems, providerItems] = await Promise.all([
    fetchTasksApi(),
    fetchScriptsApi(),
    fetchTrunksApi(),
    fetchBatchesApi(),
    fetchProvidersApi(),
  ])
  tasks.value = taskItems
  scripts.value = scriptItems
  trunks.value = trunkItems
  batches.value = batchItems
  providers.value = providerItems
  if (activeTask.value) {
    activeTask.value = tasks.value.find((item) => item.id === activeTask.value.id) || null
  }
  await nextTick()
  if (activeTask.value && taskTableRef.value?.setCurrentRow) {
    taskTableRef.value.setCurrentRow(activeTask.value)
  }
}

/**
 * 根据任务主键同步当前激活任务，并驱动表格高亮到对应行。
 *
 * @param {number | null | undefined} taskId 当前需要激活展示的任务主键。
 * @returns {Promise<void>} 激活状态同步完成后的 Promise。
 */
async function setActiveTaskById(taskId) {
  if (!taskId) {
    activeTask.value = null
    return
  }
  activeTask.value = tasks.value.find((item) => item.id === taskId) || null
  await nextTick()
  if (taskTableRef.value?.setCurrentRow) {
    taskTableRef.value.setCurrentRow(activeTask.value)
  }
}

/**
 * 加载当前选中任务下的会话列表。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadSessions() {
  if (!activeTask.value) {
    sessions.value = []
    taskRuns.value = []
    return
  }
  const [sessionItems, taskRunItems] = await Promise.all([
    fetchTaskSessionsApi(activeTask.value.id),
    fetchTaskRunsApi(activeTask.value.id),
  ])
  sessions.value = sessionItems
  taskRuns.value = taskRunItems
}

/**
 * 根据当前选中任务状态决定是否自动轮询任务进度。
 *
 * @returns {void}
 */
function syncTaskAutoRefresh() {
  if (autoRefreshTimer.value) {
    window.clearInterval(autoRefreshTimer.value)
    autoRefreshTimer.value = null
  }
  if (!activeTask.value || !['queued', 'running'].includes(activeTask.value.task_status)) {
    return
  }
  autoRefreshTimer.value = window.setInterval(async () => {
    await loadTaskData()
    await loadSessions()
  }, 5000)
}

/**
 * 处理任务切换行为。
 *
 * @param {object | null} currentRow 当前选中的任务对象。
 * @returns {Promise<void>} 会话刷新完成后的 Promise。
 */
async function handleTaskChange(currentRow) {
  if (!currentRow && activeTask.value) {
    return
  }
  activeTask.value = currentRow
  await loadSessions()
  syncTaskAutoRefresh()
}

/**
 * 根据所选话术加载对应版本列表。
 *
 * @param {number | null} scriptId 当前选中的话术主键。
 * @returns {Promise<void>} 版本加载完成后的 Promise。
 */
async function handleTaskScriptChange(scriptId) {
  if (!scriptId) {
    currentTaskVersions.value = []
    taskForm.script_version_id = null
    return
  }
  currentTaskVersions.value = await fetchScriptVersionsApi(scriptId)
  taskForm.script_version_id = currentTaskVersions.value[0]?.id || null
}

/**
 * 归一化任务表单里选择的线路主键数组，避免空值、重复值和字符串主键直接进入后端。
 *
 * @param {Array<number | string>} trunkIds 当前表单里选择的线路主键数组。
 * @returns {Array<number>} 清洗后的线路主键数组。
 */
function normalizeTaskTrunkIds(trunkIds) {
  return Array.from(
    new Set(
      (trunkIds || [])
        .map((item) => Number(item))
        .filter((item) => Number.isInteger(item) && item > 0),
    ),
  )
}

/**
 * 解析任务详情里已绑定的线路池，兼容历史单线路任务和新的多线路池任务。
 *
 * @param {object | null} taskItem 当前编辑的任务对象。
 * @returns {Array<number>} 可直接回填到多选线路框中的线路主键数组。
 */
function resolveTaskSelectedTrunkIds(taskItem) {
  if (!taskItem) {
    return []
  }

  // 兼容旧任务只保存了 trunk_id 的场景，编辑时仍然能够自动回填到新的多选线路池控件。
  const candidateTrunkIds = Array.isArray(taskItem.trunk_ids) && taskItem.trunk_ids.length
    ? taskItem.trunk_ids
    : taskItem.trunk_id
      ? [taskItem.trunk_id]
      : []
  return normalizeTaskTrunkIds(candidateTrunkIds)
}

/**
 * 打开任务弹窗。
 *
 * @param {'create' | 'edit'} mode 当前弹窗模式。
 * @param {object | null} row 当前编辑的任务对象。
 * @returns {Promise<void>} 弹窗初始化完成后的 Promise。
 */
async function openTaskDialog(mode, row = null) {
  taskDialogMode.value = mode
  editingTaskId.value = row?.id || null
  Object.assign(taskForm, createDefaultTaskForm())

  if (mode === 'edit' && row) {
    Object.assign(taskForm, {
      task_code: row.task_code,
      task_name: row.task_name,
      task_type: row.task_type,
      script_id: row.script_id,
      script_version_id: row.script_version_id,
      trunk_id: row.trunk_id,
      trunk_ids: resolveTaskSelectedTrunkIds(row),
      batch_id: row.batch_id,
      max_concurrency: row.max_concurrency,
      cps_limit: row.cps_limit,
      retry_limit: row.retry_limit,
      retry_interval_seconds: row.retry_interval_seconds,
      call_time_range_text: JSON.stringify(row.call_time_range || {}, null, 2),
      extra_config_text: JSON.stringify(row.extra_config || {}, null, 2),
      task_status: row.task_status,
    })
  }

  if (taskForm.script_id) {
    await handleTaskScriptChange(taskForm.script_id)
  }

  taskDialogVisible.value = true
}

/**
 * 提交任务新增或编辑操作。
 *
 * @returns {Promise<void>} 保存完成后的 Promise。
 */
async function submitTask() {
  if (!Number.isInteger(Number(taskForm.max_concurrency)) || Number(taskForm.max_concurrency) < 1) {
    ElMessage.warning('并发必须是大于等于 1 的整数')
    return
  }
  if (!Number.isInteger(Number(taskForm.cps_limit)) || Number(taskForm.cps_limit) < 1) {
    ElMessage.warning('CPS 必须是大于等于 1 的整数')
    return
  }
  if (!Number.isInteger(Number(taskForm.retry_limit)) || Number(taskForm.retry_limit) < 0) {
    ElMessage.warning('重试次数必须是大于等于 0 的整数')
    return
  }
  if (!Number.isInteger(Number(taskForm.retry_interval_seconds)) || Number(taskForm.retry_interval_seconds) < 0) {
    ElMessage.warning('重试间隔必须是大于等于 0 的整数秒')
    return
  }
  submittingTask.value = true
  try {
    // 提交前统一把线路池主键数组清洗为整型，避免多选控件返回的字符串值影响后端分组调度。
    const selectedTrunkIds = normalizeTaskTrunkIds(taskForm.trunk_ids)
    const payload = {
      task_code: taskForm.task_code,
      task_name: taskForm.task_name,
      task_type: taskForm.task_type,
      script_id: taskForm.script_id,
      script_version_id: taskForm.script_version_id,
      trunk_id: selectedTrunkIds[0] || null,
      trunk_ids: selectedTrunkIds,
      trunk_group_id: null,
      batch_id: taskForm.batch_id || null,
      max_concurrency: Number(taskForm.max_concurrency),
      cps_limit: Number(taskForm.cps_limit),
      retry_limit: Number(taskForm.retry_limit),
      retry_interval_seconds: Number(taskForm.retry_interval_seconds),
      call_time_range: parseJsonText(taskForm.call_time_range_text, {}),
      created_by: 1,
      extra_config: parseJsonText(taskForm.extra_config_text, {}),
    }

    if (taskDialogMode.value === 'create') {
      await createTaskApi(payload)
      ElMessage.success('任务已创建')
    } else {
      await updateTaskApi(editingTaskId.value, {
        ...payload,
        task_status: taskForm.task_status,
      })
      ElMessage.success('任务已更新')
    }

    taskDialogVisible.value = false
    await loadTaskData()
  } finally {
    submittingTask.value = false
  }
}

/**
 * 更新任务状态。
 *
 * @param {object} row 当前选中的任务对象。
 * @param {string} targetStatus 目标任务状态。
 * @returns {Promise<void>} 状态更新完成后的 Promise。
 */
async function updateTaskStatus(row, targetStatus) {
  await updateTaskStatusApi(row.id, { task_status: targetStatus })
  ElMessage.success('任务状态已更新')
  await loadTaskData()
  await setActiveTaskById(row.id)
  await loadSessions()
  syncTaskAutoRefresh()
}

/**
 * 删除指定任务。
 *
 * @param {object} row 当前选中的任务对象。
 * @returns {Promise<void>} 删除完成后的 Promise。
 */
async function removeTask(row) {
  await ElMessageBox.confirm(`确定删除任务「${row.task_name}」吗？`, '删除确认', { type: 'warning' })
  await deleteTaskApi(row.id)
  ElMessage.success('任务已删除')
  if (activeTask.value?.id === row.id) {
    activeTask.value = null
  }
  await loadTaskData()
  await loadSessions()
}

/**
 * 触发任务运行时分发表生成。
 *
 * @param {object} row 当前选中的任务对象。
 * @returns {Promise<void>} 入队完成后的 Promise。
 */
async function queueTask(row) {
  const result = await queueTaskApi(row.id)
  ElMessage.success(`已创建 ${result.created_dispatches} 条分发表`)
  await loadTaskData()
  await setActiveTaskById(row.id)
  await loadSessions()
  syncTaskAutoRefresh()
}

/**
 * 解析执行批次标题文本。
 *
 * @param {object} runItem 当前执行批次对象。
 * @returns {string} 返回适合界面展示的执行批次标题。
 */
function resolveRunTitle(runItem) {
  return `第 ${runItem.run_no} 次执行`
}

/**
 * 将会话列表按“有意向优先、最近优先”排序，方便客服优先跟进高价值客户。
 *
 * @param {Array<object>} sessionItems 当前批次下的原始会话数组。
 * @returns {Array<object>} 排序后的会话数组。
 */
function sortSessionsByIntentPriority(sessionItems) {
  return [...(sessionItems || [])].sort((leftSession, rightSession) => {
    const intentPriorityDiff = resolveIntentPriority(rightSession.intent_level) - resolveIntentPriority(leftSession.intent_level)
    if (intentPriorityDiff !== 0) {
      return intentPriorityDiff
    }

    const rightTime = resolveSessionSortTimestamp(rightSession)
    const leftTime = resolveSessionSortTimestamp(leftSession)
    if (rightTime !== leftTime) {
      return rightTime - leftTime
    }
    return Number(rightSession.id || 0) - Number(leftSession.id || 0)
  })
}

/**
 * 解析会话的意向优先级分值，分值越高越应排到顶部。
 *
 * @param {string | null | undefined} intentLevel 当前会话的意向等级。
 * @returns {number} 用于排序的数值优先级。
 */
function resolveIntentPriority(intentLevel) {
  const normalizedIntentLevel = String(intentLevel || '').trim().toUpperCase()
  if (!normalizedIntentLevel) {
    return 0
  }
  const priorityMap = {
    A: 400,
    S: 380,
    B: 300,
    C: 200,
    D: 100,
  }
  return priorityMap[normalizedIntentLevel] || 50
}

/**
 * 解析会话用于排序的时间戳，优先按结束、应答、开始时间回退。
 *
 * @param {object} sessionItem 当前会话对象。
 * @returns {number} 可直接用于排序的毫秒时间戳。
 */
function resolveSessionSortTimestamp(sessionItem) {
  const candidateValues = [
    sessionItem.ended_at,
    sessionItem.answered_at,
    sessionItem.started_at,
    sessionItem.created_at,
  ]
  for (const candidateValue of candidateValues) {
    const timestamp = Date.parse(candidateValue || '')
    if (!Number.isNaN(timestamp)) {
      return timestamp
    }
  }
  return 0
}

/**
 * 把意向等级格式化为页面展示文本。
 *
 * @param {string | null | undefined} intentLevel 当前会话的意向等级。
 * @returns {string} 页面展示用的意向文本。
 */
function formatIntentLevel(intentLevel) {
  const normalizedIntentLevel = String(intentLevel || '').trim().toUpperCase()
  if (!normalizedIntentLevel) {
    return '未识别'
  }
  return normalizedIntentLevel
}

/**
 * 根据意向等级返回用于状态标签展示的样式类。
 *
 * @param {string | null | undefined} intentLevel 当前会话的意向等级。
 * @returns {string} 供状态标签使用的样式类名。
 */
function resolveIntentClass(intentLevel) {
  const normalizedIntentLevel = String(intentLevel || '').trim().toUpperCase()
  if (['A', 'S'].includes(normalizedIntentLevel)) {
    return 'is-success'
  }
  if (normalizedIntentLevel === 'B') {
    return 'is-warning'
  }
  if (['C', 'D'].includes(normalizedIntentLevel)) {
    return 'is-danger'
  }
  return ''
}

/**
 * 获取指定执行批次下的会话列表。
 *
 * @param {number} runId 执行批次主键。
 * @returns {Array<object>} 返回该批次的会话数组。
 */
function resolveRunSessions(runId) {
  return runSessionsMap.value.get(runId) || []
}

const hasActiveTask = computed(() => Boolean(activeTask.value))
void hasActiveTask

/**
 * 初始化任务页数据。
 *
 * @returns {Promise<void>} 初始化完成后的 Promise。
 */
async function initializePage() {
  await loadTaskData()
  await loadSessions()
  await nextTick()
  syncInitialPanelHeight()
  syncTaskAutoRefresh()
}

onMounted(initializePage)
onBeforeUnmount(() => {
  if (autoRefreshTimer.value) {
    window.clearInterval(autoRefreshTimer.value)
    autoRefreshTimer.value = null
  }
  stopPanelResize()
})
</script>

<style scoped lang="scss">
.task-page-stack {
  display: flex;
  flex-direction: column;
  gap: 0;
  height: calc(100vh - 148px);
  min-height: 920px;
}

.task-page-stack.is-resizing {
  user-select: none;
  cursor: row-resize;
}

.task-page-panel {
  min-height: 0;
}

.task-page-panel-top {
  flex: 0 0 auto;
}

.task-page-panel-bottom {
  flex: 1 1 auto;
  min-height: 360px;
}

.task-page-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.task-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
}

.task-table-wrap :deep(.el-table) {
  height: 100%;
}

.task-page-card-bottom {
  overflow: auto;
}

.task-page-resize-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 18px;
  margin: 8px 0;
  cursor: row-resize;
}

.task-page-resize-grip {
  width: 88px;
  height: 6px;
  border-radius: 999px;
  background: linear-gradient(90deg, #bfd6ff 0%, #7aa5f9 50%, #bfd6ff 100%);
  box-shadow: 0 0 0 1px rgba(82, 120, 204, 0.12);
}

.task-progress-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 16px;
}

.runtime-dependency-panel {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.runtime-dependency-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid #dbe8ff;
  background: linear-gradient(180deg, #fbfdff 0%, #eff5ff 100%);
}

.runtime-dependency-label {
  font-size: 12px;
  color: var(--app-text-soft);
}

.runtime-dependency-card strong {
  font-size: 20px;
  color: #2d4f96;
}

.task-runtime-alert {
  margin-bottom: 16px;
}

.task-progress-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.task-progress-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid #dbe8ff;
  background: linear-gradient(180deg, #fbfdff 0%, #eff5ff 100%);
}

.task-progress-label {
  font-size: 12px;
  color: var(--app-text-soft);
}

.task-progress-card strong {
  font-size: 24px;
  color: #2d4f96;
}

.batch-name-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-progress-card small {
  font-size: 12px;
  color: #7b89a8;
}

.current-call-card {
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid #dbe8ff;
  background: linear-gradient(180deg, #f9fcff 0%, #eef5ff 100%);
}

.task-run-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid #d9e7ff;
  background: linear-gradient(135deg, #f7fbff 0%, #eef5ff 100%);
}

.task-run-banner h3 {
  margin: 0;
  font-size: 18px;
  color: #29467a;
}

.task-run-banner p {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--app-text-soft);
}

.task-history-card {
  margin-top: 16px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid #dbe8ff;
  background: #fdfefe;
}

.task-history-header h3 {
  margin: 0;
  font-size: 16px;
}

.task-history-header p {
  margin: 6px 0 14px;
  font-size: 12px;
  color: var(--app-text-soft);
}

.current-call-card h3 {
  margin: 0;
  font-size: 16px;
}

.current-call-card p {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--app-text-soft);
}

.current-call-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.current-call-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 14px;
  background: #ffffff;
  border: 1px solid #e1ecff;
  font-size: 12px;
  color: #5c6b88;
}

.current-call-item strong {
  font-size: 16px;
  color: #31466f;
}

@media (max-width: 1400px) {
  .task-page-stack {
    height: auto;
    min-height: 0;
  }

  .task-progress-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .task-page-stack {
    height: auto;
  }

  .task-page-panel-top,
  .task-page-panel-bottom {
    min-height: 0;
  }

  .task-page-resize-handle {
    display: none;
  }

  .task-progress-grid {
    grid-template-columns: 1fr;
  }
}
</style>
