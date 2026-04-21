const api = require('../../../utils/api')
const { TRAINING_TYPE_LABELS } = require('../../../utils/constants')
const { hasAdminAccess, formatDateTime } = require('../../../utils/page-helpers')

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

function mapRecord(item) {
  return {
    ...item,
    statusText: STATUS_TEXT_MAP[item.status] || item.status || '-',
    trainingTypeText: TRAINING_TYPE_LABELS[item.training_type] || item.training_type || '-',
    submitTimeText: formatDateTime(item.created_at),
    // 已审核且存在体检表时，拼接完整下载 URL（和网页端 toFileUrl 逻辑一致）
    trainingFormUrl: (item.status === 'reviewed' && item.training_form_path)
      ? api.toAbsoluteFileUrl(item.training_form_path)
      : '',
    hasTrainingForm: item.status === 'reviewed' && !!item.training_form_path
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
    initialized: false,
    
    showActivateModal: false,
    activateStudent: {},
    activating: false
  },

  async onLoad() {
    if (!this.ensureAdminAccess()) return
    await this.refreshAll(true)
    this._skipRefreshOnShow = true
    this.setData({ initialized: true })

    // 预加载订阅消息 templateId，供审核操作后静默请求授权
    api.getWechatConfig().then(res => {
      if (res && res.success && res.template_id) {
        this._subscribeTemplateId = res.template_id
        // 首次进入时也检查是否需要提醒授权（onShow 在 initialized 之前已执行，不会触发）
        setTimeout(() => this.promptAdminSubscription(), 800)
      }
    }).catch(() => {})
  },

  /**
   * 静默请求一次订阅授权（不弹自定义提示，直接调用系统授权弹窗）。
   * 在审核操作完成后调用，每审核一个学员积累一次发送配额。
   */
  silentRequestSubscription() {
    if (!this._subscribeTemplateId) return
    wx.requestSubscribeMessage({
      tmplIds: [this._subscribeTemplateId],
      success: () => {},
      fail: () => {}
    })
  },

  /**
   * 定期提醒管理员授权订阅（每 3 天一次）。
   * 确保所有管理员（包括不常审核的）都能积累发送配额。
   */
  promptAdminSubscription() {
    if (!this._subscribeTemplateId) return

    const PROMPT_INTERVAL_MS = 1 * 24 * 60 * 60 * 1000  // 1 天
    const lastPrompt = wx.getStorageSync('admin_sub_last_prompt') || 0
    if (Date.now() - lastPrompt < PROMPT_INTERVAL_MS) return

    wx.showModal({
      title: '接收新学员通知',
      content: '授权后可收到新学员报名提醒，每次授权可收到一条通知。',
      confirmText: '去授权',
      cancelText: '下次再说',
      success: (res) => {
        wx.setStorageSync('admin_sub_last_prompt', Date.now())
        if (res.confirm) {
          wx.requestSubscribeMessage({
            tmplIds: [this._subscribeTemplateId],
            success: () => {},
            fail: () => {}
          })
        }
      }
    })
  },

  async onShow() {
    if (!this.ensureAdminAccess(false)) return
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 })
    }
    if (this.data.initialized) {
      if (this._skipRefreshOnShow) {
        this._skipRefreshOnShow = false
      } else {
        await this.refreshAll(true)
      }
      // 定期提醒管理员授权订阅（所有管理员打开此页都会触发检查）
      setTimeout(() => this.promptAdminSubscription(), 800)
    }
  },

  onPullDownRefresh() {
    if (!this.ensureAdminAccess(false)) {
      wx.stopPullDownRefresh()
      return
    }
    this.refreshAll(true)
  },

  onReachBottom() {
    if (!this.ensureAdminAccess(false)) return
    if (!this.data.loading && this.data.hasMore) {
      this.loadRecords(false)
    }
  },

  ensureAdminAccess(showToast = true) {
    if (hasAdminAccess()) return true

    if (showToast) {
      wx.showToast({
        title: '仅管理员可进入审核管理',
        icon: 'none'
      })
    }

    wx.switchTab({
      url: '/pages/user/submit/submit'
    })
    return false
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
      this.silentRequestSubscription()
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

    const { confirm, content } = await new Promise(resolve => {
      wx.showModal({
        title: '驳回记录',
        content: '照片不清晰', // 默认提示或初始值
        placeholderText: '请输入驳回原因',
        editable: true,
        success: res => resolve({ confirm: !!res.confirm, content: res.content || '' }),
        fail: () => resolve({ confirm: false, content: '' })
      })
    })

    if (!confirm) return

    wx.showLoading({ title: '处理中...' })
    try {
      await api.reviewStudent(id, 'reject', content.trim())
      wx.hideLoading()
      wx.showToast({ title: '已驳回', icon: 'success' })
      this.silentRequestSubscription()
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
  },

  async onDownloadTrainingFormTap(e) {
    const { id, name, idCard } = e.currentTarget.dataset
    if (!id) {
      wx.showToast({ title: '参数错误', icon: 'none' })
      return
    }
    wx.showLoading({ title: '下载中...' })
    try {
      // 使用 api.js 中的封装方法，传递姓名和身份证号用于构建文件名
      await api.downloadTrainingForm(id, name, idCard)
      wx.hideLoading()
    } catch (err) {
      wx.hideLoading()
      console.error('下载体检表失败:', err)
      wx.showToast({ title: err.message || '下载失败', icon: 'none' })
    }
  },

  async onQueryCardTap(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.showLoading({ title: '查询中...' })
    try {
      const result = await api.queryCard(id)
      wx.hideLoading()
      if (result && result.card_id) {
        this.setData({
          showCardInfoModal: true,
          cardInfo: result
        })
      } else {
        wx.showToast({ title: result.message || '未查到信息', icon: 'none' })
      }
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '查询失败', icon: 'none' })
    }
  },

  closeCardInfoModal() {
    this.setData({ showCardInfoModal: false, cardInfo: {} })
  },

  onActivateCardTap(e) {
    const { id, name, phone, idCard, examProject } = e.currentTarget.dataset
    if (!id) {
      wx.showToast({ title: '参数错误', icon: 'none' })
      return
    }

    this.setData({
      showActivateModal: true,
      activateStudent: { id, name, phone, idCard, examProject }
    })
  },

  closeActivateModal() {
    if (this.data.activating) return
    this.setData({
      showActivateModal: false,
      activateStudent: {}
    })
  },

  preventD() {
    // 阻止事件冒泡即可
  },

  async confirmActivateCard() {
    const { id } = this.data.activateStudent
    if (!id || this.data.activating) return

    this.setData({ activating: true })
    try {
      const result = await api.activateCard(id)
      wx.showToast({ title: result.message || '开卡成功', icon: 'success' })
      this.closeActivateModal()
      // 刷新列表以更新开卡状态
      await this.loadRecords(true)
    } catch (err) {
      wx.showToast({ title: err.message || '开卡失败', icon: 'none' })
    } finally {
      this.setData({ activating: false })
    }
  }
})
