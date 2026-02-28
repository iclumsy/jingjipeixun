// app.js
const api = require('./utils/api')

App({
  onLaunch() {
    // 启动即尝试登录，页面侧根据登录状态决定跳转
    this.ensureLogin()
  },

  async ensureLogin(force = false) {
    if (!force && this._loginPromise) {
      return this._loginPromise
    }
    this._loginPromise = this.login()
      .finally(() => {
        this._loginPromise = null
      })
    return this._loginPromise
  },

  async login() {
    this.globalData.loginState = 'loading'
    this.globalData.loginError = ''
    try {
      const result = await api.login()

      this.globalData.userInfo = result
      this.globalData.isAdmin = !!result.isAdmin
      this.globalData.openid = result.openid || ''
      this.globalData.loginState = 'success'
      this.globalData.loginError = ''
      wx.setStorageSync('is_admin', !!result.isAdmin)
      wx.setStorageSync('openid', result.openid || '')

      console.log('登录成功', result)
      return result
    } catch (err) {
      console.error('登录失败', err)
      this.globalData.userInfo = null
      this.globalData.isAdmin = false
      this.globalData.openid = ''
      this.globalData.loginState = 'failed'
      this.globalData.loginError = err.message || '请检查网络连接或联系管理员'
      wx.setStorageSync('is_admin', false)
      wx.removeStorageSync('openid')
      throw err
    }
  },

  globalData: {
    userInfo: null,
    isAdmin: false,
    openid: null,
    loginState: 'idle',
    loginError: '',
    // 发布前请替换为你的后端 HTTPS 地址（必须在小程序后台配置 request 合法域名）
    apiBaseUrl: 'http://jingji.ctirad.fun:7777'
  }
})
