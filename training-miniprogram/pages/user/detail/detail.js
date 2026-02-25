// pages/user/detail/detail.js
const api = require('../../../utils/api')
const { STATUS_LABELS, TRAINING_TYPE_LABELS } = require('../../../utils/constants')

Page({
  data: {
    studentId: '',
    student: null,
    downloadUrls: {},
    statusText: '',
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

    const date = new Date(time)
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
    // 跳转到编辑页面，传递学员ID
    wx.navigateTo({
      url: `/pages/user/submit/submit?id=${this.data.studentId}`
    })
  }
})
