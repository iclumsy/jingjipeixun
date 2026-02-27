const axios = require('axios')
const cloud = require('wx-server-sdk')
const path = require('path')
const crypto = require('crypto')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})
const db = cloud.database()
const CONFIG_COLLECTION = 'config'
const BASE_URL_CONFIG_DOC_ID = 'origin_system_sync'

const DEFAULT_TIMEOUT_MS = 60000
const PROXY_MAX_AGE_SEC = 3600
const PROXY_PREFIX = 'origin-sync/health-check'

function trimSlash(value = '') {
  return String(value || '').trim().replace(/\/+$/, '')
}

async function getBaseUrl(event = {}) {
  const direct = trimSlash(event.api_base_url || event.base_url || '')
  if (direct) {
    return direct
  }

  try {
    const result = await db.collection(CONFIG_COLLECTION).doc(BASE_URL_CONFIG_DOC_ID).get()
    const raw = result && result.data ? result.data : {}
    const config = raw && typeof raw.data === 'object' ? raw.data : raw
    return trimSlash(
      (config && (config.base_url || config.baseUrl || config.origin_system_base_url || config.originSystemBaseUrl)) || ''
    )
  } catch (err) {
    return ''
  }
}

async function safeAxiosGet(url, config = {}) {
  try {
    return await axios.get(url, config)
  } catch (err) {
    const message = String((err && err.message) || '')
    if (/unable to verify the first certificate/i.test(message) && /^https:\/\//i.test(url)) {
      const fallbackUrl = url.replace(/^https:\/\//i, 'http://')
      return axios.get(fallbackUrl, config)
    }
    throw err
  }
}

async function safeAxiosPost(url, data, config = {}) {
  try {
    return await axios.post(url, data, config)
  } catch (err) {
    const message = String((err && err.message) || '')
    if (/unable to verify the first certificate/i.test(message) && /^https:\/\//i.test(url)) {
      const fallbackUrl = url.replace(/^https:\/\//i, 'http://')
      return axios.post(fallbackUrl, data, config)
    }
    throw err
  }
}

function toAbsoluteUrl(baseUrl, pathValue) {
  const raw = String(pathValue || '').trim()
  if (!raw) return ''
  const absolute = /^https?:\/\//i.test(raw)
    ? raw
    : (raw.startsWith('/') ? `${baseUrl}${raw}` : `${baseUrl}/${raw}`)
  try {
    return encodeURI(decodeURI(absolute))
  } catch (err) {
    try {
      return encodeURI(absolute)
    } catch (innerErr) {
      return absolute
    }
  }
}

function resolveEffectiveBaseUrl(defaultBaseUrl, responseUrl = '') {
  const raw = String(responseUrl || '').trim()
  if (!raw) return defaultBaseUrl
  const idx = raw.indexOf('/api/')
  if (idx > 0) {
    return raw.slice(0, idx).replace(/\/+$/, '')
  }
  return defaultBaseUrl
}

function sanitizeSegment(value = '') {
  const normalized = String(value || '').replace(/[^a-zA-Z0-9_-]/g, '_')
  return normalized || 'unknown'
}

async function proxyRemoteFileToCloud(fileUrl, studentId) {
  if (!fileUrl) return { fileID: '', downloadUrl: '' }

  const response = await safeAxiosGet(fileUrl, {
    responseType: 'arraybuffer',
    timeout: DEFAULT_TIMEOUT_MS,
    validateStatus: () => true
  })
  if (response.status < 200 || response.status >= 300) {
    throw new Error(`体检表下载失败: HTTP ${response.status}`)
  }

  const fileBuffer = Buffer.from(response.data || '')
  if (!fileBuffer.length) {
    throw new Error('体检表下载失败: 文件为空')
  }

  const ext = path.extname(String(fileUrl).split('?')[0] || '').toLowerCase() || '.docx'
  const hash = crypto.createHash('md5').update(fileUrl).digest('hex').slice(0, 16)
  const cloudPath = `${PROXY_PREFIX}/${sanitizeSegment(studentId)}/form_${hash}${ext}`
  const uploadResult = await cloud.uploadFile({
    cloudPath,
    fileContent: fileBuffer
  })

  const fileID = uploadResult && uploadResult.fileID ? uploadResult.fileID : ''
  if (!fileID) {
    return { fileID: '', downloadUrl: '' }
  }

  const tempResult = await cloud.getTempFileURL({
    fileList: [{
      fileID,
      maxAge: PROXY_MAX_AGE_SEC
    }]
  })
  const tempFile = (tempResult.fileList || []).find(item => item.fileID === fileID)
  return {
    fileID,
    downloadUrl: (tempFile && tempFile.tempFileURL) || ''
  }
}

exports.main = async (event = {}) => {
  const studentId = String(event.student_id || '').trim()
  if (!studentId) {
    return {
      error: '参数错误',
      message: '学员ID不能为空'
    }
  }

  const baseUrl = await getBaseUrl(event)
  if (!baseUrl) {
    return {
      error: '配置错误',
      message: '未在云数据库 config/origin_system_sync 中配置 base_url'
    }
  }

  try {
    const approveResponse = await safeAxiosPost(
      `${baseUrl}/api/students/${encodeURIComponent(studentId)}/approve`,
      {},
      {
        timeout: DEFAULT_TIMEOUT_MS,
        validateStatus: () => true
      }
    )

    if (approveResponse.status < 200 || approveResponse.status >= 300) {
      const msg = approveResponse.data && (approveResponse.data.error || approveResponse.data.message)
      return {
        error: '生成失败',
        message: msg || `HTTP ${approveResponse.status}`
      }
    }

    const student = approveResponse.data || {}
    const formPath = student.training_form_path || ''
    const effectiveBaseUrl = resolveEffectiveBaseUrl(
      baseUrl,
      approveResponse && approveResponse.config && approveResponse.config.url
    )
    const formUrl = formPath ? toAbsoluteUrl(effectiveBaseUrl, formPath) : ''
    const proxied = formUrl
      ? await proxyRemoteFileToCloud(formUrl, studentId)
      : { fileID: '', downloadUrl: '' }

    return {
      success: true,
      fileID: proxied.fileID || formPath,
      downloadUrl: proxied.downloadUrl || '',
      message: formPath ? '体检表生成成功' : '审核通过，但未生成体检表'
    }
  } catch (err) {
    return {
      error: '生成失败',
      message: err.message || '请求网页系统失败'
    }
  }
}
