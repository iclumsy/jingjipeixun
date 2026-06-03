Page({
  data: {
    score: 0,
    total: 0,
    correct: 0,
    durationText: '0 分钟',
    passed: false
  },

  onLoad(options = {}) {
    const score = Number(options.score || 0)
    const duration = Number(options.duration || 0)
    this.setData({
      score,
      total: Number(options.total || 0),
      correct: Number(options.correct || 0),
      durationText: `${Math.floor(duration / 60)} 分 ${duration % 60} 秒`,
      passed: score >= 70
    })
  },

  goHome() {
    wx.switchTab({ url: '/pages/practice/index/index' })
  }
})
