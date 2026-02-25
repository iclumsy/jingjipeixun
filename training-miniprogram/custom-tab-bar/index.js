Component({
  data: {
    selected: 0,
    color: "#999999",
    selectedColor: "#667eea",
    list: []
  },

  attached() {
    this.updateTabBar()
  },

  methods: {
    updateTabBar() {
      const app = getApp()
      const isAdmin = app.globalData.isAdmin

      // 根据用户角色动态设置 TabBar
      const allTabs = [
        {
          pagePath: "/pages/user/submit/submit",
          text: "信息采集",
          icon: "📝"
        },
        {
          pagePath: "/pages/user/list/list",
          text: "我的提交",
          icon: "📋"
        },
        {
          pagePath: "/pages/admin/review/review",
          text: "审核管理",
          icon: "✅"
        }
      ]

      // 非管理员只显示前两个标签
      const list = isAdmin ? allTabs : allTabs.slice(0, 2)

      this.setData({ list })
    },

    switchTab(e) {
      const data = e.currentTarget.dataset
      const url = data.path
      wx.switchTab({ url })
      this.setData({
        selected: data.index
      })
    }
  }
})
