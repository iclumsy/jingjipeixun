const axios = require('axios')
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const DEFAULT_TIMEOUT_MS = 60000

function trimSlash(value = '') {
  return String(value || '').trim().replace(/\/+$/, '')
}

function parseBoolean(value) {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    return ['1', 'true', 'yes', 'on'].includes(normalized)
  }
  return false
}

function parsePositiveInt(value, fallback) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback
  return Math.floor(parsed)
}

function getBaseUrl(event) {
  return trimSlash(
    event.api_base_url ||
    process.env.WEB_API_BASE_URL ||
    process.env.ORIGIN_SYSTEM_BASE_URL ||
    ''
  )
}

function withClientId(item) {
  const id = item && item.id !== undefined && item.id !== null ? String(item.id) : ''
  return {
    ...item,
    _id: id
  }
}

exports.main = async (event = {}) => {
  const wxContext = cloud.getWXContext()
  const {
    status = 'unreviewed',
    search = '',
    company = '',
    training_type = '',
    myOnly = false,
    include_total = false,
    with_total = false,
    page = 1,
    limit = 20
  } = event

  const baseUrl = getBaseUrl(event)
  if (!baseUrl) {
    return {
      error: '配置错误',
      message: '未配置网页系统 API 地址（WEB_API_BASE_URL）'
    }
  }

  try {
    const forceMyOnly = parseBoolean(myOnly)
    const response = await axios.get(`${baseUrl}/api/students`, {
      params: {
        status,
        search,
        company,
        training_type,
        my_only: forceMyOnly,
        submitter_openid: forceMyOnly ? String(event.openid || wxContext.OPENID || '').trim() : ''
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

    const pageNo = parsePositiveInt(page, 1)
    const pageSize = Math.min(parsePositiveInt(limit, 20), 100)
    const shouldIncludeTotal = parseBoolean(include_total) || parseBoolean(with_total)

    let list = Array.isArray(response.data) ? response.data : []

    list = list.map(withClientId)

    const start = (pageNo - 1) * pageSize
    const end = start + pageSize
    const sliced = list.slice(start, end)
    const hasMore = end < list.length

    const result = {
      list: sliced,
      page: pageNo,
      limit: pageSize,
      hasMore
    }

    if (shouldIncludeTotal) {
      result.total = list.length
    }

    return result
  } catch (err) {
    return {
      error: '查询失败',
      message: err.message || '请求网页系统失败'
    }
  }
}
