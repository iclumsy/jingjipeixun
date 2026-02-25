// cloudfunctions/batchReview/index.js
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 批量审核云函数
 * 支持批量审核通过和驳回
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const { student_ids, action } = event

  if (!student_ids || !Array.isArray(student_ids) || student_ids.length === 0) {
    return {
      error: '参数错误',
      message: '学员ID列表不能为空'
    }
  }

  if (!action || (action !== 'approve' && action !== 'reject')) {
    return {
      error: '参数错误',
      message: '操作类型必须是 approve 或 reject'
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
        message: '只有管理员可以批量审核学员'
      }
    }

    // 批量更新学员状态
    const updateData = {
      reviewed_at: new Date(),
      reviewed_by: wxContext.OPENID,
      updated_at: new Date(),
      status: action === 'approve' ? 'reviewed' : 'rejected'
    }

    let successCount = 0
    const errors = []

    for (const studentId of student_ids) {
      try {
        await db.collection('students')
          .doc(studentId)
          .update({
            data: updateData
          })

        successCount++

        // 如果是审核通过，检查是否需要生成体检表
        if (action === 'approve') {
          try {
            const studentResult = await db.collection('students')
              .doc(studentId)
              .get()

            const student = studentResult.data
            const projectCode = student.project_code

            // N1叉车司机、G3锅炉水处理需要生成体检表
            if (projectCode === 'N1' || projectCode === 'G3') {
              await cloud.callFunction({
                name: 'generateHealthCheck',
                data: {
                  student_id: studentId
                }
              })
            }
          } catch (err) {
            console.error('生成体检表失败:', err)
            // 不影响审核流程
          }
        }
      } catch (err) {
        console.error(`审核学员 ${studentId} 失败:`, err)
        errors.push({
          studentId,
          error: err.message
        })
      }
    }

    return {
      success: true,
      successCount,
      totalCount: student_ids.length,
      errors: errors.length > 0 ? errors : undefined
    }
  } catch (err) {
    console.error('批量审核失败:', err)
    return {
      error: '批量审核失败',
      message: err.message
    }
  }
}
