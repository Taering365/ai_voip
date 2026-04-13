<template>
  <div class="page-card table-section">
    <div class="page-toolbar">
      <div>
        <h2 class="page-title">录音管理</h2>
        <p class="page-subtitle">按每一通通话查看录音文件与转写结果，不再展示无业务意义的音频资源资产。</p>
      </div>
      <div class="page-toolbar-right">
        <el-button type="primary" plain @click="loadMediaData">刷新</el-button>
        <el-button type="primary" plain @click="openRecordingDialog">上传录音</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTabName">
      <el-tab-pane label="录音文件" name="recordings">
        <el-table :data="recordings" border>
          <el-table-column prop="session_code" label="通话编码" min-width="170" />
          <el-table-column label="任务 / 客户" min-width="220">
            <template #default="{ row }">
              <div class="cell-stack">
                <strong>{{ row.task_name || row.task_code || '--' }}</strong>
                <span>{{ row.contact_name || '--' }} / {{ row.contact_mobile || row.callee_number || '--' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="record_type" label="录音类型" width="110" />
          <el-table-column label="通话状态" width="130">
            <template #default="{ row }">
              <span class="status-chip" :class="resolveStatusClass(row.session_status)">
                {{ formatStatusLabel(row.session_status, 'session') }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="应答状态" width="120">
            <template #default="{ row }">
              {{ formatStatusLabel(row.answer_status, 'answer') }}
            </template>
          </el-table-column>
          <el-table-column label="开始时间" min-width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.call_started_at || row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="录音时长" width="120">
            <template #default="{ row }">
              {{ formatSeconds(resolveRecordingSeconds(row)) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="playRecording(row)">试听</el-button>
              <el-button link type="success" @click="downloadRecording(row)">下载</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="转写结果" name="transcripts">
        <el-table
          :data="transcripts"
          border
          row-key="id"
          @expand-change="handleTranscriptExpand"
        >
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="transcript-panel">
                <div class="transcript-panel-head">
                  <div>
                    <h3>转写对话</h3>
                    <p>
                      {{ row.contact_name || '--' }} / {{ row.contact_mobile || row.callee_number || '--' }}
                      ｜ {{ formatDateTime(row.call_started_at || row.created_at) }}
                    </p>
                  </div>
                  <div class="page-toolbar-right">
                    <el-button
                      v-if="row.recording_preview_url"
                      type="primary"
                      plain
                      @click="playTranscriptRecording(row)"
                    >
                      试听录音
                    </el-button>
                    <el-button
                      v-if="row.recording_download_url"
                      type="success"
                      plain
                      @click="downloadTranscriptRecording(row)"
                    >
                      下载录音
                    </el-button>
                  </div>
                </div>

                <el-skeleton :loading="loadingTranscriptSegmentIds.includes(row.id)" animated :rows="4">
                  <template #default>
                    <div v-if="resolveTranscriptSegments(row.id).length" class="transcript-chat-list">
                      <div
                        v-for="segment in resolveTranscriptSegments(row.id)"
                        :key="segment.id"
                        class="transcript-chat-row"
                        :class="resolveSpeakerAlignment(segment)"
                      >
                        <div class="transcript-chat-meta">
                          <span>{{ resolveSpeakerLabel(segment) }}</span>
                          <span>{{ formatSegmentTime(segment.begin_ms) }}</span>
                        </div>
                        <div class="transcript-chat-bubble">
                          {{ segment.text_content || '--' }}
                        </div>
                      </div>
                    </div>
                    <el-empty
                      v-else
                      :description="row.transcript_text ? '暂无分段，已展示汇总文本。' : '当前还没有转写分段结果'"
                    />
                    <div v-if="!resolveTranscriptSegments(row.id).length && row.transcript_text" class="transcript-summary">
                      {{ row.transcript_text }}
                    </div>
                  </template>
                </el-skeleton>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="transcript_code" label="转写编码" min-width="180" />
          <el-table-column prop="session_code" label="通话编码" min-width="170" />
          <el-table-column label="任务 / 客户" min-width="220">
            <template #default="{ row }">
              <div class="cell-stack">
                <strong>{{ row.task_name || row.task_code || '--' }}</strong>
                <span>{{ row.contact_name || '--' }} / {{ row.contact_mobile || row.callee_number || '--' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <span class="status-chip" :class="resolveStatusClass(row.task_status)">
                {{ formatTranscriptStatus(row.task_status) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="通话时长" width="120">
            <template #default="{ row }">
              {{ formatSeconds(row.call_duration || row.billsec || 0) }}
            </template>
          </el-table-column>
          <el-table-column label="转写时间" min-width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.finished_at || row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="摘要" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.transcript_text || row.error_message || '--' }}
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="recordingDialogVisible" title="上传录音文件" width="560px">
      <el-form :model="recordingForm" label-width="96px">
        <el-form-item label="会话 ID">
          <el-input v-model="recordingForm.session_id" placeholder="请输入已有通话会话 ID" />
        </el-form-item>
        <el-form-item label="录音类型">
          <el-select v-model="recordingForm.record_type" style="width: 100%;">
            <el-option label="混音 mixed" value="mixed" />
            <el-option label="主叫 caller" value="caller" />
            <el-option label="被叫 callee" value="callee" />
          </el-select>
        </el-form-item>
        <el-form-item label="录音文件">
          <el-upload
            :auto-upload="false"
            :limit="1"
            :show-file-list="true"
            :on-change="handleRecordingFileChange"
            :on-remove="handleRecordingFileRemove"
          >
            <el-button type="primary" plain>选择录音文件</el-button>
            <template #tip>
              <div class="el-upload__tip">上传后会直接归入对应通话记录，可用于在线试听、下载和转写。</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="recordingDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadingRecording" @click="submitRecordingUpload">上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="playerDialogVisible" title="录音试听" width="680px">
      <div class="player-panel">
        <div class="cell-stack">
          <strong>{{ currentPlayingRecording?.session_code || '--' }}</strong>
          <span>
            {{ currentPlayingRecording?.contact_name || '--' }} / {{ currentPlayingRecording?.contact_mobile || currentPlayingRecording?.callee_number || '--' }}
          </span>
        </div>
        <audio
          v-if="currentPlayingUrl"
          ref="playerAudioRef"
          :src="currentPlayingUrl"
          controls
          autoplay
          preload="metadata"
          class="recording-player"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { downloadBinaryFile, httpGetBlob } from '@/api/client'
import {
  fetchRecordingsApi,
  fetchTranscriptSegmentsApi,
  fetchTranscriptsApi,
  uploadRecordingFileApi,
} from '@/api/modules'
import { formatDateTime, formatStatusLabel, resolveStatusClass } from '@/utils/format'

const activeTabName = ref('recordings')
const recordings = ref([])
const transcripts = ref([])
const transcriptSegmentsMap = ref({})
const loadingTranscriptSegmentIds = ref([])
const recordingDialogVisible = ref(false)
const playerDialogVisible = ref(false)
const uploadingRecording = ref(false)
const currentPlayingUrl = ref('')
const currentPlayingRecording = ref(null)
const playerLoading = ref(false)
const playerAudioRef = ref(null)
const recordingForm = reactive(createDefaultRecordingForm())

/**
 * 创建录音上传表单默认值对象。
 *
 * @returns {object} 返回录音上传表单初始值。
 */
function createDefaultRecordingForm() {
  return {
    session_id: '',
    record_type: 'mixed',
    file: null,
  }
}

/**
 * 加载录音列表与转写结果列表。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadMediaData() {
  const [recordingItems, transcriptItems] = await Promise.all([
    fetchRecordingsApi(),
    fetchTranscriptsApi(),
  ])
  recordings.value = recordingItems
  transcripts.value = transcriptItems
}

/**
 * 打开录音上传弹窗，并重置当前表单数据。
 *
 * @returns {void}
 */
function openRecordingDialog() {
  Object.assign(recordingForm, createDefaultRecordingForm())
  recordingDialogVisible.value = true
}

/**
 * 记录当前上传控件选中的音频文件。
 *
 * @param {object} uploadFile Element Plus 上传组件回传的文件对象。
 * @returns {void}
 */
function handleRecordingFileChange(uploadFile) {
  recordingForm.file = uploadFile.raw
}

/**
 * 清理已移除的上传文件引用。
 *
 * @returns {void}
 */
function handleRecordingFileRemove() {
  recordingForm.file = null
}

/**
 * 提交录音上传请求，并在完成后刷新录音列表。
 *
 * @returns {Promise<void>} 上传完成后的 Promise。
 */
async function submitRecordingUpload() {
  if (!recordingForm.session_id || !recordingForm.file) {
    ElMessage.warning('请先选择会话 ID 和录音文件')
    return
  }

  uploadingRecording.value = true
  try {
    await uploadRecordingFileApi({
      session_id: recordingForm.session_id,
      record_type: recordingForm.record_type,
      file: recordingForm.file,
    })
    ElMessage.success('录音文件已上传')
    recordingDialogVisible.value = false
    activeTabName.value = 'recordings'
    await loadMediaData()
  } finally {
    uploadingRecording.value = false
  }
}

/**
 * 释放当前播放器使用的 Blob 地址，避免重复试听后产生浏览器内存泄漏。
 *
 * @returns {void}
 */
function revokeCurrentPlayingUrl() {
  if (!currentPlayingUrl.value) {
    return
  }

  // 试听录音改为先拉取受保护的二进制文件，再生成临时 Blob URL，因此关闭播放器时要主动释放。
  window.URL.revokeObjectURL(currentPlayingUrl.value)
  currentPlayingUrl.value = ''
}

/**
 * 拉取受保护的录音文件并打开试听弹窗。
 *
 * @param {object} row 当前录音或转写结果对象。
 * @param {string | null | undefined} previewUrl 当前行对应的试听接口地址。
 * @returns {Promise<void>} 录音加载完成后的 Promise。
 */
async function openRecordingPlayer(row, previewUrl) {
  if (!previewUrl) {
    ElMessage.warning('当前录音暂不支持试听')
    return
  }

  playerLoading.value = true
  currentPlayingRecording.value = row
  revokeCurrentPlayingUrl()

  try {
    // 这里必须显式携带 Bearer Token 请求 Blob，否则浏览器原生 audio 请求会被后端 401 拦截。
    const audioBlob = await httpGetBlob(previewUrl)
    currentPlayingUrl.value = window.URL.createObjectURL(audioBlob)
    playerDialogVisible.value = true
    await nextTick()
    await tryAutoPlayRecording()
  } finally {
    playerLoading.value = false
  }
}

/**
 * 在弹窗打开后尝试自动播放当前录音，减少用户二次点击操作。
 *
 * @returns {Promise<void>} 自动播放尝试完成后的 Promise。
 */
async function tryAutoPlayRecording() {
  const audioElement = playerAudioRef.value
  if (!audioElement || !currentPlayingUrl.value) {
    return
  }

  try {
    // 试听动作由用户点击触发，这里紧接着调用 play，尽量复用同一次用户手势实现自动播放。
    audioElement.load()
    await audioElement.play()
  } catch (error) {
    // 若浏览器策略阻止自动播放，则保留播放器控件给用户手动播放，不额外打断页面流程。
  }
}

/**
 * 打开试听弹窗，并把当前录音转换为可播放的 Blob 地址。
 *
 * @param {object} row 当前录音文件对象。
 * @returns {Promise<void>} 录音加载完成后的 Promise。
 */
function playRecording(row) {
  return openRecordingPlayer(row, row.preview_url)
}

/**
 * 从转写结果行直接试听其关联录音。
 *
 * @param {object} row 当前转写任务对象。
 * @returns {Promise<void>} 录音加载完成后的 Promise。
 */
function playTranscriptRecording(row) {
  return openRecordingPlayer(row, row.recording_preview_url)
}

/**
 * 拉取受保护的录音二进制并触发浏览器下载。
 *
 * @param {string | null | undefined} downloadUrl 当前行对应的下载接口地址。
 * @param {string} fallbackFilename 接口未返回文件名时使用的兜底文件名。
 * @returns {Promise<void>} 下载动作完成后的 Promise。
 */
async function triggerRecordingDownload(downloadUrl, fallbackFilename) {
  if (!downloadUrl) {
    ElMessage.warning('当前录音暂不支持下载')
    return
  }

  // 下载同样需要走带鉴权的二进制请求，否则新窗口打开接口时不会附带登录令牌。
  await downloadBinaryFile(downloadUrl, fallbackFilename)
}

/**
 * 下载录音文件。
 *
 * @param {object} row 当前录音文件对象。
 * @returns {Promise<void>} 下载动作完成后的 Promise。
 */
function downloadRecording(row) {
  const sessionCode = row.session_code || `session_${row.session_id || 'recording'}`
  return triggerRecordingDownload(row.download_url, `${sessionCode}.wav`)
}

/**
 * 从转写结果行直接下载其关联录音。
 *
 * @param {object} row 当前转写任务对象。
 * @returns {Promise<void>} 下载动作完成后的 Promise。
 */
function downloadTranscriptRecording(row) {
  const sessionCode = row.session_code || `session_${row.session_id || 'transcript'}`
  return triggerRecordingDownload(row.recording_download_url, `${sessionCode}.wav`)
}

/**
 * 展开转写结果时按需加载分段列表，避免页面初始化时请求过多明细。
 *
 * @param {object} row 当前转写任务对象。
 * @param {object[]} expandedRows 当前已展开的全部行数据。
 * @returns {Promise<void>} 加载完成后的 Promise。
 */
async function handleTranscriptExpand(row, expandedRows) {
  const isExpanded = expandedRows.some((item) => item.id === row.id)
  if (!isExpanded || transcriptSegmentsMap.value[row.id]) {
    return
  }

  loadingTranscriptSegmentIds.value = [...loadingTranscriptSegmentIds.value, row.id]
  try {
    const segmentItems = await fetchTranscriptSegmentsApi(row.id)
    transcriptSegmentsMap.value = {
      ...transcriptSegmentsMap.value,
      [row.id]: segmentItems,
    }
  } finally {
    loadingTranscriptSegmentIds.value = loadingTranscriptSegmentIds.value.filter((item) => item !== row.id)
  }
}

/**
 * 读取某条转写任务当前已缓存的分段列表。
 *
 * @param {number} transcriptTaskId 转写任务主键。
 * @returns {object[]} 当前任务对应的转写分段数组。
 */
function resolveTranscriptSegments(transcriptTaskId) {
  return transcriptSegmentsMap.value[transcriptTaskId] || []
}

/**
 * 根据录音记录优先选择更可信的秒级时长。
 *
 * @param {object} row 当前录音文件对象。
 * @returns {number} 统一后的秒级时长。
 */
function resolveRecordingSeconds(row) {
  if (row.call_duration) {
    return Number(row.call_duration) || 0
  }
  if (row.billsec) {
    return Number(row.billsec) || 0
  }
  return Math.round((Number(row.duration_ms) || 0) / 1000)
}

/**
 * 把秒数格式化为 `mm:ss` 或 `hh:mm:ss` 文本，便于在表格里阅读。
 *
 * @param {number} seconds 原始秒数。
 * @returns {string} 格式化后的时长文本。
 */
function formatSeconds(seconds) {
  const safeSeconds = Math.max(0, Number(seconds) || 0)
  const hour = Math.floor(safeSeconds / 3600)
  const minute = Math.floor((safeSeconds % 3600) / 60)
  const second = Math.floor(safeSeconds % 60)

  if (hour > 0) {
    return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:${String(second).padStart(2, '0')}`
  }
  return `${String(minute).padStart(2, '0')}:${String(second).padStart(2, '0')}`
}

/**
 * 把转写分段的毫秒起点格式化为带毫秒精度的聊天时间戳。
 *
 * @param {number} beginMs 分段起始毫秒。
 * @returns {string} 格式化后的时间戳文本。
 */
function formatSegmentTime(beginMs) {
  const safeMilliseconds = Math.max(0, Math.floor(Number(beginMs) || 0))
  const minute = Math.floor(safeMilliseconds / 60000)
  const second = Math.floor((safeMilliseconds % 60000) / 1000)
  const millisecond = safeMilliseconds % 1000
  return `${String(minute).padStart(2, '0')}:${String(second).padStart(2, '0')}.${String(millisecond).padStart(3, '0')}`
}

/**
 * 将转写任务状态映射为中文文案。
 *
 * @param {string | null | undefined} status 转写任务状态值。
 * @returns {string} 页面展示用的状态文本。
 */
function formatTranscriptStatus(status) {
  const normalizedStatus = String(status || '').trim().toLowerCase()
  if (!normalizedStatus) {
    return '未转写'
  }
  const statusLabelMap = {
    pending: '待转写',
    processing: '转写中',
    completed: '已完成',
    failed: '失败',
  }
  return statusLabelMap[normalizedStatus] || String(status)
}

/**
 * 根据分段角色决定聊天记录气泡的左右布局。
 *
 * @param {object} segment 当前转写分段对象。
 * @returns {string} 供样式类绑定使用的对齐标识。
 */
function resolveSpeakerAlignment(segment) {
  return segment.speaker_role === 'customer' ? 'is-right' : 'is-left'
}

/**
 * 根据分段角色生成聊天记录中的说话人名称。
 *
 * @param {object} segment 当前转写分段对象。
 * @returns {string} 当前分段对应的展示名称。
 */
function resolveSpeakerLabel(segment) {
  if (segment.speaker_role === 'customer') {
    return '客户'
  }
  if (segment.speaker_role === 'agent') {
    return '客服'
  }
  return segment.speaker_label || `声道 ${segment.channel_no ?? '--'}`
}

/**
 * 在播放器弹窗关闭时释放 Blob 地址，避免旧录音继续占用浏览器内存。
 *
 * @param {boolean} visible 当前播放器弹窗是否可见。
 * @returns {void}
 */
watch(playerDialogVisible, (visible) => {
  if (!visible) {
    revokeCurrentPlayingUrl()
  }
})

/**
 * 当录音 Blob 地址变化时再次尝试自动播放，覆盖异步拉流完成后才拿到地址的场景。
 *
 * @param {string} playbackUrl 当前播放器绑定的录音 Blob 地址。
 * @returns {Promise<void>} 自动播放尝试完成后的 Promise。
 */
watch(currentPlayingUrl, async (playbackUrl) => {
  if (!playbackUrl || !playerDialogVisible.value) {
    return
  }
  await nextTick()
  await tryAutoPlayRecording()
})

/**
 * 组件卸载前清理播放器资源，避免路由切换后残留临时对象地址。
 *
 * @returns {void}
 */
onBeforeUnmount(() => {
  revokeCurrentPlayingUrl()
})

onMounted(loadMediaData)
</script>

<style scoped>
.cell-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cell-stack span {
  color: #5f6b7a;
  font-size: 12px;
}

.transcript-panel {
  padding: 8px 8px 16px;
  background: #f7fbff;
  border-radius: 16px;
}

.transcript-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.transcript-panel-head h3 {
  margin: 0 0 4px;
  font-size: 16px;
  color: #1f2d3d;
}

.transcript-panel-head p {
  margin: 0;
  color: #6b7a90;
  font-size: 13px;
}

.transcript-chat-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.transcript-chat-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 72%;
}

.transcript-chat-row.is-right {
  margin-left: auto;
  align-items: flex-end;
}

.transcript-chat-row.is-left {
  margin-right: auto;
  align-items: flex-start;
}

.transcript-chat-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: #8091a7;
}

.transcript-chat-bubble {
  padding: 12px 14px;
  line-height: 1.7;
  font-size: 14px;
  border-radius: 18px;
  background: #ffffff;
  color: #223043;
  box-shadow: 0 10px 24px rgba(102, 143, 188, 0.12);
  word-break: break-word;
}

.transcript-chat-row.is-right .transcript-chat-bubble {
  background: linear-gradient(135deg, #2f80ed, #4aa3ff);
  color: #ffffff;
}

.transcript-summary {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 14px;
  background: #ffffff;
  color: #4e5d73;
  line-height: 1.8;
}

.player-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.recording-player {
  width: 100%;
}
</style>
