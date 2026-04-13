import { httpDelete, httpGet, httpPatch, httpPost, httpPostForm, httpPut } from './client'

/**
 * 获取登录验证码。
 *
 * @returns {Promise<unknown>} 验证码数据对象。
 */
export function fetchCaptchaApi() {
  return httpGet('/api/v1/auth/captcha')
}

/**
 * 调用登录接口并返回登录结果。
 *
 * @param {{username: string, password: string, captcha_key: string, captcha_code: string}} payload 登录表单数据。
 * @returns {Promise<unknown>} 登录响应数据。
 */
export function loginApi(payload) {
  return httpPost('/api/v1/auth/login', payload)
}

/**
 * 获取当前用户信息。
 *
 * @returns {Promise<unknown>} 当前用户信息。
 */
export function fetchCurrentUserApi() {
  return httpGet('/api/v1/system/me')
}

/**
 * 获取系统配置列表。
 *
 * @returns {Promise<unknown>} 系统配置数组。
 */
export function fetchSystemConfigsApi() {
  return httpGet('/api/v1/system/configs')
}

/**
 * 获取用户列表。
 *
 * @returns {Promise<unknown>} 用户数组。
 */
export function fetchUsersApi() {
  return httpGet('/api/v1/users')
}

/**
 * 创建系统用户。
 *
 * @param {object} payload 用户表单对象。
 * @returns {Promise<unknown>} 创建后的用户对象。
 */
export function createUserApi(payload) {
  return httpPost('/api/v1/users', payload)
}

/**
 * 更新系统用户。
 *
 * @param {number} userId 用户主键。
 * @param {object} payload 用户表单对象。
 * @returns {Promise<unknown>} 更新后的用户对象。
 */
export function updateUserApi(userId, payload) {
  return httpPut(`/api/v1/users/${userId}`, payload)
}

/**
 * 获取指定用户已分配的线路列表。
 *
 * @param {number} userId 用户主键。
 * @returns {Promise<unknown>} 已分配线路数组。
 */
export function fetchUserTrunksApi(userId) {
  return httpGet(`/api/v1/users/${userId}/trunks`)
}

/**
 * 更新指定用户的线路分配关系。
 *
 * @param {number} userId 用户主键。
 * @param {number[]} trunkIds 线路主键数组。
 * @returns {Promise<unknown>} 更新后的线路列表。
 */
export function replaceUserTrunksApi(userId, trunkIds) {
  return httpPut(`/api/v1/users/${userId}/trunks`, {
    trunk_ids: trunkIds,
  })
}

/**
 * 获取健康检查信息。
 *
 * @returns {Promise<unknown>} 健康检查响应。
 */
export function fetchHealthApi() {
  return httpGet('/api/v1/health')
}

/**
 * 获取存储配置列表。
 *
 * @returns {Promise<unknown>} 存储配置数组。
 */
export function fetchStorageProfilesApi() {
  return httpGet('/api/v1/storage/profiles')
}

/**
 * 获取默认存储配置。
 *
 * @returns {Promise<unknown>} 默认存储配置对象。
 */
export function fetchDefaultStorageProfileApi() {
  return httpGet('/api/v1/storage/profiles/default')
}

/**
 * 创建存储配置。
 *
 * @param {object} payload 存储配置表单对象。
 * @returns {Promise<unknown>} 创建后的存储配置对象。
 */
export function createStorageProfileApi(payload) {
  return httpPost('/api/v1/storage/profiles', payload)
}

/**
 * 检测存储配置是否可用。
 *
 * @param {object} payload 存储配置表单对象。
 * @returns {Promise<unknown>} 检测结果对象。
 */
export function probeStorageProfileApi(payload) {
  return httpPost('/api/v1/storage/profiles/probe', payload)
}

/**
 * 更新存储配置。
 *
 * @param {number} profileId 存储配置主键。
 * @param {object} payload 存储配置表单对象。
 * @returns {Promise<unknown>} 更新后的存储配置对象。
 */
export function updateStorageProfileApi(profileId, payload) {
  return httpPut(`/api/v1/storage/profiles/${profileId}`, payload)
}

/**
 * 设置默认存储配置。
 *
 * @param {number} profileId 存储配置主键。
 * @returns {Promise<unknown>} 更新后的默认存储配置对象。
 */
export function setDefaultStorageProfileApi(profileId) {
  return httpPost(`/api/v1/storage/profiles/${profileId}/default`)
}

/**
 * 删除存储配置。
 *
 * @param {number} profileId 存储配置主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteStorageProfileApi(profileId) {
  return httpDelete(`/api/v1/storage/profiles/${profileId}`)
}

/**
 * 获取语音接口列表。
 *
 * @returns {Promise<unknown>} 接口数组。
 */
