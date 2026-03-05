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
 * 支持多种输入格式（ISO 8601、空格分隔等），
 * 无法解析时返回 '-'。
 *
 * @param {string} value - 日期时间字符串
 * @returns {string} 格式化字符串或 '-'
 */
function formatDateTime(value) {
  if (!value) return '-'

  const raw = String(value).trim()
  const normalized = raw.includes(' ')
    ? raw.replace(/-/g, '/')
    : raw

  let date = new Date(normalized)
  if (Number.isNaN(date.getTime()) && raw.includes(' ')) {
    date = new Date(raw.replace(' ', 'T'))
  }
  if (Number.isNaN(date.getTime())) return '-'

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

module.exports = {
  parseIsAdmin,
  hasAdminAccess,
  formatDateTime
}
