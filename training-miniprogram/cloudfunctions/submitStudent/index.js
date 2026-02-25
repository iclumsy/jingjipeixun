// cloudfunctions/submitStudent/index.js
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

function isHttpUrl(value) {
  return typeof value === 'string' && /^https?:\/\//i.test(value.trim())
}

function trimSlash(value = '') {
  return String(value).trim().replace(/\/+$/, '')
}

function cleanError(err) {
  if (!err) {
    return ''
  }
  return String(err.message || err).replace(/\s+/g, ' ').trim()
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

function normalizePathValue(pathValue, fallbackPath) {
  const candidate = toSingleLineString(pathValue || fallbackPath || '')
  if (!candidate) {
    return ''
  }
  return candidate.startsWith('/') ? candidate : `/${candidate}`
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

function extractResponseErrorMessage(body, status) {
  if (!body) {
    return `HTTP ${status}`
  }

  if (typeof body === 'string') {
    return truncateText(body)
  }

  if (typeof body === 'object') {
    const fieldsText = body.fields ? truncateText(JSON.stringify(body.fields), 240) : ''
    const primary = body.error || body.message || body.msg || body.detail
    if (primary) {
      return fieldsText ? `${toSingleLineString(primary)} | fields: ${fieldsText}` : toSingleLineString(primary)
    }
    return truncateText(JSON.stringify(body), 240) || `HTTP ${status}`
  }

  return `HTTP ${status}`
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

  // 兼容 base_url 已经包含完整提交路径的配置，避免重复拼接。
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
    // 文档不存在属于正常情况，直接走默认配置
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

async function isAdminUser(openid) {
  const adminResult = await db.collection('admins')
    .where({
      openid,
      is_active: true
    })
    .get()
  return adminResult.data.length > 0
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
      photo: studentDoc.photo_path || '',
      diploma: studentDoc.diploma_path || '',
      id_card_front: studentDoc.id_card_front_path || '',
      id_card_back: studentDoc.id_card_back_path || '',
      hukou_residence: studentDoc.hukou_residence_path || '',
      hukou_personal: studentDoc.hukou_personal_path || ''
    }
  }
}

async function syncExistingStudent(event, wxContext) {
  const studentId = String(event.student_id || '').trim()
  if (!studentId) {
    return {
      error: '参数错误',
      message: '学员ID不能为空'
    }
  }

  const canSync = await isAdminUser(wxContext.OPENID)
  if (!canSync) {
    return {
      error: '权限不足',
      message: '只有管理员可以手动同步'
    }
  }

  const dbSyncConfig = await getSyncConfigFromDb()
  const envSyncConfig = getSyncConfigFromEnv()
  const syncConfig = resolveSyncConfig(dbSyncConfig, envSyncConfig, event.sync_config)

  let studentResult
  try {
    studentResult = await db.collection('students').doc(studentId).get()
  } catch (err) {
    return {
      error: '学员不存在',
      message: '未找到该学员信息'
    }
  }

  const studentDoc = studentResult.data
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
      success: false,
      synced: false,
      student_id: studentId,
      message: `未启用同步（${disabledReason}）`,
      sync: {
        enabled: false,
        target_url: syncConfig.target_url || '',
        disabled_reason: disabledReason
      }
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
    success: syncResult.success,
    synced: syncResult.success,
    student_id: studentId,
    status: syncResult.status,
    message: syncResult.message,
    sync: {
      enabled: true,
      target_url: syncConfig.target_url || ''
    }
  }
}

/**
 * 提交学员信息云函数
 * 批量插入学员记录
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const { students, training_type } = event

  const syncMode = String(event.mode || event.action || '').trim().toLowerCase()
  const shouldSyncExisting = parseBoolean(event.sync_existing) === true || syncMode === 'sync_existing'

  if (shouldSyncExisting) {
    try {
      return await syncExistingStudent(event, wxContext)
    } catch (err) {
      console.error('手动同步学员失败:', err)
      return {
        error: '同步失败',
        message: err.message
      }
    }
  }

  if (!students || !Array.isArray(students) || students.length === 0) {
    return {
      error: '参数错误',
      message: '学员数据不能为空'
    }
  }

  try {
    const insertedIds = []
    const now = new Date()
    const dbSyncConfig = await getSyncConfigFromDb()
    const envSyncConfig = getSyncConfigFromEnv()
    const syncConfig = resolveSyncConfig(dbSyncConfig, envSyncConfig, event.sync_config)
    const syncSummary = {
      enabled: syncConfig.enabled,
      target_url: syncConfig.target_url || '',
      disabled_reason: syncConfig.disabled_reason || '',
      success_count: 0,
      failed_count: 0,
      skipped_count: 0,
      failures: []
    }

    // 批量插入学员记录
    for (const student of students) {
      const studentData = {
        _openid: wxContext.OPENID,
        name: student.name,
        gender: student.gender,
        education: student.education,
        school: student.school || '',
        major: student.major || '',
        id_card: student.id_card,
        phone: student.phone,
        company: student.company,
        company_address: student.company_address,
        job_category: student.job_category,
        exam_project: student.exam_project || '',
        project_code: student.project_code || '',
        training_type: training_type,
        status: 'unreviewed',

        // 附件路径
        photo_path: student.files?.photo || '',
        diploma_path: student.files?.diploma || '',
        id_card_front_path: student.files?.id_card_front || '',
        id_card_back_path: student.files?.id_card_back || '',
        hukou_residence_path: student.files?.hukou_residence || '',
        hukou_personal_path: student.files?.hukou_personal || '',
        training_form_path: '',
        origin_sync_enabled: syncConfig.enabled,
        origin_sync_status: syncConfig.enabled ? 'pending' : 'disabled',
        origin_sync_message: syncConfig.enabled ? '待同步' : (syncConfig.disabled_reason || '未启用同步'),
        origin_sync_http_status: null,
        origin_sync_target: syncConfig.target_url || '',
        origin_synced_at: null,

        created_at: now,
        updated_at: now,
        reviewed_at: null,
        reviewed_by: ''
      }

      const result = await db.collection('students').add({
        data: studentData
      })

      insertedIds.push(result._id)

      if (!syncConfig.enabled) {
        syncSummary.skipped_count += 1
        continue
      }

      let syncResult
      try {
        syncResult = await syncStudentToOriginSystem(student, training_type, syncConfig)
      } catch (syncError) {
        syncResult = {
          success: false,
          status: null,
          message: cleanError(syncError) || '同步请求异常'
        }
      }

      try {
        await db.collection('students').doc(result._id).update({
          data: {
            origin_sync_status: syncResult.success ? 'success' : 'failed',
            origin_sync_message: syncResult.message,
            origin_sync_http_status: syncResult.status,
            origin_synced_at: syncResult.success ? new Date() : null,
            updated_at: new Date()
          }
        })
      } catch (updateErr) {
        console.warn(`更新同步状态失败(${result._id}):`, cleanError(updateErr))
      }

      if (syncResult.success) {
        syncSummary.success_count += 1
      } else {
        syncSummary.failed_count += 1
        syncSummary.failures.push({
          id: result._id,
          name: student.name,
          id_card: student.id_card,
          message: syncResult.message
        })
      }
    }

    return {
      success: true,
      ids: insertedIds,
      count: insertedIds.length,
      sync: syncSummary
    }
  } catch (err) {
    console.error('提交学员失败:', err)
    return {
      error: '提交失败',
      message: err.message
    }
  }
}