export function fetchProvidersApi() {
  return httpGet('/api/v1/providers')
}

/**
 * 创建语音接口配置。
 *
 * @param {object} payload 接口表单对象。
 * @returns {Promise<unknown>} 创建后的接口对象。
 */
export function createProviderApi(payload) {
  return httpPost('/api/v1/providers', payload)
}

/**
 * 更新语音接口配置。
 *
 * @param {number} providerId 接口主键。
 * @param {object} payload 接口表单对象。
 * @returns {Promise<unknown>} 更新后的接口对象。
 */
export function updateProviderApi(providerId, payload) {
  return httpPut(`/api/v1/providers/${providerId}`, payload)
}

/**
 * 删除语音接口配置。
 *
 * @param {number} providerId 接口主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteProviderApi(providerId) {
  return httpDelete(`/api/v1/providers/${providerId}`)
}

/**
 * 检测语音接口配置是否可用。
 *
 * @param {number} providerId 接口主键。
 * @returns {Promise<unknown>} 接口检测结果对象。
 */
export function checkProviderHealthApi(providerId) {
  return httpPost(`/api/v1/providers/${providerId}/health-check`)
}

/**
 * 获取 SIP 线路列表。
 *
 * @returns {Promise<unknown>} 线路数组。
 */
export function fetchTrunksApi() {
  return httpGet('/api/v1/trunks')
}

/**
 * 创建 SIP 线路。
 *
 * @param {object} payload 线路表单对象。
 * @returns {Promise<unknown>} 创建后的线路对象。
 */
export function createTrunkApi(payload) {
  return httpPost('/api/v1/trunks', payload)
}

/**
 * 更新 SIP 线路。
 *
 * @param {number} trunkId 线路主键。
 * @param {object} payload 线路表单对象。
 * @returns {Promise<unknown>} 更新后的线路对象。
 */
export function updateTrunkApi(trunkId, payload) {
  return httpPut(`/api/v1/trunks/${trunkId}`, payload)
}

/**
 * 更新 SIP 线路状态。
 *
 * @param {number} trunkId 线路主键。
 * @param {object} payload 状态更新对象。
 * @returns {Promise<unknown>} 更新后的线路对象。
 */
export function updateTrunkStatusApi(trunkId, payload) {
  return httpPatch(`/api/v1/trunks/${trunkId}/status`, payload)
}

/**
 * 删除指定线路。
 *
 * @param {number} trunkId 线路主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteTrunkApi(trunkId) {
  return httpDelete(`/api/v1/trunks/${trunkId}`)
}

/**
 * 检测指定线路的连通性与注册准备状态。
 *
 * @param {number} trunkId 线路主键。
 * @returns {Promise<unknown>} 检测结果对象。
 */
export function probeTrunkApi(trunkId) {
  return httpPost(`/api/v1/trunks/${trunkId}/probe`)
}

/**
 * 获取话术列表。
 *
 * @returns {Promise<unknown>} 话术数组。
 */
export function fetchScriptsApi() {
  return httpGet('/api/v1/scripts')
}

/**
 * 创建话术。
 *
 * @param {object} payload 话术表单对象。
 * @returns {Promise<unknown>} 创建后的话术对象。
 */
export function createScriptApi(payload) {
  return httpPost('/api/v1/scripts', payload)
}

/**
 * 导入系统内置的名酒品鉴会邀约示例话术。
 *
 * @returns {Promise<unknown>} 创建后的话术对象。
 */
export function createWineTastingDemoApi() {
  return httpPost('/api/v1/scripts/demo/wine-tasting')
}

/**
 * 导入系统内置的少儿编程教育推广示例话术。
 *
 * @returns {Promise<unknown>} 创建后的话术对象。
 */
export function createKidsCodingDemoApi() {
  return httpPost('/api/v1/scripts/demo/kids-coding')
}

/**
 * 更新话术。
 *
 * @param {number} scriptId 话术主键。
 * @param {object} payload 话术表单对象。
 * @returns {Promise<unknown>} 更新后的话术对象。
 */
export function updateScriptApi(scriptId, payload) {
  return httpPut(`/api/v1/scripts/${scriptId}`, payload)
}

/**
 * 删除话术。
 *
 * @param {number} scriptId 话术主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteScriptApi(scriptId) {
  return httpDelete(`/api/v1/scripts/${scriptId}`)
}

/**
 * 获取话术版本列表。
 *
 * @param {number} scriptId 话术主键。
 * @returns {Promise<unknown>} 版本数组。
 */
