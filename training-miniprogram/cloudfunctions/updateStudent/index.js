// cloudfunctions/updateStudent/index.js
const path = require('path')
const http = require('http')
const https = require('https')
const axios = require('axios')
const FormData = require('form-data')
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()
const CONFIG_COLLECTION = 'config'
const SYNC_CONFIG_DOC_ID = 'origin_system_sync'

const FILE_FIELDS = [
  'photo',
  'diploma',
  'id_card_front',
  'id_card_back',
  'hukou_residence',
  'hukou_personal'
]

const FILE_PATH_FIELD_MAP = {
  photo: 'photo_path',
  diploma: 'diploma_path',
  id_card_front: 'id_card_front_path',
  id_card_back: 'id_card_back_path',
  hukou_residence: 'hukou_residence_path',
  hukou_personal: 'hukou_personal_path'
}

const MIME_TYPE_MAP = {
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png'
}

const DEFAULT_SYNC_CONFIG = {
  enabled: false,
  base_url: '',
  submit_path: '/api/students',
  timeout_ms: 60000,
  allow_insecure_tls: false
}

const ALLOWED_UPDATE_FIELDS = [
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
  'status',
  'photo_path',
  'diploma_path',
  'id_card_front_path',
  'id_card_back_path',
  'hukou_residence_path',
  'hukou_personal_path'
]

function cleanError(err) {
  if (!err) {
    return ''
  }
  return String(err.message || err).replace(/\s+/g, ' ').trim()
}

function parseBoolean(value) {
  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (['1', 'true', 'yes', 'on'].includes(normalized)) {
      return true
    }
    if (['0', 'false', 'no', 'off'].includes(normalized)) {
      return false
    }
  }
  return undefined
}

function parseTimeout(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined
  }
  return Math.floor(parsed)
}

function readConfigObject(raw) {
  if (!raw || typeof raw !== 'object') {
    return {}
  }
  if (raw.data && typeof raw.data === 'object') {
    return raw.data
  }
  return raw
}

function pickDefinedFields(obj) {
  const source = readConfigObject(obj)
  const cleaned = {}
  Object.keys(source).forEach(key => {
    if (source[key] !== undefined) {
      cleaned[key] = source[key]
    }
  })
  return cleaned
}

function pickFirstNonEmpty(...values) {
  for (const value of values) {
    if (value === undefined || value === null) {
      continue
    }
    if (typeof value === 'string') {
      if (!value.trim()) {
        continue
      }
      return value.trim()
    }
    return value
  }
  return undefined
}

function trimSlash(value = '') {
  return String(value).trim().replace(/\/+$/, '')
}

function isHttpUrl(value) {
  return typeof value === 'string' && /^https?:\/\//i.test(value.trim())
}

function normalizePathValue(pathValue, fallbackPath) {
  const candidate = String(pathValue || fallbackPath || '').trim()
  if (!candidate) {
    return ''
  }
  return candidate.startsWith('/') ? candidate : `/${candidate}`
}

function buildTargetUrl(baseUrl, submitPath, fallbackPath) {
  const normalizedBase = trimSlash(baseUrl)
  const pathValue = normalizePathValue(submitPath, fallbackPath)

  if (!normalizedBase) {
    return ''
  }

  if (!pathValue) {
    return normalizedBase
  }

  if (normalizedBase.toLowerCase().endsWith(pathValue.toLowerCase())) {
    return normalizedBase
  }

  return `${normalizedBase}${pathValue}`
}

function getSyncConfigFromEnv() {
  return {
    enabled: parseBoolean(process.env.ORIGIN_SYSTEM_SYNC_ENABLED),
    base_url: process.env.ORIGIN_SYSTEM_BASE_URL,
    submit_path: process.env.ORIGIN_SYSTEM_SUBMIT_PATH,
    timeout_ms: parseTimeout(process.env.ORIGIN_SYSTEM_TIMEOUT_MS),
    allow_insecure_tls: parseBoolean(process.env.ORIGIN_SYSTEM_ALLOW_INSECURE_TLS)
  }
}

