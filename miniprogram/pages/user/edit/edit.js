// pages/user/edit/edit.js
const api = require('../../../utils/api')
const {
  validateStudent,
  normalizeIdCard,
  normalizePhone,
  getIdCardError,
  getPhoneError,
  getFileLabel
} = require('../../../utils/validators')
const { EDUCATION_OPTIONS } = require('../../../utils/constants')
const {
  readJobCategoriesCache,
  writeJobCategoriesCache
} = require('../../../utils/job-categories-cache')
const {
  hasAcceptedLatestAgreement,
  markAgreementAccepted
} = require('../../../utils/legal')

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

function createEmptyStudent() {
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
    application_type: 'new_exam',
    examProjects: [],
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
    trainingType: 'special_equipment',
    agreementChecked: false,
    educationOptions: EDUCATION_OPTIONS,
    fieldErrors: {
      id_card: '',
      phone: ''
    },
    jobCategories: {},
    jobCategoryNames: [],
    attachmentConfig: {},
    enabledAttachments: [],
    student: createEmptyStudent()
  },

  async onLoad(options) {
    const studentId = String((options && options.id) || '').trim()
    if (!studentId) {
      wx.showToast({
        title: '记录ID不存在',
        icon: 'none'
      })
      this.safeBackToList()
      return
    }

    this.setData({
      studentId,
      agreementChecked: hasAcceptedLatestAgreement()
    })

    // 预加载订阅消息 templateId，存到实例属性供 tap 时同步使用
    api.getWechatConfig().then(res => {
      if (res && res.success && res.template_id) {
        this._subscribeTemplateId = res.template_id
      }
    }).catch(() => {})

    await this.loadAttachmentConfig()
    await this.loadJobCategories()
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
      const profileKey = getAttachmentProfileKey(this.data.trainingType, this.data.student.application_type)
      this.setData({
        attachmentConfig,
        enabledAttachments: attachmentConfig[profileKey] || []
      })
    } catch (err) {
      console.warn('加载附件配置失败，使用默认列表', err)
      const type = getAttachmentProfileKey(this.data.trainingType, this.data.student.application_type)
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

  safeBackToList() {
    const pages = getCurrentPages()
    if (pages.length > 1) {
      wx.navigateBack()
      return
    }

    wx.switchTab({
      url: '/pages/user/list/list'
    })
  },

  async loadJobCategories() {
    try {
      const cachedCategories = readJobCategoriesCache()
      if (cachedCategories) {
        this.setData({
          jobCategories: cachedCategories
        })
        this.updateJobCategoryNames()
        await this.loadStudentData()
        return
      }

      const res = await api.getJobCategories()
      if (res && res.success && res.data) {
        writeJobCategoriesCache(res.data)
        this.setData({
          jobCategories: res.data
        })
        this.updateJobCategoryNames()
        await this.loadStudentData()
      }
    } catch (err) {
      console.error('加载作业类别失败:', err)
      wx.showToast({
        title: '加载配置失败',
        icon: 'none'
      })
    }
  },

  async loadStudentData() {
    try {
      wx.showLoading({ title: '加载中...' })
      const result = await api.getStudentDetail(this.data.studentId)
      const downloadUrls = result.downloadUrls || {}

      if (!result.student) {
        throw new Error('学员不存在')
      }

      const student = result.student
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

      const educationIndex = this.data.educationOptions.indexOf(student.education)
      const normalizedIdCard = normalizeIdCard(student.id_card)
      const normalizedPhone = normalizePhone(student.phone)

      this.setData({
        trainingType,
        status: student.status,
        rejectReason: student.reject_reason,
        jobCategoryNames: this.getJobCategoryNames(trainingType),
        enabledAttachments: this.data.attachmentConfig[getAttachmentProfileKey(trainingType, applicationType)] || [],
        fieldErrors: {
          id_card: getIdCardError(normalizedIdCard),
          phone: getPhoneError(normalizedPhone)
        },
        student: {
          name: student.name,
          gender: student.gender,
          education: student.education,
          educationIndex,
          school: student.school || '',
          major: student.major || '',
          id_card: normalizedIdCard,
          phone: normalizedPhone,
          company: student.company,
          company_address: student.company_address,
          job_category: student.job_category,
          jobCategoryIndex,
          exam_project: student.exam_project || '',
          examProjectIndex,
          project_code: student.project_code || '',
          training_project_id: student.training_project_id || '',
          application_type: applicationType,
          examProjects,
          files: {
            photo: pickAttachmentValue(student.files?.photo, student.files?.photo_path, student.photo_path, downloadUrls.photo_path),
            diploma: pickAttachmentValue(student.files?.diploma, student.files?.diploma_path, student.diploma_path, downloadUrls.diploma_path),
            id_card_front: pickAttachmentValue(student.files?.id_card_front, student.files?.id_card_front_path, student.id_card_front_path, downloadUrls.id_card_front_path),
            id_card_back: pickAttachmentValue(student.files?.id_card_back, student.files?.id_card_back_path, student.id_card_back_path, downloadUrls.id_card_back_path),
            hukou_residence: pickAttachmentValue(student.files?.hukou_residence, student.files?.hukou_residence_path, student.hukou_residence_path, downloadUrls.hukou_residence_path),
            hukou_personal: pickAttachmentValue(student.files?.hukou_personal, student.files?.hukou_personal_path, student.hukou_personal_path, downloadUrls.hukou_personal_path),
            certificate_info_page: pickAttachmentValue(student.files?.certificate_info_page, student.files?.certificate_info_page_path, student.certificate_info_page_path, downloadUrls.certificate_info_page_path),
            certificate_records_page: pickAttachmentValue(student.files?.certificate_records_page, student.files?.certificate_records_page_path, student.certificate_records_page_path, downloadUrls.certificate_records_page_path)
          }
        }
      })
      wx.hideLoading()
    } catch (err) {
      wx.hideLoading()
      console.error('加载学员数据失败:', err)
      wx.showToast({
        title: err.message || '加载失败',
        icon: 'none'
      })
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

  selectTrainingType(e) {
    const detail = e.detail || {}
    const type = detail.type || (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.type)
    if (!type || type === this.data.trainingType) return

    const nextJobCategoryNames = this.getJobCategoryNames(type)
    const applicationType = normalizeApplicationType(type, this.data.student.application_type)
    this.setData({
      trainingType: type,
      jobCategoryNames: nextJobCategoryNames,
      enabledAttachments: this.data.attachmentConfig[getAttachmentProfileKey(type, applicationType)] || [],
      'student.application_type': applicationType,
      'student.job_category': '',
      'student.jobCategoryIndex': -1,
      'student.examProjects': [],
      'student.exam_project': '',
      'student.examProjectIndex': -1,
      'student.project_code': '',
      'student.training_project_id': ''
    })
  },

  selectApplicationType(e) {
    const detail = e.detail || {}
    const applicationType = normalizeApplicationType(
      this.data.trainingType,
      detail.type || (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.type)
    )
    if (applicationType === this.data.student.application_type) return
    const profileKey = getAttachmentProfileKey(this.data.trainingType, applicationType)
    const nextAttachments = this.data.attachmentConfig[profileKey] || []
    const nextKeys = new Set(nextAttachments.map(a => a.key))
    const clearUpdates = {}
    Object.keys(this.data.student.files || {}).forEach(key => {
      if (!nextKeys.has(key)) clearUpdates[`student.files.${key}`] = ''
    })
    this.setData({
      'student.application_type': applicationType,
      enabledAttachments: nextAttachments,
      ...clearUpdates
    })
  },

  selectGender(e) {
    const detail = e.detail || {}
    const gender = detail.gender || (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.gender)
    this.setData({
      'student.gender': gender
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
      [`student.${field}`]: value
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
      'fieldErrors.id_card': getIdCardError(this.data.student.id_card)
    })
  },

  onPhoneBlur() {
    this.setData({
      'fieldErrors.phone': getPhoneError(this.data.student.phone)
    })
  },

  onPickerChange(e) {
    const detail = e.detail || {}
    const field = detail.field || (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.field) || 'education'
    const pickerIndex = Number(detail.index !== undefined ? detail.index : detail.value)

    if (field === 'education') {
      this.setData({
        'student.education': this.data.educationOptions[pickerIndex],
        'student.educationIndex': pickerIndex
      })
    }
  },

  onJobCategoryChange(e) {
    const detail = e.detail || {}
    const categoryIndex = Number(detail.index !== undefined ? detail.index : detail.value)
    const categories = this.data.jobCategories[this.data.trainingType]

    if (categories && categories.job_categories) {
      const category = categories.job_categories[categoryIndex]
      const examProjects = category.exam_projects || []

      if (examProjects.length === 1) {
        this.setData({
          'student.job_category': category.name,
          'student.jobCategoryIndex': categoryIndex,
          'student.examProjects': examProjects,
          'student.exam_project': examProjects[0].name,
          'student.examProjectIndex': 0,
          'student.project_code': examProjects[0].code,
          'student.training_project_id': examProjects[0].id
        })
      } else {
        this.setData({
          'student.job_category': category.name,
          'student.jobCategoryIndex': categoryIndex,
          'student.examProjects': examProjects,
          'student.exam_project': '',
          'student.examProjectIndex': -1,
          'student.project_code': '',
          'student.training_project_id': ''
        })
      }
    }
  },

  onExamProjectChange(e) {
    const detail = e.detail || {}
    const projectIndex = Number(detail.index !== undefined ? detail.index : detail.value)
    const project = this.data.student.examProjects[projectIndex]

    if (project) {
      this.setData({
        'student.exam_project': project.name,
        'student.examProjectIndex': projectIndex,
        'student.project_code': project.code,
        'student.training_project_id': project.id
      })
    }
  },

  onFileUploaded(e) {
    const { fileType, cloudPath } = e.detail
    this.setData({
      [`student.files.${fileType}`]: cloudPath
    })
  },

  onFileDeleted(e) {
    const { fileType } = e.detail
    this.setData({
      [`student.files.${fileType}`]: ''
    })
  },

  onAgreementChange(e) {
    const detail = e.detail || {}
    const values = detail.values || detail.value || []
    const checked = typeof detail.checked === 'boolean' ? detail.checked : values.includes('agree')
    this.setData({
      agreementChecked: checked
    })
    if (checked) {
      markAgreementAccepted()
    }
  },

  openUserAgreement() {
    wx.navigateTo({
      url: '/pages/agreement/agreement'
    })
  },

  openPrivacyPolicy() {
    wx.navigateTo({
      url: '/pages/privacy/privacy'
    })
  },

  ensureAgreementAccepted() {
    const accepted = this.data.agreementChecked || hasAcceptedLatestAgreement()
    if (!accepted) {
      wx.showModal({
        title: '请先阅读并同意协议',
        content: '更新前请先同意《用户服务协议》和《隐私政策》。',
        showCancel: false
      })
      return false
    }

    if (!hasAcceptedLatestAgreement()) {
      markAgreementAccepted()
    }
    return true
  },

  /**
   * 提交按钒入口（在用户 tap 链路内，同步请求订阅授权再进入提交逻辑）
   */
  onTapSubmit() {
    // 订阅授权必须在 tap 链路内同步调用，不能 async/await
    if (this._subscribeTemplateId) {
      wx.requestSubscribeMessage({
        tmplIds: [this._subscribeTemplateId],
        success: () => this.submitForm(),
        fail: () => this.submitForm()  // 用户拒绝或失败也继续提交
      })
    } else {
      this.submitForm()
    }
  },

  async submitForm() {
    if (this._isSubmitting) return
    this._isSubmitting = true

    if (!this.ensureAgreementAccepted()) {
      this._isSubmitting = false
      return
    }

    const normalizedStudent = {
      ...this.data.student,
      id_card: normalizeIdCard(this.data.student.id_card),
      phone: normalizePhone(this.data.student.phone)
    }

    this.setData({
      'student.id_card': normalizedStudent.id_card,
      'student.phone': normalizedStudent.phone,
      'fieldErrors.id_card': getIdCardError(normalizedStudent.id_card),
      'fieldErrors.phone': getPhoneError(normalizedStudent.phone)
    })

    const enabledAttachmentKeys = this.data.enabledAttachments.map(a => a.key)
    const validation = validateStudent(normalizedStudent, this.data.trainingType, enabledAttachmentKeys)

    if (!validation.valid) {
      const errorMsg = Object.values(validation.errors)[0]
      wx.showModal({
        title: '信息不完整',
        content: errorMsg,
        showCancel: false
      })
      this._isSubmitting = false
      return
    }

    wx.showLoading({ title: '更新中...' })

    try {
      const result = await api.updateStudent(this.data.studentId, {
        ...normalizedStudent,
        training_type: this.data.trainingType,
        status: 'unreviewed'
      })

      wx.hideLoading()

      if (!result.success) {
        throw new Error(result.message || '更新失败')
      }

      // 订阅授权已在点击提交时由 onTapSubmit 获取，此处不再重复请求
      wx.showModal({
        title: '更新成功',
        content: '学员信息已更新，等待重新审核',
        showCancel: false,
        success: () => {
          this.safeBackToList()
        }
      })
    } catch (err) {
      wx.hideLoading()
      console.error('更新失败:', err)
      wx.showModal({
        title: '更新失败',
        content: err.message || '请检查网络连接后重试',
        showCancel: false
      })
    } finally {
      this._isSubmitting = false
    }
  }
})
