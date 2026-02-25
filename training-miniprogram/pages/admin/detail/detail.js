// pages/admin/detail/detail.js
const api = require('../../../utils/api')
const { STATUS_LABELS, TRAINING_TYPE_LABELS } = require('../../../utils/constants')

Page({
  data: {
    studentId: '',
    student: null,
    downloadUrls: {},
    statusText: '',
    trainingTypeText: '',
    reviewTime: '',
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
          reviewTime: this.formatTime(result.student.reviewed_at),
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

  async onApprove() {
    const res = await wx.showModal({
      title: '确认审核',
      content: '确认通过该学员的审核吗？'
    })

    if (!res.confirm) return

    wx.showLoading({ title: '审核中...' })

    try {
      await api.reviewStudent(this.data.studentId, 'approve')

      wx.hideLoading()
      wx.showToast({
        title: '审核通过',
        icon: 'success'
      })

      setTimeout(() => {
        wx.navigateBack()
      }, 1500)
    } catch (err) {
      wx.hideLoading()
      console.error('审核失败:', err)
      wx.showToast({
        title: '审核失败',
        icon: 'none'
      })
    }
  },

  async onReject() {
    const res = await wx.showModal({
      title: '确认驳回',
      content: '确认驳回该学员的申请吗？'
    })

    if (!res.confirm) return

    wx.showLoading({ title: '处理中...' })

    try {
      await api.reviewStudent(this.data.studentId, 'reject')

      wx.hideLoading()
      wx.showToast({
        title: '已驳回',
        icon: 'success'
      })

      setTimeout(() => {
        wx.navigateBack()
      }, 1500)
    } catch (err) {
      wx.hideLoading()
      console.error('驳回失败:', err)
      wx.showToast({
        title: '操作失败',
        icon: 'none'
      })
    }
  }
})
