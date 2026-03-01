// cloudfunctions/login/index.js
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 用户登录云函数
 * 获取用户 openid 并判断是否为管理员
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const openid = wxContext.OPENID

  try {
    // 查询是否为管理员
    const adminResult = await db.collection('admins')
      .where({
        openid: openid,
        is_active: true
      })
      .get()

    const isAdmin = adminResult.data.length > 0
    const role = isAdmin ? adminResult.data[0].role : 'user'

    return {
      openid: openid,
      isAdmin: isAdmin,
      role: role,
      appid: wxContext.APPID,
      unionid: wxContext.UNIONID
    }
  } catch (err) {
    console.error('登录失败:', err)
    return {
      error: '登录失败',
      message: err.message
    }
  }
}
