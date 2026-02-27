// components/file-uploader/file-uploader.js
const { validateFileSize, validateFileType } = require('../../utils/validators')
const { MAX_FILE_SIZE } = require('../../utils/constants')
const TEMP_URL_CACHE_TTL_MS = 45 * 60 * 1000
const tempUrlCache = new Map()

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

function readTempUrlCache(fileID) {
  const cached = tempUrlCache.get(fileID)
  if (!cached) return ''
  if (cached.expireAt <= Date.now()) {
    tempUrlCache.delete(fileID)
    return ''
  }
  return cached.url
}

function writeTempUrlCache(fileID, url) {
  if (!fileID || !url) return
  tempUrlCache.set(fileID, {
    url,
    expireAt: Date.now() + TEMP_URL_CACHE_TTL_MS
  })
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
      observer: async function(newVal) {
        if (newVal) {
          // 如果是云存储路径，获取临时下载链接
          if (newVal.startsWith('cloud://')) {
            const cachedUrl = readTempUrlCache(newVal)
            if (cachedUrl) {
              this.setData({
                fileUrl: normalizeFileUrl(cachedUrl),
                cloudPath: newVal
              })
              return
            }

            try {
              const res = await wx.cloud.getTempFileURL({
                fileList: [newVal]
              })
              if (res.fileList && res.fileList.length > 0) {
                writeTempUrlCache(newVal, res.fileList[0].tempFileURL)
                this.setData({
                  fileUrl: normalizeFileUrl(res.fileList[0].tempFileURL),
                  cloudPath: newVal
                })
              }
            } catch (err) {
              console.error('获取临时链接失败:', err)
              this.setData({
                fileUrl: normalizeFileUrl(newVal),
                cloudPath: newVal
              })
            }
          } else {
            this.setData({
              fileUrl: normalizeFileUrl(newVal),
              cloudPath: newVal
            })
          }
        } else {
          this.setData({
            fileUrl: '',
            cloudPath: ''
          })
        }
      }
    }
  },

  data: {
    fileUrl: '',
    cloudPath: '',
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

        // 检查文件大小
        const fileInfo = await wx.getFileInfo({
          filePath: tempFilePath
        })

        if (!validateFileSize(fileInfo.size, MAX_FILE_SIZE)) {
          this.setData({
            error: '文件大小不能超过10MB'
          })
          return
        }

        // 检查文件类型
        if (!validateFileType(tempFilePath)) {
          this.setData({
            error: '只支持JPG、PNG格式的图片'
          })
          return
        }

        // 清除错误
        this.setData({ error: '' })

        // 如果是照片类型，可能需要裁剪
        if (this.data.fileType === 'photo') {
          // TODO: 跳转到裁剪页面
          // 暂时直接上传
          this.uploadFile(tempFilePath)
        } else {
          this.uploadFile(tempFilePath)
        }
      } catch (err) {
        console.error('选择文件失败:', err)
      }
    },

    async uploadFile(filePath) {
      this.setData({
        uploading: true,
        progress: 0
      })

      try {
        // 生成云存储路径
        const timestamp = Date.now()
        const random = Math.random().toString(36).substr(2, 9)
        const ext = filePath.substring(filePath.lastIndexOf('.'))
        const cloudPath = `temp/${this.data.fileType}_${timestamp}_${random}${ext}`

        const uploadTask = wx.cloud.uploadFile({
          cloudPath,
          filePath,
          success: res => {
            this.setData({
              fileUrl: filePath,
              cloudPath: res.fileID,
              uploading: false,
              progress: 100
            })

            // 触发上传完成事件
            this.triggerEvent('uploaded', {
              fileType: this.data.fileType,
              cloudPath: res.fileID,
              tempPath: filePath
            })
          },
          fail: err => {
            console.error('上传失败:', err)
            this.setData({
              uploading: false,
              error: '上传失败，请重试'
            })
          }
        })

        // 监听上传进度
        uploadTask.onProgressUpdate(res => {
          this.setData({
            progress: res.progress
          })
        })
      } catch (err) {
        console.error('上传失败:', err)
        this.setData({
          uploading: false,
          error: '上传失败，请重试'
        })
      }
    },

    previewImage() {
      if (this.data.fileUrl) {
        wx.previewImage({
          urls: [this.data.fileUrl],
          current: this.data.fileUrl
        })
      }
    },

    deleteFile() {
      this.setData({
        fileUrl: '',
        cloudPath: '',
        progress: 0,
        error: ''
      })

      this.triggerEvent('deleted', {
        fileType: this.data.fileType
      })
    }
  }
})
