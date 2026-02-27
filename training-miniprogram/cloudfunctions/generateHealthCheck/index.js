const axios = require('axios')
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})
const db = cloud.database()
const CONFIG_COLLECTION = 'config'
const BASE_URL_CONFIG_DOC_ID = 'origin_system_sync'

const DEFAULT_TIMEOUT_MS = 60000

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
    const approveResponse = await axios.post(
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

    return {
      success: true,
      fileID: formPath,
      downloadUrl: formPath ? toAbsoluteUrl(baseUrl, formPath) : '',
      message: formPath ? '体检表生成成功' : '审核通过，但未生成体检表'
    }
  } catch (err) {
    return {
      error: '生成失败',
      message: err.message || '请求网页系统失败'
    }
  }
}
