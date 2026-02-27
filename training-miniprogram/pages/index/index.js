// pages/index/index.js
const app = getApp()
const { hasAcceptedLatestAgreement } = require('../../utils/legal')

Page({
  data: {
    isAdmin: false,
    loading: true,
    showPrivacyAgreement: false
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
      loading: true
    })
    this.checkUserRole()
  },

  async checkUserRole() {
    try {
      // 等待登录完成
      if (app.globalData.userInfo) {
        this.redirectToPage()
      } else {
        // 等待登录
        setTimeout(() => {
          this.checkUserRole()
        }, 500)
      }
    } catch (err) {
      console.error('检查用户角色失败:', err)
      this.setData({ loading: false })
    }
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
