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
  },

  onShow() {
    // 更新 TabBar 选中状态
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 1
      })
    }
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
    const { student } = e.detail
    wx.navigateTo({
      url: `/pages/user/detail/detail?id=${student._id}`
    })
  },

  goToSubmit() {
    wx.switchTab({
      url: '/pages/user/submit/submit'
    })
  }
})
