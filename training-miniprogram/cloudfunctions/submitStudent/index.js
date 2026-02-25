// cloudfunctions/submitStudent/index.js
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 提交学员信息云函数
 * 批量插入学员记录
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const { students, training_type } = event

  if (!students || !Array.isArray(students) || students.length === 0) {
    return {
      error: '参数错误',
      message: '学员数据不能为空'
    }
  }

  try {
    const insertedIds = []
    const now = new Date()

    // 批量插入学员记录
    for (const student of students) {
      const studentData = {
        _openid: wxContext.OPENID,
        name: student.name,
        gender: student.gender,
        education: student.education,
        school: student.school || '',
        major: student.major || '',
        id_card: student.id_card,
        phone: student.phone,
        company: student.company,
        company_address: student.company_address,
        job_category: student.job_category,
        exam_project: student.exam_project || '',
        project_code: student.project_code || '',
        training_type: training_type,
        status: 'unreviewed',

        // 附件路径
        photo_path: student.files?.photo || '',
        diploma_path: student.files?.diploma || '',
        id_card_front_path: student.files?.id_card_front || '',
        id_card_back_path: student.files?.id_card_back || '',
        hukou_residence_path: student.files?.hukou_residence || '',
        hukou_personal_path: student.files?.hukou_personal || '',
        training_form_path: '',

        created_at: now,
        updated_at: now,
        reviewed_at: null,
        reviewed_by: ''
      }

      const result = await db.collection('students').add({
        data: studentData
      })

      insertedIds.push(result._id)
    }

    return {
      success: true,
      ids: insertedIds,
      count: insertedIds.length
    }
  } catch (err) {
    console.error('提交学员失败:', err)
    return {
      error: '提交失败',
      message: err.message
    }
  }
}
