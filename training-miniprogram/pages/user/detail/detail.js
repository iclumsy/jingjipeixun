// pages/user/detail/detail.js
const api = require('../../../utils/api')
const { STATUS_LABELS, TRAINING_TYPE_LABELS } = require('../../../utils/constants')

const STATUS_HINTS = {
  unreviewed: '资料已提交，正在等待管理员审核',
  reviewed: '资料已审核通过，可在后台继续办理',
  rejected: '资料已被驳回，可修改后重新提交'
}

const ATTACHMENT_FIELDS = [
  'photo_path',
  'diploma_path',
  'id_card_front_path',
  'id_card_back_path',
  'hukou_residence_path',
  'hukou_personal_path'
]

function isSafePreviewUrl(value = '') {
  const raw = String(value || '').trim()
  if (!raw) return false
  return (
    /^https?:\/\//i.test(raw) ||
    /^wxfile:\/\//i.test(raw) ||
    /^data:image\//i.test(raw) ||
    /^\/(?!\/)/.test(raw)
  )
}

async function resolvePreviewPath(url) {
  const raw = String(url || '').trim()
  if (!raw) return ''
  return isSafePreviewUrl(raw) ? raw : ''
}

Page({
  data: {
    studentId: '',
    student: null,
    downloadUrls: {},
    previewUrls: {},
    statusText: '',
    statusHint: '',
    trainingTypeText: '',
    createTime: '',
    loading: true
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ studentId: options.id })
      this.loadDetail()
    }
  },

  async loadDetail() {
    this.setData({ loading: true })

    try {
      const result = await api.getStudentDetail(this.data.studentId)

      if (result.student) {
        const downloadUrls = result.downloadUrls || {}
        const previewUrls = await this.buildPreviewUrls(downloadUrls)

        this.setData({
          student: result.student,
          downloadUrls,
          previewUrls,
          statusText: STATUS_LABELS[result.student.status] || result.student.status,
          statusHint: STATUS_HINTS[result.student.status] || '',
          trainingTypeText: TRAINING_TYPE_LABELS[result.student.training_type] || result.student.training_type,
          createTime: this.formatTime(result.student.created_at),
          loading: false
        })
      }
    } catch (err) {
      console.error('加载详情失败:', err)
      this.setData({ loading: false })
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    }
  },

  async buildPreviewUrls(downloadUrls) {
    const previewUrls = {}
    for (const field of ATTACHMENT_FIELDS) {
      const url = downloadUrls[field]
      if (!url) continue
      try {
        previewUrls[field] = await resolvePreviewPath(url)
      } catch (err) {
        previewUrls[field] = ''
      }
    }
    return previewUrls
  },

  formatTime(time) {
    if (!time) return '-'

    const raw = String(time).trim()
    const normalized = raw.includes(' ')
      ? raw.replace(/-/g, '/')
      : raw

    let date = new Date(normalized)
    if (Number.isNaN(date.getTime()) && raw.includes(' ')) {
      date = new Date(raw.replace(' ', 'T'))
    }
    if (Number.isNaN(date.getTime())) return '-'
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')

    return `${year}-${month}-${day} ${hour}:${minute}`
  },

  previewImage(e) {
    const { url } = e.currentTarget.dataset
    const urls = Object.values(this.data.downloadUrls)
      .map(item => String(item || '').trim())
      .filter(isSafePreviewUrl)
    const current = isSafePreviewUrl(url) ? url : (urls[0] || '')

    if (!current || urls.length === 0) {
      wx.showToast({
        title: '附件地址不可用',
        icon: 'none'
      })
      return
    }

    wx.previewImage({
      urls,
      current
    })
  },

  editStudent() {
    wx.navigateTo({
      url: `/pages/user/edit/edit?id=${this.data.studentId}`,
      fail: () => {
        wx.showToast({
          title: '跳转失败，请重试',
          icon: 'none'
        })
      }
    })
  }
})
