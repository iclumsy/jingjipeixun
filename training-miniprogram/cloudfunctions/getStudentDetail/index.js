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
    const response = await axios.get(`${baseUrl}/api/students/${encodeURIComponent(studentId)}`, {
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

    const student = response.data || {}
    const withClientId = {
      ...student,
      _id: student.id !== undefined && student.id !== null ? String(student.id) : ''
    }

    const fileFields = [
      'photo_path',
      'diploma_path',
      'id_card_front_path',
      'id_card_back_path',
      'hukou_residence_path',
      'hukou_personal_path',
      'training_form_path'
    ]

    const downloadUrls = {}
    fileFields.forEach(field => {
      if (student[field]) {
        downloadUrls[field] = toAbsoluteUrl(baseUrl, student[field])
      }
    })

    return {
      student: withClientId,
      downloadUrls
    }
  } catch (err) {
    return {
      error: '查询失败',
      message: err.message || '请求网页系统失败'
    }
  }
}
