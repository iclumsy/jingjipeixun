const app = getApp()
const practice = require('../../../utils/practice')

Page({
  data: {
    loading: true,
    error: '',
    banks: [],
    activeBankIndex: 0,
    activeBank: null,
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
      const banks = (Array.isArray(summary && summary.banks) ? summary.banks : [])
        .map(bank => ({
          ...bank,
          studyState: practice.buildBankStudyState(bank)
        }))
      const activeBankIndex = Math.min(this.data.activeBankIndex, Math.max(banks.length - 1, 0))
      this.setData({
        loading: false,
        banks,
        activeBankIndex,
        activeBank: banks[activeBankIndex] || null,
        isAdmin: !!app.globalData.isAdmin,
        error: app.globalData.practiceError || ''
      })
    } catch (err) {
      this.setData({
        loading: false,
        error: err.message || '练习数据加载失败',
        banks: [],
        activeBank: null,
        isAdmin: !!app.globalData.isAdmin
      })
    }
  },

  selectBank(e) {
    const index = Number(e.currentTarget.dataset.index || 0)
    this.setData({
      activeBankIndex: index,
      activeBank: this.data.banks[index] || null
    })
  },

  startMode(e) {
    const bank = this.data.activeBank
    if (!bank) return
    const { mode, filter, lastQuestionId } = e.currentTarget.dataset
    const startQuestionId = practice.resolveStartQuestionId(mode, lastQuestionId, bank.studyState)
    const wrongIds = bank.studyState && Array.isArray(bank.studyState.wrongQuestionIds)
      ? bank.studyState.wrongQuestionIds.join(',')
      : ''
    if (mode === 'wrong' && !wrongIds) {
      wx.showToast({ title: '暂无错题', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: `/pages/practice/session/session?bankId=${bank.id}&mode=${mode}&filter=${filter || ''}&title=${encodeURIComponent(bank.displayName || '真题练习')}&wrongIds=${encodeURIComponent(wrongIds)}&lastQuestionId=${encodeURIComponent(startQuestionId || '')}`
    })
  }
})
