const FORCE_CREATE_SUBMIT_KEY = 'submit_force_create_mode'

function parseIsAdmin(raw) {
  if (raw === true || raw === 1) return true
  const text = String(raw || '').trim().toLowerCase()
  return text === 'true' || text === '1'
}

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

  pageLifetimes: {
    show() {
      this.updateTabBar()
    }
  },

  methods: {
    getCurrentRoute() {
      const pages = getCurrentPages()
      if (!pages || pages.length === 0) return ''
      const current = pages[pages.length - 1]
      return current && current.route ? `/${current.route}` : ''
    },

    getSelectedIndex(list, route) {
      const index = list.findIndex(item => item.pagePath === route)
      return index >= 0 ? index : 0
    },

    updateTabBar() {
      const app = getApp()
      const currentRoute = this.getCurrentRoute()
      const isAdminFromGlobal = !!(app && app.globalData && app.globalData.isAdmin)
      const isAdminFromStorage = parseIsAdmin(wx.getStorageSync('is_admin'))
      const isAdmin = isAdminFromGlobal || isAdminFromStorage

      // 根据用户角色动态设置 TabBar
      const allTabs = [
        {
          pagePath: "/pages/user/submit/submit",
          text: "信息采集",
          iconText: "填"
        },
        {
          pagePath: "/pages/user/list/list",
          text: "我的提交",
          iconText: "单"
        },
        {
          pagePath: "/pages/admin/review/review",
          text: "审核管理",
          iconText: "审"
        }
      ]

      // 非管理员只显示前两个标签
      const list = isAdmin ? allTabs : allTabs.slice(0, 2)
      const selected = this.getSelectedIndex(list, currentRoute)

      this.setData({ list, selected })
    },

    triggerForceCreateOnCurrentSubmitPage() {
      const pages = getCurrentPages()
      if (!pages || pages.length === 0) return
      const currentPage = pages[pages.length - 1]
      if (!currentPage || currentPage.route !== 'pages/user/submit/submit') return

      if (typeof currentPage.forceEnterCreateMode === 'function') {
        currentPage.forceEnterCreateMode()
      }
    },

    triggerCurrentPageRefresh(route) {
      const pages = getCurrentPages()
      if (!pages || pages.length === 0) return
      const currentPage = pages[pages.length - 1]
      if (!currentPage || !currentPage.route) return
      const currentRoute = `/${currentPage.route}`
      if (currentRoute !== route) return

      if (typeof currentPage.onTabReselect === 'function') {
        currentPage.onTabReselect()
      }
    },

    markForceCreateSubmitEntry(url) {
      if (url !== '/pages/user/submit/submit') return
      wx.setStorageSync(FORCE_CREATE_SUBMIT_KEY, true)
    },

    switchTab(e) {
      const data = e.currentTarget.dataset
      const url = data.path

      this.markForceCreateSubmitEntry(url)

      const currentRoute = this.getCurrentRoute()
      if (currentRoute === url) {
        if (url === '/pages/user/submit/submit') {
          this.triggerForceCreateOnCurrentSubmitPage()
        }
        this.triggerCurrentPageRefresh(url)
      } else {
        wx.switchTab({ url })
      }

      this.setData({
        selected: data.index
      })
    }
  }
})
