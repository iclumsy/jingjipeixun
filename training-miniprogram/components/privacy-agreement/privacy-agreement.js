// components/privacy-agreement/privacy-agreement.js
Component({
  properties: {
    show: {
      type: Boolean,
      value: false
    }
  },

  methods: {
    preventTouchMove() {
      // 阻止遮罩层滚动穿透
      return false
    },

    openPrivacyPolicy() {
      wx.navigateTo({
        url: '/pages/privacy/privacy'
      })
    },

    onAgree() {
      // 保存用户同意状态
      wx.setStorageSync('privacy_agreed', true)
      wx.setStorageSync('privacy_agreed_time', new Date().toISOString())

      this.triggerEvent('agree')
    },

    onDisagree() {
      wx.showModal({
        title: '提示',
        content: '您需要同意隐私政策才能使用本小程序',
        showCancel: false,
        success: () => {
          // 用户不同意，退出小程序
          wx.exitMiniProgram()
        }
      })
    }
  }
})
