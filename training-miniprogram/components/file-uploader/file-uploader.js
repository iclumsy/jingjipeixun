// components/file-uploader/file-uploader.js
const api = require('../../utils/api')
const { validateFileSize, validateFileType } = require('../../utils/validators')
const { MAX_FILE_SIZE } = require('../../utils/constants')

function isHttpUrl(value = '') {
  return /^http:\/\//i.test(String(value || '').trim())
}

function isHttpsUrl(value = '') {
  return /^https:\/\//i.test(String(value || '').trim())
}

function isLocalFileUrl(value = '') {
  return /^wxfile:\/\//i.test(String(value || '').trim())
}

function isDataImageUrl(value = '') {
  return /^data:image\//i.test(String(value || '').trim())
}

function isAppAssetPath(value = '') {
  return /^\/(?!\/)/.test(String(value || '').trim())
}

function normalizeFileUrl(value = '') {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (!/^https?:\/\//i.test(raw)) return raw
  try {
    return encodeURI(decodeURI(raw))
  } catch (err) {
    try {
      return encodeURI(raw)
    } catch (innerErr) {
      return raw
    }
  }
}

function withMiniToken(url) {
  const token = api.getToken()
  if (!token) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}mini_token=${encodeURIComponent(token)}`
}

function toAbsoluteServerUrl(relativePath = '') {
  const rel = String(relativePath || '').trim()
  if (!rel) return ''
  const baseUrl = api.getBaseUrl()
  if (!baseUrl) return ''
  const path = rel.startsWith('/') ? rel : `/${rel}`
  return withMiniToken(`${baseUrl}${path}`)
}

function toSafeImageSrc(value = '') {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (isHttpUrl(raw)) return ''
  if (
    isHttpsUrl(raw) ||
    isLocalFileUrl(raw) ||
    isDataImageUrl(raw) ||
    isAppAssetPath(raw)
  ) {
    return raw
  }
  if (raw.startsWith('students/')) {
    return toAbsoluteServerUrl(raw)
  }
  return ''
}

Component({
  properties: {
    fileType: {
      type: String,
      value: ''
    },
    label: {
      type: String,
      value: '上传文件'
    },
    required: {
      type: Boolean,
      value: false
    },
    compact: {
      type: Boolean,
      value: false
    },
    value: {
      type: String,
      value: '',
      observer: function(newVal) {
        const normalized = normalizeFileUrl(newVal)
        this.setData({
          fileUrl: normalized,
          previewUrl: toSafeImageSrc(normalized),
          storedPath: normalized
        })
      }
    }
  },

  data: {
    fileUrl: '',
    previewUrl: '',
    storedPath: '',
    uploading: false,
    progress: 0,
    error: ''
  },

  methods: {
    async chooseFile() {
      try {
        const res = await wx.chooseImage({
          count: 1,
          sizeType: ['compressed'],
          sourceType: ['album', 'camera']
        })
        const tempFilePath = res.tempFilePaths[0]

        const fileInfo = await wx.getFileInfo({
          filePath: tempFilePath
        })
        if (!validateFileSize(fileInfo.size, MAX_FILE_SIZE)) {
          this.setData({
            error: '文件大小不能超过10MB'
          })
          return
        }
        if (!validateFileType(tempFilePath)) {
          this.setData({
            error: '只支持JPG、PNG格式的图片'
          })
          return
        }

        this.setData({ error: '' })
        await this.uploadFile(tempFilePath)
      } catch (err) {
        console.error('选择文件失败:', err)
      }
    },

    async uploadFile(filePath) {
      this.setData({
        uploading: true,
        progress: 10,
        error: ''
      })

      const pages = getCurrentPages()
      const page = pages && pages.length ? pages[pages.length - 1] : null
      const trainingType = page && page.data
        ? page.data.trainingType || (page.data.editStudent && page.data.editStudent.training_type) || ''
        : ''
      const idCard = page && page.data
        ? (page.data.student && page.data.student.id_card) || (page.data.editStudent && page.data.editStudent.id_card) || ''
        : ''
      const name = page && page.data
        ? (page.data.student && page.data.student.name) || (page.data.editStudent && page.data.editStudent.name) || ''
        : ''
      const company = page && page.data
        ? (page.data.student && page.data.student.company) || (page.data.editStudent && page.data.editStudent.company) || ''
        : ''

      try {
        const result = await api.uploadAttachment(filePath, {
          fileType: this.data.fileType,
          trainingType,
          idCard,
          name,
          company
        })

        const storedPath = normalizeFileUrl(result.path || '')
        const previewUrl = toSafeImageSrc(storedPath) || filePath
        this.setData({
          fileUrl: storedPath,
          storedPath,
          previewUrl,
          uploading: false,
          progress: 100
        })

        this.triggerEvent('uploaded', {
          fileType: this.data.fileType,
          filePath: storedPath,
          cloudPath: storedPath,
          tempPath: filePath
        })
      } catch (err) {
        console.error('上传失败:', err)
        this.setData({
          uploading: false,
          progress: 0,
          error: err.message || '上传失败，请重试'
        })
      }
    },

    previewImage() {
      const current = toSafeImageSrc(this.data.previewUrl) || toSafeImageSrc(this.data.fileUrl)
      if (!current) {
        wx.showToast({
          title: '附件地址不可用，请稍后重试',
          icon: 'none'
        })
        return
      }

      wx.previewImage({
        urls: [current],
        current
      })
    },

    deleteFile() {
      this.setData({
        fileUrl: '',
        previewUrl: '',
        storedPath: '',
        progress: 0,
        error: ''
      })

      this.triggerEvent('deleted', {
        fileType: this.data.fileType
      })
    }
  }
})
