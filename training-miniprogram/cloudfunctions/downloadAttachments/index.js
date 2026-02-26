const axios = require('axios')
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const DEFAULT_TIMEOUT_MS = 60000

function trimSlash(value = '') {
  return String(value || '').trim().replace(/\/+$/, '')
}

function getBaseUrl(event) {
  return trimSlash(
    event.api_base_url ||
    process.env.WEB_API_BASE_URL ||
    process.env.ORIGIN_SYSTEM_BASE_URL ||
    ''
  )
}

exports.main = async (event = {}) => {
  const studentId = String(event.student_id || '').trim()
  if (!studentId) {
    return {
      error: '参数错误',
      message: '学员ID不能为空'
    }
  }

  const baseUrl = getBaseUrl(event)
  if (!baseUrl) {
    return {
      error: '配置错误',
      message: '未配置网页系统 API 地址（WEB_API_BASE_URL）'
    }
  }

  try {
    const response = await axios.get(`${baseUrl}/api/students/${encodeURIComponent(studentId)}/attachments.zip`, {
      responseType: 'arraybuffer',
      timeout: DEFAULT_TIMEOUT_MS,
      validateStatus: () => true
    })

    if (response.status < 200 || response.status >= 300) {
      let errorMessage = `HTTP ${response.status}`
      try {
        const parsed = JSON.parse(Buffer.from(response.data).toString('utf-8'))
        errorMessage = parsed.error || parsed.message || errorMessage
      } catch (_) {
        // ignore parse error
      }
      return {
        error: '打包失败',
        message: errorMessage
      }
    }

    const timestamp = Date.now()
    const cloudPath = `temp/attachments_${studentId}_${timestamp}.zip`

    const uploadResult = await cloud.uploadFile({
      cloudPath,
      fileContent: Buffer.from(response.data)
    })

    const tempFileResult = await cloud.getTempFileURL({
      fileList: [{
        fileID: uploadResult.fileID,
        maxAge: 3600
      }]
    })

    return {
      success: true,
      fileID: uploadResult.fileID,
      downloadUrl: tempFileResult.fileList[0].tempFileURL,
      fileCount: -1
    }
  } catch (err) {
    return {
      error: '打包失败',
      message: err.message || '请求网页系统失败'
    }
  }
}
