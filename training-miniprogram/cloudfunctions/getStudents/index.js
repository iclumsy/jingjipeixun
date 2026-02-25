// cloudfunctions/getStudents/index.js
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()
const _ = db.command

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
    page = 1,
    limit = 20
  } = event

  try {
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
      where.company = db.RegExp({
        regexp: company,
        options: 'i'
      })
    }

    // 搜索（姓名、身份证、手机号）
    if (search) {
      where._or = [
        { name: db.RegExp({ regexp: search, options: 'i' }) },
        { id_card: db.RegExp({ regexp: search, options: 'i' }) },
        { phone: db.RegExp({ regexp: search, options: 'i' }) }
      ]
    }

    // 查询管理员权限
    const adminResult = await db.collection('admins')
      .where({
        openid: wxContext.OPENID,
        is_active: true
      })
      .get()

    const isAdmin = adminResult.data.length > 0

    // 如果不是管理员，只能查看自己提交的
    if (!isAdmin) {
      where._openid = wxContext.OPENID
    }

    // 分页查询
    const skip = (page - 1) * limit
    const result = await db.collection('students')
      .where(where)
      .orderBy('created_at', 'desc')
      .skip(skip)
      .limit(limit)
      .get()

    // 查询总数
    const countResult = await db.collection('students')
      .where(where)
      .count()

    return {
      list: result.data,
      total: countResult.total,
      page: page,
      limit: limit,
      hasMore: skip + result.data.length < countResult.total
    }
  } catch (err) {
    console.error('获取学员列表失败:', err)
    return {
      error: '查询失败',
      message: err.message
    }
  }
}
