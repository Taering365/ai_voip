import axios from 'axios'
import { ElMessage } from 'element-plus'

const ACCESS_TOKEN_KEY = 'aivoip_access_token'
const USER_INFO_KEY = 'aivoip_user_info'

const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:3900',
  timeout: 30000,
})

/**
 * 将接口相对路径转换为完整后端访问地址。
 *
 * @param {string | null | undefined} path 后端返回的相对或绝对接口路径。
 * @returns {string} 可直接给浏览器访问的完整 URL。
 */
export function buildApiUrl(path) {
  const normalizedPath = String(path || '').trim()
  if (!normalizedPath) {
    return ''
  }
  if (normalizedPath.startsWith('http://') || normalizedPath.startsWith('https://')) {
    return normalizedPath
  }
  const baseUrl = String(httpClient.defaults.baseURL || '').replace(/\/$/, '')
  const targetPath = normalizedPath.startsWith('/') ? normalizedPath : `/${normalizedPath}`
  return `${baseUrl}${targetPath}`
}

/**
 * 从浏览器本地存储中读取访问令牌。
 *
 * @returns {string} 已保存的访问令牌；不存在时返回空字符串。
 */
export function getAccessToken() {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY) || ''
}

/**
 * 将访问令牌保存到浏览器本地存储中。
 *
 * @param {string} token 后端返回的加密访问令牌。
 * @returns {void}
 */
export function setAccessToken(token) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token)
}

/**
 * 清理本地保存的登录凭证。
 *
 * @returns {void}
 */
export function clearAccessToken() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY)
  window.localStorage.removeItem(USER_INFO_KEY)
}

/**
 * 将当前用户信息写入浏览器本地存储。
 *
 * @param {object} userInfo 当前登录用户的基础信息对象。
 * @returns {void}
 */
export function setStoredUserInfo(userInfo) {
  window.localStorage.setItem(USER_INFO_KEY, JSON.stringify(userInfo || {}))
}

/**
 * 从浏览器本地存储中读取用户信息。
 *
 * @returns {object | null} 解析后的用户对象；没有数据时返回 `null`。
 */
export function getStoredUserInfo() {
  const rawValue = window.localStorage.getItem(USER_INFO_KEY)

  if (!rawValue) {
    return null
  }

  try {
    return JSON.parse(rawValue)
  } catch (error) {
    return null
  }
}

/**
 * 统一处理接口成功响应结构。
 *
 * @param {import('axios').AxiosResponse} response Axios 响应对象。
 * @returns {unknown} 业务响应中的 `data` 字段内容。
 */
function unwrapApiResponse(response) {
  return response.data?.data
}

/**
 * 统一处理接口异常并向页面抛出错误。
 *
 * @param {unknown} error Axios 或运行时异常对象。
 * @returns {Promise<never>} 以 Promise rejection 形式继续抛出异常。
 */
function handleApiError(error) {
  const responseMessage = error?.response?.data?.message
  const fallbackMessage = error?.message || '请求失败'
  const finalMessage = responseMessage || fallbackMessage

  if (error?.response?.status === 401) {
    clearAccessToken()
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
  }

  ElMessage.error(finalMessage)
  return Promise.reject(error)
}

httpClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

httpClient.interceptors.response.use(unwrapApiResponse, handleApiError)

/**
 * 发起 GET 请求。
 *
 * @param {string} url 请求路径。
 * @param {object} params 查询参数对象。
 * @returns {Promise<unknown>} 业务响应数据。
 */
export function httpGet(url, params = {}) {
  return httpClient.get(url, { params })
}

/**
 * 发起带鉴权的二进制 GET 请求。
 *
 * 参数:
 *   url: 需要访问的接口路径，可传相对路径或完整 URL。
 *   params: 需要拼接到查询字符串中的参数对象。
 *
 * 返回:
 *   Promise<import('axios').AxiosResponse<Blob>>: 返回原始 Axios 响应，供调用方读取 Blob 与响应头。
 */
