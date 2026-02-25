// cloudfunctions/exportExcel/index.js
const cloud = require('wx-server-sdk')
const xlsx = require('node-xlsx')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 导出Excel云函数
 * 将学员数据导出为Excel文件
 */
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const { status = '', company = '', training_type = '' } = event

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
        message: '只有管理员可以导出数据'
      }
    }

    // 构建查询条件
    const where = {}
    if (status) where.status = status
    if (training_type) where.training_type = training_type
    if (company) {
      where.company = db.RegExp({
        regexp: company,
        options: 'i'
      })
    }

    // 查询学员数据
    const result = await db.collection('students')
      .where(where)
      .orderBy('created_at', 'desc')
      .limit(1000) // 限制最多导出1000条
      .get()

    if (result.data.length === 0) {
      return {
        error: '无数据',
        message: '没有符合条件的学员数据'
      }
    }

    // 准备Excel数据
    const headers = [
      '姓名', '性别', '文化程度', '毕业学校', '所学专业',
      '身份证号', '手机号', '单位名称', '单位地址',
      '培训类型', '作业类别', '操作项目', '项目代码',
      '状态', '提交时间'
    ]

    const rows = result.data.map(student => [
      student.name,
      student.gender,
      student.education,
      student.school || '',
      student.major || '',
      student.id_card,
      student.phone,
      student.company,
      student.company_address,
      student.training_type === 'special_operation' ? '特种作业' : '特种设备',
      student.job_category,
      student.exam_project || '',
      student.project_code || '',
      student.status === 'unreviewed' ? '未审核' : student.status === 'reviewed' ? '已审核' : '已驳回',
      formatDate(student.created_at)
    ])

    const data = [headers, ...rows]

    // 生成Excel文件
    const buffer = xlsx.build([{
      name: '学员信息',
      data: data,
      options: {}
    }])

    // 上传到云存储
    const timestamp = Date.now()
    const cloudPath = `exports/学员信息_${timestamp}.xlsx`

    const uploadResult = await cloud.uploadFile({
      cloudPath: cloudPath,
      fileContent: buffer
    })

    // 生成临时下载链接
    const tempFileResult = await cloud.getTempFileURL({
      fileList: [{
        fileID: uploadResult.fileID,
        maxAge: 3600 // 1小时有效期
      }]
    })

    return {
      success: true,
      fileID: uploadResult.fileID,
      downloadUrl: tempFileResult.fileList[0].tempFileURL,
      count: result.data.length
    }
  } catch (err) {
    console.error('导出Excel失败:', err)
    return {
      error: '导出失败',
      message: err.message
    }
  }
}

function formatDate(date) {
  if (!date) return ''
  const d = new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hour = String(d.getHours()).padStart(2, '0')
  const minute = String(d.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}
