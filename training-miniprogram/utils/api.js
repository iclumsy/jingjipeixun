// utils/api.js
// 服务器直连 API 封装（不依赖云函数/云数据库）

const STORAGE_KEYS = {
  token: 'mini_token',
  openid: 'openid',
  isAdmin: 'is_admin',
  baseUrl: 'api_base_url'
}

const DEFAULT_BASE_URL = ''
const DEFAULT_TIMEOUT = 60000

const FILE_FIELD_TO_PATH_KEY = {
  photo: 'photo_path',
  diploma: 'diploma_path',
  id_card_front: 'id_card_front_path',
  id_card_back: 'id_card_back_path',
  hukou_residence: 'hukou_residence_path',
  hukou_personal: 'hukou_personal_path'
}

function trimSlash(value = '') {
  return String(value || '').trim().replace(/\/+$/, '')
}

function trimText(value = '') {
  return String(value || '').trim()
}

function getBaseUrl() {
  const app = getApp ? getApp() : null
  const fromGlobal = trimSlash(app && app.globalData ? app.globalData.apiBaseUrl : '')
  if (fromGlobal) return fromGlobal

  const fromStorage = trimSlash(wx.getStorageSync(STORAGE_KEYS.baseUrl) || '')
  if (fromStorage) return fromStorage

  return trimSlash(DEFAULT_BASE_URL)
}

function isDevToolsEnv() {
  try {
    const info = wx.getSystemInfoSync()
    return String(info.platform || '').toLowerCase() === 'devtools'
  } catch (err) {
    return false
  }
}

function ensureBaseUrl() {
  const baseUrl = getBaseUrl()
  if (!baseUrl) {
    throw new Error('未配置服务器地址，请先在 app.js 设置 globalData.apiBaseUrl')
  }
  if (/^http:\/\//i.test(baseUrl) && !isDevToolsEnv()) {
    throw new Error('当前服务器地址是 HTTP，真机与发布版本必须使用 HTTPS 合法域名')
  }
  return baseUrl
}

function setBaseUrl(baseUrl) {
  const normalized = trimSlash(baseUrl)
  wx.setStorageSync(STORAGE_KEYS.baseUrl, normalized)
  return normalized
}

function getToken() {
  return trimText(wx.getStorageSync(STORAGE_KEYS.token) || '')
}

function clearAuthStorage() {
  wx.removeStorageSync(STORAGE_KEYS.token)
  wx.removeStorageSync(STORAGE_KEYS.openid)
  wx.removeStorageSync(STORAGE_KEYS.isAdmin)
}

