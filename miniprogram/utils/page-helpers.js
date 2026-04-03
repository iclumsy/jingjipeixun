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
 * 统一按北京时间（UTC+8）输出，兼容后端 SQLite 的 UTC 字符串时间。
 * 支持多种输入格式（ISO 8601、空格分隔等），无法解析时返回 '-'。
 *
 * @param {string} value - 日期时间字符串
 * @returns {string} 格式化字符串或 '-'
 */
function formatDateTime(value) {
  if (!value) return '-'

  const raw = String(value).trim()
  const utcTimestamp = parseUtcTimestamp(raw)
  if (Number.isNaN(utcTimestamp)) return '-'

  const beijingDate = new Date(utcTimestamp + (8 * 60 * 60 * 1000))

  const year = beijingDate.getUTCFullYear()
  const month = String(beijingDate.getUTCMonth() + 1).padStart(2, '0')
  const day = String(beijingDate.getUTCDate()).padStart(2, '0')
  const hour = String(beijingDate.getUTCHours()).padStart(2, '0')
  const minute = String(beijingDate.getUTCMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

function parseUtcTimestamp(raw = '') {
  const text = String(raw || '').trim()
  if (!text) return Number.NaN

  const sqliteMatch = text.match(
    /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/
  )
  if (sqliteMatch) {
    const [, year, month, day, hour = '00', minute = '00', second = '00'] = sqliteMatch
    return Date.UTC(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
      Number(second)
    )
  }

  const parsed = Date.parse(text)
  if (!Number.isNaN(parsed)) return parsed

  return Date.parse(text.replace(' ', 'T'))
}

module.exports = {
  parseIsAdmin,
  hasAdminAccess,
  formatDateTime
}
