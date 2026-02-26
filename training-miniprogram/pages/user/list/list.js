// pages/user/list/list.js
const api = require('../../../utils/api')

Page({
  data: {
    students: [],
    page: 1,
    limit: 20,
    hasMore: true,
    loading: false
  },

  onLoad() {
    this.loadMyStudents(true)
    this._skipRefreshOnShow = true
  },

  onShow() {
    // 更新 TabBar 选中状态
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 1
      })
    }

    if (this._skipRefreshOnShow) {
      this._skipRefreshOnShow = false
      return
    }

    // 每次回到标签页都刷新，确保状态最新
    this.loadMyStudents(true)
  },

  onPullDownRefresh() {
    this.loadMyStudents(true)
  },

  onReachBottom() {
    if (!this.data.loading && this.data.hasMore) {
      this.loadMyStudents(false)
    }
  },

  async loadMyStudents(refresh = false) {
    if (this.data.loading) return

    this.setData({ loading: true })

    try {
      const page = refresh ? 1 : this.data.page
      const result = await api.getStudents({
        status: '', // 查询所有状态
        myOnly: true, // 只查询当前用户的提交
        page,
        limit: this.data.limit
      })

      const students = refresh ? result.list : [...this.data.students, ...result.list]

      this.setData({
        students,
        page: page + 1,
        hasMore: result.hasMore,
        loading: false
      })

      if (refresh) {
        wx.stopPullDownRefresh()
      }
    } catch (err) {
      console.error('加载失败:', err)
      this.setData({ loading: false })
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })

      if (refresh) {
        wx.stopPullDownRefresh()
      }
    }
  },

  onStudentTap(e) {
    const detail = e && e.detail ? e.detail : {}
    const dataset = e && e.currentTarget && e.currentTarget.dataset ? e.currentTarget.dataset : {}
    const student = detail.student || dataset.student || null
    const studentId = detail.id || (student && (student._id || student.id)) || dataset.id

    if (!studentId) {
      console.warn('onStudentTap missing student id:', { detail, dataset, student })
      wx.showToast({
        title: '学员ID缺失',
        icon: 'none'
      })
      return
    }

    const status = (student && student.status) || detail.status || dataset.status || ''

    // 仅驳回记录允许修改，其他状态只能查看
    if (status === 'rejected') {
      wx.navigateTo({
        url: `/pages/user/edit/edit?id=${studentId}`,
        fail: () => {
          wx.showToast({
            title: '跳转失败，请重试',
            icon: 'none'
          })
        }
      })
      return
    }

    wx.navigateTo({
      url: `/pages/user/detail/detail?id=${studentId}`,
      fail: () => {
        wx.showToast({
          title: '跳转失败，请重试',
          icon: 'none'
        })
      }
    })
  },

  goToSubmit() {
    wx.switchTab({
      url: '/pages/user/submit/submit'
    })
  },

  onTabReselect() {
    this.loadMyStudents(true)
  }
})
