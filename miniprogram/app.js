/**
 * 微信小程序入口文件。
 *
 * 负责应用初始化、用户登录和全局状态管理：
 *
 * 登录流程:
 *   1. onLaunch 时自动触发 ensureLogin()
 *   2. ensureLogin() 确保同一时间只有一个登录请求在进行
 *   3. login() 调用 api.login() 获取令牌和用户信息
 *   4. 登录结果存入 globalData 和本地存储
 *
 * 全局状态 (globalData):
 *   userInfo       - 登录返回的用户信息对象
 *   isAdmin        - 是否为管理员
 *   openid         - 用户 openid
 *   loginState     - 登录状态: 'idle'/'loading'/'success'/'failed'
 *   loginError     - 登录失败时的错误信息
 *   apiBaseUrl     - 后端 API 基础地址
 */
const api = require('./utils/api')

App({
  /** 小程序启动时触发，自动尝试登录 */
  onLaunch() {
    this.ensureLogin()
  },

  /**
   * 确保登录已执行（去重复）。
   *
   * 通过 Promise 缓存确保同一时间只有一个登录请求在进行，
   * 避免多个页面同时触发重复登录。
   *
   * @param {boolean} force - 是否强制重新登录（忽略缓存的 Promise）
   * @returns {Promise} 登录结果
   */
  async ensureLogin(force = false) {
    if (!force && this._loginPromise) {
      return this._loginPromise  // 返回已有的登录 Promise
    }
    this._loginPromise = this.login()
      .finally(() => {
        this._loginPromise = null  // 登录完成后清除缓存
      })
    return this._loginPromise
  },

  /**
   * 执行实际的登录操作。
   *
   * 调用 api.login() 完成微信登录流程：
   * 1. wx.login() 获取 code
   * 2. 发送 code 到后端换取令牌和 openid
   * 3. 将登录信息存入 globalData 和本地存储
   */
  async login() {
    this.globalData.loginState = 'loading'   // 设置登录中状态
    this.globalData.loginError = ''
    try {
      const result = await api.login()

      // 登录成功：更新全局状态和本地存储
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
      // 登录失败：清空状态并记录错误
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

  // ======================== 全局状态 ========================
  globalData: {
    userInfo: null,          // 用户信息对象
    isAdmin: false,          // 是否为管理员
    openid: null,            // 用户 openid
    loginState: 'idle',      // 登录状态: idle/loading/success/failed
    loginError: '',          // 登录错误信息
    // 临时允许 HTTP 接口地址（上线前请改为 false 并切换到 HTTPS）
    allowInsecureHttp: true,
    // 后端 API 基础地址（发布前替换为 HTTPS 地址，并在小程序后台配置 request 合法域名）
    apiBaseUrl: 'http://49.232.213.198:5001/'
    // apiBaseUrl: 'http://jingji.ctirad.fun:7777'
  }
})
