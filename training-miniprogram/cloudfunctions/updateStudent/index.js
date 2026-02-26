const path = require('path')
const axios = require('axios')
const FormData = require('form-data')
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const DEFAULT_TIMEOUT_MS = 60000
const FILE_FIELDS = [
  'photo',
  'diploma',
  'id_card_front',
  'id_card_back',
  'hukou_residence',
  'hukou_personal'
]

const MIME_TYPE_MAP = {
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png'
}

const ALLOWED_TEXT_FIELDS = [
  'name',
  'gender',
  'education',
  'school',
  'major',
  'id_card',
  'phone',
  'company',
  'company_address',
  'job_category',
  'exam_project',
  'project_code',
  'training_type',
  'status'
]

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

function buildFilename(fileID, fallbackName) {
  const rawExt = path.extname(String(fileID).split('?')[0] || '').toLowerCase()
  const ext = rawExt || '.jpg'
  return `${fallbackName}${ext}`
}

function getMimeType(filename) {
  const ext = path.extname(filename || '').toLowerCase()
  return MIME_TYPE_MAP[ext] || 'application/octet-stream'
}

async function appendCloudFileToForm(form, fieldName, fileID, fallbackName) {
  if (!fileID || !String(fileID).startsWith('cloud://')) {
    return false
  }

  const downloadResult = await cloud.downloadFile({
    fileID: String(fileID)
  })

  const fileBuffer = Buffer.isBuffer(downloadResult.fileContent)
    ? downloadResult.fileContent
    : Buffer.from(downloadResult.fileContent || '')

  if (!fileBuffer || !fileBuffer.length) {
    throw new Error(`${fieldName} 文件内容为空`)
  }

  const filename = buildFilename(fileID, fallbackName)
  form.append(fieldName, fileBuffer, {
    filename,
    contentType: getMimeType(filename)
  })

  return true
}

exports.main = async (event = {}) => {
  const studentId = String(event.student_id || '').trim()
  const updates = event.updates || {}

  if (!studentId || !updates || typeof updates !== 'object') {
    return {
      error: '参数错误',
      message: '学员ID和更新数据不能为空'
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
    const form = new FormData()

    ALLOWED_TEXT_FIELDS.forEach(field => {
      if (updates[field] !== undefined) {
        form.append(field, String(updates[field] || ''))
      }
    })

    const files = updates.files && typeof updates.files === 'object' ? updates.files : {}
    const tempCloudFiles = []

    for (const field of FILE_FIELDS) {
      const fileValue = files[field]
      if (!fileValue || !String(fileValue).startsWith('cloud://')) {
        continue
      }

      const uploaded = await appendCloudFileToForm(
        form,
        field,
        fileValue,
        `${updates.id_card || 'unknown'}-${field}`
      )

      if (uploaded) {
        tempCloudFiles.push(String(fileValue))
      }
    }

    const updateResponse = await axios.put(
      `${baseUrl}/api/students/${encodeURIComponent(studentId)}`,
      form,
      {
        headers: form.getHeaders(),
        timeout: DEFAULT_TIMEOUT_MS,
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
        validateStatus: () => true
      }
    )

    if (updateResponse.status < 200 || updateResponse.status >= 300) {
      const msg = updateResponse.data && (updateResponse.data.error || updateResponse.data.message)
      return {
        error: '更新失败',
        message: msg || `HTTP ${updateResponse.status}`
      }
    }

    if (String(updates.status || '') === 'unreviewed') {
      try {
        await axios.post(
          `${baseUrl}/api/students/${encodeURIComponent(studentId)}/reject`,
          {
            delete: false,
            status: 'unreviewed'
          },
          {
            timeout: DEFAULT_TIMEOUT_MS,
            validateStatus: () => true
          }
        )
      } catch (err) {
        console.warn('更新后回置未审核状态失败:', err.message || err)
      }
    }

    if (tempCloudFiles.length) {
      try {
        await cloud.deleteFile({
          fileList: tempCloudFiles
        })
      } catch (err) {
        console.warn('删除临时云文件失败:', err.message || err)
      }
    }

    const detailResponse = await axios.get(
      `${baseUrl}/api/students/${encodeURIComponent(studentId)}`,
      {
        timeout: DEFAULT_TIMEOUT_MS,
        validateStatus: () => true
      }
    )

    const student = detailResponse.status >= 200 && detailResponse.status < 300
      ? withClientId(detailResponse.data)
      : withClientId(updateResponse.data)

    return {
      success: true,
      student
    }
  } catch (err) {
    return {
      error: '更新失败',
      message: err.message || '请求网页系统失败'
    }
  }
}
