// cloudfunctions/generateHealthCheck/index.js
const cloud = require('wx-server-sdk')
const Docxtemplater = require('docxtemplater')
const PizZip = require('pizzip')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 生成体检表云函数
 * 为N1叉车司机和G3锅炉水处理生成体检表
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
        message: '只有管理员可以生成体检表'
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
    const projectCode = student.project_code

    // 只为N1叉车司机和G3锅炉水处理生成体检表
    if (projectCode !== 'N1' && projectCode !== 'G3') {
      return {
        success: false,
        message: '该项目不需要生成体检表'
      }
    }

    // 确定模板文件
    const templateName = projectCode === 'N1' ? '叉车司机体检表.docx' : '锅炉水处理体检表.docx'
    const templatePath = `templates/${templateName}`

    // 下载模板文件
    let templateBuffer
    try {
      const downloadResult = await cloud.downloadFile({
        fileID: `cloud://your-env.xxxx/${templatePath}`
      })
      templateBuffer = downloadResult.fileContent
    } catch (err) {
      console.error('下载模板失败:', err)
      return {
        error: '模板不存在',
        message: '请先上传体检表模板到云存储'
      }
    }

    // 准备数据
    const data = {
      name: student.name,
      gender: student.gender,
      id_card: student.id_card,
      phone: student.phone,
      company: student.company,
      date: formatDate(new Date())
    }

    // 生成Word文档
    const zip = new PizZip(templateBuffer)
    const doc = new Docxtemplater(zip, {
      paragraphLoop: true,
      linebreaks: true
    })

    doc.setData(data)

    try {
      doc.render()
    } catch (err) {
      console.error('渲染文档失败:', err)
      return {
        error: '生成失败',
        message: '文档模板格式错误'
      }
    }

    const buffer = doc.getZip().generate({
      type: 'nodebuffer',
      compression: 'DEFLATE'
    })

    // 上传到云存储
    const cloudPath = `students/${student.training_type}/${student.company}-${student.name}/${student.id_card}-${student.name}-体检表.docx`

    const uploadResult = await cloud.uploadFile({
      cloudPath: cloudPath,
      fileContent: buffer
    })

    // 更新学员记录
    await db.collection('students')
      .doc(student_id)
      .update({
        data: {
          training_form_path: uploadResult.fileID,
          updated_at: new Date()
        }
      })

    return {
      success: true,
      fileID: uploadResult.fileID,
      message: '体检表生成成功'
    }
  } catch (err) {
    console.error('生成体检表失败:', err)
    return {
      error: '生成失败',
      message: err.message
    }
  }
}

function formatDate(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}年${month}月${day}日`
}
