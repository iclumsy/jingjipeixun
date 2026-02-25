// cloudfunctions/updateStudent/index.js
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 更新学员信息云函数
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const { student_id, updates } = event

  if (!student_id || !updates) {
    return {
      error: '参数错误',
      message: '学员ID和更新数据不能为空'
    }
  }

  try {
    // 查询学员信息
    const studentResult = await db.collection('students')
      .doc(student_id)
      .get()

    if (!studentResult.data) {
      return {
        error: '学员不存在',
        message: '未找到该学员信息'
      }
    }

    const student = studentResult.data

    // 检查权限：管理员或本人
    const adminResult = await db.collection('admins')
      .where({
        openid: wxContext.OPENID,
        is_active: true
      })
      .get()

    const isAdmin = adminResult.data.length > 0
    const isOwner = student._openid === wxContext.OPENID

    if (!isAdmin && !isOwner) {
      return {
        error: '权限不足',
        message: '只能修改自己提交的学员信息'
      }
    }

    // 更新学员信息
    const updateData = {
      ...updates,
      updated_at: new Date()
    }

    await db.collection('students')
      .doc(student_id)
      .update({
        data: updateData
      })

    // 返回更新后的学员信息
    const result = await db.collection('students')
      .doc(student_id)
      .get()

    return {
      success: true,
      student: result.data
    }
  } catch (err) {
    console.error('更新学员失败:', err)
    return {
      error: '更新失败',
      message: err.message
    }
  }
}
