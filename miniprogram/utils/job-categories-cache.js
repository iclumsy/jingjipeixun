/**
 * 作业类别配置缓存模块。
 *
 * 使用两级缓存策略减少网络请求：
 *   1. 内存缓存（memoryJobCategories）：最快，进程内有效
 *   2. 本地存储缓存（wx.setStorageSync）：持久化，跨页面有效
 *
 * 缓存策略:
 *   - TTL 为 5 分钟，过期后自动重新获取
 *   - 读取时先检查内存缓存，再检查本地存储
 *   - 写入时同时更新内存和本地存储
 */

const JOB_CATEGORIES_CACHE_KEY = 'job_categories_cache_v1'   // 本地存储键名（带版本号）
const JOB_CATEGORIES_CACHE_TTL_MS = 5 * 60 * 1000           // 缓存有效期 5 分钟

// 内存级缓存（进程内有效，页面切换不丢失）
let memoryJobCategories = null    // 缓存的数据
let memoryJobCategoriesAt = 0     // 缓存时间戳

function readJobCategoriesCache() {
  const now = Date.now()
  if (memoryJobCategories && now - memoryJobCategoriesAt < JOB_CATEGORIES_CACHE_TTL_MS) {
    return memoryJobCategories
  }

  const cached = wx.getStorageSync(JOB_CATEGORIES_CACHE_KEY)
  if (!cached || !cached.data || !cached.updatedAt) {
    return null
  }

  const updatedAt = Number(cached.updatedAt)
  if (!Number.isFinite(updatedAt) || now - updatedAt >= JOB_CATEGORIES_CACHE_TTL_MS) {
    return null
  }

  memoryJobCategories = cached.data
  memoryJobCategoriesAt = updatedAt
  return memoryJobCategories
}

function writeJobCategoriesCache(data) {
  if (!data || typeof data !== 'object') {
    return
  }

  const updatedAt = Date.now()
  memoryJobCategories = data
  memoryJobCategoriesAt = updatedAt

  wx.setStorageSync(JOB_CATEGORIES_CACHE_KEY, {
    data,
    updatedAt
  })
}

module.exports = {
  readJobCategoriesCache,
  writeJobCategoriesCache
}
