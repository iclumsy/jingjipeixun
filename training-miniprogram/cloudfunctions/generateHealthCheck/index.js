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

function toAbsoluteUrl(baseUrl, pathValue) {
  const raw = String(pathValue || '').trim()
  if (!raw) return ''
  if (/^https?:\/\//i.test(raw)) return raw
  if (raw.startsWith('/')) return `${baseUrl}${raw}`
  return `${baseUrl}/${raw}`
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