async function getSyncConfigFromDb() {
  try {
    const result = await db.collection(CONFIG_COLLECTION).doc(SYNC_CONFIG_DOC_ID).get()
    return readConfigObject(result.data)
  } catch (err) {
    if (err && err.errCode !== -1) {
      console.warn('读取原系统同步配置失败:', cleanError(err))
    }
    return {}
  }
}

function resolveSyncConfig(dbConfig, envConfig, eventConfig) {
  const mergedRaw = {
    ...DEFAULT_SYNC_CONFIG,
    ...pickDefinedFields(dbConfig),
    ...pickDefinedFields(envConfig),
    ...pickDefinedFields(eventConfig)
  }

  const merged = {
    enabled: pickFirstNonEmpty(
      mergedRaw.enabled,
      mergedRaw.sync_enabled,
      mergedRaw.syncEnabled
    ),
    base_url: pickFirstNonEmpty(
      mergedRaw.base_url,
      mergedRaw.baseUrl,
      mergedRaw.origin_system_base_url,
      mergedRaw.originSystemBaseUrl
    ),
    submit_path: pickFirstNonEmpty(
      mergedRaw.submit_path,
      mergedRaw.submitPath,
      mergedRaw.origin_system_submit_path,
      mergedRaw.originSystemSubmitPath
    ),
    submit_url: pickFirstNonEmpty(
      mergedRaw.submit_url,
      mergedRaw.submitUrl,
      mergedRaw.url,
      mergedRaw.origin_system_submit_url,
      mergedRaw.originSystemSubmitUrl
    ),
    timeout_ms: pickFirstNonEmpty(
      mergedRaw.timeout_ms,
      mergedRaw.timeoutMs,
      mergedRaw.origin_system_timeout_ms,
      mergedRaw.originSystemTimeoutMs
    ),
    allow_insecure_tls: pickFirstNonEmpty(
      mergedRaw.allow_insecure_tls,
      mergedRaw.allowInsecureTls,
      mergedRaw.origin_system_allow_insecure_tls,
      mergedRaw.originSystemAllowInsecureTls
    )
  }

  const enabled = parseBoolean(merged.enabled)
  const hasConfiguredTarget = Boolean(merged.base_url) || isHttpUrl(merged.submit_url)
  merged.enabled = enabled === undefined ? hasConfiguredTarget : enabled
  merged.timeout_ms = parseTimeout(merged.timeout_ms) || DEFAULT_SYNC_CONFIG.timeout_ms
  merged.allow_insecure_tls = parseBoolean(merged.allow_insecure_tls) === true

  if (isHttpUrl(merged.submit_url)) {
    merged.target_url = merged.submit_url.trim()
    return merged
  }

  if (!merged.base_url) {
    merged.enabled = false
    merged.target_url = ''
    merged.disabled_reason = '未配置原系统地址'
    return merged
  }

  merged.target_url = buildTargetUrl(
    merged.base_url,
    merged.submit_path,
    DEFAULT_SYNC_CONFIG.submit_path
  )

  if (!merged.target_url || !isHttpUrl(merged.target_url)) {
    merged.enabled = false
    merged.target_url = ''
    merged.disabled_reason = '同步地址不合法'
  }

  return merged
}

