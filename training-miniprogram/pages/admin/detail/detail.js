const api = require('../../../utils/api')
const { TRAINING_TYPE_LABELS } = require('../../../utils/constants')

const STATUS_TEXT_MAP = {
  unreviewed: '待审核',
  reviewed: '已通过',
  rejected: '已驳回'
}

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

Page({
  data: {
    studentId: '',
    student: null,
    downloadUrls: {},
    statusText: '-',
    trainingTypeText: '-',
    submitTimeText: '-',
    reviewTimeText: '-',
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
      const student = result.student
      if (!student) {
        throw new Error('记录不存在')
      }

      this.setData({
        student,
        downloadUrls: result.downloadUrls || {},
        statusText: STATUS_TEXT_MAP[student.status] || student.status || '-',
        trainingTypeText: TRAINING_TYPE_LABELS[student.training_type] || student.training_type || '-',
        submitTimeText: formatTime(student.created_at),
        reviewTimeText: formatTime(student.reviewed_at),
        loading: false
      })
    } catch (err) {
      console.error('加载审核详情失败:', err)
      this.setData({ loading: false })
      wx.showToast({ title: err.message || '加载失败', icon: 'none' })
    }
  },

  previewImage(e) {
    const { url } = e.currentTarget.dataset
    if (!url) return

    const urls = Object.values(this.data.downloadUrls).filter(item => !!item)
    wx.previewImage({
      current: url,
      urls
    })
  },

  async onApprove() {
    if (!this.data.student || this.data.student.status !== 'unreviewed') return

    const confirmed = await this.confirmAction('审核通过', '确认通过该记录吗？')
    if (!confirmed) return

    wx.showLoading({ title: '审核中...' })
    try {
      await api.reviewStudent(this.data.studentId, 'approve')
      wx.hideLoading()
      wx.showToast({ title: '已通过', icon: 'success' })
      await this.loadDetail()
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    }
  },

  async onReject() {
    if (!this.data.student || this.data.student.status !== 'unreviewed') return

    const confirmed = await this.confirmAction('驳回记录', '确认驳回该记录吗？')
    if (!confirmed) return

    wx.showLoading({ title: '处理中...' })
    try {
      await api.reviewStudent(this.data.studentId, 'reject')
      wx.hideLoading()
      wx.showToast({ title: '已驳回', icon: 'success' })
      await this.loadDetail()
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    }
  },

  confirmAction(title, content) {
    return new Promise(resolve => {
      wx.showModal({
        title,
        content,
        success: res => resolve(!!res.confirm),
        fail: () => resolve(false)
      })
    })
  }
})
