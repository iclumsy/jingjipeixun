// cloudfunctions/getStudentDetail/index.js
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 获取学员详情云函数
 * 返回学员信息和附件临时链接
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
    // 查询学员信息
    const result = await db.collection('students')
      .doc(student_id)
      .get()

    if (!result.data) {
      return {
        error: '学员不存在',
        message: '未找到该学员信息'
      }
    }

    const student = result.data

    // 查询管理员权限
    const adminResult = await db.collection('admins')
      .where({
        openid: wxContext.OPENID,
        is_active: true
      })
      .get()

    const isAdmin = adminResult.data.length > 0

    // 非管理员只能查看自己提交的记录
    if (!isAdmin && student._openid !== wxContext.OPENID) {
      return {
        error: '权限不足',
        message: '只能查看自己提交的学员信息'
      }
    }

    // 生成附件临时下载链接
    const fileList = []
    const fileFields = [
      'photo_path',
      'diploma_path',
      'id_card_front_path',
      'id_card_back_path',
      'hukou_residence_path',
      'hukou_personal_path',
      'training_form_path'
    ]

    fileFields.forEach(field => {
      if (student[field]) {
        fileList.push({
          fileID: student[field],
          maxAge: 3600 // 1小时有效期
        })
      }
    })

    let downloadUrls = {}
    if (fileList.length > 0) {
      const tempFileResult = await cloud.getTempFileURL({
        fileList: fileList
      })

      tempFileResult.fileList.forEach(file => {
        const field = fileFields.find(f => student[f] === file.fileID)
        if (field) {
          downloadUrls[field] = file.tempFileURL
        }
      })
    }

    return {
      student: student,
      downloadUrls: downloadUrls
    }
  } catch (err) {
    console.error('获取学员详情失败:', err)
    return {
      error: '查询失败',
      message: err.message
    }
  }
}
