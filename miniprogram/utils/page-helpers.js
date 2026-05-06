/**
 * 页面辅助工具函数。
 *
 * 提供小程序页面常用的工具函数：
 * - parseIsAdmin: 解析管理员标识（兼容多种格式）
 * - hasAdminAccess: 判断当前用户是否有管理员权限
 * - formatDateTime: 格式化日期时间字符串为 YYYY-MM-DD HH:mm
 */

/** 解析管理员标识，兼容 boolean/number/string 多种格式 */
function parseIsAdmin(raw) {
  if (raw === true || raw === 1) return true
  const text = String(raw || '').trim().toLowerCase()
  return text === 'true' || text === '1'
}

/**
 * 判断当前用户是否有管理员权限。
 * 同时检查 globalData 和本地存储，任一为 true 即认为有权限。
 * @returns {boolean}
 */
function hasAdminAccess() {
  const app = getApp()
  const fromGlobal = !!(app && app.globalData && app.globalData.isAdmin)
  const fromStorage = parseIsAdmin(wx.getStorageSync('is_admin'))
  return fromGlobal || fromStorage
}

/**
 * 格式化日期时间字符串为 YYYY-MM-DD HH:mm 格式。
 *
 * 统一按北京时间（UTC+8）输出。
 * 后端 SQLite 默认写入本地时间字符串（无时区标记），这类值直接按原始时钟时间展示；
 * 带有明确时区的 ISO 字符串则转换为北京时间。
 * 支持多种输入格式（ISO 8601、空格分隔等），无法解析时返回 '-'。
 *
 * @param {string} value - 日期时间字符串
 * @returns {string} 格式化字符串或 '-'
 */
function formatDateTime(value) {
  if (!value) return '-'

  const raw = String(value).trim()
  const parts = parseDateTimeParts(raw)
  if (!parts) return '-'

  const { year, month, day, hour, minute } = parts
  return `${year}-${month}-${day} ${hour}:${minute}`
}

function parseDateTimeParts(raw = '') {
  const text = String(raw || '').trim()
  if (!text) return null

  const localTimeMatch = text.match(
    /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.\d{1,6})?)?)?$/
  )
  if (localTimeMatch) {
    const [, year, month, day, hour = '00', minute = '00'] = localTimeMatch
    return { year, month, day, hour, minute }
  }

  let parsed = Date.parse(text)
  if (Number.isNaN(parsed)) {
    parsed = Date.parse(text.replace(' ', 'T'))
  }
  if (Number.isNaN(parsed)) return null

  const beijingDate = new Date(parsed + (8 * 60 * 60 * 1000))
  return {
    year: String(beijingDate.getUTCFullYear()),
    month: String(beijingDate.getUTCMonth() + 1).padStart(2, '0'),
    day: String(beijingDate.getUTCDate()).padStart(2, '0'),
    hour: String(beijingDate.getUTCHours()).padStart(2, '0'),
    minute: String(beijingDate.getUTCMinutes()).padStart(2, '0')
  }
}

module.exports = {
  parseIsAdmin,
  hasAdminAccess,
  formatDateTime
}
