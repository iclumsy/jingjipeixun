// pages/admin/batch/batch.js
const api = require('../../../utils/api')
const { STATUS_LABELS } = require('../../../utils/constants')

Page({
  data: {
    students: [],
    statusOptions: ['未审核', '已审核'],
    statusValues: ['unreviewed', 'reviewed'],
    statusIndex: 0,
    selectedCount: 0,
    allSelected: false
  },

  onLoad() {
    this.loadStudents()
  },

  async loadStudents() {
    wx.showLoading({ title: '加载中...' })

    try {
      const status = this.data.statusValues[this.data.statusIndex]
      const result = await api.getStudents({
        status,
        limit: 100
      })

      const students = result.list.map(s => ({
        ...s,
        selected: false,
        statusText: STATUS_LABELS[s.status]
      }))

      this.setData({ students })
      wx.hideLoading()
    } catch (err) {
      wx.hideLoading()
      console.error('加载失败:', err)
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    }
  },

  onStatusChange(e) {
    const index = parseInt(e.detail.value)
    this.setData({
      statusIndex: index,
      selectedCount: 0,
      allSelected: false
    })
    this.loadStudents()
  },

  onSelectAll(e) {
    const allSelected = e.detail.value.includes('all')
    const students = this.data.students.map(s => ({
      ...s,
      selected: allSelected
    }))

    this.setData({
      students,
      allSelected,
      selectedCount: allSelected ? students.length : 0
    })
  },

  onStudentSelect(e) {
    const selectedIds = e.detail.value
    const students = this.data.students.map(s => ({
      ...s,
      selected: selectedIds.includes(s._id)
    }))

    this.setData({
      students,
      selectedCount: selectedIds.length,
      allSelected: selectedIds.length === students.length
    })
  },

  async onBatchApprove() {
    const selectedIds = this.data.students
      .filter(s => s.selected)
      .map(s => s._id)

    if (selectedIds.length === 0) {
      wx.showToast({
        title: '请选择学员',
        icon: 'none'
      })
      return
    }

    const res = await wx.showModal({
      title: '确认批量审核',
      content: `确认通过 ${selectedIds.length} 名学员的审核吗？`
    })

    if (!res.confirm) return

    wx.showLoading({ title: '处理中...' })

    try {
      await api.batchReview(selectedIds, 'approve')
      wx.hideLoading()
      wx.showToast({
        title: '批量审核成功',
        icon: 'success'
      })

      setTimeout(() => {
        this.loadStudents()
      }, 1500)
    } catch (err) {
      wx.hideLoading()
      console.error('批量审核失败:', err)
      wx.showToast({
        title: '操作失败',
        icon: 'none'
      })
    }
  },

  async onBatchReject() {
    const selectedIds = this.data.students
      .filter(s => s.selected)
      .map(s => s._id)

    if (selectedIds.length === 0) {
      wx.showToast({
        title: '请选择学员',
        icon: 'none'
      })
      return
    }

    const res = await wx.showModal({
      title: '确认批量驳回',
      content: `确认驳回 ${selectedIds.length} 名学员的申请吗？`
    })

    if (!res.confirm) return

    wx.showLoading({ title: '处理中...' })

    try {
      await api.batchReview(selectedIds, 'reject')
      wx.hideLoading()
      wx.showToast({
        title: '批量驳回成功',
        icon: 'success'
      })

      setTimeout(() => {
        this.loadStudents()
      }, 1500)
    } catch (err) {
      wx.hideLoading()
      console.error('批量驳回失败:', err)
      wx.showToast({
        title: '操作失败',
        icon: 'none'
      })
    }
  }
})
