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

function normalizeIds(ids) {
  if (!Array.isArray(ids)) return []
  return ids
    .map(item => Number(item))
    .filter(item => Number.isFinite(item) && item > 0)
}

exports.main = async (event = {}) => {
  const { student_ids, action } = event
  const ids = normalizeIds(student_ids)

  if (!ids.length) {
    return {
      error: '参数错误',
      message: '学员ID列表不能为空'
    }
  }

  if (!action || (action !== 'approve' && action !== 'reject')) {
    return {
      error: '参数错误',
      message: '操作类型必须是 approve 或 reject'
    }
  }

  const baseUrl = await getBaseUrl(event)
  if (!baseUrl) {
    return {
      error: '配置错误',
      message: '未在云数据库 config/origin_system_sync 中配置 base_url'
    }
  }

  const errors = []
  let successCount = 0

  for (const id of ids) {
    try {
      if (action === 'approve') {
        const response = await axios.post(
          `${baseUrl}/api/students/${id}/approve`,
          {},
          {
            timeout: DEFAULT_TIMEOUT_MS,
            validateStatus: () => true
          }
        )

        if (response.status < 200 || response.status >= 300) {
          const msg = response.data && (response.data.error || response.data.message)
          errors.push({ studentId: String(id), error: msg || `HTTP ${response.status}` })
          continue
        }
      } else {
        const response = await axios.post(
          `${baseUrl}/api/students/${id}/reject`,
          {
            delete: false,
            status: 'rejected'
          },
          {
            timeout: DEFAULT_TIMEOUT_MS,
            validateStatus: () => true
          }
        )

        if (response.status < 200 || response.status >= 300) {
          const msg = response.data && (response.data.error || response.data.message)
          errors.push({ studentId: String(id), error: msg || `HTTP ${response.status}` })
          continue
        }
      }

      successCount += 1
    } catch (err) {
      errors.push({ studentId: String(id), error: err.message || '请求失败' })
    }
  }

  return {
    success: true,
    successCount,
    totalCount: ids.length,
    errors: errors.length ? errors : undefined
  }
}
