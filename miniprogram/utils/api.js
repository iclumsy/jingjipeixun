/**
 * 小程序 API 封装模块。
 *
 * 本模块封装了小程序与后端服务器的所有交互，不依赖云函数/云数据库：
 *
 * 核心功能:
 *   1. 认证流程: wx.login 获取 code -> 换取令牌 -> 存储令牌
 *   2. 学员数据: 提交/查询/详情/更新/删除
 *   3. 文件上传: 附件图片上传
 *   4. 审核操作: 通过/驳回
 *   5. 配置获取: 作业类别、公司列表
 *
 * 存储键:
 *   mini_token    - 用户认证令牌
 *   openid        - 用户 openid
 *   is_admin      - 是否为管理员
 *   api_base_url  - API 基础地址（可动态设置）
 *
 * 依赖: 微信小程序 API (wx.request, wx.uploadFile, wx.login 等)
 */

// ======================== 常量配置 ========================

/** 本地存储键名 */
const STORAGE_KEYS = {
  token: 'mini_token',       // 用户认证令牌
  openid: 'openid',          // 用户 openid
  isAdmin: 'is_admin',       // 是否为管理员
  baseUrl: 'api_base_url'    // API 基础地址
}

const DEFAULT_BASE_URL = ''       // 默认 API 地址（空时使用 globalData.apiBaseUrl）
const DEFAULT_TIMEOUT = 60000     // 请求超时时间 60 秒

/** 前端字段名 -> 数据库路径字段名映射 */
const FILE_FIELD_TO_PATH_KEY = {
  photo: 'photo_path',
  diploma: 'diploma_path',
  id_card_front: 'id_card_front_path',
  id_card_back: 'id_card_back_path',
  hukou_residence: 'hukou_residence_path',
  hukou_personal: 'hukou_personal_path'
}

/** 各培训类型允许的附件字段列表 */
const ALLOWED_ATTACHMENTS_BY_TYPE = {
  special_operation: ['diploma', 'id_card_front', 'id_card_back'],
  special_equipment: ['photo', 'diploma', 'id_card_front', 'id_card_back', 'hukou_residence', 'hukou_personal']
}

// ======================== 工具函数 ========================

/** 去除字符串末尾的斜杠 */
function trimSlash(value = '') {
  return String(value || '').trim().replace(/\/+$/, '')
}

/** 去除字符串前后空白 */
function trimText(value = '') {
  return String(value || '').trim()
}

/** 规范化培训类型，无效值回退到 'special_operation' */
function normalizeTrainingType(trainingType = '') {
  const value = trimText(trainingType)
  if (value === 'special_operation' || value === 'special_equipment') {
    return value
  }
  return 'special_operation'
}

/** 将各种值解析为布尔值（支持 '1'/'true'/'yes'/'on'） */
function parseBoolean(value) {
  if (typeof value === 'boolean') return value
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase())
}

/**
 * 获取 API 基础地址。
 * 优先级: globalData > 本地存储 > 默认值
 */
function getBaseUrl() {
  const app = getApp ? getApp() : null
  const fromGlobal = trimSlash(app && app.globalData ? app.globalData.apiBaseUrl : '')
  if (fromGlobal) return fromGlobal

  const fromStorage = trimSlash(wx.getStorageSync(STORAGE_KEYS.baseUrl) || '')
  if (fromStorage) return fromStorage

  return trimSlash(DEFAULT_BASE_URL)
}

/** 检测是否在微信开发者工具中运行（开发工具允许 HTTP） */
function isDevToolsEnv() {
  try {
    if (typeof wx.getDeviceInfo === 'function') {
      const deviceInfo = wx.getDeviceInfo() || {}
      if (String(deviceInfo.platform || '').toLowerCase() === 'devtools') {
        return true
      }
    }

    if (typeof wx.getAppBaseInfo === 'function') {
      const appBaseInfo = wx.getAppBaseInfo() || {}
      const hostEnv = String((appBaseInfo.host && appBaseInfo.host.env) || '').toLowerCase()
      if (hostEnv === 'devtools') {
        return true
      }
    }

    return false
  } catch (err) {
    return false
  }
}

/** 是否允许使用不安全的 HTTP 连接（仅开发环境） */
function allowInsecureHttp() {
  const app = getApp ? getApp() : null
  const globalFlag = app && app.globalData ? app.globalData.allowInsecureHttp : undefined
  if (globalFlag !== undefined && globalFlag !== null && globalFlag !== '') {
    return parseBoolean(globalFlag)
  }
  const fromStorage = wx.getStorageSync('allow_insecure_http')
  if (fromStorage !== undefined && fromStorage !== null && fromStorage !== '') {
    return parseBoolean(fromStorage)
  }
  return false
}

/**
 * 确保 API 基础地址已配置且合法。
 * 真机环境下不允许使用 HTTP（除非明确允许）。
 * @returns {string} 合法的基础地址
 * @throws {Error} 未配置或不合法时抛出错误
 */