export function fetchScriptVersionsApi(scriptId) {
  return httpGet(`/api/v1/scripts/${scriptId}/versions`)
}

/**
 * 创建话术版本。
 *
 * @param {number} scriptId 话术主键。
 * @param {object} payload 版本表单对象。
 * @returns {Promise<unknown>} 创建后的版本对象。
 */
export function createScriptVersionApi(scriptId, payload) {
  return httpPost(`/api/v1/scripts/${scriptId}/versions`, payload)
}

/**
 * 删除话术版本。
 *
 * @param {number} scriptId 话术主键。
 * @param {number} versionId 版本主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteScriptVersionApi(scriptId, versionId) {
  return httpDelete(`/api/v1/scripts/${scriptId}/versions/${versionId}`)
}

/**
 * 更新话术版本画布信息。
 *
 * @param {number} versionId 版本主键。
 * @param {object} payload 版本更新对象。
 * @returns {Promise<unknown>} 更新后的版本对象。
 */
export function updateScriptVersionApi(versionId, payload) {
  return httpPut(`/api/v1/scripts/versions/${versionId}`, payload)
}

/**
 * 发布话术版本。
 *
 * @param {number} scriptId 话术主键。
 * @param {number} versionId 版本主键。
 * @returns {Promise<unknown>} 发布后的版本对象。
 */
export function publishScriptVersionApi(scriptId, versionId) {
  return httpPost(`/api/v1/scripts/${scriptId}/versions/${versionId}/publish`)
}

/**
 * 获取话术节点列表。
 *
 * @param {number} versionId 话术版本主键。
 * @returns {Promise<unknown>} 节点数组。
 */
export function fetchScriptNodesApi(versionId) {
  return httpGet(`/api/v1/scripts/versions/${versionId}/nodes`)
}

/**
 * 创建话术节点。
 *
 * @param {number} versionId 话术版本主键。
 * @param {object} payload 节点表单对象。
 * @returns {Promise<unknown>} 创建后的节点对象。
 */
export function createScriptNodeApi(versionId, payload) {
  return httpPost(`/api/v1/scripts/versions/${versionId}/nodes`, payload)
}

/**
 * 更新话术节点。
 *
 * @param {number} nodeId 节点主键。
 * @param {object} payload 节点更新对象。
 * @returns {Promise<unknown>} 更新后的节点对象。
 */
export function updateScriptNodeApi(nodeId, payload) {
  return httpPut(`/api/v1/scripts/nodes/${nodeId}`, payload)
}

/**
 * 删除话术节点。
 *
 * @param {number} nodeId 节点主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteScriptNodeApi(nodeId) {
  return httpDelete(`/api/v1/scripts/nodes/${nodeId}`)
}

/**
 * 获取话术连线列表。
 *
 * @param {number} versionId 话术版本主键。
 * @returns {Promise<unknown>} 连线数组。
 */
export function fetchScriptEdgesApi(versionId) {
  return httpGet(`/api/v1/scripts/versions/${versionId}/edges`)
}

/**
 * 创建话术连线。
 *
 * @param {number} versionId 话术版本主键。
 * @param {object} payload 连线表单对象。
 * @returns {Promise<unknown>} 创建后的连线对象。
 */
export function createScriptEdgeApi(versionId, payload) {
  return httpPost(`/api/v1/scripts/versions/${versionId}/edges`, payload)
}

/**
 * 更新话术连线。
 *
 * @param {number} edgeId 连线主键。
 * @param {object} payload 连线更新对象。
 * @returns {Promise<unknown>} 更新后的连线对象。
 */
export function updateScriptEdgeApi(edgeId, payload) {
  return httpPut(`/api/v1/scripts/edges/${edgeId}`, payload)
}

/**
 * 删除话术连线。
 *
 * @param {number} edgeId 连线主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteScriptEdgeApi(edgeId) {
  return httpDelete(`/api/v1/scripts/edges/${edgeId}`)
}

/**
 * 获取名单批次列表。
 *
 * @returns {Promise<unknown>} 名单批次数组。
 */
export function fetchBatchesApi() {
  return httpGet('/api/v1/contacts/batches')
}

/**
 * 创建名单批次。
 *
 * @param {object} payload 批次表单对象。
 * @returns {Promise<unknown>} 创建后的批次对象。
 */
export function createBatchApi(payload) {
  return httpPost('/api/v1/contacts/batches', payload)
}

