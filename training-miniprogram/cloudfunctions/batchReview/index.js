const axios = require('axios')

const DEFAULT_TIMEOUT_MS = 60000

function trimSlash(value = '') {
  return String(value || '').trim().replace(/\/+$/, '')
}

function getBaseUrl(event) {
  return trimSlash(
    event.api_base_url ||
    process.env.WEB_API_BASE_URL ||
    process.env.ORIGIN_SYSTEM_BASE_URL ||
    ''
  )
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

  const baseUrl = getBaseUrl(event)
  if (!baseUrl) {
    return {
      error: '配置错误',
      message: '未配置网页系统 API 地址（WEB_API_BASE_URL）'
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
