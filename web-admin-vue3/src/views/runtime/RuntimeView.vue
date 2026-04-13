<template>
  <div class="split-grid">
    <div class="page-card table-section">
      <div class="page-toolbar">
        <div>
          <h2 class="page-title">话术运行调试</h2>
          <p class="page-subtitle">直接调用运行态接口进行单步推进与全流程模拟。</p>
        </div>
      </div>

      <el-form :model="runtimeForm" label-width="110px">
        <el-form-item label="话术版本 ID">
          <el-input-number v-model="runtimeForm.script_version_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="当前节点编码">
          <el-input v-model="runtimeForm.current_node_code" />
        </el-form-item>
        <el-form-item label="识别文本">
          <el-input v-model="runtimeForm.asr_text" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="匹配关键词">
          <el-input v-model="runtimeForm.keyword_text" placeholder="使用英文逗号分隔，例如 可以,同意" />
        </el-form-item>
        <el-form-item label="变量 JSON">
          <JsonEditor v-model="runtimeForm.variables_text" />
        </el-form-item>
        <div class="page-toolbar-right">
          <el-button type="primary" :loading="runningStep" @click="runStep">执行单步</el-button>
          <el-button type="success" :loading="runningSimulation" @click="runSimulation">模拟流程</el-button>
        </div>
      </el-form>

      <div style="margin-top: 18px;">
        <h3>运行结果</h3>
        <pre class="json-block">{{ runtimeResultText }}</pre>
      </div>
    </div>

    <div class="page-card table-section">
      <div class="page-toolbar">
        <div>
          <h2 class="page-title">任务调度调试</h2>
          <p class="page-subtitle">验证任务分发表、待调度联系人以及会话推进链路。</p>
        </div>
      </div>

      <el-form :model="dispatchForm" label-width="110px">
        <el-form-item label="任务 ID">
          <el-input-number v-model="dispatchForm.task_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="拉取数量">
          <el-input-number v-model="dispatchForm.limit" :min="1" :max="100" style="width: 100%" />
        </el-form-item>
        <div class="page-toolbar-right">
          <el-button type="primary" :loading="queueingTask" @click="queueTaskDispatches">生成分发表</el-button>
          <el-button type="success" :loading="loadingPending" @click="loadPendingDispatches">拉取待调度</el-button>
        </div>
      </el-form>

      <div style="margin-top: 18px;">
        <h3>待调度结果</h3>
        <pre class="json-block">{{ dispatchResultText }}</pre>
      </div>
    </div>

    <div class="page-card table-section">
      <div class="page-toolbar">
        <div>
          <h2 class="page-title">会话创建与推进</h2>
          <p class="page-subtitle">用于联调运行态会话创建接口和状态推进接口。</p>
        </div>
      </div>

      <el-form :model="sessionForm" label-width="110px">
        <el-form-item label="任务 ID">
          <el-input-number v-model="sessionForm.task_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="分发记录 ID">
          <el-input-number v-model="sessionForm.dispatch_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="主叫号码">
          <el-input v-model="sessionForm.caller_number" />
        </el-form-item>
        <el-form-item label="被叫号码">
          <el-input v-model="sessionForm.callee_number" />
        </el-form-item>
        <el-form-item label="SIP Call ID">
          <el-input v-model="sessionForm.sip_call_id" />
        </el-form-item>
        <el-form-item label="额外信息">
          <JsonEditor v-model="sessionForm.extra_meta_text" />
        </el-form-item>
        <div class="page-toolbar-right">
          <el-button type="primary" :loading="creatingSession" @click="createSession">创建会话</el-button>
        </div>
      </el-form>

      <el-divider />

      <el-form :model="progressForm" label-width="110px">
        <el-form-item label="会话 ID">
          <el-input-number v-model="progressForm.session_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="会话状态">
          <el-select v-model="progressForm.session_status">
            <el-option label="initiated" value="initiated" />
            <el-option label="ringing" value="ringing" />
            <el-option label="answered" value="answered" />
            <el-option label="completed" value="completed" />
            <el-option label="failed" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="应答状态">
          <el-input v-model="progressForm.answer_status" />
        </el-form-item>
        <el-form-item label="当前节点">
          <el-input v-model="progressForm.current_node_code" />
        </el-form-item>
        <el-form-item label="挂断原因">
          <el-input v-model="progressForm.hangup_cause" />
        </el-form-item>
        <el-form-item label="结果编码">
          <el-input v-model="progressForm.result_code" />
        </el-form-item>
        <el-form-item label="意向等级">
          <el-input v-model="progressForm.intent_level" />
        </el-form-item>
        <el-form-item label="计费时长">
          <el-input-number v-model="progressForm.billsec" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="总时长">
          <el-input-number v-model="progressForm.duration" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="事件类型">
          <el-input v-model="progressForm.event_type" />
        </el-form-item>
        <el-form-item label="事件负载">
          <JsonEditor v-model="progressForm.payload_text" />
        </el-form-item>
        <div class="page-toolbar-right">
          <el-button type="success" :loading="progressingSession" @click="progressSession">推进会话</el-button>
        </div>
      </el-form>

      <div style="margin-top: 18px;">
        <h3>会话接口结果</h3>
        <pre class="json-block">{{ sessionResultText }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import JsonEditor from '@/components/JsonEditor.vue'
import {
  createRuntimeSessionApi,
  executeScriptStepApi,
  fetchPendingDispatchesApi,
  progressRuntimeSessionApi,
  queueTaskApi,
  simulateScriptApi,
} from '@/api/modules'
import { formatJson, parseJsonText } from '@/utils/format'

const runtimeForm = reactive({
  script_version_id: 1,
  current_node_code: '',
  asr_text: '',
  keyword_text: '',
  variables_text: '{}',
})
const dispatchForm = reactive({
  task_id: 1,
  limit: 20,
})
const sessionForm = reactive({
  task_id: 1,
  dispatch_id: 1,
  caller_number: '',
  callee_number: '',
  sip_call_id: '',
  extra_meta_text: '{}',
})
const progressForm = reactive({
  session_id: 1,
  session_status: 'initiated',
  answer_status: '',
  current_node_code: '',
  hangup_cause: '',
  result_code: '',
  intent_level: '',
  billsec: 0,
  duration: 0,
  event_type: 'system',
  payload_text: '{}',
})
const runtimeResult = ref(null)
const dispatchResult = ref(null)
const sessionResult = ref(null)
const runningStep = ref(false)
const runningSimulation = ref(false)
const queueingTask = ref(false)
const loadingPending = ref(false)
const creatingSession = ref(false)
const progressingSession = ref(false)

/**
 * 构造运行态单步执行请求体。
 *
 * @returns {object} 单步执行请求体对象。
 */
function buildRuntimePayload() {
  return {
    current_node_code: runtimeForm.current_node_code || null,
    asr_text: runtimeForm.asr_text || null,
    intent_code: null,
    matched_keywords: runtimeForm.keyword_text
      .split(',')
      .map((keyword) => keyword.trim())
      .filter(Boolean),
    timeout: false,
    silence: false,
    nomatch: false,
    variables: parseJsonText(runtimeForm.variables_text, {}),
  }
}

/**
 * 执行话术单步推进。
 *
 * @returns {Promise<void>} 执行完成后的 Promise。
 */
async function runStep() {
  runningStep.value = true
  try {
    runtimeResult.value = await executeScriptStepApi(runtimeForm.script_version_id, buildRuntimePayload())
    ElMessage.success('单步执行完成')
  } finally {
    runningStep.value = false
  }
}

/**
 * 执行话术全流程模拟。
 *
 * @returns {Promise<void>} 模拟完成后的 Promise。
 */
async function runSimulation() {
  runningSimulation.value = true
  try {
    runtimeResult.value = await simulateScriptApi(runtimeForm.script_version_id, {
      steps: [buildRuntimePayload()],
    })
    ElMessage.success('模拟执行完成')
  } finally {
    runningSimulation.value = false
  }
}

/**
 * 生成指定任务的分发表。
 *
 * @returns {Promise<void>} 入队完成后的 Promise。
 */
async function queueTaskDispatches() {
  queueingTask.value = true
  try {
    dispatchResult.value = await queueTaskApi(dispatchForm.task_id)
    ElMessage.success('分发表生成完成')
  } finally {
    queueingTask.value = false
  }
}

/**
 * 拉取指定任务的待调度联系人列表。
 *
 * @returns {Promise<void>} 拉取完成后的 Promise。
 */
async function loadPendingDispatches() {
  loadingPending.value = true
  try {
    dispatchResult.value = await fetchPendingDispatchesApi(dispatchForm.task_id, dispatchForm.limit)
    ElMessage.success('待调度联系人已拉取')
  } finally {
    loadingPending.value = false
  }
}

/**
 * 创建运行态会话。
 *
 * @returns {Promise<void>} 创建完成后的 Promise。
 */
async function createSession() {
  creatingSession.value = true
  try {
    sessionResult.value = await createRuntimeSessionApi(sessionForm.task_id, {
      dispatch_id: sessionForm.dispatch_id,
      caller_number: sessionForm.caller_number || null,
      callee_number: sessionForm.callee_number,
      sip_call_id: sessionForm.sip_call_id || null,
      extra_meta: parseJsonText(sessionForm.extra_meta_text, {}),
    })
    progressForm.session_id = sessionResult.value?.id || progressForm.session_id
    ElMessage.success('会话已创建')
  } finally {
    creatingSession.value = false
  }
}

/**
 * 推进运行态会话状态。
 *
 * @returns {Promise<void>} 推进完成后的 Promise。
 */
async function progressSession() {
  progressingSession.value = true
  try {
    sessionResult.value = await progressRuntimeSessionApi(progressForm.session_id, {
      session_status: progressForm.session_status,
      answer_status: progressForm.answer_status || null,
      current_node_code: progressForm.current_node_code || null,
      hangup_cause: progressForm.hangup_cause || null,
      result_code: progressForm.result_code || null,
      intent_level: progressForm.intent_level || null,
      billsec: progressForm.billsec,
      duration: progressForm.duration,
      event_type: progressForm.event_type,
      payload: parseJsonText(progressForm.payload_text, {}),
    })
    ElMessage.success('会话状态已推进')
  } finally {
    progressingSession.value = false
  }
}

const runtimeResultText = computed(() => formatJson(runtimeResult.value || {}))
const dispatchResultText = computed(() => formatJson(dispatchResult.value || {}))
const sessionResultText = computed(() => formatJson(sessionResult.value || {}))
</script>