/**
 * 删除名单批次。
 *
 * @param {number} batchId 批次主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteBatchApi(batchId) {
  return httpDelete(`/api/v1/contacts/batches/${batchId}`)
}

/**
 * 获取联系人列表。
 *
 * @param {number | null} batchId 批次筛选条件。
 * @returns {Promise<unknown>} 联系人数组。
 */
export function fetchContactRecordsApi(batchId = null) {
  return httpGet('/api/v1/contacts/records', batchId ? { batch_id: batchId } : {})
}

/**
 * 创建联系人。
 *
 * @param {object} payload 联系人表单对象。
 * @returns {Promise<unknown>} 创建后的联系人对象。
 */
export function createContactRecordApi(payload) {
  return httpPost('/api/v1/contacts/records', payload)
}

/**
 * 批量导入联系人。
 *
 * @param {object} payload 联系人导入表单对象。
 * @returns {Promise<unknown>} 导入结果摘要对象。
 */
export function importContactRecordsApi(payload) {
  return httpPost('/api/v1/contacts/records/import', payload)
}

/**
 * 删除联系人。
 *
 * @param {number} recordId 联系人主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteContactRecordApi(recordId) {
  return httpDelete(`/api/v1/contacts/records/${recordId}`)
}

/**
 * 获取任务列表。
 *
 * @returns {Promise<unknown>} 任务数组。
 */
export function fetchTasksApi() {
  return httpGet('/api/v1/tasks')
}

/**
 * 创建任务。
 *
 * @param {object} payload 任务表单对象。
 * @returns {Promise<unknown>} 创建后的任务对象。
 */
export function createTaskApi(payload) {
  return httpPost('/api/v1/tasks', payload)
}

/**
 * 更新任务。
 *
 * @param {number} taskId 任务主键。
 * @param {object} payload 任务表单对象。
 * @returns {Promise<unknown>} 更新后的任务对象。
 */
export function updateTaskApi(taskId, payload) {
  return httpPut(`/api/v1/tasks/${taskId}`, payload)
}

/**
 * 更新任务状态。
 *
 * @param {number} taskId 任务主键。
 * @param {object} payload 状态更新对象。
 * @returns {Promise<unknown>} 更新后的任务对象。
 */
export function updateTaskStatusApi(taskId, payload) {
  return httpPatch(`/api/v1/tasks/${taskId}/status`, payload)
}

/**
 * 删除任务。
 *
 * @param {number} taskId 任务主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteTaskApi(taskId) {
  return httpDelete(`/api/v1/tasks/${taskId}`)
}

/**
 * 获取任务会话列表。
 *
 * @param {number} taskId 任务主键。
 * @returns {Promise<unknown>} 会话数组。
 */
export function fetchTaskSessionsApi(taskId) {
  return httpGet(`/api/v1/tasks/${taskId}/sessions`)
}

/**
 * 获取任务执行批次列表。
 *
 * @param {number} taskId 任务主键。
 * @returns {Promise<unknown>} 执行批次数组。
 */
export function fetchTaskRunsApi(taskId) {
  return httpGet(`/api/v1/tasks/${taskId}/runs`)
}

/**
 * 获取质检规则列表。
 *
 * @returns {Promise<unknown>} 质检规则数组。
 */
export function fetchQcRulesApi() {
  return httpGet('/api/v1/qc/rules')
}

/**
 * 创建质检规则。
 *
 * @param {object} payload 质检规则表单对象。
 * @returns {Promise<unknown>} 创建后的质检规则对象。
 */
export function createQcRuleApi(payload) {
  return httpPost('/api/v1/qc/rules', payload)
}

/**
 * 更新质检规则。
 *
 * @param {number} ruleId 质检规则主键。
 * @param {object} payload 质检规则表单对象。
 * @returns {Promise<unknown>} 更新后的质检规则对象。
 */
export function updateQcRuleApi(ruleId, payload) {
  return httpPut(`/api/v1/qc/rules/${ruleId}`, payload)
}

/**
 * 删除质检规则。
 *
 * @param {number} ruleId 质检规则主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteQcRuleApi(ruleId) {
  return httpDelete(`/api/v1/qc/rules/${ruleId}`)
}

/**
 * 获取质检结果列表。
 *
 * @returns {Promise<unknown>} 质检结果数组。
 */
export function fetchQcResultsApi() {
  return httpGet('/api/v1/qc/results')
}

/**
 * 获取音频资源列表。
 *
 * @returns {Promise<unknown>} 音频资源数组。
 */
export function fetchAudioAssetsApi() {
  return httpGet('/api/v1/media/audio-assets')
}

/**
 * 创建音频资源元数据。
 *
 * @param {object} payload 音频资源表单对象。
 * @returns {Promise<unknown>} 创建后的音频资源对象。
 */
