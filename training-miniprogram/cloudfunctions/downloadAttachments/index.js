// cloudfunctions/downloadAttachments/index.js
const cloud = require('wx-server-sdk')
const JSZip = require('jszip')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

/**
 * 打包下载附件云函数
 * 将学员的所有附件打包为ZIP文件
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
        message: '只有管理员可以下载附件'
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

    // 检查学员状态
    if (student.status !== 'reviewed') {
      return {
        error: '状态错误',
        message: '只能下载已审核学员的附件'
      }
    }

    // 收集所有附件
    const fileFields = [
      { field: 'photo_path', name: '个人照片.jpg' },
      { field: 'diploma_path', name: '学历证书.jpg' },
      { field: 'id_card_front_path', name: '身份证正面.jpg' },
      { field: 'id_card_back_path', name: '身份证反面.jpg' },
      { field: 'hukou_residence_path', name: '户口本户籍页.jpg' },
      { field: 'hukou_personal_path', name: '户口本个人页.jpg' },
      { field: 'training_form_path', name: '体检表.docx' }
    ]

    const zip = new JSZip()
    let fileCount = 0

    // 下载并添加文件到ZIP
    for (const fileInfo of fileFields) {
      const fileID = student[fileInfo.field]
      if (!fileID) continue

      try {
        const downloadResult = await cloud.downloadFile({
          fileID: fileID
        })

        const fileName = `${student.id_card}-${student.name}-${fileInfo.name}`
        zip.file(fileName, downloadResult.fileContent)
        fileCount++
      } catch (err) {
        console.error(`下载文件 ${fileInfo.field} 失败:`, err)
        // 继续处理其他文件
      }
    }

    if (fileCount === 0) {
      return {
        error: '无附件',
        message: '该学员没有可下载的附件'
      }
    }

    // 生成ZIP文件
    const zipBuffer = await zip.generateAsync({
      type: 'nodebuffer',
      compression: 'DEFLATE',
      compressionOptions: {
        level: 9
      }
    })

    // 上传到云存储
    const timestamp = Date.now()
    const cloudPath = `temp/attachments_${student.id_card}_${timestamp}.zip`

    const uploadResult = await cloud.uploadFile({
      cloudPath: cloudPath,
      fileContent: zipBuffer
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
      fileCount: fileCount
    }
  } catch (err) {
    console.error('打包附件失败:', err)
    return {
      error: '打包失败',
      message: err.message
    }
  }
}
