const api = require('../../../utils/api')
const { TRAINING_TYPE_LABELS, EDUCATION_OPTIONS } = require('../../../utils/constants')
const { hasAdminAccess, formatDateTime } = require('../../../utils/page-helpers')
const {
  validateStudent,
  normalizeIdCard,
  normalizePhone,
  getIdCardError,
  getPhoneError,
  getFileLabel
} = require('../../../utils/validators')
const {
  readJobCategoriesCache,
  writeJobCategoriesCache
} = require('../../../utils/job-categories-cache')

const STATUS_TEXT_MAP = {
  unreviewed: '待审核',
  reviewed: '已通过',
  rejected: '已驳回'
}

const DEFAULT_ATTACHMENTS = {
  special_equipment: ['photo', 'diploma', 'id_card_front', 'id_card_back', 'hukou_residence', 'hukou_personal'],
  special_equipment_renewal: ['photo', 'certificate_info_page', 'certificate_records_page'],
  special_operation: ['diploma', 'id_card_front', 'id_card_back']
}

function normalizeApplicationType(trainingType, applicationType) {
  if (trainingType !== 'special_equipment') return 'new_exam'
  return applicationType === 'renewal' ? 'renewal' : 'new_exam'
}

function getAttachmentProfileKey(trainingType, applicationType) {
  if (trainingType === 'special_equipment' && normalizeApplicationType(trainingType, applicationType) === 'renewal') {
    return 'special_equipment_renewal'
  }
  return trainingType
}

function createEmptyEditStudent() {
  return {
    name: '',
    gender: '男',
    education: '',
    educationIndex: -1,
    school: '',
    major: '',
    id_card: '',
    phone: '',
    company: '',
    company_address: '',
    job_category: '',
    jobCategoryIndex: -1,
    exam_project: '',
    examProjectIndex: -1,
    project_code: '',
    training_project_id: '',
    examProjects: [],
    training_type: 'special_equipment',
    application_type: 'new_exam',
    files: {
      photo: '',
      diploma: '',
      id_card_front: '',
      id_card_back: '',
      hukou_residence: '',
      hukou_personal: '',
      certificate_info_page: '',
      certificate_records_page: ''
    }
  }
}

function pickAttachmentValue(downloadValue, ...fallbacks) {
  const candidates = [downloadValue, ...fallbacks]
  for (const item of candidates) {
    const value = String(item || '').trim()
    if (!value) continue
    if (
      value.startsWith('cloud://') ||
      value.startsWith('wxfile://') ||
      value.startsWith('students/') ||
      /^https:\/\//i.test(value)
    ) {
      return value
    }
  }
  return ''
}

