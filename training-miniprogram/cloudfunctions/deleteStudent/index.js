const axios = require('axios')
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})
const db = cloud.database()
const CONFIG_COLLECTION = 'config'
const BASE_URL_CONFIG_DOC_ID = 'origin_system_sync'

const DEFAULT_TIMEOUT_MS = 30000

function trimSlash(value = '') {
  return String(value || '').trim().replace(/\/+$/, '')
}

function trimText(value = '') {
  return String(value || '').trim()
}

function getApiKeyFromConfig(config = {}, event = {}) {
  const direct = trimText(
    event.api_key
      || event.apiKey
      || event.origin_system_api_key
      || event.originSystemApiKey
  )
  if (direct) return direct

  return trimText(
    config.api_key
      || config.apiKey
      || config.origin_system_api_key
      || config.originSystemApiKey
  )
}

async function getRemoteConfig(event = {}) {
  const directBaseUrl = trimSlash(event.api_base_url || event.base_url || '')
  const directApiKey = getApiKeyFromConfig({}, event)
  if (directBaseUrl) {
    return {
      baseUrl: directBaseUrl,
      apiKey: directApiKey
    }
  }

  try {
    const result = await db.collection(CONFIG_COLLECTION).doc(BASE_URL_CONFIG_DOC_ID).get()
    const raw = result && result.data ? result.data : {}
    const config = raw && typeof raw.data === 'object' ? raw.data : raw
    return {
      baseUrl: trimSlash(
        (config && (config.base_url || config.baseUrl || config.origin_system_base_url || config.originSystemBaseUrl)) || ''
      ),
      apiKey: getApiKeyFromConfig(config, event)
    }
  } catch (err) {
    return {
      baseUrl: '',
      apiKey: directApiKey
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

  const { baseUrl, apiKey } = await getRemoteConfig(event)
  if (!baseUrl) {
    return {
      error: '配置错误',
      message: '未在云数据库 config/origin_system_sync 中配置 base_url'
    }
  }
  if (!apiKey) {
    return {
      error: '配置错误',
      message: '未在云数据库 config/origin_system_sync 中配置 api_key'
    }
  }

  try {
    const response = await axios.post(
      `${baseUrl}/api/students/${encodeURIComponent(studentId)}/reject`,
      { delete: true },
      {
        headers: {
          'X-API-Key': apiKey
        },
        timeout: DEFAULT_TIMEOUT_MS,
        validateStatus: () => true
      }
    )

    if (response.status < 200 || response.status >= 300) {
      const msg = response.data && (response.data.error || response.data.message)
      return {
        error: '删除失败',
        message: msg || `HTTP ${response.status}`
      }
    }

    return {
      success: true,
      message: (response.data && response.data.message) || '删除成功'
    }
  } catch (err) {
    return {
      error: '删除失败',
      message: err.message || '请求网页系统失败'
    }
  }
}
