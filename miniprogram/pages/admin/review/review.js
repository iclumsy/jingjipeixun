const api = require('../../../utils/api')
const { TRAINING_TYPE_LABELS, STATUS_LABELS } = require('../../../utils/constants')
const { hasAdminAccess, formatDateTime } = require('../../../utils/page-helpers')

// 启动时的本地兜底筛选项；onLoad 会从 /api/config/student_filters 拉取最新版本覆盖。
// 状态/培训类型筛选条目变更请改后端配置接口，前端无需发版。
const FALLBACK_STATUS_FILTERS = [
  { label: '待审核', value: 'unreviewed' },
  { label: '已审核', value: 'reviewed' },
  { label: '已报名', value: 'registered' },
  { label: '已驳回', value: 'rejected' },
  { label: '考试通过', value: 'exam_passed' }
]

const FALLBACK_TRAINING_TYPE_FILTERS = [
  { label: '特种设备', value: 'special_equipment' },
  { label: '特种作业', value: 'special_operation' }
]

function normalizeAdminStatusFilters(filters = []) {
  const byValue = new Map()
  FALLBACK_STATUS_FILTERS.forEach(item => byValue.set(item.value, { ...item }))
  if (Array.isArray(filters)) {
    filters.forEach(item => {
      if (!item || !item.value) return
      if (!byValue.has(item.value)) return
      byValue.set(item.value, {
        ...item,
        label: FALLBACK_STATUS_FILTERS.find(fallback => fallback.value === item.value).label
      })
    })
  }
  return FALLBACK_STATUS_FILTERS.map(item => byValue.get(item.value) || item)
}

// 后端 enrich 缺失时的本地能力位兜底，逻辑须与 services/student_serializer.py::_build_actions 保持一致
function buildLocalActions(item) {
  const status = item.status || ''
  const tt = item.training_type || ''
  const isSe = tt === 'special_equipment'
  const isPassed = status === 'reviewed' || status === 'registered' || status === 'exam_passed'
  const cardActivated = !!item.card_activated
  const hasHealthForm = !!item.training_form_path
  return {
    canApprove: status === 'unreviewed',
    canReject: status !== 'registered' && status !== 'exam_passed',
    canDelete: true,
    canSubmitReg: isSe && status === 'reviewed',
    canMarkExamPassed: status === 'reviewed' || status === 'registered',
    canActivateCard: isSe && isPassed && !cardActivated,
    canQueryCard: isSe && isPassed && cardActivated,
    canDownloadRegForm: status === 'registered' || status === 'exam_passed',
    canDownloadHealthForm: isPassed && hasHealthForm,
    canEdit: status === 'rejected'
  }
}

function mapRecord(item) {
  const fallbackTags = []
  if (item.training_type === 'special_equipment' && item.application_type === 'renewal') {
    fallbackTags.push({ text: '复审', color: '#e65100', bg: '#fff3e0' })
  }
  const actions = item.actions ? {
    ...buildLocalActions(item),
    ...item.actions
  } : buildLocalActions(item)
  const canViewLearningStatus = item.status === 'reviewed' || item.status === 'registered'
  return {
    ...item,
    actions,
    canViewLearningStatus,
    statusText: item.statusText || STATUS_LABELS[item.status] || item.status || '-',
    statusClass: item.statusClass || item.status || '',
    trainingTypeText: item.trainingTypeText || TRAINING_TYPE_LABELS[item.training_type] || item.training_type || '-',
    tags: Array.isArray(item.tags) ? item.tags : fallbackTags,
    submitTimeText: formatDateTime(item.created_at)
  }
}

