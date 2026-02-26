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

exports.main = async (event = {}) => {
  const { status = '', training_type = '', company = '' } = event

  const baseUrl = await getBaseUrl(event)
  if (!baseUrl) {
    return {
      error: '配置错误',
      message: '未在云数据库 config/origin_system_sync 中配置 base_url'
    }
  }

  try {
    const response = await axios.get(`${baseUrl}/api/companies`, {
      params: {
        status,
        training_type,
        company
      },
      timeout: DEFAULT_TIMEOUT_MS,
      validateStatus: () => true
    })

    if (response.status < 200 || response.status >= 300) {
      const msg = response.data && (response.data.error || response.data.message)
      return {
        error: '查询失败',
        message: msg || `HTTP ${response.status}`
      }
    }

    const companies = Array.isArray(response.data) ? response.data : []
    return {
      companies
    }
  } catch (err) {
    return {
      error: '查询失败',
      message: err.message || '请求网页系统失败'
    }
  }
}
