const app = getApp()

Page({
  data: {
    loading: true,
    error: '',
    banks: [],
    isAdmin: false
  },

  onLoad() {
    this.loadSummary()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().updateTabBar()
    }
  },

  onPullDownRefresh() {
    this.loadSummary().finally(() => wx.stopPullDownRefresh())
  },

  async loadSummary() {
    this.setData({ loading: true, error: '' })
    try {
      await app.ensureLogin()
      const summary = await app.refreshPracticeSummary()
      this.setData({
        loading: false,
        banks: Array.isArray(summary && summary.banks) ? summary.banks : [],
        isAdmin: !!app.globalData.isAdmin,
        error: app.globalData.practiceError || ''
      })
    } catch (err) {
      this.setData({
        loading: false,
        error: err.message || '练习数据加载失败',
        banks: [],
        isAdmin: !!app.globalData.isAdmin
      })
    }
  },

  startMode(e) {
    const { bankId, mode, title } = e.currentTarget.dataset
    if (!bankId || !mode) return
    const bank = this.data.banks.find(item => String(item.id) === String(bankId))
    const wrongIds = bank && bank.progress && Array.isArray(bank.progress.wrongQuestionIds)
      ? bank.progress.wrongQuestionIds.join(',')
      : ''
    wx.navigateTo({
      url: `/pages/practice/session/session?bankId=${bankId}&mode=${mode}&title=${encodeURIComponent(title || '练习')}&wrongIds=${encodeURIComponent(wrongIds)}`
    })
  }
})