function withMiniToken(url) {
  const token = getToken()
  if (!token) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}mini_token=${encodeURIComponent(token)}`
}

function normalizeErrorMessage(data, statusCode) {
  if (data && typeof data === 'object') {
    if (data.message) return String(data.message)
    if (data.error) return String(data.error)
  }
  if (statusCode === 401) return '登录已失效，请重新进入小程序'
  if (statusCode === 403) return '无权限执行该操作'
  return `请求失败（${statusCode || 'network'}）`
}

function requestApi(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const baseUrl = ensureBaseUrl()
  const token = options.auth === false ? '' : getToken()
  const url = `${baseUrl}${path}`

  const headers = {
    ...(options.headers || {})
  }
  if (options.json !== false) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json'
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
    headers['X-Mini-Token'] = token
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method,
      data: options.data,
      header: headers,
      timeout: options.timeout || DEFAULT_TIMEOUT,
      success: res => {
        const { statusCode, data } = res
        if (statusCode >= 200 && statusCode < 300) {
          resolve(data)
          return
        }
        const error = new Error(normalizeErrorMessage(data, statusCode))
        error.code = statusCode
        error.response = data
        reject(error)
      },
      fail: err => {
        const error = new Error((err && err.errMsg) || '网络请求失败')
        error.code = 0
        reject(error)
      }
    })
  })
}

function uploadFileApi(path, filePath, formData = {}, options = {}) {
  const baseUrl = ensureBaseUrl()
  const token = options.auth === false ? '' : getToken()
  const url = `${baseUrl}${path}`
  const headers = {
    ...(options.headers || {})
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
    headers['X-Mini-Token'] = token
  }

  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url,
      filePath,
      name: options.name || 'file',
      formData,
      header: headers,
      timeout: options.timeout || DEFAULT_TIMEOUT,
      success: res => {
        const statusCode = res.statusCode || 0
        let data = {}
        try {
          data = JSON.parse(res.data || '{}')
        } catch (err) {
          data = {}
        }
        if (statusCode >= 200 && statusCode < 300) {
          resolve(data)
          return
        }
        const error = new Error(normalizeErrorMessage(data, statusCode))
        error.code = statusCode
        error.response = data
        reject(error)
      },
      fail: err => {
        const error = new Error((err && err.errMsg) || '文件上传失败')
        error.code = 0
        reject(error)
      }
    })
  })
}

function wxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: res => {
        if (!res || !res.code) {
          reject(new Error('微信登录 code 获取失败'))
          return
        }
        resolve(res.code)
      },
      fail: err => reject(new Error((err && err.errMsg) || '微信登录失败'))
    })
  })
}

async function login() {
  const code = await wxLogin()
  const result = await requestApi('/api/miniprogram/login', {
    method: 'POST',
    data: { code },
    auth: false
  })

  const token = trimText(result.token || '')
  const openid = trimText(result.openid || '')
  const isAdmin = !!(result.isAdmin || result.is_admin)
  if (!token || !openid) {
    throw new Error(result.message || '登录返回数据无效')
  }

  wx.setStorageSync(STORAGE_KEYS.token, token)
  wx.setStorageSync(STORAGE_KEYS.openid, openid)
  wx.setStorageSync(STORAGE_KEYS.isAdmin, isAdmin)

  return {
    token,
    openid,
    isAdmin
  }
}

function normalizeStudentFiles(files = {}) {
  const baseUrl = getBaseUrl()

  const toRelativeStudentPath = value => {
    const raw = trimText(value)
    if (!raw) return ''
    if (raw.startsWith('students/')) return raw
    if (raw.startsWith('/students/')) return raw.slice(1)
    if (!/^https?:\/\//i.test(raw)) return ''

    const stripQuery = input => String(input || '').split('#')[0].split('?')[0]
    const cleaned = stripQuery(raw)

    if (baseUrl && !cleaned.startsWith(baseUrl)) {
      return ''
    }

    const marker = '/students/'
    const idx = cleaned.indexOf(marker)
    if (idx < 0) {
      return ''
    }
    return cleaned.slice(idx + 1)
  }

  const normalized = {}
  Object.keys(FILE_FIELD_TO_PATH_KEY).forEach(key => {
    const value = toRelativeStudentPath(files[key] || '')
    if (value) {
      normalized[key] = value
    }
  })
  return normalized
}

function buildStudentPayload(student = {}, trainingType = '') {
  return {
    name: trimText(student.name),
    gender: trimText(student.gender),
    education: trimText(student.education),
    school: trimText(student.school),
    major: trimText(student.major),
    id_card: trimText(student.id_card),
    phone: trimText(student.phone),
    company: trimText(student.company),
    company_address: trimText(student.company_address),
    job_category: trimText(student.job_category),
    exam_project: trimText(student.exam_project),
    project_code: trimText(student.project_code),
    training_type: trimText(trainingType || student.training_type || 'special_operation'),
    files: normalizeStudentFiles(student.files || {})
  }
}

async function submitStudent(students, trainingType) {
  if (!Array.isArray(students) || students.length === 0) {
    throw new Error('学员数据不能为空')
  }

  const ids = []
  for (const student of students) {
    const payload = buildStudentPayload(student, trainingType)
    const result = await requestApi('/api/students', {
      method: 'POST',
      data: payload
    })
    ids.push(String(result.id || ''))
  }

  return {
    success: true,
    ids,
    count: ids.length
  }
}

function syncStudent() {
  return Promise.resolve({
    success: true,
    synced: true,
    message: '已使用直连模式，无需同步'
  })
}

function parseBoolean(value) {
  if (typeof value === 'boolean') return value
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase())
}

function parsePositiveInt(value, fallback) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback
  return Math.floor(parsed)
}

function withClientId(item) {
  return {
    ...item,
    _id: item && item.id !== undefined && item.id !== null ? String(item.id) : ''
  }
}

async function getStudents(params = {}) {
  const {
    page = 1,
    limit = 20,
    include_total = false,
    with_total = false,
    ...rest
  } = params

  const query = {
    ...rest
  }
  if (parseBoolean(rest.myOnly)) {
    query.my_only = true
  }
  delete query.myOnly

  const result = await requestApi('/api/students', {
    method: 'GET',
    data: query
  })

  let list = Array.isArray(result) ? result.map(withClientId) : []
  const pageNo = parsePositiveInt(page, 1)
  const pageSize = Math.min(parsePositiveInt(limit, 20), 100)
  const start = (pageNo - 1) * pageSize
  const end = start + pageSize
  const sliced = list.slice(start, end)
  const hasMore = end < list.length

  const response = {
    list: sliced,
    page: pageNo,
    limit: pageSize,
    hasMore
  }
  if (parseBoolean(include_total) || parseBoolean(with_total)) {
    response.total = list.length
  }
  return response
}

function toAbsoluteFileUrl(pathValue) {
  const raw = trimText(pathValue)
  if (!raw) return ''
  if (/^https?:\/\//i.test(raw)) {
    return withMiniToken(raw)
  }
  const baseUrl = ensureBaseUrl()
  const rel = raw.startsWith('/') ? raw : `/${raw}`
  return withMiniToken(`${baseUrl}${rel}`)
}

function buildDownloadUrls(student = {}) {
  const urls = {}
  Object.values(FILE_FIELD_TO_PATH_KEY).forEach(pathKey => {
    if (student[pathKey]) {
      urls[pathKey] = toAbsoluteFileUrl(student[pathKey])
    }
  })
  return urls
}

async function getStudentDetail(studentId) {
  const id = encodeURIComponent(String(studentId || '').trim())
  if (!id) {
    throw new Error('学员ID不能为空')
  }
  const student = await requestApi(`/api/students/${id}`, {
    method: 'GET'
  })
  const mapped = withClientId(student || {})
  return {
    student: mapped,
    downloadUrls: buildDownloadUrls(mapped)
  }
}

async function reviewStudent(studentId, action) {
  const id = encodeURIComponent(String(studentId || '').trim())
  if (!id || !action) {
    throw new Error('学员ID和操作类型不能为空')
  }

  if (action === 'approve') {
    const student = await requestApi(`/api/students/${id}/approve`, {
      method: 'POST',
      data: {}
    })
    return {
      success: true,
      student: withClientId(student)
    }
  }

  if (action === 'reject') {
    const result = await requestApi(`/api/students/${id}/reject`, {
      method: 'POST',
      data: {
        delete: false,
        status: 'rejected'
      }
    })
    return {
      success: true,
      student: withClientId(result.student || {}),
      message: result.message || ''
    }
  }

  throw new Error('操作类型必须是 approve 或 reject')
}

async function updateStudent(studentId, updates = {}) {
  const id = encodeURIComponent(String(studentId || '').trim())
  if (!id) throw new Error('学员ID不能为空')

  const payload = {
    ...updates,
    files: normalizeStudentFiles(updates.files || {})
  }
  const student = await requestApi(`/api/students/${id}`, {
    method: 'PUT',
    data: payload
  })
  return {
    success: true,
    student: withClientId(student)
  }
}

async function deleteStudent(studentId) {
  const id = encodeURIComponent(String(studentId || '').trim())
  if (!id) throw new Error('学员ID不能为空')

  const result = await requestApi(`/api/students/${id}/reject`, {
    method: 'POST',
    data: {
      delete: true
    }
  })
  return {
    success: true,
    message: result.message || '删除成功'
  }
}

async function getCompanies(params = {}) {
  const companies = await requestApi('/api/companies', {
    method: 'GET',
    data: params
  })
  return {
    companies: Array.isArray(companies) ? companies : []
  }
}

async function getJobCategories() {
  const data = await requestApi('/api/config/job_categories', {
    method: 'GET'
  })
  return {
    success: true,
    data
  }
}

async function uploadAttachment(filePath, options = {}) {
  const fileType = trimText(options.fileType || options.file_type)
  if (!fileType) {
    throw new Error('文件类型不能为空')
  }
  if (!filePath) {
    throw new Error('文件路径不能为空')
  }

  return uploadFileApi('/api/miniprogram/upload', filePath, {
    file_type: fileType,
    training_type: trimText(options.trainingType || options.training_type || 'special_operation'),
    id_card: trimText(options.idCard || options.id_card),
    name: trimText(options.name),
    company: trimText(options.company)
  })
}

module.exports = {
  login,
  submitStudent,
  syncStudent,
  getStudents,
  getStudentDetail,
  reviewStudent,
  updateStudent,
  deleteStudent,
  getCompanies,
  getJobCategories,
  uploadAttachment,
  getBaseUrl,
  setBaseUrl,
  getToken,
  clearAuthStorage
}
