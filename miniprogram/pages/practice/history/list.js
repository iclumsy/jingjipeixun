const api = require('../../../utils/api')

Page({
  data: {
    loading: true,
    bankId: null,
    bankTitle: '',
    list: []
  },

  onLoad(options) {
    const bankId = Number(options.bankId || 0)
    const bankTitle = decodeURIComponent(options.title || '真题练习')
    this.setData({ bankId, bankTitle })
    this.loadHistory()
  },

  onPullDownRefresh() {
    this.loadHistory().finally(() => wx.stopPullDownRefresh())
  },

  async loadHistory() {
    this.setData({ loading: true })
    try {
      const res = await api.getExamHistory(this.data.bankId)
      if (res && res.success) {
        const formatted = (res.list || []).map(item => {
          const dur = item.duration_seconds || 0
          const min = Math.floor(dur / 60)
          const sec = dur % 60
          const durationText = min > 0 ? `${min}分${sec}秒` : `${sec}秒`
          
          let dateText = item.created_at || ''
          if (dateText.length > 16) {
            dateText = dateText.substring(0, 16)
          }
          
          return {
            ...item,
            durationText,
            dateText
          }
        })
        this.setData({ list: formatted })
      }
    } catch (err) {
      wx.showToast({ title: err.message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  viewDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({
      url: `/pages/practice/history/detail?recordId=${id}`
    })
  }
})