function ensureBaseUrl() {
  const baseUrl = getBaseUrl()
  if (!baseUrl) {
    throw new Error('未配置服务器地址，请先在 app.js 设置 globalData.apiBaseUrl')
  }
  if (/^http:\/\//i.test(baseUrl) && !isDevToolsEnv() && !allowInsecureHttp()) {
    throw new Error('当前服务器地址是 HTTP，真机与发布版本必须使用 HTTPS 合法域名')
  }
  return baseUrl
}

/** 设置 API 基础地址（存入本地存储） */
function setBaseUrl(baseUrl) {
  const normalized = trimSlash(baseUrl)
  wx.setStorageSync(STORAGE_KEYS.baseUrl, normalized)
  return normalized
}

/** 从本地存储获取认证令牌 */
function getToken() {
  return trimText(wx.getStorageSync(STORAGE_KEYS.token) || '')
}

/** 清除所有认证相关的本地存储 */
function clearAuthStorage() {
  wx.removeStorageSync(STORAGE_KEYS.token)
  wx.removeStorageSync(STORAGE_KEYS.openid)
  wx.removeStorageSync(STORAGE_KEYS.isAdmin)
}

/** 在 URL 中附加 mini_token 查询参数（用于图片、文件等静态资源 URL） */
function withMiniToken(url) {
  const token = getToken()
  if (!token) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}mini_token=${encodeURIComponent(token)}`
}

/** 在 URL 中附加时间戳参数以破坏缓存 */
function withCacheBust(url) {
  const raw = trimText(url)
  if (!raw) return ''
  const sep = raw.includes('?') ? '&' : '?'
  return `${raw}${sep}v=${Date.now()}`
}

/** 标准化错误消息：优先从响应体提取 message/error，否则根据状态码生成 */
function normalizeErrorMessage(data, statusCode) {
  if (data && typeof data === 'object') {
    if (data.message) return String(data.message)
    if (data.error) return String(data.error)
  }
  if (statusCode === 401) return '登录已失效，请重新进入小程序'
  if (statusCode === 403) return '无权限执行该操作'
  return `请求失败（${statusCode || 'network'}）`
}

// ======================== 网络请求封装 ========================

/**
 * 发送 API 请求（JSON 格式）。
 *
 * 自动处理：
 * - 拼接基础地址
 * - 添加 Bearer 令牌认证头
 * - 解析响应和错误处理
 *
 * @param {string} path - API 路径（如 '/api/students'）
 * @param {Object} options - 请求选项 {method, data, headers, auth, json}
 * @returns {Promise<Object>} 响应数据
 */
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

/**
 * 上传文件到 API。
 *
 * 使用 wx.uploadFile 上传文件，自动添加认证令牌。
 *
 * @param {string} path - API 路径
 * @param {string} filePath - 微信临时文件路径
 * @param {Object} formData - 额外的表单数据
 * @param {Object} options - 请求选项 {name, timeout}
 * @returns {Promise<Object>} 响应数据
 */
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

// ======================== 认证流程 ========================

/**
 * 封装 wx.login() 为 Promise。
 * @returns {Promise<string>} 临时登录凭证 code
 */
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

/**
 * 执行小程序登录流程。
 *
 * 流程:
 * 1. 调用 wx.login() 获取临时 code
 * 2. 发送 code 到后端 /api/miniprogram/login
 * 3. 后端向微信服务器换取 openid
 * 4. 后端签发令牌并返回
 * 5. 小程序存储令牌和用户信息
 *
 * @returns {Promise<Object>} {openid, isAdmin, token}
 */
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

// ======================== 学员数据操作 ========================

/**
 * 标准化学员的文件字段。
 *
 * 将前端的文件临时路径转换为统一的数据结构，
 * 并过滤当前培训类型不需要的附件字段。
 *
 * @param {Object} files - 文件字段映射 {fieldName: tempFilePath}
 * @param {string} trainingType - 培训类型
 * @returns {Object} 标准化后的文件字段
 */
function normalizeStudentFiles(files = {}, trainingType = '') {
  const baseUrl = getBaseUrl()
  const normalizedType = normalizeTrainingType(trainingType)
  const allowedSet = new Set(ALLOWED_ATTACHMENTS_BY_TYPE[normalizedType] || [])

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
    if (!allowedSet.has(key)) {
      return
    }
    const value = toRelativeStudentPath(files[key] || '')
    if (value) {
      normalized[key] = value
    }
  })
  return normalized
}

/**
 * 构建学员提交的数据载荷。
 *
 * 用于将前端学员表单数据转换为后端 API 时的参数格式。
 *
 * @param {Object} student - 学员表单数据
 * @param {string} trainingType - 培训类型
 * @returns {Object} API 请求载荷
 */
function buildStudentPayload(student = {}, trainingType = '') {
  const normalizedType = normalizeTrainingType(trainingType || student.training_type || 'special_operation')
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
    training_type: normalizedType,
    files: normalizeStudentFiles(student.files || {}, normalizedType)
  }
}

/**
 * 提交学员数据（支持批量）。
 *
 * 流程:
 * 1. 先提交基本信息（JSON）
 * 2. 获取服务器返回的学员 ID
 * 3. 逐个上传附件文件
 *
 * @param {Array} students - 学员数据数组
 * @param {string} trainingType - 培训类型
 * @returns {Promise<Array>} 提交结果数组
 */
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

/**
 * 查询学员列表。
 *
 * @param {Object} params - 查询参数 {status, training_type, company, page, per_page}
 * @returns {Promise<Object>} {students, total, page, per_page, pages}
 */
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

/**
 * 将相对文件路径转换为完整的 URL（包含令牌和缓存破坏参数）。
 *
 * @param {string} pathValue - 服务器返回的相对路径
 * @returns {string} 完整的文件 URL
 */
function toAbsoluteFileUrl(pathValue) {
  const raw = trimText(pathValue)
  if (!raw) return ''
  if (/^https?:\/\//i.test(raw)) {
    return withCacheBust(withMiniToken(raw))
  }
  const baseUrl = ensureBaseUrl()
  const rel = raw.startsWith('/') ? raw : `/${raw}`
  return withCacheBust(withMiniToken(`${baseUrl}${rel}`))
}

/** 构建学员所有附件的下载 URL 映射 */
function buildDownloadUrls(student = {}) {
  const urls = {}
  Object.values(FILE_FIELD_TO_PATH_KEY).forEach(pathKey => {
    if (student[pathKey]) {
      urls[pathKey] = toAbsoluteFileUrl(student[pathKey])
    }
  })
  return urls
}

/**
 * 获取单个学员的详细信息（包含文件下载 URL）。
 *
 * @param {number|string} studentId - 学员 ID
 * @returns {Promise<Object>} 学员详情对象
 */
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

/**
 * 审核学员记录（通过/驳回）。
 *
 * @param {number|string} studentId - 学员 ID
 * @param {string} action - 操作类型: 'approve' 或 'reject'
 * @returns {Promise<Object>} 操作结果
 */
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

/**
 * 更新学员信息（部分更新）。
 *
 * @param {number|string} studentId - 学员 ID
 * @param {Object} updates - 要更新的字段
 * @returns {Promise<Object>} 操作结果
 */
async function updateStudent(studentId, updates = {}) {
  const id = encodeURIComponent(String(studentId || '').trim())
  if (!id) throw new Error('学员ID不能为空')
  const normalizedType = normalizeTrainingType(updates.training_type || '')

  const payload = {
    ...updates,
    files: normalizeStudentFiles(updates.files || {}, normalizedType)
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

/**
 * 删除学员记录及关联文件。
 *
 * @param {number|string} studentId - 学员 ID
 * @returns {Promise<Object>} 操作结果
 */
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

/**
 * 获取公司名称列表（用于筛选）。
 *
 * @param {Object} params - 查询参数 {status, training_type}
 * @returns {Promise<Array>} 公司名称数组
 */
async function getCompanies(params = {}) {
  const companies = await requestApi('/api/companies', {
    method: 'GET',
    data: params
  })
  return {
    companies: Array.isArray(companies) ? companies : []
  }
}

/**
 * 获取作业类别配置数据。
 * @returns {Promise<Object>} 作业类别配置
 */
async function getJobCategories() {
  const data = await requestApi('/api/config/job_categories', {
    method: 'GET'
  })
  return {
    success: true,
    data
  }
}

/**
 * 获取微信相关配置（如订阅消息模板ID）。
 * @returns {Promise<Object>} 微信配置对象
 */
async function getWechatConfig() {
  const data = await requestApi('/api/config/wechat', {
    method: 'GET'
  })
  return data
}

/**
 * 上传学员附件图片。
 *
 * @param {string} filePath - 微信临时文件路径
 * @param {Object} options - 上传选项 {studentId, fieldName, name, idCard, company, trainingType}
 * @returns {Promise<Object>} 上传结果
 */
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

// ======================== 导出接口 ========================
module.exports = {
  login,               // 登录
  submitStudent,        // 提交学员
  syncStudent,          // 同步/查询当前用户的学员记录
  getStudents,          // 获取学员列表
  getStudentDetail,     // 获取学员详情
  reviewStudent,        // 审核学员
  updateStudent,        // 更新学员
  deleteStudent,        // 删除学员
  getCompanies,         // 获取公司列表
  getJobCategories,     // 获取作业类别配置
  getWechatConfig,      // 获取微信配置
  uploadAttachment,     // 上传附件
  toAbsoluteFileUrl,    // 文件路径转 URL
  getBaseUrl,           // 获取 API 地址
  setBaseUrl,           // 设置 API 地址
  getToken,             // 获取令牌
  clearAuthStorage      // 清除认证存储
}
