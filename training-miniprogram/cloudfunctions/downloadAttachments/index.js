const axios = require('axios')
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})
const db = cloud.database()
const CONFIG_COLLECTION = 'config'
const BASE_URL_CONFIG_DOC_ID = 'origin_system_sync'

const DEFAULT_TIMEOUT_MS = 60000

function trimSlash(value = '') {
  return String(value || '').trim().replace(/\/+$/, '')
}

async function getBaseUrl(event = {}) {
  const direct = trimSlash(event.api_base_url || event.base_url || '')
  if (direct) {
    return direct
  }

  try {
    const result = await db.collection(CONFIG_COLLECTION).doc(BASE_URL_CONFIG_DOC_ID).get()
    const raw = result && result.data ? result.data : {}
    const config = raw && typeof raw.data === 'object' ? raw.data : raw
    return trimSlash(
      (config && (config.base_url || config.baseUrl || config.origin_system_base_url || config.originSystemBaseUrl)) || ''
    )
  } catch (err) {
    return ''
  }
}

exports.main = async (event = {}) => {
  const studentId = String(event.student_id || '').trim()
  if (!studentId) {
    return {
      error: '参数错误',
      message: '学员ID不能为空'
    }
  }

  const baseUrl = await getBaseUrl(event)
  if (!baseUrl) {
    return {
      error: '配置错误',
      message: '未在云数据库 config/origin_system_sync 中配置 base_url'
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