function mapLearningActivity(item = {}) {
  const type = item.type || ''
  const rawTimeText = item.timeText || formatDateTime(item.happenedAt)
  const shortTimeText = rawTimeText && rawTimeText !== '-'
    ? rawTimeText.replace(/^\d{4}-/, '')
    : rawTimeText
  const hasNumber = value => value !== undefined && value !== null && value !== ''
  let primaryText = item.detail || '-'
  let secondaryText = ''
  if (type === 'exam') {
    primaryText = `${hasNumber(item.score) ? item.score : '-'} 分 · ${item.passed ? '通过' : '未通过'}`
    secondaryText = [
      hasNumber(item.total) ? `总题数 ${item.total}` : '',
      hasNumber(item.correctCount) ? `答对 ${item.correctCount}` : '',
      item.durationText ? `用时${item.durationText}` : ''
    ].filter(Boolean).join('，')
  } else {
    primaryText = hasNumber(item.doneCount) ? `已完成 ${item.doneCount} 题` : '题库练习'
    secondaryText = [
      hasNumber(item.correctCount) ? `答对 ${item.correctCount} 题` : '',
      hasNumber(item.wrongCount) ? `错题 ${item.wrongCount} 题` : ''
    ].filter(Boolean).join('，')
  }
  return {
    ...item,
    typeClass: type === 'exam' ? 'exam' : 'practice',
    typeText: type === 'exam' ? '模拟考试' : '题库练习',
    timeText: rawTimeText,
    shortTimeText,
    primaryText,
    secondaryText
  }
}

function mapExamRecord(item = {}) {
  const rawTimeText = item.timeText || formatDateTime(item.createdAt || item.created_at)
  const shortTimeText = rawTimeText && rawTimeText !== '-'
    ? rawTimeText.replace(/^\d{4}-/, '')
    : rawTimeText
  const hasNumber = value => value !== undefined && value !== null && value !== ''
  return {
    ...item,
    score: hasNumber(item.score) ? Number(item.score) : null,
    total: hasNumber(item.total) ? Number(item.total) : null,
    correctCount: hasNumber(item.correctCount) ? Number(item.correctCount) : Number(item.correct_count || 0),
    durationText: item.durationText || '',
    passed: !!item.passed,
    timeText: rawTimeText,
    shortTimeText,
    scoreText: hasNumber(item.score) ? `${item.score}分` : '-',
    resultText: item.passed ? '通过' : '未通过'
  }
}

function normalizeLearningStatus(result = {}) {
  const summary = result.summary || {}
  const examStats = result.examStats || {}
  const bestScore = summary.bestScore === undefined ? null : summary.bestScore
  const latestScore = summary.latestScore === undefined ? null : summary.latestScore
  const examRecords = Array.isArray(examStats.records) ? examStats.records.map(mapExamRecord) : []
  return {
    success: !!result.success,
    student: result.student || {},
    bank: result.bank || null,
    summary: {
      state: summary.state || 'not_started',
      stateText: summary.stateText || '未开始',
      adviceText: summary.adviceText || '',
      doneCount: Number(summary.doneCount || 0),
      questionCount: Number(summary.questionCount || 0),
      progressPercent: Number(summary.progressPercent || 0),
      seenCount: Number(summary.seenCount || 0),
      masteredCount: Number(summary.masteredCount || 0),
      untouchedCount: Number(summary.untouchedCount || 0),
      answeredCount: Number(summary.answeredCount || 0),
      studyProgressPercent: Number(summary.studyProgressPercent || summary.progressPercent || 0),
      answerProgressPercent: Number(summary.answerProgressPercent || 0),
      masteryPercent: Number(summary.masteryPercent || 0),
      correctCount: Number(summary.correctCount || 0),
      correctRate: Number(summary.correctRate || 0),
      wrongCount: Number(summary.wrongCount || 0),
      lastStudyTimeText: summary.lastStudyTimeText || formatDateTime(summary.lastStudyAt),
      examCount: Number(summary.examCount || 0),
      latestScore,
      latestScoreText: latestScore === null || latestScore === '' ? '-' : `${latestScore}分`,
      bestScore,
      bestScoreText: bestScore === null || bestScore === '' ? '-' : `${bestScore}分`,
      passCount: Number(summary.passCount || 0),
      latestPassed: !!summary.latestPassed,
      latestDurationText: summary.latestDurationText || '',
      studyDurationText: summary.studyDurationText || '-'
    },
    examStats: {
      count: Number(examStats.count || 0),
      bestScore: examStats.bestScore,
      passCount: Number(examStats.passCount || 0),
      latest: examStats.latest || null,
      records: examRecords
    },
    activities: Array.isArray(result.activities) ? result.activities.map(mapLearningActivity) : []
  }
}

