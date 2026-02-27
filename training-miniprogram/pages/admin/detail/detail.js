const api = require('../../../utils/api')
const { TRAINING_TYPE_LABELS, EDUCATION_OPTIONS } = require('../../../utils/constants')
const {
  validateStudent,
  normalizeIdCard,
  normalizePhone,
  getIdCardError,
  getPhoneError
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

function formatTime(value) {
  if (!value) return '-'
  const raw = String(value).trim()
  const normalized = raw.includes(' ')
    ? raw.replace(/-/g, '/')
    : raw

  let date = new Date(normalized)
  if (Number.isNaN(date.getTime()) && raw.includes(' ')) {
    date = new Date(raw.replace(' ', 'T'))
  }
  if (Number.isNaN(date.getTime())) return '-'
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
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
    examProjects: [],
    training_type: 'special_equipment',
    files: {}
  }
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
    if (!options.id) return
    this.setData({ studentId: String(options.id) })
    await this.initPage()
  },

  async initPage() {
    this.setData({ loading: true })
    await this.loadJobCategories()
    await this.loadDetail()
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

  updateJobCategoryNames() {
    const categories = this.data.jobCategories[this.data.trainingType]
    if (categories && categories.job_categories) {
      const names = categories.job_categories.map(c => c.name)
      this.setData({
        jobCategoryNames: names
      })
      return
    }

    this.setData({
      jobCategoryNames: []
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
        trainingTypeText: TRAINING_TYPE_LABELS[trainingType] || trainingType,
        statusText: STATUS_TEXT_MAP[student.status] || student.status || '-',
        submitTimeText: formatTime(student.created_at),
        reviewTimeText: formatTime(student.reviewed_at),
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
          examProjects,
          training_type: trainingType,
          files: {
            photo: downloadUrls.photo_path || student.photo_path || student.files?.photo || '',
            diploma: downloadUrls.diploma_path || student.diploma_path || student.files?.diploma || '',
            id_card_front: downloadUrls.id_card_front_path || student.id_card_front_path || student.files?.id_card_front || '',
            id_card_back: downloadUrls.id_card_back_path || student.id_card_back_path || student.files?.id_card_back || '',
            hukou_residence: downloadUrls.hukou_residence_path || student.hukou_residence_path || student.files?.hukou_residence || '',
            hukou_personal: downloadUrls.hukou_personal_path || student.hukou_personal_path || student.files?.hukou_personal || ''
          }
        },
        loading: false
      })

      this.updateJobCategoryNames()
    } catch (err) {
      console.error('加载审核详情失败:', err)
      this.setData({ loading: false })
      wx.showToast({ title: err.message || '加载失败', icon: 'none' })
    }
  },

  selectTrainingType(e) {
    const type = e.currentTarget.dataset.type
    if (!type || type === this.data.trainingType) return

    this.setData({
      trainingType: type,
      trainingTypeText: TRAINING_TYPE_LABELS[type] || type,
      'editStudent.training_type': type,
      'editStudent.job_category': '',
      'editStudent.jobCategoryIndex': -1,
      'editStudent.exam_project': '',
      'editStudent.examProjectIndex': -1,
      'editStudent.project_code': '',
      'editStudent.examProjects': []
    })
    this.updateJobCategoryNames()
  },

  onJobCategoryChange(e) {
    const categoryIndex = parseInt(e.detail.value)
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
        'editStudent.project_code': examProjects[0].code
      })
      return
    }

    this.setData({
      'editStudent.job_category': category.name,
      'editStudent.jobCategoryIndex': categoryIndex,
      'editStudent.examProjects': examProjects,
      'editStudent.exam_project': '',
      'editStudent.examProjectIndex': -1,
      'editStudent.project_code': ''
    })
  },

  onExamProjectChange(e) {
    const projectIndex = parseInt(e.detail.value)
    const project = this.data.editStudent.examProjects[projectIndex]
    if (!project) return

    this.setData({
      'editStudent.exam_project': project.name,
      'editStudent.examProjectIndex': projectIndex,
      'editStudent.project_code': project.code
    })
  },

  selectGender(e) {
    const gender = e.currentTarget.dataset.gender
    this.setData({
      'editStudent.gender': gender
    })
  },

  onInputChange(e) {
    const { field } = e.currentTarget.dataset
    let value = e.detail.value
    if (!field) return

    if (field === 'id_card') {
      value = normalizeIdCard(value).slice(0, 18)
    }
    if (field === 'phone') {
      value = normalizePhone(value).slice(0, 11)
    }

    this.setData({
      [`editStudent.${field}`]: value
    })

    if (field === 'id_card') {
      this.setData({
        'fieldErrors.id_card': getIdCardError(value)
      })
    }

    if (field === 'phone') {
      this.setData({
        'fieldErrors.phone': getPhoneError(value)
      })
    }
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
    const index = parseInt(e.detail.value)
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
    const files = { ...(this.data.editStudent.files || {}) }
    delete files[fileType]
    this.setData({
      'editStudent.files': files
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

    const validation = validateStudent(normalizedStudent, this.data.trainingType)
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

    const confirmed = await this.confirmAction('驳回记录', '确认驳回该记录吗？')
    if (!confirmed) return

    this.setData({
      actionLoading: true,
      actionType: 'reject'
    })
    wx.showLoading({ title: '处理中...' })
    try {
      await api.reviewStudent(this.data.studentId, 'reject')
      wx.hideLoading()
      wx.showToast({ title: '已驳回', icon: 'success' })
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
  }
})
