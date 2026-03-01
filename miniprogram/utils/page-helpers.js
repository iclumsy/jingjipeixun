function parseIsAdmin(raw) {
  if (raw === true || raw === 1) return true
  const text = String(raw || '').trim().toLowerCase()
  return text === 'true' || text === '1'
}

function hasAdminAccess() {
  const app = getApp()
  const fromGlobal = !!(app && app.globalData && app.globalData.isAdmin)
  const fromStorage = parseIsAdmin(wx.getStorageSync('is_admin'))
  return fromGlobal || fromStorage
}

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
