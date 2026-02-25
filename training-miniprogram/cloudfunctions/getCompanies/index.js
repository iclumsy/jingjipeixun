// cloudfunctions/getCompanies/index.js
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 获取公司列表云函数
 * 返回去重后的公司名称列表
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const { status = '', training_type = '' } = event

  try {
    // 构建查询条件
    const where = {}

    if (status) {
      where.status = status
    }

    if (training_type) {
      where.training_type = training_type
    }

    // 查询管理员权限
    const adminResult = await db.collection('admins')
      .where({
        openid: wxContext.OPENID,
        is_active: true
      })
      .get()

    const isAdmin = adminResult.data.length > 0

    // 非管理员只返回自己提交记录里的公司
    if (!isAdmin) {
      where._openid = wxContext.OPENID
    }

    // 查询所有学员
    const result = await db.collection('students')
      .where(where)
      .field({
        company: true
      })
      .get()

    // 去重
    const companies = [...new Set(result.data.map(item => item.company).filter(c => c))]

    return {
      companies: companies.sort()
    }
  } catch (err) {
    console.error('获取公司列表失败:', err)
    return {
      error: '查询失败',
      message: err.message
    }
  }
}
