// app.js
const api = require('./utils/api')

App({
  onLaunch() {
    // 自动登录（服务器直连）
    this.login()
  },

  async login() {
    try {
      wx.showLoading({ title: '登录中...' })
      const result = await api.login()

      this.globalData.userInfo = result
      this.globalData.isAdmin = !!result.isAdmin
      this.globalData.openid = result.openid || ''
      wx.setStorageSync('is_admin', !!result.isAdmin)
      wx.setStorageSync('openid', result.openid || '')

      wx.hideLoading()
      console.log('登录成功', result)

      // 根据角色跳转到对应页面
      if (result.isAdmin) {
        wx.switchTab({
          url: '/pages/admin/review/review',
          fail: () => {
            // 如果 switchTab 失败，使用 navigateTo
            wx.redirectTo({ url: '/pages/admin/review/review' })
          }
        })
      } else {
        wx.switchTab({
          url: '/pages/user/submit/submit',
          fail: () => {
            wx.redirectTo({ url: '/pages/user/submit/submit' })
          }
        })
      }
    } catch (err) {
      wx.hideLoading()
      console.error('登录失败', err)
      wx.showModal({
        title: '登录失败',
        content: err.message || '请检查网络连接或联系管理员',
        showCancel: false
      })
    }
  },

  globalData: {
    userInfo: null,
    isAdmin: false,
    openid: null,
    // 发布前请替换为你的后端 HTTPS 地址（必须在小程序后台配置 request 合法域名）
    apiBaseUrl: 'http://jingji.ctirad.fun:7777'
  }
})
