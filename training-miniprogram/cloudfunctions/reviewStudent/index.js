// cloudfunctions/reviewStudent/index.js
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 审核学员云函数
 * 支持审核通过和驳回
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const { student_id, action } = event

  if (!student_id || !action) {
    return {
      error: '参数错误',
      message: '学员ID和操作类型不能为空'
    }
  }

  try {
    // 检查管理员权限
    const adminResult = await db.collection('admins')
      .where({
        openid: wxContext.OPENID,
        is_active: true
      })
      .get()

    if (adminResult.data.length === 0) {
      return {
        error: '权限不足',
        message: '只有管理员可以审核学员'
      }
    }

    // 更新学员状态
    const updateData = {
      reviewed_at: new Date(),
      reviewed_by: wxContext.OPENID,
      updated_at: new Date()
    }

    if (action === 'approve') {
      updateData.status = 'reviewed'
    } else if (action === 'reject') {
      updateData.status = 'rejected'
    } else {
      return {
        error: '参数错误',
        message: '操作类型必须是 approve 或 reject'
      }
    }

    await db.collection('students')
      .doc(student_id)
      .update({
        data: updateData
      })

    // 如果是审核通过，检查是否需要生成体检表
    if (action === 'approve') {
      const studentResult = await db.collection('students')
        .doc(student_id)
        .get()

      const student = studentResult.data
      const projectCode = student.project_code

      // N1叉车司机、G3锅炉水处理需要生成体检表
      if (projectCode === 'N1' || projectCode === 'G3') {
        // 调用生成体检表云函数
        try {
          await cloud.callFunction({
            name: 'generateHealthCheck',
            data: {
              student_id: student_id
            }
          })
        } catch (err) {
          console.error('生成体检表失败:', err)
          // 不影响审核流程
        }
      }
    }

    // 返回更新后的学员信息
    const result = await db.collection('students')
      .doc(student_id)
      .get()

    return {
      success: true,
      student: result.data
    }
  } catch (err) {
    console.error('审核学员失败:', err)
    return {
      error: '审核失败',
      message: err.message
    }
  }
}
