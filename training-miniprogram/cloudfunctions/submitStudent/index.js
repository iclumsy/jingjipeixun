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
    return
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
}

async function createOneStudent(baseUrl, student, trainingType, submitterOpenid) {
  const form = new FormData()

  const textFields = [
    'name', 'gender', 'education', 'school', 'major', 'id_card', 'phone',
    'company', 'company_address', 'job_category', 'exam_project', 'project_code'
  ]

  textFields.forEach(field => {
    form.append(field, String(student[field] || ''))
  })
  form.append('training_type', String(trainingType || 'special_operation'))
  form.append('submitter_openid', String(submitterOpenid || ''))

  const uploadedCloudFiles = []
  for (const field of FILE_FIELDS) {
    const fileID = student.files && student.files[field]
    if (!fileID) continue

    await appendCloudFileToForm(
      form,
      field,
      fileID,
      `${student.id_card || 'unknown'}-${field}`
    )

    if (String(fileID).startsWith('cloud://')) {
      uploadedCloudFiles.push(String(fileID))
    }
  }

  const response = await axios.post(`${baseUrl}/api/students`, form, {
    headers: form.getHeaders(),
    timeout: DEFAULT_TIMEOUT_MS,
    maxBodyLength: Infinity,
    maxContentLength: Infinity,
    validateStatus: () => true
  })

  if (response.status < 200 || response.status >= 300) {
    const msg = response.data && (response.data.error || response.data.message)
    throw new Error(msg || `HTTP ${response.status}`)
  }

  if (uploadedCloudFiles.length) {
    try {
      await cloud.deleteFile({
        fileList: uploadedCloudFiles
      })
    } catch (err) {
      // 临时文件删除失败不影响主流程
      console.warn('删除临时云文件失败:', err.message || err)
    }
  }

  return response.data
}

exports.main = async (event = {}) => {
  const wxContext = cloud.getWXContext()
  const syncMode = String(event.mode || event.action || '').trim().toLowerCase()
  if (syncMode === 'sync_existing' || String(event.sync_existing || '').toLowerCase() === 'true') {
    return {
      success: true,
      synced: true,
      message: '当前已直接写入网页系统，无需手动同步'
    }
  }

  const { students, training_type } = event

  if (!students || !Array.isArray(students) || students.length === 0) {
    return {
      error: '参数错误',
      message: '学员数据不能为空'
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
    const ids = []

    for (const student of students) {
      const effectiveTrainingType = training_type || student.training_type || 'special_operation'
      const result = await createOneStudent(baseUrl, student, effectiveTrainingType, wxContext.OPENID)
      ids.push(String(result.id || ''))
    }

    return {
      success: true,
      ids,
      count: ids.length
    }
  } catch (err) {
    return {
      error: '提交失败',
      message: err.message || '请求网页系统失败'
    }
  }
}