function mapOperationLog(item = {}) {
  const status = item.status || 'success'
  return {
    ...item,
    timeText: formatDateTime(item.created_at),
    actionText: item.action_label || item.action || '-',
    actorText: [item.actor_name || '-', item.actor_source || ''].filter(Boolean).join(' · '),
    statusClass: status === 'fail' ? 'fail' : (status === 'warning' ? 'warning' : 'success'),
    statusText: status === 'fail' ? '失败' : (status === 'warning' ? '提醒' : '成功')
  }
}

Page({
  data: {
    statusFilters: FALLBACK_STATUS_FILTERS,
    trainingTypeFilters: FALLBACK_TRAINING_TYPE_FILTERS,
    filters: {
      status: 'unreviewed',
      training_type: 'special_equipment',
      company: '',
      search: '',
      project: ''
    },
    companyOptions: ['全部'],
    companyIndex: 0,
    records: [],
    reviewProjects: [],
    reviewProjectCounts: {},
    reviewTotalMatchingCount: 0,
    page: 1,
    limit: 20,
    hasMore: true,
    loading: false,
    refreshing: false,
    initialized: false,

    showActivateModal: false,
    activateStudent: {},
    activating: false,

    // 报名表下载进度弹窗
    showRegFormLogModal: false,
    regFormLogs: [],
    regFormLoading: false,
    regFormError: false,
    regFormLogAnchor: '',
    regFormLogTitle: '',

    // 更多操作弹窗
    showMoreActionsModal: false,
    moreActionsStudent: {},

    // 双 Tab 切换属性
    currentTab: 'review', // review (信息审核) | report (学习统计)

    // 学习统计 Tab 对应的数据状态
    statusTabs: [
      { label: '全部', value: 'all' },
      { label: '学习中', value: 'active' },
      { label: '已通过', value: 'passed' },
      { label: '未开始', value: 'not_started' }
    ],
    activeStatus: 'all',
    searchQuery: '',
    reportProjects: [],
    reportProjectCounts: {},
    reportTotalMatchingCount: 0,
    activeProject: '',
    reportList: [],
    reportPage: 1,
    reportLimit: 20,
    reportHasMore: true,
    reportLoading: false,
    reportRefreshing: false,
    reportInitialized: false
  },

  async onLoad() {
    if (!this.ensureAdminAccess()) return

    // 异步加载筛选 tab 配置，失败时使用本地兜底
    api.getStudentFilters('admin').then(res => {
      if (!res) return
      const updates = {}
      if (Array.isArray(res.status_filters) && res.status_filters.length > 0) {
        updates.statusFilters = normalizeAdminStatusFilters(res.status_filters)
      }
      if (Array.isArray(res.training_type_filters) && res.training_type_filters.length > 0) {
        updates.trainingTypeFilters = res.training_type_filters
      }
      if (res.default && typeof res.default === 'object') {
        if (res.default.status) updates['filters.status'] = res.default.status
        if (res.default.training_type) updates['filters.training_type'] = res.default.training_type
      }
      if (Object.keys(updates).length > 0) this.setData(updates)
    }).catch(() => { })

    await this.refreshAll(true)
    this._skipRefreshOnShow = true
    this.setData({ initialized: true })

    // 预加载订阅消息 templateId，供审核操作后静默请求授权
    api.getWechatConfig().then(res => {
      if (res && res.success && res.template_id) {
        this._subscribeTemplateId = res.template_id
        this._lastBroadcastTs = (res.last_broadcast_ts || 0) * 1000  // 转毫秒
        // 首次进入时也检查是否需要提醒授权（onShow 在 initialized 之前已执行，不会触发）
        setTimeout(() => this.promptAdminSubscription(), 800)
      }
    }).catch(() => { })
  },

  /**
   * 静默请求一次订阅授权（不弹自定义提示，直接调用系统授权弹窗）。
   * 在审核操作完成后调用，每审核一个学员积累一次发送配额。
   */
  silentRequestSubscription() {
    if (!this._subscribeTemplateId) return
    wx.requestSubscribeMessage({
      tmplIds: [this._subscribeTemplateId],
      success: () => { },
      fail: () => { }
    })
  },

  /**
   * 定期提醒管理员授权订阅。
   * 触发条件（满足其一即弹窗）：
   * 1. 距上次提醒超过 1 天
   * 2. 服务端在上次提醒之后又发送过通知（配额已被消耗）
   */
  promptAdminSubscription() {
    if (!this._subscribeTemplateId) return

    const PROMPT_INTERVAL_MS = 1 * 24 * 60 * 60 * 1000  // 1 天
    const lastPrompt = wx.getStorageSync('admin_sub_last_prompt') || 0
    const broadcastAfterPrompt = this._lastBroadcastTs && this._lastBroadcastTs > lastPrompt

    if (!broadcastAfterPrompt && Date.now() - lastPrompt < PROMPT_INTERVAL_MS) return

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
            success: (subRes) => {
              if (subRes[this._subscribeTemplateId] === 'accept') {
                wx.showToast({ title: '已开启通知', icon: 'success' })
              }
            },
            fail: () => { }
          })
        }
      }
    })
  },

  async onShow() {
    if (!this.ensureAdminAccess(false)) return
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().updateTabBar()
    }
    if (this.data.initialized) {
      if (this._skipRefreshOnShow) {
        this._skipRefreshOnShow = false
      } else {
        if (this.data.currentTab === 'review') {
          await this.refreshAll(true)
        } else {
          await this.refreshReportAll()
        }
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
    if (this.data.currentTab === 'review') {
      this.refreshAll(true)
    } else {
      this.refreshReportAll()
    }
  },

  onReachBottom() {
    if (this.data.currentTab === 'review') {
      if (!this.data.loading && this.data.hasMore) {
        this.loadRecords(false)
      }
    } else {
      if (!this.data.reportLoading && this.data.reportHasMore) {
        this.loadReportRecords(false)
      }
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
        reviewProjects: result.projects || [],
        reviewProjectCounts: result.projectCounts || {},
        reviewTotalMatchingCount: result.totalMatching || 0,
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
      'filters.project': '',
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

  async onApproveTap(e) {
    const { id } = e.currentTarget.dataset
    if (!id) return

    const record = this.data.records.find(r => r._id === id)
    const canApprove = record && record.actions ? record.actions.canApprove : (record && record.status === 'unreviewed')
    if (!canApprove) {
      wx.showToast({ title: '当前状态不可审核通过', icon: 'none' })
      return
    }

    const confirmed = await this.confirmAction('审核通过', '确认通过该记录吗？')
    if (!confirmed) return

    wx.showLoading({ title: '审核中...' })
    try {
      await api.reviewStudent(id, 'approve')
      wx.hideLoading()
      wx.showToast({ title: '已审核', icon: 'success' })
      this.silentRequestSubscription()
      await this.loadRecords(true)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    }
  },

  async onRejectTap(e) {
    const { id } = e.currentTarget.dataset
    if (!id) return

    const record = this.data.records.find(r => r._id === id)
    const canReject = record && record.actions ? record.actions.canReject : (record && record.status !== 'registered')
    if (!canReject) {
      wx.showToast({ title: '省网已生成报名流水号，无法直接驳回，请先撤销', icon: 'none' })
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

  async onLearningStatusTap(e) {
    const { id, name } = e.currentTarget.dataset
    if (!id) {
      wx.showToast({ title: '记录ID不存在', icon: 'none' })
      return
    }

    let student = this.data.records.find(item => String(item._id) === String(id))
    if (!student) {
      if (name) {
        student = { _id: id, name: name }
      } else {
        const repItem = this.data.reportList && this.data.reportList.find(item => String(item.id) === String(id))
        if (repItem) {
          student = { _id: id, name: repItem.name }
        } else {
          student = { _id: id }
        }
      }
    }
    this.setData({
      showLearningStatusModal: true,
      learningStatusStudent: student,
      learningStatus: normalizeLearningStatus(),
      learningStatusError: '',
      learningStatusLoading: true
    })
    await this.loadLearningStatusForStudent(id)
  },

  async loadLearningStatusForStudent(id) {
    this.setData({ learningStatusLoading: true, learningStatusError: '' })
    try {
      const result = await api.getStudentLearningStatus(id)
      this.setData({
        learningStatus: normalizeLearningStatus(result),
        learningStatusLoading: false,
        learningStatusError: ''
      })
    } catch (err) {
      console.warn('加载学习情况失败:', err)
      this.setData({
        learningStatus: normalizeLearningStatus(),
        learningStatusLoading: false,
        learningStatusError: err.message || '学习情况加载失败'
      })
    }
  },

  async refreshLearningStatus() {
    const student = this.data.learningStatusStudent || {}
    if (!student._id || this.data.learningStatusLoading) return
    await this.loadLearningStatusForStudent(student._id)
  },

  closeLearningStatusModal() {
    this.setData({
      showLearningStatusModal: false,
      learningStatusStudent: {},
      learningStatus: normalizeLearningStatus(),
      learningStatusError: ''
    })
  },

  async onOperationLogTap(e) {
    const { id } = e.currentTarget.dataset
    if (!id) {
      wx.showToast({ title: '记录ID不存在', icon: 'none' })
      return
    }

    const student = this.data.records.find(item => String(item._id) === String(id)) || { _id: id }
    this.setData({
      showOperationLogModal: true,
      operationLogStudent: student,
      operationLogs: [],
      operationLogsError: '',
      operationLogsLoading: true
    })
    await this.loadOperationLogsForStudent(id)
  },

  async loadOperationLogsForStudent(id) {
    this.setData({ operationLogsLoading: true, operationLogsError: '' })
    try {
      const result = await api.getStudentOperationLogs(id)
      const logs = Array.isArray(result.logs) ? result.logs.map(mapOperationLog) : []
      this.setData({
        operationLogs: logs,
        operationLogsLoading: false,
        operationLogsError: ''
      })
    } catch (err) {
      console.warn('加载操作记录失败:', err)
      this.setData({
        operationLogs: [],
        operationLogsLoading: false,
        operationLogsError: err.message || '操作记录加载失败'
      })
    }
  },

  async refreshOperationLogs() {
    const student = this.data.operationLogStudent || {}
    if (!student._id || this.data.operationLogsLoading) return
    await this.loadOperationLogsForStudent(student._id)
  },

  closeOperationLogModal() {
    this.setData({
      showOperationLogModal: false,
      operationLogStudent: {},
      operationLogs: [],
      operationLogsError: ''
    })
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
  },

  async onSubmitRegisterTap(e) {
    const { id } = e.currentTarget.dataset
    if (!id) return

    const student = this.data.records.find(r => r._id === id)
    if (!student) return

    this.setData({
      showSubmitModal: true,
      submitStudent: student
    })
  },

  closeSubmitModal() {
    if (this.data.submitting) return
    this.setData({
      showSubmitModal: false,
      submitStudent: null
    })
  },

  async confirmSubmitRegister() {
    const student = this.data.submitStudent
    if (!student) return

    // 关闭确认弹窗，打开日志弹窗
    this.setData({
      showSubmitModal: false,
      submitting: true,
      showRegFormLogModal: true,
      regFormLogs: [],
      regFormLoading: true,
      regFormError: false,
      regFormLogTitle: '📤 提交报名到省平台'
    })

    this._addRegLog('正在向省平台提交报名信息...')
    this._addRegLog(`学员: ${student.name}  身份证: ${student.id_card}`)

    try {
      const res = await api.submitPlatformRegistration(student._id)

      // 展示后端返回的步骤日志
      if (res && res.steps && res.steps.length) {
        res.steps.forEach(log => {
          const isOk = log.startsWith('[OK]')
          const isFail = log.startsWith('[FAIL]')
          this._addRegLog(log.replace(/^\[(OK|FAIL|WARNING|INFO)\]\s*/, ''), {
            done: isOk, error: isFail
          })
        })
      }

      if (res && res.results && res.results.length > 0) {
        const detail = res.results[0]
        if (detail.success) {
          this._addRegLog('🎉 报名提交成功！', { done: true })
          await this.loadRecords(true)
        } else {
          this._addRegLog(`报名失败: ${detail.message || '未知'}`, { error: true })
          this.setData({ regFormError: true })
        }
      } else if (res && res.success) {
        this._addRegLog('🎉 报名提交成功！', { done: true })
        await this.loadRecords(true)
      } else {
        this._addRegLog(`操作异常: ${res.message || '无数据返回'}`, { error: true })
        this.setData({ regFormError: true })
      }
    } catch (err) {
      this._addRegLog(`提交异常: ${err.message || '网络错误'}`, { error: true })
      this.setData({ regFormError: true })
    } finally {
      this.setData({ submitting: false, regFormLoading: false, submitStudent: null })
      // 成功时 2 秒后自动关闭
      if (!this.data.regFormError) {
        setTimeout(() => this.closeRegFormLogModal(), 2000)
      }
    }
  },

  // ========== 报名表下载 - 实时日志弹窗模式 ==========
  _addRegLog(text, opts = {}) {
    const logs = this.data.regFormLogs.concat({ text, done: !!opts.done, error: !!opts.error })
    this.setData({ regFormLogs: logs, regFormLogAnchor: 'regFormLogBottom' })
  },

  closeRegFormLogModal() {
    this.setData({ showRegFormLogModal: false, regFormLogs: [], regFormError: false })
  },

  onRetryRegForm() {
    const d = this.data._lastRegFormParams
    if (d) {
      this.setData({ regFormLogs: [], regFormError: false })
      this._doDownloadRegForm(d.id, d.name, d.idCard)
    }
  },

  async onDownloadRegFormTap(e) {
    const { id, name, idCard } = e.currentTarget.dataset
    if (!id) return

    const record = this.data.records.find(r => r._id === id)
    const canDownload = record && record.actions
      ? record.actions.canDownloadRegForm
      : (record && record.status === 'registered')
    if (!canDownload) {
      wx.showModal({
        title: '提示',
        content: '必须先提交报名成功，并在平台生成流水号之后才可下载报名申请表。',
        showCancel: false
      })
      return
    }

    this.setData({
      showRegFormLogModal: true,
      regFormLogs: [],
      regFormLoading: true,
      regFormError: false,
      _lastRegFormParams: { id, name, idCard }
    })

    await this._doDownloadRegForm(id, name, idCard)
  },

  async _doDownloadRegForm(id, name, idCard) {
    try {
      // 步骤 1: 查询 BMID
      this._addRegLog('正在查询平台报名流水号(BMID)...')
      const bmidResult = await api.requestApi(`/api/sxtsks/bmid/${id}`, { method: 'GET' })
      if (!bmidResult || !bmidResult.success || !bmidResult.bmid) {
        throw new Error(bmidResult.message || '无法获取该学员在平台的报名记录')
      }
      this._addRegLog(`流水号获取成功: BMID=${bmidResult.bmid}`, { done: true })

      // 步骤 2: 使用已获取的 BMID 直接下载 PDF（不再重复查询 BMID）
      this._addRegLog('正在从省平台获取最新数据并生成 PDF...')
      const bmid = encodeURIComponent(bmidResult.bmid)
      const baseUrl = api.getBaseUrl()
      const token = api.getToken()
      const cleanName = (name || '').trim()
      const cleanIdCard = (idCard || '').trim()
      const filename = `${cleanIdCard || 'id'}-${cleanName || '学员'}-报名申请表.pdf`
      const filePath = `${wx.env.USER_DATA_PATH}/${filename}`
      const url = `${baseUrl}/api/sxtsks/form/${bmid}?student_id=${id}&no_cache=${Date.now()}`
        + (token ? `&mini_token=${encodeURIComponent(token)}` : '')

      await new Promise((resolve, reject) => {
        wx.downloadFile({
          url,
          filePath,
          header: token ? { Authorization: `Bearer ${token}`, 'X-Mini-Token': token } : {},
          success(res) {
            const finalPath = res.filePath || res.tempFilePath
            if (res.statusCode !== 200 && !finalPath) {
              reject(new Error(`下载失败（${res.statusCode}）`))
              return
            }
            wx.openDocument({
              filePath: finalPath,
              showMenu: true,
              success() { resolve() },
              fail(err) { reject(new Error(err.errMsg || '保存文档失败')) }
            })
          },
          fail(err) {
            reject(new Error(err.errMsg || '下载失败'))
          }
        })
      })
      this._addRegLog('报名申请表下载完成！', { done: true })

      this.setData({ regFormLoading: false })
      // 1.5 秒后自动关闭弹窗
      setTimeout(() => this.closeRegFormLogModal(), 1500)

    } catch (err) {
      console.error('报名表下载失败:', err)
      this._addRegLog(`失败: ${err.message || '未知错误'}`, { error: true })
      this.setData({ regFormLoading: false, regFormError: true })
    }
  },

  // ========== 更多操作弹窗 ==========
  onMoreActionsTap(e) {
    const { id } = e.currentTarget.dataset
    if (!id) return
    const record = this.data.records.find(r => String(r._id) === String(id))
    if (!record) {
      wx.showToast({ title: '记录不存在', icon: 'none' })
      return
    }
    this.setData({
      showMoreActionsModal: true,
      moreActionsStudent: record
    })
  },

  closeMoreActionsModal() {
    this.setData({
      showMoreActionsModal: false,
      moreActionsStudent: {}
    })
  },

  onMoreReject() {
    const id = this.data.moreActionsStudent && this.data.moreActionsStudent._id
    if (!id) return
    this.closeMoreActionsModal()
    this.onRejectTap({ currentTarget: { dataset: { id } } })
  },

  async onMarkExamPassedTap(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    const confirmed = await this.confirmAction('考试通过', '确认将该学员标记为理论考试已通过吗？')
    if (!confirmed) return

    wx.showLoading({ title: '处理中...' })
    try {
      await api.markExamPassed(id)
      wx.hideLoading()
      wx.showToast({ title: '考试通过', icon: 'success' })
      await this.loadRecords(true)
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    }
  },

  onMoreExamPassed() {
    const id = this.data.moreActionsStudent && this.data.moreActionsStudent._id
    if (!id) return
    this.closeMoreActionsModal()
    this.onMarkExamPassedTap({ currentTarget: { dataset: { id } } })
  },

  // ========== 双 Tab 切换 ==========
  switchSegmentTab(e) {
    const tab = e.currentTarget.dataset.tab
    if (tab === this.data.currentTab) return
    this.setData({
      currentTab: tab
    }, () => {
      if (tab === 'report' && !this.data.reportInitialized) {
        this.refreshReportAll()
      } else if (tab === 'review') {
        this.refreshAll(true)
      }
    })
  },

  // ========== 学习统计 (Report) 模块业务方法 ==========
  async refreshReportAll() {
    this.setData({
      reportPage: 1,
      reportHasMore: true
    }, () => {
      this.loadReportRecords(true)
    })
  },

  async loadReportRecords(refresh = false) {
    if (this.data.reportLoading && !refresh) return

    this._reportReqSeq = (this._reportReqSeq || 0) + 1
    const currentSeq = this._reportReqSeq

    this.setData({
      reportLoading: true,
      reportRefreshing: refresh
    })

    try {
      const page = refresh ? 1 : this.data.reportPage
      const result = await api.getLearningStats({
        search: this.data.searchQuery,
        status: this.data.activeStatus,
        project: this.data.activeProject,
        page,
        limit: this.data.reportLimit
      })

      if (currentSeq !== this._reportReqSeq) {
        return
      }

      const currentList = (result.list || []).map(item => {
        let shortTime = item.lastStudyTimeText || '-'
        if (shortTime && shortTime.length >= 10 && /^\d{4}-/.test(shortTime)) {
          shortTime = shortTime.substring(5)
        }

        let durationText = '-'
        const secs = Number(item.studyDurationSeconds || 0)
        if (secs > 0) {
          let hoursVal = secs / 3600
          if (hoursVal > 0 && hoursVal < 0.1) {
            hoursVal = 0.1
          }
          const hoursStr = hoursVal.toFixed(1)
          durationText = parseFloat(hoursStr) + '小时'
        } else if (secs === 0 && item.studyDurationText && item.studyDurationText !== '-') {
          durationText = item.studyDurationText
        }

        return {
          ...item,
          lastStudyTimeText: shortTime,
          studyDurationText: durationText,
          expanded: false
        }
      })

      const records = refresh ? currentList : this.data.reportList.concat(currentList)

      this.setData({
        reportList: records,
        reportProjects: result.projects || this.data.reportProjects,
        reportProjectCounts: result.project_counts || {},
        reportTotalMatchingCount: result.total_matching_count || 0,
        reportPage: page + 1,
        reportHasMore: !!result.hasMore,
        reportLoading: false,
        reportRefreshing: false,
        reportInitialized: true
      })
    } catch (err) {
      if (currentSeq !== this._reportReqSeq) return
      console.error('加载学习统计数据失败:', err)
      this.setData({
        reportLoading: false,
        reportRefreshing: false
      })
      wx.showToast({
        title: err.message || '加载统计失败',
        icon: 'none'
      })
    } finally {
      if (currentSeq === this._reportReqSeq) {
        wx.stopPullDownRefresh()
      }
    }
  },

  onReportStatusTabTap(e) {
    const { val } = e.currentTarget.dataset
    if (val === this.data.activeStatus) return
    this.setData({
      activeStatus: val
    }, () => {
      this.refreshReportAll()
    })
  },

  onReportSearchInput(e) {
    this.setData({
      searchQuery: e.detail.value
    })
  },

  onReportSearchConfirm() {
    this.refreshReportAll()
  },

  onReportSearchClear() {
    this.setData({
      searchQuery: ''
    }, () => {
      this.refreshReportAll()
    })
  },

  onReviewSearchInput(e) {
    this.setData({
      'filters.search': e.detail.value
    })
  },

  onReviewSearchConfirm() {
    this.refreshAll(true)
  },

  onReviewSearchClear() {
    this.setData({
      'filters.search': ''
    }, () => {
      this.refreshAll(true)
    })
  },

  onReportProjectTap(e) {
    const val = e.currentTarget.dataset.val
    if (val === this.data.activeProject) return
    this.setData({
      activeProject: val
    }, () => {
      this.refreshReportAll()
    })
  },

  onReviewProjectTap(e) {
    const val = e.currentTarget.dataset.val
    if (val === this.data.filters.project) return
    this.setData({
      'filters.project': val
    }, () => {
      this.refreshAll(true)
    })
  },

  onReportToggleExpand(e) {
    const index = e.currentTarget.dataset.index
    const expandedKey = `reportList[${index}].expanded`
    this.setData({
      [expandedKey]: !this.data.reportList[index].expanded
    })
  },

  onReportCallStudent(e) {
    const { phone } = e.currentTarget.dataset
    if (!phone) {
      wx.showToast({
        title: '手机号不存在',
        icon: 'none'
      })
      return
    }
    wx.makePhoneCall({
      phoneNumber: phone,
      fail: () => { }
    })
  },

  onReportCopyPhoneAndNotify(e) {
    const { phone, name } = e.currentTarget.dataset
    if (!phone) return
    wx.setClipboardData({
      data: phone,
      success: () => {
        wx.showModal({
          title: '复制成功',
          content: `已复制学员 ${name} 的手机号/微信号 (${phone})。可以打开微信搜索联系他督促学习。`,
          showCancel: false,
          confirmText: '我知道了'
        })
      }
    })
  }
})