function toSingleLineString(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function truncateText(value, maxLength = 200) {
  const normalized = toSingleLineString(value)
  if (!normalized) {
    return ''
  }
  if (normalized.length <= maxLength) {
    return normalized
  }
  return `${normalized.slice(0, maxLength)}...`
}

function extractResponseErrorMessage(body, status) {
  if (!body) {
    return `HTTP ${status}`
  }

  if (typeof body === 'string') {
    return truncateText(body)
  }

  if (typeof body === 'object') {
    const primary = body.error || body.message || body.msg || body.detail
    if (primary) {
      return toSingleLineString(primary)
    }
    return truncateText(JSON.stringify(body), 240) || `HTTP ${status}`
  }

  return `HTTP ${status}`
}

function getNetworkHint(code) {
  switch (String(code || '').toUpperCase()) {
    case 'ECONNREFUSED':
      return '目标地址拒绝连接，请检查端口与防火墙'
    case 'ENOTFOUND':
      return '域名无法解析，请检查 base_url'
    case 'ETIMEDOUT':
      return '请求超时，请检查网络与服务性能'
    case 'ECONNRESET':
      return '连接被中断，请检查反向代理与网关'
    case 'DEPTH_ZERO_SELF_SIGNED_CERT':
    case 'SELF_SIGNED_CERT_IN_CHAIN':
    case 'UNABLE_TO_VERIFY_LEAF_SIGNATURE':
      return '证书校验失败，可在同步配置中开启 allow_insecure_tls'
    default:
      return ''
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

function toSyncStudentPayload(studentDoc) {
  return {
    name: studentDoc.name || '',
    gender: studentDoc.gender || '',
    education: studentDoc.education || '',
    school: studentDoc.school || '',
    major: studentDoc.major || '',
    id_card: studentDoc.id_card || '',
    phone: studentDoc.phone || '',
    company: studentDoc.company || '',
    company_address: studentDoc.company_address || '',
    job_category: studentDoc.job_category || '',
    exam_project: studentDoc.exam_project || '',
    project_code: studentDoc.project_code || '',
    files: {
      photo: studentDoc.photo_path || studentDoc.files?.photo || studentDoc.files?.photo_path || '',
      diploma: studentDoc.diploma_path || studentDoc.files?.diploma || studentDoc.files?.diploma_path || '',
      id_card_front: studentDoc.id_card_front_path || studentDoc.files?.id_card_front || studentDoc.files?.id_card_front_path || '',
      id_card_back: studentDoc.id_card_back_path || studentDoc.files?.id_card_back || studentDoc.files?.id_card_back_path || '',
      hukou_residence: studentDoc.hukou_residence_path || studentDoc.files?.hukou_residence || studentDoc.files?.hukou_residence_path || '',
      hukou_personal: studentDoc.hukou_personal_path || studentDoc.files?.hukou_personal || studentDoc.files?.hukou_personal_path || ''
    }
  }
}

async function syncStudentToOriginSystem(student, trainingType, syncConfig) {
  const form = new FormData()
  const textFields = [
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
    'project_code'
  ]

  for (const field of textFields) {
    form.append(field, String(student[field] || ''))
  }
  form.append('training_type', String(trainingType || 'special_operation'))

  for (const field of FILE_FIELDS) {
    const fileID = student.files?.[field]
    if (!fileID) {
      continue
    }
    const fallbackName = `${student.id_card || 'unknown'}-${field}`
    await appendCloudFileToForm(form, field, fileID, fallbackName)
  }

  let response
  try {
    const httpAgent = new http.Agent({ keepAlive: true })
    const httpsAgent = new https.Agent({
      keepAlive: true,
      rejectUnauthorized: !syncConfig.allow_insecure_tls
    })

    response = await axios.post(syncConfig.target_url, form, {
      headers: form.getHeaders(),
      timeout: syncConfig.timeout_ms,
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
      httpAgent,
      httpsAgent,
      validateStatus: () => true
    })
  } catch (networkErr) {
    const code = networkErr && networkErr.code ? `(${networkErr.code})` : ''
    const hint = getNetworkHint(networkErr && networkErr.code)
    const hintText = hint ? `，${hint}` : ''
    return {
      success: false,
      status: null,
      message: `同步失败: 网络异常${code}${hintText} ${cleanError(networkErr)}`.trim()
    }
  }

  if (response.status >= 200 && response.status < 300) {
    return {
      success: true,
      status: response.status,
      message: '同步成功'
    }
  }

  const errorMessage = extractResponseErrorMessage(response.data, response.status)
  return {
    success: false,
    status: response.status,
    message: `同步失败: ${errorMessage}`
  }
}

function normalizeUpdates(rawUpdates = {}) {
  const normalized = {}
  const files = rawUpdates.files && typeof rawUpdates.files === 'object' ? rawUpdates.files : {}

  FILE_FIELDS.forEach(field => {
    const byStandardKey = files[field]
    const byLegacyKey = files[`${field}_path`]
    const finalValue = byStandardKey !== undefined ? byStandardKey : byLegacyKey
    if (finalValue !== undefined) {
      normalized[FILE_PATH_FIELD_MAP[field]] = finalValue || ''
    }
  })

  Object.keys(rawUpdates).forEach(key => {
    if (key === 'files') {
      return
    }
    if (ALLOWED_UPDATE_FIELDS.includes(key)) {
      normalized[key] = rawUpdates[key]
    }
  })

  normalized.updated_at = new Date()
  return normalized
}

async function doSyncAfterResubmit(studentId, studentDoc) {
  const dbSyncConfig = await getSyncConfigFromDb()
  const envSyncConfig = getSyncConfigFromEnv()
  const syncConfig = resolveSyncConfig(dbSyncConfig, envSyncConfig, null)

  if (!syncConfig.enabled) {
    const disabledReason = syncConfig.disabled_reason || '未启用同步'
    await db.collection('students').doc(studentId).update({
      data: {
        origin_sync_enabled: false,
        origin_sync_status: 'disabled',
        origin_sync_message: disabledReason,
        origin_sync_http_status: null,
        origin_sync_target: syncConfig.target_url || '',
        origin_synced_at: null,
        updated_at: new Date()
      }
    })

    return {
      enabled: false,
      success: false,
      status: null,
      message: `未启用同步（${disabledReason}）`,
      target_url: syncConfig.target_url || '',
      disabled_reason: disabledReason
    }
  }

  let syncResult
  try {
    const syncPayload = toSyncStudentPayload(studentDoc)
    syncResult = await syncStudentToOriginSystem(syncPayload, studentDoc.training_type, syncConfig)
  } catch (err) {
    syncResult = {
      success: false,
      status: null,
      message: cleanError(err) || '同步请求异常'
    }
  }

  await db.collection('students').doc(studentId).update({
    data: {
      origin_sync_enabled: true,
      origin_sync_status: syncResult.success ? 'success' : 'failed',
      origin_sync_message: syncResult.message,
      origin_sync_http_status: syncResult.status,
      origin_sync_target: syncConfig.target_url || '',
      origin_synced_at: syncResult.success ? new Date() : null,
      updated_at: new Date()
    }
  })

  return {
    enabled: true,
    success: syncResult.success,
    status: syncResult.status,
    message: syncResult.message,
    target_url: syncConfig.target_url || ''
  }
}

/**
 * 更新学员信息云函数
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const { student_id, updates } = event

  if (!student_id || !updates || typeof updates !== 'object') {
    return {
      error: '参数错误',
      message: '学员ID和更新数据不能为空'
    }
  }

  try {
    const studentResult = await db.collection('students').doc(student_id).get()
    if (!studentResult.data) {
      return {
        error: '学员不存在',
        message: '未找到该学员信息'
      }
    }

    const student = studentResult.data

    const adminResult = await db.collection('admins')
      .where({
        openid: wxContext.OPENID,
        is_active: true
      })
      .get()

    const isAdmin = adminResult.data.length > 0
    const isOwner = student._openid === wxContext.OPENID
    if (!isAdmin && !isOwner) {
      return {
        error: '权限不足',
        message: '只能修改自己提交的学员信息'
      }
    }

    const updateData = normalizeUpdates(updates)
    await db.collection('students').doc(student_id).update({
      data: updateData
    })

    const result = await db.collection('students').doc(student_id).get()
    const updatedStudent = result.data

    let sync = null
    const shouldSync = updatedStudent.status === 'unreviewed'
    if (shouldSync) {
      sync = await doSyncAfterResubmit(student_id, updatedStudent)
      const latest = await db.collection('students').doc(student_id).get()
      return {
        success: true,
        student: latest.data,
        sync
      }
    }

    return {
      success: true,
      student: updatedStudent,
      sync
    }
  } catch (err) {
    console.error('更新学员失败:', err)
    return {
      error: '更新失败',
      message: err.message
    }
  }
}