export function httpGetBlobResponse(url, params = {}) {
  const accessToken = getAccessToken()
  const requestHeaders = {}

  // 浏览器原生 audio / window.open 不会自动携带 Bearer Token，因此二进制文件统一走显式鉴权请求。
  if (accessToken) {
    requestHeaders.Authorization = `Bearer ${accessToken}`
  }

  return axios
    .get(buildApiUrl(url), {
      params,
      responseType: 'blob',
      timeout: 30000,
      headers: requestHeaders,
    })
    .catch(handleApiError)
}

/**
 * 发起带鉴权的二进制 GET 请求，并直接返回 Blob 对象。
 *
 * 参数:
 *   url: 需要访问的接口路径，可传相对路径或完整 URL。
 *   params: 需要拼接到查询字符串中的参数对象。
 *
 * 返回:
 *   Promise<Blob>: 接口返回的二进制文件对象。
 */
export async function httpGetBlob(url, params = {}) {
  const response = await httpGetBlobResponse(url, params)
  return response.data
}

/**
 * 从响应头中解析下载文件名。
 *
 * 参数:
 *   contentDisposition: 接口返回的 `Content-Disposition` 响应头原文。
 *   fallbackName: 当响应头中没有文件名时使用的兜底文件名。
 *
 * 返回:
 *   string: 浏览器下载时应使用的文件名。
 */
export function resolveDownloadFilename(contentDisposition, fallbackName = 'download.bin') {
  const headerText = String(contentDisposition || '')
  const utf8Match = headerText.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1])
  }

  const plainMatch = headerText.match(/filename=\"?([^\";]+)\"?/i)
  if (plainMatch?.[1]) {
    return plainMatch[1]
  }
  return fallbackName
}

/**
 * 通过带鉴权的二进制请求触发浏览器下载。
 *
 * 参数:
 *   url: 需要下载的接口路径，可传相对路径或完整 URL。
 *   fallbackName: 接口未返回文件名时的兜底下载文件名。
 *
 * 返回:
 *   Promise<void>: 浏览器下载动作触发完成后的 Promise。
 */
export async function downloadBinaryFile(url, fallbackName = 'download.bin') {
  const response = await httpGetBlobResponse(url)
  const blobUrl = window.URL.createObjectURL(response.data)
  const downloadLink = document.createElement('a')
  const filename = resolveDownloadFilename(response.headers?.['content-disposition'], fallbackName)

  // 使用隐藏的 a 标签触发下载，可以复用同一套鉴权请求结果，避免再次访问后端。
  downloadLink.href = blobUrl
  downloadLink.download = filename
  downloadLink.style.display = 'none'
  document.body.appendChild(downloadLink)
  downloadLink.click()
  document.body.removeChild(downloadLink)
  window.URL.revokeObjectURL(blobUrl)
}

/**
 * 发起 POST 请求。
 *
 * @param {string} url 请求路径。
 * @param {object} data 请求体对象。
 * @returns {Promise<unknown>} 业务响应数据。
 */
export function httpPost(url, data = {}) {
  return httpClient.post(url, data)
}

/**
 * 发起 multipart/form-data POST 请求。
 *
 * @param {string} url 请求路径。
 * @param {FormData} formData 表单数据对象。
 * @returns {Promise<unknown>} 业务响应数据。
 */
export function httpPostForm(url, formData) {
  return httpClient.post(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

/**
 * 发起 PUT 请求。
 *
 * @param {string} url 请求路径。
 * @param {object} data 请求体对象。
 * @returns {Promise<unknown>} 业务响应数据。
 */
export function httpPut(url, data = {}) {
  return httpClient.put(url, data)
}

/**
 * 发起 PATCH 请求。
 *
 * @param {string} url 请求路径。
 * @param {object} data 请求体对象。
 * @returns {Promise<unknown>} 业务响应数据。
 */
export function httpPatch(url, data = {}) {
  return httpClient.patch(url, data)
}

/**
 * 发起 DELETE 请求。
 *
 * @param {string} url 请求路径。
 * @returns {Promise<unknown>} 业务响应数据。
 */
export function httpDelete(url) {
  return httpClient.delete(url)
}
