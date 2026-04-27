const api = require('../../../utils/api')
const { TRAINING_TYPE_LABELS, EDUCATION_OPTIONS, STATUS_LABELS } = require('../../../utils/constants')
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
const {
  MATERIAL_LABELS,
  normalizeGeneratedMaterials,
  buildManualCropPayload
} = require('./materials')

// 编辑表单本地兜底：附件类型与培训类型的映射，仅在后端 attachment 配置接口失败时使用。
// 真正的附件清单由 /api/config/attachments 下发；状态/能力位由后端 enrich 提供。
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
    statusClass: '',
    submitTimeText: '-',
    reviewTimeText: '-',
    loading: true,
    saving: false,
    actionLoading: false,
    actionType: '',
    canReview: false,
    materialsLoading: false,
    regenFormLoading: false,
    generatedMaterials: [],
    generatedMaterialsExists: false,
    materialModal: {
      visible: false,
      title: '',
      materialType: '',
      panels: [],
      activeKey: '',
      activePanel: null,
      submitting: false
    }
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
    await this.loadGeneratedMaterials()
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
        // 文案优先读后端 enrich 字段，缺失时回退到本地常量
        trainingTypeText: student.trainingTypeText || TRAINING_TYPE_LABELS[trainingType] || trainingType,
        statusText: student.statusText || STATUS_LABELS[student.status] || student.status || '-',
        statusClass: student.statusClass || student.status || '',
        submitTimeText: formatDateTime(student.created_at),
        reviewTimeText: formatDateTime(student.reviewed_at),
        // 审核权限优先读后端 actions.canApprove
        canReview: (student.actions && typeof student.actions.canApprove === 'boolean')
          ? student.actions.canApprove
          : (student.status === 'unreviewed'),
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

  async loadGeneratedMaterials() {
    if (!this.data.studentId) return
    this.setData({ materialsLoading: true })
    try {
      const result = await api.getGeneratedMaterials(this.data.studentId)
      const materials = normalizeGeneratedMaterials(result.materials || [], api.toAbsoluteFileUrl)
      this.setData({
        generatedMaterials: materials,
        generatedMaterialsExists: !!result.exists && materials.length > 0,
        materialsLoading: false
      })
    } catch (err) {
      console.warn('加载报名材料失败:', err)
      this.setData({
        generatedMaterials: [],
        generatedMaterialsExists: false,
        materialsLoading: false
      })
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
      await this.loadGeneratedMaterials()
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

  previewGeneratedMaterial(e) {
    const index = Number(e.currentTarget.dataset.index)
    const item = this.data.generatedMaterials[index]
    if (!item || !item.previewUrl) {
      wx.showToast({ title: '材料地址不可用', icon: 'none' })
      return
    }
    if (/\.docx?$/i.test(item.name || '')) {
      wx.showLoading({ title: '打开中...' })
      wx.downloadFile({
        url: item.previewUrl,
        success: res => {
          wx.hideLoading()
          wx.openDocument({
            filePath: res.tempFilePath,
            showMenu: true,
            fail: () => wx.showToast({ title: '文件打开失败', icon: 'none' })
          })
        },
        fail: () => {
          wx.hideLoading()
          wx.showToast({ title: '文件下载失败', icon: 'none' })
        }
      })
      return
    }
    wx.previewImage({
      urls: this.data.generatedMaterials
        .filter(mat => mat.previewUrl && !/\.docx?$/i.test(mat.name || ''))
        .map(mat => mat.previewUrl),
      current: item.previewUrl
    })
  },

  openMaterialAdjust(e) {
    const index = Number(e.currentTarget.dataset.index)
    const material = this.data.generatedMaterials[index]
    if (!material || !material.materialType) return
    const panels = this.buildAdjustPanels(material.materialType)
    if (!panels.length) {
      wx.showToast({ title: '未找到原始附件', icon: 'none' })
      return
    }
    this.setData({
      materialModal: {
        visible: true,
        title: `调整${MATERIAL_LABELS[material.materialType] || '报名材料'}`,
        materialType: material.materialType,
        panels,
        activeKey: panels[0].key,
        activePanel: panels[0],
        whiteBg: true,
        submitting: false
      }
    }, () => {
      this.prepareActiveCropPanel()
    })
  },

  closeMaterialAdjust() {
    if (this.data.materialModal.submitting) return
    this.hideMaterialAdjust()
  },

  hideMaterialAdjust() {
    this.setData({
      materialModal: {
        visible: false,
        title: '',
        materialType: '',
        panels: [],
        activeKey: '',
        activePanel: null,
        whiteBg: true,
        submitting: false
      }
    })
  },

  buildAdjustPanels(materialType) {
    const files = (this.data.editStudent && this.data.editStudent.files) || {}
    const toUrl = value => {
      const raw = String(value || '').trim()
      if (!raw) return ''
      if (/^https?:\/\//i.test(raw) || /^wxfile:\/\//i.test(raw)) return raw
      try {
        return api.toAbsoluteFileUrl(raw)
      } catch (err) {
        return ''
      }
    }
    const makePanel = (key, label, source, fixedRatio) => ({
      key,
      label,
      sourceUrl: toUrl(source),
      fixedRatio: fixedRatio || 0,
      imageWidth: 0,
      imageHeight: 0,
      stageWidth: 0,
      stageHeight: 0,
      displayWidth: 0,
      displayHeight: 0,
      offsetX: 0,
      offsetY: 0,
      rotation: 0,
      points: [],
      cropRect: null,
      touched: false,
      ready: false,
      imageStyle: '',
      frameStyle: '',
      lines: [],
      handles: []
    })

    if (materialType === 'photo') {
      return files.photo ? [makePanel('points', '个人照片', files.photo, 5 / 7)] : []
    }
    if (materialType === 'id_card') {
      return [
        files.id_card_front ? makePanel('front_points', '正面', files.id_card_front) : null,
        files.id_card_back ? makePanel('back_points', '反面', files.id_card_back) : null
      ].filter(Boolean)
    }
    if (materialType === 'hukou') {
      return [
        files.hukou_residence ? makePanel('home_points', '首页', files.hukou_residence) : null,
        files.hukou_personal ? makePanel('personal_points', '个人页', files.hukou_personal) : null
      ].filter(Boolean)
    }
    if (materialType === 'diploma') {
      return files.diploma ? [makePanel('points', '学历证书', files.diploma)] : []
    }
    return []
  },

  switchAdjustPanel(e) {
    const key = e.currentTarget.dataset.key
    const panel = this.data.materialModal.panels.find(item => item.key === key)
    if (!panel) return
    this.setData({
      'materialModal.activeKey': key,
      'materialModal.activePanel': panel
    }, () => {
      this.prepareActiveCropPanel()
    })
  },

  toggleWhiteBg(e) {
    this.setData({ 'materialModal.whiteBg': e.detail.value })
  },

  prepareActiveCropPanel() {
    const panel = this.data.materialModal.activePanel
    if (!panel || !panel.sourceUrl) return
    const panelIndex = this.getPanelIndex(panel.key)
    if (panel.ready) return

    Promise.all([
      new Promise((resolve, reject) => {
        wx.getImageInfo({
          src: panel.sourceUrl,
          success: resolve,
          fail: reject
        })
      }),
      new Promise(resolve => {
        wx.createSelectorQuery()
          .in(this)
          .select('#materialCropStage')
          .boundingClientRect(rect => resolve(rect || {}))
          .exec()
      })
    ]).then(([info, rect]) => {
      this._lastStageRect = rect || {}
      const imageWidth = info.width || 1
      const imageHeight = info.height || 1
      const stageWidth = rect.width || 300
      const stageHeight = rect.height || 360
      const scale = Math.min(stageWidth / imageWidth, stageHeight / imageHeight)
      const displayWidth = imageWidth * scale
      const displayHeight = imageHeight * scale
      const offsetX = (stageWidth - displayWidth) / 2
      const offsetY = (stageHeight - displayHeight) / 2
      const nextPanel = {
        ...panel,
        imageWidth,
        imageHeight,
        stageWidth,
        stageHeight,
        displayWidth,
        displayHeight,
        offsetX,
        offsetY,
        ready: true
      }

      if (nextPanel.fixedRatio) {
        nextPanel.cropRect = this.createDefaultCropRect(nextPanel)
        nextPanel.points = this.rectToPoints(nextPanel.cropRect)
      } else {
        nextPanel.points = [
          [0, 0],
          [imageWidth, 0],
          [imageWidth, imageHeight],
          [0, imageHeight]
        ]
      }
      this.refreshPanelStyles(nextPanel)
      this.updatePanelAt(panelIndex, nextPanel)
    }).catch(err => {
      console.warn('准备调整图片失败:', err)
      wx.showToast({ title: '图片加载失败', icon: 'none' })
    })
  },

  createDefaultCropRect(panel) {
    const ratio = panel.fixedRatio || 1
    let width = panel.imageWidth * 0.82
    let height = width / ratio
    if (height > panel.imageHeight * 0.9) {
      height = panel.imageHeight * 0.9
      width = height * ratio
    }
    return {
      x: Math.round((panel.imageWidth - width) / 2),
      y: Math.round((panel.imageHeight - height) / 2),
      w: Math.round(width),
      h: Math.round(height)
    }
  },

  rectToPoints(rect) {
    if (!rect) return []
    return [
      [rect.x, rect.y],
      [rect.x + rect.w, rect.y],
      [rect.x + rect.w, rect.y + rect.h],
      [rect.x, rect.y + rect.h]
    ]
  },

  pointToDisplay(panel, point) {
    const scale = panel.displayWidth / panel.imageWidth
    const rad = (panel.rotation || 0) * Math.PI / 180
    const cx = panel.offsetX + panel.displayWidth / 2
    const cy = panel.offsetY + panel.displayHeight / 2
    const dx = (point[0] - panel.imageWidth / 2) * scale
    const dy = (point[1] - panel.imageHeight / 2) * scale
    return {
      x: cx + dx * Math.cos(rad) - dy * Math.sin(rad),
      y: cy + dx * Math.sin(rad) + dy * Math.cos(rad)
    }
  },

  displayToPoint(panel, x, y) {
    const scale = panel.imageWidth / panel.displayWidth
    const rad = -((panel.rotation || 0) * Math.PI / 180)
    const cx = panel.offsetX + panel.displayWidth / 2
    const cy = panel.offsetY + panel.displayHeight / 2
    const dx = x - cx
    const dy = y - cy
    const px = Math.max(0, Math.min(panel.imageWidth, Math.round((dx * Math.cos(rad) - dy * Math.sin(rad)) * scale + panel.imageWidth / 2)))
    const py = Math.max(0, Math.min(panel.imageHeight, Math.round((dx * Math.sin(rad) + dy * Math.cos(rad)) * scale + panel.imageHeight / 2)))
    return [px, py]
  },

  refreshPanelStyles(panel) {
    panel.imageStyle = [
      `width:${panel.displayWidth}px`,
      `height:${panel.displayHeight}px`,
      `left:${panel.offsetX}px`,
      `top:${panel.offsetY}px`,
      `transform:rotate(${panel.rotation || 0}deg)`
    ].join(';')

    if (panel.fixedRatio && panel.cropRect) {
      const tl = this.pointToDisplay(panel, [panel.cropRect.x, panel.cropRect.y])
      const br = this.pointToDisplay(panel, [panel.cropRect.x + panel.cropRect.w, panel.cropRect.y + panel.cropRect.h])
      panel.frameStyle = [
        `left:${tl.x}px`,
        `top:${tl.y}px`,
        `width:${br.x - tl.x}px`,
        `height:${br.y - tl.y}px`
      ].join(';')
      panel.points = this.rectToPoints(panel.cropRect)
    }

    const displayPoints = (panel.points || []).map(point => this.pointToDisplay(panel, point))
    panel.lines = displayPoints.length === 4 ? displayPoints.map((point, index) => {
      const next = displayPoints[(index + 1) % displayPoints.length]
      const dx = next.x - point.x
      const dy = next.y - point.y
      const length = Math.sqrt(dx * dx + dy * dy)
      const angle = Math.atan2(dy, dx) * 180 / Math.PI
      return {
        index,
        style: `left:${point.x}px;top:${point.y}px;width:${length}px;transform:rotate(${angle}deg);`
      }
    }) : []

    panel.handles = displayPoints.map((display, index) => {
      return {
        index,
        text: String(index + 1),
        style: `left:${display.x}px;top:${display.y}px;`
      }
    })
  },

  getPanelIndex(key) {
    return this.data.materialModal.panels.findIndex(item => item.key === key)
  },

  updatePanelAt(index, panel) {
    if (index < 0) return
    const panels = this.data.materialModal.panels.slice()
    panels[index] = panel
    this.setData({
      'materialModal.panels': panels,
      'materialModal.activePanel': panel
    })
  },

  onCropHandleStart(e) {
    this.refreshStageRect()
    const index = Number(e.currentTarget.dataset.index)
    const touch = e.touches && e.touches[0]
    if (!touch) return
    this._cropDrag = {
      type: 'handle',
      index,
      startX: touch.clientX,
      startY: touch.clientY
    }
  },

  onCropFrameStart(e) {
    this.refreshStageRect()
    const touch = e.touches && e.touches[0]
    const panel = this.data.materialModal.activePanel
    if (!touch || !panel || !panel.cropRect) return
    this._cropDrag = {
      type: 'frame',
      startX: touch.clientX,
      startY: touch.clientY,
      rect: { ...panel.cropRect }
    }
  },

  onCropTouchMove(e) {
    const drag = this._cropDrag
    const touch = e.touches && e.touches[0]
    const panel = this.data.materialModal.activePanel
    if (!drag || !touch || !panel || !panel.ready) return
    const panelIndex = this.getPanelIndex(panel.key)
    const nextPanel = { ...panel }

    if (nextPanel.fixedRatio && nextPanel.cropRect) {
      const scale = nextPanel.imageWidth / nextPanel.displayWidth
      if (drag.type === 'frame') {
        const dx = Math.round((touch.clientX - drag.startX) * scale)
        const dy = Math.round((touch.clientY - drag.startY) * scale)
        nextPanel.cropRect = this.clampCropRect(nextPanel, {
          ...drag.rect,
          x: drag.rect.x + dx,
          y: drag.rect.y + dy
        })
      } else {
        nextPanel.cropRect = this.resizeFixedCropRect(nextPanel, drag.index, touch.clientX, touch.clientY)
      }
      nextPanel.touched = true
      this.refreshPanelStyles(nextPanel)
      this.updatePanelAt(panelIndex, nextPanel)
      return
    }

    if (drag.type !== 'handle') return
    const stage = this.getTouchInStage(touch)
    const points = (nextPanel.points || []).map(item => item.slice())
    points[drag.index] = this.displayToPoint(nextPanel, stage.x, stage.y)
    nextPanel.points = points
    nextPanel.touched = true
    this.refreshPanelStyles(nextPanel)
    this.updatePanelAt(panelIndex, nextPanel)
  },

  onCropTouchEnd() {
    this._cropDrag = null
  },

  getTouchInStage(touch) {
    const rect = this._lastStageRect || {}
    return {
      x: touch.clientX - (rect.left || 0),
      y: touch.clientY - (rect.top || 0)
    }
  },

  refreshStageRect() {
    wx.createSelectorQuery()
      .in(this)
      .select('#materialCropStage')
      .boundingClientRect(rect => {
        this._lastStageRect = rect || {}
      })
      .exec()
  },

  resizeFixedCropRect(panel, handleIndex, clientX, clientY) {
    this.refreshStageRect()
    const stage = this.getTouchInStage({ clientX, clientY })
    const point = this.displayToPoint(panel, stage.x, stage.y)
    const rect = panel.cropRect
    const ratio = panel.fixedRatio || 1
    let x = rect.x
    let y = rect.y
    let w = rect.w
    let h = rect.h

    if (handleIndex === 0 || handleIndex === 3) {
      w = Math.max(40, rect.x + rect.w - point[0])
      x = rect.x + rect.w - w
    } else {
      w = Math.max(40, point[0] - rect.x)
    }
    h = Math.round(w / ratio)
    if (handleIndex === 0 || handleIndex === 1) {
      y = rect.y + rect.h - h
    }
    return this.clampCropRect(panel, { x, y, w, h })
  },

  clampCropRect(panel, rect) {
    let w = Math.min(rect.w, panel.imageWidth)
    let h = Math.min(rect.h, panel.imageHeight)
    if (panel.fixedRatio) {
      const ratio = panel.fixedRatio
      if (h > panel.imageHeight) {
        h = panel.imageHeight
        w = Math.round(h * ratio)
      }
      if (w > panel.imageWidth) {
        w = panel.imageWidth
        h = Math.round(w / ratio)
      }
    }
    const x = Math.max(0, Math.min(panel.imageWidth - w, rect.x))
    const y = Math.max(0, Math.min(panel.imageHeight - h, rect.y))
    return { x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) }
  },

  rotateActivePanel(e) {
    const direction = e.currentTarget.dataset.direction
    const panel = this.data.materialModal.activePanel
    if (!panel) return
    const panelIndex = this.getPanelIndex(panel.key)
    const delta = direction === 'left' ? -90 : 90
    const nextPanel = {
      ...panel,
      rotation: (panel.rotation + delta + 360) % 360
    }
    this.fitPanelToStage(nextPanel)
    this.refreshPanelStyles(nextPanel)
    this.updatePanelAt(panelIndex, nextPanel)
  },

  fitPanelToStage(panel) {
    const rotated = Math.abs((panel.rotation || 0) % 180) === 90
    const sourceWidth = rotated ? panel.imageHeight : panel.imageWidth
    const sourceHeight = rotated ? panel.imageWidth : panel.imageHeight
    const scale = Math.min(panel.stageWidth / sourceWidth, panel.stageHeight / sourceHeight)
    panel.displayWidth = panel.imageWidth * scale
    panel.displayHeight = panel.imageHeight * scale
    panel.offsetX = (panel.stageWidth - panel.displayWidth) / 2
    panel.offsetY = (panel.stageHeight - panel.displayHeight) / 2
  },

  resetActivePanel() {
    const panel = this.data.materialModal.activePanel
    if (!panel || !panel.ready) return
    const panelIndex = this.getPanelIndex(panel.key)
    const nextPanel = {
      ...panel,
      touched: false,
      rotation: 0
    }
    if (nextPanel.fixedRatio) {
      nextPanel.cropRect = this.createDefaultCropRect(nextPanel)
      nextPanel.points = this.rectToPoints(nextPanel.cropRect)
    } else {
      nextPanel.points = [
        [0, 0],
        [nextPanel.imageWidth, 0],
        [nextPanel.imageWidth, nextPanel.imageHeight],
        [0, nextPanel.imageHeight]
      ]
    }
    this.refreshPanelStyles(nextPanel)
    this.updatePanelAt(panelIndex, nextPanel)
  },

  async confirmMaterialAdjust() {
    const modal = this.data.materialModal
    if (!modal.materialType || modal.submitting) return
    const state = {}
    modal.panels.forEach(panel => {
      const rotateKey = this.getRotationKey(modal.materialType, panel.key)
      if (rotateKey) state[rotateKey] = panel.rotation
      if (panel.touched) state[panel.key] = panel.points
    })
    const payload = buildManualCropPayload(modal.materialType, state)
    // photo 白底开关
    if (modal.materialType === 'photo' && modal.whiteBg === false) {
      payload.adjustments.skip_white_bg = true
    }
    this.setData({ 'materialModal.submitting': true })
    wx.showLoading({ title: '生成中...' })
    try {
      const result = await api.manualCropMaterial(this.data.studentId, payload)
      wx.hideLoading()
      wx.showToast({ title: result.message || '已重新生成', icon: 'success' })
      this.hideMaterialAdjust()
      await this.loadGeneratedMaterials()
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '调整失败', icon: 'none' })
      this.setData({ 'materialModal.submitting': false })
    }
  },

  async regenTrainingForm() {
    if (this.data.regenFormLoading) return
    this.setData({ regenFormLoading: true })
    wx.showLoading({ title: '生成中...' })
    try {
      const result = await api.regenerateTrainingForm(this.data.studentId)
      wx.hideLoading()
      wx.showToast({ title: result.message || '已重新生成', icon: 'success' })
      await this.loadGeneratedMaterials()
    } catch (err) {
      wx.hideLoading()
      wx.showToast({ title: err.message || '重新生成失败', icon: 'none' })
    } finally {
      this.setData({ regenFormLoading: false })
    }
  },

  getRotationKey(materialType, panelKey) {
    if (materialType === 'photo' || materialType === 'diploma') return 'rotate'
    if (materialType === 'id_card') {
      return panelKey === 'front_points' ? 'front_rotate' : 'back_rotate'
    }
    if (materialType === 'hukou') {
      return panelKey === 'home_points' ? 'home_rotate' : 'personal_rotate'
    }
    return ''
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