export function createAudioAssetApi(payload) {
  return httpPost('/api/v1/media/audio-assets', payload)
}

/**
 * 根据播报文案真实生成一条在线 TTS 音频资源。
 *
 * @param {object} payload TTS 生成请求对象。
 * @returns {Promise<unknown>} 创建后的音频资源对象。
 */
export function generateTtsAudioAssetApi(payload) {
  return httpPost('/api/v1/media/audio-assets/generate-tts', payload)
}

/**
 * 删除音频资源。
 *
 * @param {number} assetId 音频资源主键。
 * @returns {Promise<unknown>} 删除接口响应。
 */
export function deleteAudioAssetApi(assetId) {
  return httpDelete(`/api/v1/media/audio-assets/${assetId}`)
}

/**
 * 获取录音文件列表。
 *
 * @returns {Promise<unknown>} 录音文件数组。
 */
export function fetchRecordingsApi() {
  return httpGet('/api/v1/media/recordings')
}

/**
 * 上传录音文件并写入默认存储。
 *
 * @param {{session_id: number|string, record_type: string, file: File}} payload 录音上传表单对象。
 * @returns {Promise<unknown>} 上传后的录音文件对象。
 */
export function uploadRecordingFileApi(payload) {
  const formData = new FormData()
  formData.append('session_id', String(payload.session_id))
  formData.append('record_type', payload.record_type || 'mixed')
  formData.append('file', payload.file)
  return httpPostForm('/api/v1/media/recordings/upload', formData)
}

/**
 * 获取转写任务列表。
 *
 * @returns {Promise<unknown>} 转写任务数组。
 */
export function fetchTranscriptsApi() {
  return httpGet('/api/v1/media/transcripts')
}

/**
 * 对录音文件发起在线转写任务。
 *
 * @param {object} payload 转写任务表单对象。
 * @returns {Promise<unknown>} 创建后的转写任务对象。
 */
export function createTranscriptTaskApi(payload) {
  return httpPost('/api/v1/media/transcripts', payload)
}

/**
 * 获取转写分段列表。
 *
 * @param {number} transcriptTaskId 转写任务主键。
 * @returns {Promise<unknown>} 转写分段数组。
 */
export function fetchTranscriptSegmentsApi(transcriptTaskId) {
  return httpGet(`/api/v1/media/transcripts/${transcriptTaskId}/segments`)
}

/**
 * 执行话术单步运行。
 *
 * @param {number} versionId 话术版本主键。
 * @param {object} payload 单步执行请求体。
 * @returns {Promise<unknown>} 单步执行结果。
 */
export function executeScriptStepApi(versionId, payload) {
  return httpPost(`/api/v1/runtime/scripts/${versionId}/step`, payload)
}

/**
 * 执行话术全流程模拟。
 *
 * @param {number} versionId 话术版本主键。
 * @param {object} payload 模拟执行请求体。
 * @returns {Promise<unknown>} 模拟执行结果。
 */
export function simulateScriptApi(versionId, payload) {
  return httpPost(`/api/v1/runtime/scripts/${versionId}/simulate`, payload)
}

/**
 * 生成任务分发表。
 *
 * @param {number} taskId 任务主键。
 * @returns {Promise<unknown>} 入队结果。
 */
export function queueTaskApi(taskId) {
  return httpPost(`/api/v1/runtime/tasks/${taskId}/queue`)
}

/**
 * 拉取待调度联系人。
 *
 * @param {number} taskId 任务主键。
 * @param {number} limit 拉取条数上限。
 * @returns {Promise<unknown>} 待调度联系人集合。
 */
export function fetchPendingDispatchesApi(taskId, limit = 20) {
  return httpGet(`/api/v1/runtime/tasks/${taskId}/dispatches/pending`, { limit })
}

/**
 * 为待调度记录创建会话。
 *
 * @param {number} taskId 任务主键。
 * @param {object} payload 会话创建对象。
 * @returns {Promise<unknown>} 创建后的会话对象。
 */
export function createRuntimeSessionApi(taskId, payload) {
  return httpPost(`/api/v1/runtime/tasks/${taskId}/sessions`, payload)
}

/**
 * 推进会话状态。
 *
 * @param {number} sessionId 会话主键。
 * @param {object} payload 状态推进对象。
 * @returns {Promise<unknown>} 更新后的会话对象。
 */
export function progressRuntimeSessionApi(sessionId, payload) {
  return httpPatch(`/api/v1/runtime/sessions/${sessionId}/progress`, payload)
}
