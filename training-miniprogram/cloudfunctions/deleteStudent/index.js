const axios = require('axios')

const DEFAULT_TIMEOUT_MS = 30000

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

exports.main = async (event = {}) => {
  const studentId = String(event.student_id || '').trim()

  if (!studentId) {
    return {
      error: '参数错误',
      message: '学员ID不能为空'
    }
  }

  const baseUrl = getBaseUrl(event)
  if (!baseUrl) {
    return {
      error: '配置错误',
      message: '未配置网页系统 API 地址（WEB_API_BASE_URL）'
    }
  }

  try {
    const response = await axios.post(
      `${baseUrl}/api/students/${encodeURIComponent(studentId)}/reject`,
      { delete: true },
      {
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
