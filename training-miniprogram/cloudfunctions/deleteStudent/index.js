// cloudfunctions/deleteStudent/index.js
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 删除学员云函数
 * 仅管理员可调用
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const { student_id } = event

  if (!student_id) {
    return {
      error: '参数错误',
      message: '学员ID不能为空'
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
        message: '只有管理员可以删除学员'
      }
    }

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

    // 删除云存储文件
    const fileFields = [
      'photo_path',
      'diploma_path',
      'id_card_front_path',
      'id_card_back_path',
      'hukou_residence_path',
      'hukou_personal_path',
      'training_form_path'
    ]

    const filesToDelete = []
    fileFields.forEach(field => {
      if (student[field]) {
        filesToDelete.push(student[field])
      }
    })

    if (filesToDelete.length > 0) {
      try {
        await cloud.deleteFile({
          fileList: filesToDelete
        })
      } catch (err) {
        console.error('删除文件失败:', err)
        // 继续删除数据库记录
      }
    }

    // 删除数据库记录
    await db.collection('students')
      .doc(student_id)
      .remove()

    return {
      success: true,
      message: '删除成功'
    }
  } catch (err) {
    console.error('删除学员失败:', err)
    return {
      error: '删除失败',
      message: err.message
    }
  }
}
