const FORCE_CREATE_SUBMIT_KEY = 'submit_force_create_mode'
const { hasAdminAccess, hasPracticeAccess } = require('../utils/page-helpers')

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

    async updateTabBar() {
      const app = getApp()
      if (app && typeof app.ensureLogin === 'function') {
        try {
          await app.ensureLogin()
        } catch (err) {
          // 登录失败时继续使用最小标签，页面会展示对应错误。
        }
      }
      const currentRoute = this.getCurrentRoute()
      const isAdmin = hasAdminAccess()
      const canPractice = hasPracticeAccess()

      // 根据用户角色动态设置 TabBar
      const userTabs = [
        {
          pagePath: "/pages/user/submit/submit",
          text: "信息采集",
          iconText: "填"
        },
        {
          pagePath: "/pages/user/list/list",
          text: "我的提交",
          iconText: "单"
        }
      ]
      const practiceTab = {
        pagePath: "/pages/practice/index/index",
        text: "真题练习",
        iconText: "练"
      }
      const adminTabs = [
        {
          pagePath: "/pages/admin/review/review",
          text: "学员管理",
          iconText: "管"
        }
      ]

      const list = isAdmin
        ? [...userTabs, practiceTab, ...adminTabs]
        : (canPractice ? [...userTabs, practiceTab] : userTabs)
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
        this.setData({
          selected: data.index
        })
      } else {
        wx.switchTab({ url })
      }
    }
  }
})
