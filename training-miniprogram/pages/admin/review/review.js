// pages/admin/review/review.js
const api = require('../../../utils/api')

Page({
  data: {
    students: [],
    filters: {
      status: 'unreviewed',
      training_type: '',
      company: '',
      search: ''
    },
    statusOptions: ['全部', '未审核', '已审核', '已驳回'],
    statusValues: ['', 'unreviewed', 'reviewed', 'rejected'],
    statusIndex: 1,
    trainingTypeOptions: ['全部', '特种作业', '特种设备'],
    trainingTypeValues: ['', 'special_operation', 'special_equipment'],
    trainingTypeIndex: 0,
    companies: [],
    companyIndex: 0,
    page: 1,
    limit: 20,
    hasMore: true,
    loading: false,
    refreshing: false
  },

  onLoad() {
    this.loadCompanies()
    this.loadStudents(true)
  },

  onShow() {
    // 更新 TabBar 选中状态
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 2
      })
    }
  },

  onPullDownRefresh() {
    this.loadStudents(true)
  },

  onReachBottom() {
    if (!this.data.loading && this.data.hasMore) {
      this.loadStudents(false)
    }
  },

  async loadCompanies() {
    try {
      const result = await api.getCompanies({
        status: this.data.filters.status,
        training_type: this.data.filters.training_type
      })

      if (result.companies) {
        this.setData({
          companies: ['全部', ...result.companies]
        })
      }
    } catch (err) {
      console.error('加载公司列表失败:', err)
    }
  },

  async loadStudents(refresh = false) {
    if (this.data.loading) return

    this.setData({
      loading: true,
      refreshing: refresh
    })

    try {
      const page = refresh ? 1 : this.data.page
      const result = await api.getStudents({
        ...this.data.filters,
        page,
        limit: this.data.limit
      })

      const students = refresh ? result.list : [...this.data.students, ...result.list]

      this.setData({
        students,
        page: page + 1,
        hasMore: result.hasMore,
        loading: false,
        refreshing: false
      })

      if (refresh) {
        wx.stopPullDownRefresh()
      }
    } catch (err) {
      console.error('加载学员列表失败:', err)
      this.setData({
        loading: false,
        refreshing: false
      })

      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })

      if (refresh) {
        wx.stopPullDownRefresh()
      }
    }
  },

  onStatusChange(e) {
    const index = parseInt(e.detail.value)
    this.setData({
      statusIndex: index,
      'filters.status': this.data.statusValues[index],
      page: 1
    })
    this.loadStudents(true)
    this.loadCompanies()
  },

  onStatusSelect(e) {
    const value = e.currentTarget.dataset.value
    this.setData({
      'filters.status': value,
      page: 1
    })
    this.loadStudents(true)
    this.loadCompanies()
  },

  onTrainingTypeChange(e) {
    const index = parseInt(e.detail.value)
    this.setData({
      trainingTypeIndex: index,
      'filters.training_type': this.data.trainingTypeValues[index],
      page: 1
    })
    this.loadStudents(true)
    this.loadCompanies()
  },

  onTrainingTypeSelect(e) {
    const value = e.currentTarget.dataset.value
    this.setData({
      'filters.training_type': value,
      page: 1
    })
    this.loadStudents(true)
    this.loadCompanies()
  },

  onCompanyChange(e) {
    const index = parseInt(e.detail.value)
    const company = index === 0 ? '' : this.data.companies[index]
    this.setData({
      companyIndex: index,
      'filters.company': company,
      page: 1
    })
    this.loadStudents(true)
  },

  onSearchInput(e) {
    this.setData({
      'filters.search': e.detail.value
    })
  },

  onSearchConfirm() {
    this.setData({ page: 1 })
    this.loadStudents(true)
  },

  onStudentTap(e) {
    const { student } = e.detail
    wx.navigateTo({
      url: `/pages/admin/detail/detail?id=${student._id}`
    })
  },

  viewDetail(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({
      url: `/pages/admin/detail/detail?id=${id}`
    })
  },

  async quickApprove(e) {
    const { id } = e.currentTarget.dataset

    wx.showModal({
      title: '确认通过',
      content: '确定通过该学员的审核吗？',
      success: async (res) => {
        if (res.confirm) {
          wx.showLoading({ title: '审核中...' })
          try {
            await api.reviewStudent(id, 'approve')
            wx.hideLoading()
            wx.showToast({
              title: '审核通过',
              icon: 'success'
            })
            this.loadStudents(true)
          } catch (err) {
            wx.hideLoading()
            wx.showToast({
              title: '操作失败',
              icon: 'none'
            })
          }
        }
      }
    })
  },

  async quickReject(e) {
    const { id } = e.currentTarget.dataset

    wx.showModal({
      title: '确认驳回',
      content: '确定驳回该学员的审核吗？',
      success: async (res) => {
        if (res.confirm) {
          wx.showLoading({ title: '处理中...' })
          try {
            await api.reviewStudent(id, 'reject')
            wx.hideLoading()
            wx.showToast({
              title: '已驳回',
              icon: 'success'
            })
            this.loadStudents(true)
          } catch (err) {
            wx.hideLoading()
            wx.showToast({
              title: '操作失败',
              icon: 'none'
            })
          }
        }
      }
    })
  },

  stopPropagation() {
    // 阻止事件冒泡
  }
})
