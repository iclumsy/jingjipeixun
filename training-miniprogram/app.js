// app.js
App({
  onLaunch() {
    // 初始化云开发
    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力')
    } else {
      wx.cloud.init({
        env: 'cloudbase-4gmtzpetf829faa7', // 替换为你的云开发环境ID
        traceUser: true
      })
    }

    // 自动登录
    this.login()
  },

  async login() {
    try {
      wx.showLoading({ title: '登录中...' })

      const { result } = await wx.cloud.callFunction({
        name: 'login'
      })

      this.globalData.userInfo = result
      this.globalData.isAdmin = result.isAdmin
      this.globalData.openid = result.openid

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
        content: '请检查网络连接或联系管理员',
        showCancel: false
      })
    }
  },

  globalData: {
    userInfo: null,
    isAdmin: false,
    openid: null
  }
})
