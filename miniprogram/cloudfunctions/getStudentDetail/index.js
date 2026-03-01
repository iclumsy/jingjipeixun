const axios = require('axios')
const cloud = require('wx-server-sdk')
const path = require('path')
const crypto = require('crypto')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})
const db = cloud.database()
const CONFIG_COLLECTION = 'config'
const BASE_URL_CONFIG_DOC_ID = 'origin_system_sync'

const DEFAULT_TIMEOUT_MS = 60000
const PREVIEW_FILE_MAX_AGE_SEC = 3600
const PREVIEW_PROXY_PREFIX = 'origin-sync/preview'
const PROXY_CONCURRENCY = 2
const FILE_ID_CACHE_TTL_MS = 2 * 60 * 60 * 1000
const fileIdCache = new Map()

function trimSlash(value = '') {
  return String(value || '').trim().replace(/\/+$/, '')
}

function trimText(value = '') {
  return String(value || '').trim()
}

function getApiKeyFromConfig(config = {}, event = {}) {
  const direct = trimText(
    event.api_key
      || event.apiKey
      || event.origin_system_api_key
      || event.originSystemApiKey
  )
  if (direct) return direct

  return trimText(
    config.api_key
      || config.apiKey
      || config.origin_system_api_key
      || config.originSystemApiKey
  )
}

function buildApiHeaders(apiKey = '') {
  if (!apiKey) return {}
  return {
    'X-API-Key': apiKey
  }
}

async function getRemoteConfig(event = {}) {
  const directBaseUrl = trimSlash(event.api_base_url || event.base_url || '')
  const directApiKey = getApiKeyFromConfig({}, event)
  if (directBaseUrl) {
    return {
      baseUrl: directBaseUrl,
      apiKey: directApiKey
    }
  }

  try {
    const result = await db.collection(CONFIG_COLLECTION).doc(BASE_URL_CONFIG_DOC_ID).get()
    const raw = result && result.data ? result.data : {}
    const config = raw && typeof raw.data === 'object' ? raw.data : raw
    return {
      baseUrl: trimSlash(
        (config && (config.base_url || config.baseUrl || config.origin_system_base_url || config.originSystemBaseUrl)) || ''
      ),
      apiKey: getApiKeyFromConfig(config, event)
    }
  } catch (err) {
    return {
      baseUrl: '',
      apiKey: directApiKey
    }
  }
}

