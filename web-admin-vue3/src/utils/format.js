/**
 * 将输入值格式化为可读时间字符串。
 *
 * @param {string | number | null | undefined} value 需要格式化的时间值。
 * @returns {string} 格式化后的时间文本；若原值为空则返回 `--`。
 */
export function formatDateTime(value) {
  if (!value) {
    return '--'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  const second = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}

/**
 * 将任意对象转为适合界面展示的 JSON 文本。
 *
 * @param {unknown} value 需要序列化的任意值。
 * @returns {string} 序列化结果；序列化失败时回退为字符串。
 */
export function formatJson(value) {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch (error) {
    return String(value ?? '')
  }
}

/**
 * 将 JSON 文本解析为对象。
 *
 * @param {string} text 页面表单中的 JSON 文本。
 * @param {unknown} fallback 解析失败时返回的默认值。
 * @returns {unknown} 成功时返回解析后的对象，失败时返回默认值。
 */
export function parseJsonText(text, fallback = {}) {
  if (!text || !String(text).trim()) {
    return fallback
  }

  return JSON.parse(text)
}

/**
 * 根据状态值推导出界面展示用的标签类型。
 *
 * @param {string | null | undefined} status 当前状态字符串。
 * @returns {string} 对应的状态类型标识。
 */
export function resolveStatusClass(status) {
  const normalizedStatus = String(status ?? '').toLowerCase()

  if (['active', 'enabled', 'published', 'completed', 'success', 'answered'].includes(normalizedStatus)) {
    return 'is-active'
  }

  if (['draft', 'pending', 'queued', 'running'].includes(normalizedStatus)) {
    return 'is-draft'
  }

  if (['paused', 'warning', 'timeout'].includes(normalizedStatus)) {
    return 'is-warning'
  }

  return 'is-danger'
}

/**
 * 将任务、执行批次、会话、应答和结果状态转换为中文文案。
 *
 * @param {string | null | undefined} status 当前原始状态值。
 * @param {'task' | 'run' | 'session' | 'answer' | 'result'} category 当前状态所属分类。
 * @returns {string} 返回适合页面展示的中文文本；未知状态时回退为原始值或 `--`。
 */
export function formatStatusLabel(status, category = 'task') {
  const normalizedStatus = String(status ?? '').trim().toLowerCase()
  if (!normalizedStatus) {
    return '--'
  }

  const statusLabelMap = {
    task: {
      draft: '草稿',
      pending: '待处理',
      queued: '排队中',
      running: '运行中',
      completed: '已完成',
      terminated: '已停止',
      failed: '失败',
      cancelled: '已取消',
    },
    run: {
      draft: '草稿',
      pending: '待处理',
      queued: '排队中',
      running: '运行中',
      completed: '已完成',
      terminated: '已停止',
      failed: '失败',
      cancelled: '已取消',
    },
    session: {
      pending: '待处理',
      dialing: '拨号中',
      ringing: '振铃中',
      answered: '已接通',
      completed: '已结束',
      failed: '失败',
      cancelled: '已取消',
    },
    answer: {
      unanswered: '未应答',
      answered: '已应答',
      timeout: '超时',
      rejected: '已拒接',
    },
    result: {
      busy: '忙线',
      hangup: '已挂断',
      call_failed: '呼叫失败',
      forced_hangup: '系统挂断',
      no_playback_plan: '无播放计划',
    },
  }

  return statusLabelMap[category]?.[normalizedStatus] || String(status)
}

/**
 * 生成后台头部显示的当前时间文本。
 *
 * @returns {{date: string, time: string, week: string}} 当前日期、时间与星期信息。
 */
export function getCurrentClock() {
  const date = new Date()
  const weeks = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  const dateText = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate(),
  ).padStart(2, '0')}`
  const timeText = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(
    2,
    '0',
  )}:${String(date.getSeconds()).padStart(2, '0')}`

  return {
    date: dateText,
    time: timeText,
    week: weeks[date.getDay()],
  }
}
