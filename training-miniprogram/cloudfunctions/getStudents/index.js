// cloudfunctions/getStudents/index.js
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()
const ADMIN_CACHE_TTL_MS = 60 * 1000
const adminCache = new Map()

const LIST_FIELDS = {
  name: true,
  gender: true,
  education: true,
  id_card: true,
  phone: true,
  company: true,
  company_address: true,
  job_category: true,
  exam_project: true,
  project_code: true,
  training_type: true,
  status: true,
  created_at: true,
  reviewed_at: true
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
  return false
}

function parsePositiveInt(value, fallback) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback
  }
  return Math.floor(parsed)
}

async function isActiveAdmin(openid) {
  const now = Date.now()
  const cached = adminCache.get(openid)
  if (cached && cached.expireAt > now) {
    return cached.value
  }

  const adminResult = await db.collection('admins')
    .where({
      openid,
      is_active: true
    })
    .limit(1)
    .get()

  const value = adminResult.data.length > 0
  adminCache.set(openid, {
    value,
    expireAt: now + ADMIN_CACHE_TTL_MS
  })
  return value
}

/**
 * 获取学员列表云函数
 * 支持分页、筛选、搜索
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const {
    status = 'unreviewed',
    search = '',
    company = '',
    training_type = '',
    myOnly = false,
    include_total = false,
    with_total = false,
    include_full = false,
    page = 1,
    limit = 20
  } = event

  try {
    const pageNo = parsePositiveInt(page, 1)
    const pageSize = Math.min(parsePositiveInt(limit, 20), 100)
    const shouldIncludeTotal = parseBoolean(include_total) || parseBoolean(with_total)
    const includeFull = parseBoolean(include_full)

    // 构建查询条件
    const where = {}

    // 状态筛选
    if (status) {
      where.status = status
    }

    // 培训类型筛选
    if (training_type) {
      where.training_type = training_type
    }

    // 公司筛选
    if (company) {
      const companyKeyword = String(company).trim()
      if (companyKeyword) {
        where.company = companyKeyword
      }
    }

    // 搜索（姓名、身份证、手机号）
    if (search) {
      where._or = [
        { name: db.RegExp({ regexp: search, options: 'i' }) },
        { id_card: db.RegExp({ regexp: search, options: 'i' }) },
        { phone: db.RegExp({ regexp: search, options: 'i' }) }
      ]
    }

    const forceMyOnly = parseBoolean(myOnly)

    // myOnly=true 时，无论是否管理员都只查自己的提交
    // 非管理员默认也只能查看自己的提交
    if (forceMyOnly) {
      where._openid = wxContext.OPENID
    } else {
      const isAdmin = await isActiveAdmin(wxContext.OPENID)

      if (!isAdmin) {
        where._openid = wxContext.OPENID
      }
    }

    const skip = (pageNo - 1) * pageSize
    const queryLimit = shouldIncludeTotal ? pageSize : pageSize + 1
    let query = db.collection('students')
      .where(where)
      .orderBy('created_at', 'desc')
      .skip(skip)
      .limit(queryLimit)

    if (!includeFull) {
      query = query.field(LIST_FIELDS)
    }

    const queryResult = await query.get()

    let list = queryResult.data || []
    let hasMore = false

    if (list.length > pageSize) {
      hasMore = true
      list = list.slice(0, pageSize)
    }

    let total
    if (shouldIncludeTotal) {
      const countResult = await db.collection('students')
        .where(where)
        .count()
      total = countResult.total
      hasMore = skip + list.length < total
    }

    const response = {
      list,
      page: pageNo,
      limit: pageSize,
      hasMore
    }

    if (shouldIncludeTotal) {
      response.total = total
    }

    return response
  } catch (err) {
    console.error('获取学员列表失败:', err)
    return {
      error: '查询失败',
      message: err.message
    }
  }
}