async function safeAxiosGet(url, config = {}) {
  try {
    return await axios.get(url, config)
  } catch (err) {
    const message = String((err && err.message) || '')
    if (/unable to verify the first certificate/i.test(message) && /^https:\/\//i.test(url)) {
      const fallbackUrl = url.replace(/^https:\/\//i, 'http://')
      return axios.get(fallbackUrl, config)
    }
    throw err
  }
}

function toAbsoluteUrl(baseUrl, pathValue) {
  const raw = String(pathValue || '').trim()
  if (!raw) return ''
  const absolute = /^https?:\/\//i.test(raw)
    ? raw
    : (raw.startsWith('/') ? `${baseUrl}${raw}` : `${baseUrl}/${raw}`)
  try {
    return encodeURI(decodeURI(absolute))
  } catch (err) {
    try {
      return encodeURI(absolute)
    } catch (innerErr) {
      return absolute
    }
  }
}

function resolveEffectiveBaseUrl(defaultBaseUrl, responseUrl = '') {
  const raw = String(responseUrl || '').trim()
  if (!raw) return defaultBaseUrl
  const idx = raw.indexOf('/api/')
  if (idx > 0) {
    return raw.slice(0, idx).replace(/\/+$/, '')
  }
  return defaultBaseUrl
}

function isCloudFileId(value = '') {
  return String(value || '').startsWith('cloud://')
}

function sanitizeSegment(value = '') {
  const normalized = String(value || '').replace(/[^a-zA-Z0-9_-]/g, '_')
  return normalized || 'unknown'
}

function getFileExtFromUrl(fileUrl = '', contentType = '') {
  const cleanUrl = String(fileUrl || '').split('?')[0]
  const urlExt = path.extname(cleanUrl).toLowerCase()
  if (urlExt) return urlExt

  const type = String(contentType || '').toLowerCase()
  if (type.includes('png')) return '.png'
  if (type.includes('jpeg') || type.includes('jpg')) return '.jpg'
  if (type.includes('webp')) return '.webp'
  if (type.includes('gif')) return '.gif'
  if (type.includes('pdf')) return '.pdf'
  return '.bin'
}

function buildProxyCloudPath(studentId, fieldName, sourceUrl, ext) {
  const hash = crypto.createHash('md5').update(String(sourceUrl || '')).digest('hex').slice(0, 16)
  return [
    PREVIEW_PROXY_PREFIX,
    sanitizeSegment(studentId),
    `${sanitizeSegment(fieldName)}_${hash}${ext}`
  ].join('/')
}

function readFileIdCache(sourceUrl) {
  const cached = fileIdCache.get(sourceUrl)
  if (!cached) return ''
  if (cached.expireAt <= Date.now()) {
    fileIdCache.delete(sourceUrl)
    return ''
  }
  return cached.fileID
}

function writeFileIdCache(sourceUrl, fileID) {
  if (!sourceUrl || !fileID) return
  fileIdCache.set(sourceUrl, {
    fileID,
    expireAt: Date.now() + FILE_ID_CACHE_TTL_MS
  })
}

async function mapWithConcurrency(items, concurrency, mapper) {
  if (!items.length) return []
  const results = new Array(items.length)
  let cursor = 0

  async function worker() {
    while (true) {
      const current = cursor
      cursor += 1
      if (current >= items.length) return
      results[current] = await mapper(items[current], current)
    }
  }

  const workerCount = Math.min(Math.max(concurrency, 1), items.length)
  await Promise.all(Array.from({ length: workerCount }, () => worker()))
  return results
}

async function proxyRemoteAttachmentToCloudFileId(sourceUrl, studentId, fieldName, apiKey) {
  if (!sourceUrl) return ''
  if (isCloudFileId(sourceUrl)) return sourceUrl

  const cachedFileID = readFileIdCache(sourceUrl)
  if (cachedFileID) return cachedFileID

  const response = await safeAxiosGet(sourceUrl, {
    headers: buildApiHeaders(apiKey),
    responseType: 'arraybuffer',
    timeout: DEFAULT_TIMEOUT_MS,
    validateStatus: () => true
  })

  if (response.status < 200 || response.status >= 300) {
    throw new Error(`下载附件失败: ${fieldName} HTTP ${response.status}`)
  }

  const fileBuffer = Buffer.from(response.data || '')
  if (!fileBuffer.length) {
    throw new Error(`下载附件失败: ${fieldName} 文件为空`)
  }

  const ext = getFileExtFromUrl(sourceUrl, response.headers && response.headers['content-type'])
  const cloudPath = buildProxyCloudPath(studentId, fieldName, sourceUrl, ext)
  const uploadResult = await cloud.uploadFile({
    cloudPath,
    fileContent: fileBuffer
  })
  const fileID = uploadResult && uploadResult.fileID ? uploadResult.fileID : ''
  if (fileID) {
    writeFileIdCache(sourceUrl, fileID)
  }
  return fileID
}

exports.main = async (event = {}) => {
  const studentId = String(event.student_id || '').trim()
  if (!studentId) {
    return {
      error: '参数错误',
      message: '学员ID不能为空'
    }
  }

  const { baseUrl, apiKey } = await getRemoteConfig(event)
  if (!baseUrl) {
    return {
      error: '配置错误',
      message: '未在云数据库 config/origin_system_sync 中配置 base_url'
    }
  }
  if (!apiKey) {
    return {
      error: '配置错误',
      message: '未在云数据库 config/origin_system_sync 中配置 api_key'
    }
  }

  try {
    const response = await safeAxiosGet(`${baseUrl}/api/students/${encodeURIComponent(studentId)}`, {
      headers: buildApiHeaders(apiKey),
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
    const effectiveBaseUrl = resolveEffectiveBaseUrl(
      baseUrl,
      response && response.config && response.config.url
    )
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

    const tasks = fileFields
      .filter(field => !!student[field])
      .map(field => ({
        field,
        sourceUrl: toAbsoluteUrl(effectiveBaseUrl, student[field])
      }))

    const proxyResults = await mapWithConcurrency(tasks, PROXY_CONCURRENCY, async task => {
      const { field, sourceUrl } = task
      try {
        const fileID = await proxyRemoteAttachmentToCloudFileId(sourceUrl, withClientId._id || studentId, field, apiKey)
        return { field, fileID }
      } catch (err) {
        console.warn(`附件中转失败 ${field}:`, err.message || err)
        return { field, fileID: '' }
      }
    })

    const fileListForTemp = proxyResults
      .map(item => item.fileID)
      .filter(Boolean)
      .map(fileID => ({ fileID, maxAge: PREVIEW_FILE_MAX_AGE_SEC }))

    const fileIdToTempUrl = {}
    if (fileListForTemp.length) {
      try {
        const tempResult = await cloud.getTempFileURL({
          fileList: fileListForTemp
        })
        ;(tempResult.fileList || []).forEach(item => {
          if (item.fileID && item.tempFileURL) {
            fileIdToTempUrl[item.fileID] = item.tempFileURL
          }
        })
      } catch (err) {
        console.warn('获取附件临时链接失败:', err.message || err)
      }
    }

    const downloadUrls = {}
    proxyResults.forEach(item => {
      if (item.fileID && fileIdToTempUrl[item.fileID]) {
        downloadUrls[item.field] = fileIdToTempUrl[item.fileID]
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
