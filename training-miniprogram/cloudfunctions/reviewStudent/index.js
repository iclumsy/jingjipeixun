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

function withClientId(student) {
  if (!student || typeof student !== 'object') return student
  return {
    ...student,
    _id: student.id !== undefined && student.id !== null ? String(student.id) : ''
  }
}

exports.main = async (event = {}) => {
  const { student_id, action } = event
  const studentId = String(student_id || '').trim()

  if (!studentId || !action) {
    return {
      error: '参数错误',
      message: '学员ID和操作类型不能为空'
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
    if (action === 'approve') {
      const response = await axios.post(
        `${baseUrl}/api/students/${encodeURIComponent(studentId)}/approve`,
        {},
        {
          timeout: DEFAULT_TIMEOUT_MS,
          validateStatus: () => true
        }
      )

      if (response.status < 200 || response.status >= 300) {
        const msg = response.data && (response.data.error || response.data.message)
        return {
          error: '审核失败',
          message: msg || `HTTP ${response.status}`
        }
      }

      return {
        success: true,
        student: withClientId(response.data)
      }
    }

    if (action === 'reject') {
      const response = await axios.post(
        `${baseUrl}/api/students/${encodeURIComponent(studentId)}/reject`,
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
        return {
          error: '审核失败',
          message: msg || `HTTP ${response.status}`
        }
      }

      return {
        success: true,
        student: withClientId(response.data && response.data.student),
        message: response.data && response.data.message
      }
    }

    return {
      error: '参数错误',
      message: '操作类型必须是 approve 或 reject'
    }
  } catch (err) {
    return {
      error: '审核失败',
      message: err.message || '请求网页系统失败'
    }
  }
}