Page({
  data: {
    studentId: '',
    student: null,
    editStudent: createEmptyEditStudent(),
    downloadUrls: {},
    trainingType: 'special_equipment',
    trainingTypeText: '-',
    educationOptions: EDUCATION_OPTIONS,
    jobCategories: {},
    jobCategoryNames: [],
    attachmentConfig: {},
    enabledAttachments: [],
    fieldErrors: {
      id_card: '',
      phone: ''
    },
    statusText: '-',
    submitTimeText: '-',
    reviewTimeText: '-',
    loading: true,
    saving: false,
    actionLoading: false,
    actionType: '',
    canReview: false
  },

  async onLoad(options) {
    if (!this.ensureAdminAccess()) return
    if (!options.id) return
    this.setData({ studentId: String(options.id) })
    await this.initPage()

    // 预加载订阅消息 templateId，供审核操作后积累配额
    api.getWechatConfig().then(res => {
      if (res && res.success && res.template_id) {
        this._subscribeTemplateId = res.template_id
      }
    }).catch(() => {})
  },

  async initPage() {
    this.setData({ loading: true })
    await this.loadAttachmentConfig()
    await this.loadJobCategories()
    await this.loadDetail()
  },

  async loadAttachmentConfig() {
    const toList = (keys) => keys.map(key => ({ key, label: getFileLabel(key) }))

    try {
      const raw = await api.getAttachmentConfig()
      const attachmentConfig = {}
      Object.keys(DEFAULT_ATTACHMENTS).forEach(type => {
        const keys = Array.isArray(raw[type]) && raw[type].length > 0 ? raw[type] : DEFAULT_ATTACHMENTS[type]
        attachmentConfig[type] = toList(keys)
      })
      const profileKey = getAttachmentProfileKey(this.data.trainingType, this.data.editStudent.application_type)
      this.setData({
        attachmentConfig,
        enabledAttachments: attachmentConfig[profileKey] || []
      })
    } catch (err) {
      console.warn('加载附件配置失败，使用默认列表', err)
      const type = getAttachmentProfileKey(this.data.trainingType, this.data.editStudent.application_type)
      const attachmentConfig = {}
      Object.keys(DEFAULT_ATTACHMENTS).forEach(key => {
        attachmentConfig[key] = toList(DEFAULT_ATTACHMENTS[key])
      })
      this.setData({
        attachmentConfig,
        enabledAttachments: toList(DEFAULT_ATTACHMENTS[type] || [])
      })
    }
  },

  async loadJobCategories() {
    try {
      const cachedCategories = readJobCategoriesCache()
      if (cachedCategories) {
        this.setData({
          jobCategories: cachedCategories
        })
        this.updateJobCategoryNames()
        return
      }

      const res = await api.getJobCategories()
      if (res && res.success && res.data) {
        writeJobCategoriesCache(res.data)
        this.setData({
          jobCategories: res.data
        })
        this.updateJobCategoryNames()
      }
    } catch (err) {
      console.error('加载作业类别失败:', err)
    }
  },

  getJobCategoryNames(trainingType = this.data.trainingType) {
    const categories = this.data.jobCategories[trainingType]
    const list = categories && Array.isArray(categories.job_categories)
      ? categories.job_categories
      : []
    return list.map(item => item.name)
  },

  updateJobCategoryNames(trainingType = this.data.trainingType) {
    this.setData({
      jobCategoryNames: this.getJobCategoryNames(trainingType)
    })
  },

  async loadDetail() {
    this.setData({ loading: true })

    try {
      const result = await api.getStudentDetail(this.data.studentId)
      const student = result.student
      if (!student) {
        throw new Error('记录不存在')
      }

      const downloadUrls = result.downloadUrls || {}
      const trainingType = student.training_type || 'special_equipment'
      const applicationType = normalizeApplicationType(trainingType, student.application_type)
      const categories = this.data.jobCategories[trainingType]
      let jobCategoryIndex = -1
      let examProjects = []
      let examProjectIndex = -1

      if (categories && categories.job_categories) {
        jobCategoryIndex = categories.job_categories.findIndex(c => c.name === student.job_category)
        if (jobCategoryIndex >= 0) {
          examProjects = categories.job_categories[jobCategoryIndex].exam_projects || []
          examProjectIndex = examProjects.findIndex(p => p.name === student.exam_project)
        }
      }

      const normalizedIdCard = normalizeIdCard(student.id_card)
      const normalizedPhone = normalizePhone(student.phone)
      const educationIndex = this.data.educationOptions.indexOf(student.education)

      this.setData({
        student,
        downloadUrls,
        trainingType,
        enabledAttachments: this.data.attachmentConfig[getAttachmentProfileKey(trainingType, applicationType)] || [],
        jobCategoryNames: this.getJobCategoryNames(trainingType),
        trainingTypeText: TRAINING_TYPE_LABELS[trainingType] || trainingType,
        statusText: STATUS_TEXT_MAP[student.status] || student.status || '-',
        submitTimeText: formatDateTime(student.created_at),
        reviewTimeText: formatDateTime(student.reviewed_at),
        canReview: student.status === 'unreviewed',
        fieldErrors: {
          id_card: getIdCardError(normalizedIdCard),
          phone: getPhoneError(normalizedPhone)
        },
        editStudent: {
          name: student.name || '',
          gender: student.gender || '男',
          education: student.education || '',
          educationIndex,
          school: student.school || '',
          major: student.major || '',
          id_card: normalizedIdCard,
          phone: normalizedPhone,
          company: student.company || '',
          company_address: student.company_address || '',
          job_category: student.job_category || '',
          jobCategoryIndex,
          exam_project: student.exam_project || '',
          examProjectIndex,
          project_code: student.project_code || '',
          training_project_id: student.training_project_id || '',
          examProjects,
          training_type: trainingType,
          application_type: applicationType,
          files: {
            photo: pickAttachmentValue(student.files?.photo, student.photo_path, downloadUrls.photo_path),
            diploma: pickAttachmentValue(student.files?.diploma, student.diploma_path, downloadUrls.diploma_path),
            id_card_front: pickAttachmentValue(student.files?.id_card_front, student.id_card_front_path, downloadUrls.id_card_front_path),
            id_card_back: pickAttachmentValue(student.files?.id_card_back, student.id_card_back_path, downloadUrls.id_card_back_path),
            hukou_residence: pickAttachmentValue(student.files?.hukou_residence, student.hukou_residence_path, downloadUrls.hukou_residence_path),
            hukou_personal: pickAttachmentValue(student.files?.hukou_personal, student.hukou_personal_path, downloadUrls.hukou_personal_path),
            certificate_info_page: pickAttachmentValue(student.files?.certificate_info_page, student.certificate_info_page_path, downloadUrls.certificate_info_page_path),
            certificate_records_page: pickAttachmentValue(student.files?.certificate_records_page, student.certificate_records_page_path, downloadUrls.certificate_records_page_path)
          }
        },
        loading: false
      })
    } catch (err) {
      console.error('加载审核详情失败:', err)
      this.setData({ loading: false })
      wx.showToast({ title: err.message || '加载失败', icon: 'none' })
    }
  },

  selectTrainingType(e) {
    const detail = e.detail || {}
    const type = detail.type || (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.type)
    if (!type || type === this.data.trainingType) return

    const nextJobCategoryNames = this.getJobCategoryNames(type)
    const applicationType = normalizeApplicationType(type, this.data.editStudent.application_type)
    this.setData({
      trainingType: type,
      enabledAttachments: this.data.attachmentConfig[getAttachmentProfileKey(type, applicationType)] || [],
      jobCategoryNames: nextJobCategoryNames,
      trainingTypeText: TRAINING_TYPE_LABELS[type] || type,
      'editStudent.training_type': type,
      'editStudent.application_type': applicationType,
      'editStudent.job_category': '',
      'editStudent.jobCategoryIndex': -1,
      'editStudent.exam_project': '',
      'editStudent.examProjectIndex': -1,
      'editStudent.project_code': '',
      'editStudent.training_project_id': '',
      'editStudent.examProjects': []
    })
  },

  selectApplicationType(e) {
    const detail = e.detail || {}
    const applicationType = normalizeApplicationType(
      this.data.trainingType,
      detail.type || (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.type)
    )
    if (applicationType === this.data.editStudent.application_type) return
    const profileKey = getAttachmentProfileKey(this.data.trainingType, applicationType)
    const nextAttachments = this.data.attachmentConfig[profileKey] || []
    const nextKeys = new Set(nextAttachments.map(a => a.key))
    const clearUpdates = {}
    Object.keys(this.data.editStudent.files || {}).forEach(key => {
      if (!nextKeys.has(key)) clearUpdates[`editStudent.files.${key}`] = ''
    })
    this.setData({
      'editStudent.application_type': applicationType,
      enabledAttachments: nextAttachments,
      ...clearUpdates
    })
  },

  onJobCategoryChange(e) {
    const detail = e.detail || {}
    const categoryIndex = Number(detail.index !== undefined ? detail.index : detail.value)
    const categories = this.data.jobCategories[this.data.trainingType]
    if (!(categories && categories.job_categories)) return

    const category = categories.job_categories[categoryIndex]
    const examProjects = category.exam_projects || []

    if (examProjects.length === 1) {
      this.setData({
        'editStudent.job_category': category.name,
        'editStudent.jobCategoryIndex': categoryIndex,
        'editStudent.examProjects': examProjects,
        'editStudent.exam_project': examProjects[0].name,
        'editStudent.examProjectIndex': 0,
        'editStudent.project_code': examProjects[0].code,
        'editStudent.training_project_id': examProjects[0].id
      })
      return
    }

    this.setData({
      'editStudent.job_category': category.name,
      'editStudent.jobCategoryIndex': categoryIndex,
      'editStudent.examProjects': examProjects,
      'editStudent.exam_project': '',
      'editStudent.examProjectIndex': -1,
      'editStudent.project_code': '',
      'editStudent.training_project_id': ''
    })
  },

  onExamProjectChange(e) {
    const detail = e.detail || {}
    const projectIndex = Number(detail.index !== undefined ? detail.index : detail.value)
    const project = this.data.editStudent.examProjects[projectIndex]
    if (!project) return

    this.setData({
      'editStudent.exam_project': project.name,
      'editStudent.examProjectIndex': projectIndex,
      'editStudent.project_code': project.code,
      'editStudent.training_project_id': project.id
    })
  },

  selectGender(e) {
    const detail = e.detail || {}
    const gender = detail.gender || (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.gender)
    this.setData({
      'editStudent.gender': gender
    })
  },

  onInputChange(e) {
    const detail = e.detail || {}
    const field = detail.field || (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.field)
    let value = detail.value
    if (value === undefined) {
      value = e.detail && e.detail.value
    }
    if (!field) return

    if (field === 'id_card') {
      value = normalizeIdCard(value).slice(0, 18)
    }
    if (field === 'phone') {
      value = normalizePhone(value).slice(0, 11)
    }

    const updates = {
      [`editStudent.${field}`]: value
    }

    if (field === 'id_card') {
      updates['fieldErrors.id_card'] = getIdCardError(value)
    }

    if (field === 'phone') {
      updates['fieldErrors.phone'] = getPhoneError(value)
    }

    this.setData(updates)
  },

  onIdCardBlur() {
    this.setData({
      'fieldErrors.id_card': getIdCardError(this.data.editStudent.id_card)
    })
  },

  onPhoneBlur() {
    this.setData({
      'fieldErrors.phone': getPhoneError(this.data.editStudent.phone)
    })
  },

  onEducationChange(e) {
    const detail = e.detail || {}
    const index = Number(detail.index !== undefined ? detail.index : detail.value)
    this.setData({
      'editStudent.education': this.data.educationOptions[index],
      'editStudent.educationIndex': index
    })
  },

  onFileUploaded(e) {
    const { fileType, cloudPath } = e.detail
    this.setData({
      [`editStudent.files.${fileType}`]: cloudPath
    })
  },

  onFileDeleted(e) {
    const { fileType } = e.detail
    this.setData({
      [`editStudent.files.${fileType}`]: ''
    })
  },

  prepareStudentForSave() {
    const normalizedStudent = {
      ...this.data.editStudent,
      id_card: normalizeIdCard(this.data.editStudent.id_card),
      phone: normalizePhone(this.data.editStudent.phone)
    }

    this.setData({
      'editStudent.id_card': normalizedStudent.id_card,
      'editStudent.phone': normalizedStudent.phone,
      'fieldErrors.id_card': getIdCardError(normalizedStudent.id_card),
      'fieldErrors.phone': getPhoneError(normalizedStudent.phone)
    })

    const enabledAttachmentKeys = this.data.enabledAttachments.map(a => a.key)
    const validation = validateStudent(normalizedStudent, this.data.trainingType, enabledAttachmentKeys)
    if (!validation.valid) {
      const message = Object.values(validation.errors)[0] || '信息不完整'
      return {
        valid: false,
        message
      }
    }

    return {
      valid: true,
      student: normalizedStudent
    }
  },

  buildUpdates(normalizedStudent) {
    return {
      ...normalizedStudent,
      training_type: this.data.trainingType
    }
  },

  async saveChanges(silent = false) {
    if (this.data.saving) return false

    const prepared = this.prepareStudentForSave()
    if (!prepared.valid) {
      if (!silent) {
        wx.showToast({ title: prepared.message, icon: 'none' })
      }
      return false
    }

    if (!silent) {
      wx.showLoading({ title: '保存中...' })
    }
    this.setData({ saving: true })

    try {
      const result = await api.updateStudent(
        this.data.studentId,
        this.buildUpdates(prepared.student)
      )

      if (!result || !result.success) {
        throw new Error((result && result.message) || '保存失败')
      }

      await this.loadDetail()

      if (!silent) {
        wx.showToast({ title: '已保存', icon: 'success' })
      }
      return true
    } catch (err) {
      if (!silent) {
        wx.showToast({ title: err.message || '保存失败', icon: 'none' })
      }
      return false
    } finally {
      if (!silent) {
        wx.hideLoading()
      }
      this.setData({ saving: false })
    }
  },

  async onSave() {
    await this.saveChanges(false)
  },

  async onApprove() {
    if (!this.data.canReview) {
      wx.showToast({ title: '仅待审核记录可操作', icon: 'none' })
      return
    }

    const saveOk = await this.saveChanges(true)
    if (!saveOk) {
      wx.showToast({ title: '请先修正信息再审核', icon: 'none' })
      return
    }

    const confirmed = await this.confirmAction('审核通过', '确认通过该记录吗？')
    if (!confirmed) return

    this.setData({
      actionLoading: true,
      actionType: 'approve'
    })
    wx.showLoading({ title: '审核中...' })
    try {
      await api.reviewStudent(this.data.studentId, 'approve')
      wx.hideLoading()
      wx.showToast({ title: '已通过', icon: 'success' })
      this.silentRequestSubscription()
      await this.loadDetail()
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    } finally {
      this.setData({
        actionLoading: false,
        actionType: ''
      })
    }
  },

  async onReject() {
    if (!this.data.canReview) {
      wx.showToast({ title: '仅待审核记录可操作', icon: 'none' })
      return
    }

    const saveOk = await this.saveChanges(true)
    if (!saveOk) {
      wx.showToast({ title: '请先修正信息再驳回', icon: 'none' })
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

    this.setData({
      actionLoading: true,
      actionType: 'reject'
    })
    wx.showLoading({ title: '处理中...' })
    try {
      await api.reviewStudent(this.data.studentId, 'reject', content.trim())
      wx.hideLoading()
      wx.showToast({ title: '已驳回', icon: 'success' })
      this.silentRequestSubscription()
      await this.loadDetail()
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    } finally {
      this.setData({
        actionLoading: false,
        actionType: ''
      })
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

  async onQueryCard() {
    if (this.data.queryingCard) return
    this.setData({ queryingCard: true })

    try {
      const result = await api.queryCard(this.data.studentId)
      if (result && result.card_id) {
        const lines = [
          `姓名: ${result.name || '-'}`,
          `性别: ${result.sex || '-'}`,
          `身份证: ${result.id_card || '-'}`,
          `手机号: ${result.phone || '-'}`,
          `项目: ${result.project_name || '-'}`,
          `开卡时间: ${result.card_time || '-'}`,
          `状态: ${result.state || '-'}`,
          `卡号: ${result.card_id || '-'}`,
          `密码: ${result.card_pwd || '-'}`
        ]
        wx.showModal({
          title: '学习卡信息',
          content: lines.join('\n'),
          showCancel: false,
          confirmText: '知道了'
        })
      } else {
        wx.showToast({ title: result.message || '未查到卡号', icon: 'none' })
      }
    } catch (err) {
      wx.showToast({ title: err.message || '查询失败', icon: 'none' })
    } finally {
      this.setData({ queryingCard: false })
    }
  },

  ensureAdminAccess() {
    if (hasAdminAccess()) return true

    wx.showToast({
      title: '仅管理员可进入审核详情',
      icon: 'none'
    })

    const pages = getCurrentPages()
    if (pages.length > 1) {
      wx.navigateBack()
      return false
    }

    wx.switchTab({
      url: '/pages/user/submit/submit'
    })
    return false
  },

  silentRequestSubscription() {
    if (!this._subscribeTemplateId) return
    wx.requestSubscribeMessage({
      tmplIds: [this._subscribeTemplateId],
      success: () => {},
      fail: () => {}
    })
  }
})
