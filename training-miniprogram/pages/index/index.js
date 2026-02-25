// pages/index/index.js
const app = getApp()

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
    // 检查用户是否已同意隐私政策
    const privacyAgreed = wx.getStorageSync('privacy_agreed')

    if (!privacyAgreed) {
      // 未同意，显示隐私协议弹窗
      this.setData({
        showPrivacyAgreement: true,
        loading: false
      })
    } else {
      // 已同意，继续登录流程
      this.checkUserRole()
    }
  },

  onPrivacyAgree() {
    // 用户同意隐私政策
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
