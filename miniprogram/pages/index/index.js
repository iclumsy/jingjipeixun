// pages/index/index.js
const app = getApp()
const { hasAcceptedLatestAgreement } = require('../../utils/legal')

Page({
  data: {
    isAdmin: false,
    loading: true,
    showPrivacyAgreement: false,
    loginError: ''
  },

  onLoad() {
    this.checkPrivacyAgreement()
  },

  checkPrivacyAgreement() {
    // 检查用户是否已同意最新版本的《用户服务协议》《隐私政策》
    if (!hasAcceptedLatestAgreement()) {
      this.setData({
        showPrivacyAgreement: true,
        loading: false
      })
    } else {
      this.checkUserRole()
    }
  },

  onPrivacyAgree() {
    this.setData({
      showPrivacyAgreement: false,
      loading: true,
      loginError: ''
    })
    this.checkUserRole()
  },

  async checkUserRole() {
    try {
      this.setData({
        loading: true,
        loginError: ''
      })

      await app.ensureLogin()

      if (app.globalData.userInfo && app.globalData.loginState === 'success') {
        this.redirectToPage()
        return
      }

      throw new Error(app.globalData.loginError || '登录失败，请重试')
    } catch (err) {
      console.error('检查用户角色失败:', err)
      this.setData({
        loading: false,
        loginError: err.message || '登录状态检查失败'
      })
    }
  },

  async retryLogin() {
    this.setData({
      loading: true,
      loginError: ''
    })

    try {
      await app.ensureLogin(true)
    } catch (err) {
      // 失败由 checkUserRole 统一展示
    }
    this.checkUserRole()
  },

  redirectToPage() {
    const isAdmin = app.globalData.isAdmin

    if (isAdmin) {
      wx.switchTab({
        url: '/pages/admin/review/review'
      })
    } else {
      wx.switchTab({
        url: '/pages/user/submit/submit'
      })
    }
  }
})
