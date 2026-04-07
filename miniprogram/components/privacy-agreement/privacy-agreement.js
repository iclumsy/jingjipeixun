// components/privacy-agreement/privacy-agreement.js
const { markAgreementAccepted } = require('../../utils/legal')

Component({
  properties: {
    show: {
      type: Boolean,
      value: false
    },
    // 不同意时是否退出小程序，默认 true；设为 false 时仅触发 disagree 事件由父页面处理
    exitOnDisagree: {
      type: Boolean,
      value: true
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

    openUserAgreement() {
      wx.navigateTo({
        url: '/pages/agreement/agreement'
      })
    },

    onAgree() {
      // 保存用户同意状态（隐私政策 + 用户服务协议）
      markAgreementAccepted()

      this.triggerEvent('agree')
    },

    onDisagree() {
      if (this.properties.exitOnDisagree) {
        wx.showModal({
          title: '提示',
          content: '您需要同意《用户服务协议》和《隐私政策》后才能使用本小程序',
          showCancel: false,
          success: () => {
            wx.exitMiniProgram()
          }
        })
      } else {
        // 不退出，将控制权还给父页面
        this.triggerEvent('disagree')
      }
    }
  }
})
