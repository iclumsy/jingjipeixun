// pages/user/detail/detail.js
const api = require('../../../utils/api')
const { STATUS_LABELS, TRAINING_TYPE_LABELS } = require('../../../utils/constants')

const STATUS_HINTS = {
  unreviewed: '资料已提交，正在等待管理员审核',
  reviewed: '资料已审核通过，可在后台继续办理',
  rejected: '资料已被驳回，可修改后重新提交'
}

Page({
  data: {
    studentId: '',
    student: null,
    downloadUrls: {},
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
        this.setData({
          student: result.student,
          downloadUrls: result.downloadUrls || {},
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
    const urls = Object.values(this.data.downloadUrls).filter(u => u)

    wx.previewImage({
      urls: urls,
      current: url
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
