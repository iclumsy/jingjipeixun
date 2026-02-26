const api = require('../../../utils/api')
const { TRAINING_TYPE_LABELS } = require('../../../utils/constants')

const STATUS_FILTERS = [
  { label: '待审核', value: 'unreviewed' },
  { label: '已通过', value: 'reviewed' },
  { label: '已驳回', value: 'rejected' }
]

const TRAINING_TYPE_FILTERS = [
  { label: '特种设备', value: 'special_equipment' },
  { label: '特种作业', value: 'special_operation' }
]

const STATUS_TEXT_MAP = {
  unreviewed: '待审核',
  reviewed: '已通过',
  rejected: '已驳回'
}

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

function mapRecord(item) {
  return {
    ...item,
    statusText: STATUS_TEXT_MAP[item.status] || item.status || '-',
    trainingTypeText: TRAINING_TYPE_LABELS[item.training_type] || item.training_type || '-',
    submitTimeText: formatTime(item.created_at)
  }
}

Page({
  data: {
    statusFilters: STATUS_FILTERS,
    trainingTypeFilters: TRAINING_TYPE_FILTERS,
    filters: {
      status: 'unreviewed',
      training_type: 'special_equipment',
      company: ''
    },
    companyOptions: ['全部'],
    companyIndex: 0,
    records: [],
    page: 1,
    limit: 20,
    hasMore: true,
    loading: false,
    refreshing: false,
    initialized: false
  },

  async onLoad() {
    await this.refreshAll(true)
    this._skipRefreshOnShow = true
    this.setData({ initialized: true })
  },

  async onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 })
    }
    if (this.data.initialized) {
      if (this._skipRefreshOnShow) {
        this._skipRefreshOnShow = false
        return
      }
      await this.refreshAll(true)
    }
  },

  onPullDownRefresh() {
    this.refreshAll(true)
  },

  onReachBottom() {
    if (!this.data.loading && this.data.hasMore) {
      this.loadRecords(false)
    }
  },

  async refreshAll(forceCompanyReload = false) {
    await this.loadCompanies(forceCompanyReload)
    await this.loadRecords(true)
  },

  async loadCompanies(forceReload = false) {
    const filterKey = `${this.data.filters.status}|${this.data.filters.training_type}`
    if (!forceReload && this._companyFilterKey === filterKey && this.data.companyOptions.length > 0) {
      return
    }

    try {
      const result = await api.getCompanies({
        status: this.data.filters.status,
        training_type: this.data.filters.training_type
      })

      const companies = ['全部', ...(result.companies || [])]
      const selectedCompany = this.data.filters.company
      const nextIndex = Math.max(0, companies.findIndex(item => item === selectedCompany))

      this.setData({
        companyOptions: companies,
        companyIndex: nextIndex,
        'filters.company': nextIndex === 0 ? '' : companies[nextIndex]
      })
      this._companyFilterKey = filterKey
    } catch (err) {
      console.error('加载公司筛选失败:', err)
      this.setData({
        companyOptions: ['全部'],
        companyIndex: 0,
        'filters.company': ''
      })
    }
  },

  async loadRecords(refresh = false) {
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

      const currentList = Array.isArray(result.list) ? result.list.map(mapRecord) : []
      const records = refresh ? currentList : this.data.records.concat(currentList)

      this.setData({
        records,
        page: page + 1,
        hasMore: !!result.hasMore,
        loading: false,
        refreshing: false
      })
    } catch (err) {
      console.error('加载审核记录失败:', err)
      this.setData({
        loading: false,
        refreshing: false
      })
      wx.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      wx.stopPullDownRefresh()
    }
  },

  async onStatusFilterTap(e) {
    const { value } = e.currentTarget.dataset
    if (value === this.data.filters.status) return

    this.setData({
      'filters.status': value,
      page: 1
    })
    await this.refreshAll(true)
  },

  async onTrainingTypeFilterTap(e) {
    const { value } = e.currentTarget.dataset
    if (value === this.data.filters.training_type) return

    this.setData({
      'filters.training_type': value,
      page: 1
    })
    await this.refreshAll(true)
  },

  async onCompanyChange(e) {
    const index = Number(e.detail.value)
    const company = index === 0 ? '' : this.data.companyOptions[index]

    this.setData({
      companyIndex: index,
      'filters.company': company,
      page: 1
    })
    await this.loadRecords(true)
  },

  openDetail(e) {
    const { id } = e.currentTarget.dataset
    if (!id) {
      wx.showToast({ title: '记录ID不存在', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: `/pages/admin/detail/detail?id=${id}`
    })
  },

  async onDeleteTap(e) {
    const { id } = e.currentTarget.dataset
    if (!id) return

    const confirmed = await this.confirmAction(
      '删除记录',
      '删除后不可恢复，是否继续？'
    )

    if (!confirmed) return

    wx.showLoading({ title: '删除中...' })
    try {
      await api.deleteStudent(id)
      wx.hideLoading()
      wx.showToast({ title: '已删除', icon: 'success' })
      await this.loadRecords(true)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '删除失败', icon: 'none' })
    }
  },

  async onApproveTap(e) {
    const { id, status } = e.currentTarget.dataset
    if (!id) return

    if (status !== 'unreviewed') {
      wx.showToast({ title: '仅待审核记录可操作', icon: 'none' })
      return
    }

    const confirmed = await this.confirmAction('审核通过', '确认通过该记录吗？')
    if (!confirmed) return

    wx.showLoading({ title: '审核中...' })
    try {
      await api.reviewStudent(id, 'approve')
      wx.hideLoading()
      wx.showToast({ title: '已通过', icon: 'success' })
      await this.loadRecords(true)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    }
  },

  async onRejectTap(e) {
    const { id, status } = e.currentTarget.dataset
    if (!id) return

    if (status !== 'unreviewed') {
      wx.showToast({ title: '仅待审核记录可操作', icon: 'none' })
      return
    }

    const confirmed = await this.confirmAction('驳回记录', '确认驳回该记录吗？')
    if (!confirmed) return

    wx.showLoading({ title: '处理中...' })
    try {
      await api.reviewStudent(id, 'reject')
      wx.hideLoading()
      wx.showToast({ title: '已驳回', icon: 'success' })
      await this.loadRecords(true)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    }
  },

  confirmAction(title, content) {
    return new Promise(resolve => {
      wx.showModal({
        title,
        content,
        success: res => resolve(!!res.confirm),
        fail: () => resolve(false)
      })
    })
  },

  async onTabReselect() {
    if (this.data.loading) return
    await this.refreshAll(true)
  }
})
