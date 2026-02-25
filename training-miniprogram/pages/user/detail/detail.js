// pages/user/detail/detail.js
const api = require('../../../utils/api')
const { STATUS_LABELS, TRAINING_TYPE_LABELS } = require('../../../utils/constants')
const EDIT_STUDENT_ID_KEY = 'submit_edit_student_id'

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
    // submit 是 tabBar 页面，使用 switchTab 并通过本地缓存传递编辑ID
    wx.setStorageSync(EDIT_STUDENT_ID_KEY, this.data.studentId)
    wx.switchTab({
      url: '/pages/user/submit/submit',
      fail: () => {
        wx.showToast({
          title: '跳转失败，请重试',
          icon: 'none'
        })
      }
    })
  }
})
