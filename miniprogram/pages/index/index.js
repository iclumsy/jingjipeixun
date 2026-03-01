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
      const loginState = app.globalData.loginState
      const loginError = app.globalData.loginError || ''

      if (loginState === 'failed') {
        this.setData({
          loading: false,
          loginError
        })
        return
      }

      if (app.globalData.userInfo && loginState === 'success') {
        this.redirectToPage()
        return
      }

      if (!this.data.loading) {
        this.setData({
          loading: true,
          loginError: ''
        })
      }

      clearTimeout(this._checkTimer)
      this._checkTimer = setTimeout(() => {
        this.checkUserRole()
      }, 400)
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

  onUnload() {
    clearTimeout(this._checkTimer)
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
