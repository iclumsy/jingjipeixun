const JOB_CATEGORIES_CACHE_KEY = 'job_categories_cache_v1'
const JOB_CATEGORIES_CACHE_TTL_MS = 5 * 60 * 1000

let memoryJobCategories = null
let memoryJobCategoriesAt = 0

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
