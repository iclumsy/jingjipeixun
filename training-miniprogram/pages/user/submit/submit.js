// pages/user/submit/submit.js
const api = require('../../../utils/api')
const {
  validateStudent,
  normalizeIdCard,
  normalizePhone,
  getIdCardError,
  getPhoneError
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

const FORCE_CREATE_SUBMIT_KEY = 'submit_force_create_mode'

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
    examProjects: [],
    files: {
      photo: '',
      diploma: '',
      id_card_front: '',
      id_card_back: '',
      hukou_residence: '',
      hukou_personal: ''
    }
  }
}

Page({
  data: {
    trainingType: 'special_equipment',
    agreementChecked: false,
    educationOptions: EDUCATION_OPTIONS,
    fieldErrors: {
      id_card: '',
      phone: ''
    },
    jobCategories: {},
    jobCategoryNames: [],
    student: createEmptyStudent()
  },

  onLoad() {
    this.setData({
      agreementChecked: hasAcceptedLatestAgreement()
    })
    this.loadJobCategories()
  },

  async onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 0
      })
    }

    await this.handleForceCreateEntry()
  },

  async handleForceCreateEntry() {
    const shouldForceCreate = wx.getStorageSync(FORCE_CREATE_SUBMIT_KEY) === true
    if (!shouldForceCreate) return false

    wx.removeStorageSync(FORCE_CREATE_SUBMIT_KEY)
    this.resetToCreateMode()
    return true
  },

  resetToCreateMode() {
    const nextType = 'special_equipment'
    this.setData({
      trainingType: nextType,
      jobCategoryNames: this.getJobCategoryNames(nextType),
      fieldErrors: {
        id_card: '',
        phone: ''
      },
      student: createEmptyStudent()
    })
  },

  forceEnterCreateMode() {
    wx.removeStorageSync(FORCE_CREATE_SUBMIT_KEY)
    this.resetToCreateMode()
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
      wx.showToast({
        title: '加载配置失败',
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
    const type = e.currentTarget.dataset.type
    if (!type || type === this.data.trainingType) return

    const nextJobCategoryNames = this.getJobCategoryNames(type)
    this.setData({
      trainingType: type,
      jobCategoryNames: nextJobCategoryNames,
      'student.job_category': '',
      'student.jobCategoryIndex': -1,
      'student.examProjects': [],
      'student.exam_project': '',
      'student.examProjectIndex': -1,
      'student.project_code': ''
    })
  },

  selectGender(e) {
    const gender = e.currentTarget.dataset.gender
    this.setData({
      'student.gender': gender
    })
  },

  onInputChange(e) {
    const { field } = e.currentTarget.dataset
    let value = e.detail.value

    if (field === 'id_card') {
      value = normalizeIdCard(value).slice(0, 18)
    }

    if (field === 'phone') {
      value = normalizePhone(value).slice(0, 11)
    }

    this.setData({
      [`student.${field}`]: value
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
      'fieldErrors.id_card': getIdCardError(this.data.student.id_card)
    })
  },

  onPhoneBlur() {
    this.setData({
      'fieldErrors.phone': getPhoneError(this.data.student.phone)
    })
  },

  onPickerChange(e) {
    const { field } = e.currentTarget.dataset
    const pickerIndex = parseInt(e.detail.value)

    if (field === 'education') {
      this.setData({
        'student.education': this.data.educationOptions[pickerIndex],
        'student.educationIndex': pickerIndex
      })
    }
  },

  onJobCategoryChange(e) {
    const categoryIndex = parseInt(e.detail.value)
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
          'student.project_code': examProjects[0].code
        })
      } else {
        this.setData({
          'student.job_category': category.name,
          'student.jobCategoryIndex': categoryIndex,
          'student.examProjects': examProjects,
          'student.exam_project': '',
          'student.examProjectIndex': -1,
          'student.project_code': ''
        })
      }
    }
  },

  onExamProjectChange(e) {
    const projectIndex = parseInt(e.detail.value)
    const project = this.data.student.examProjects[projectIndex]

    if (project) {
      this.setData({
        'student.exam_project': project.name,
        'student.examProjectIndex': projectIndex,
        'student.project_code': project.code
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
    const values = e.detail.value || []
    const checked = values.includes('agree')
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
        content: '提交前请先同意《用户服务协议》和《隐私政策》。',
        showCancel: false
      })
      return false
    }

    if (!hasAcceptedLatestAgreement()) {
      markAgreementAccepted()
    }
    return true
  },

  async submitForm() {
    if (!this.ensureAgreementAccepted()) return

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

    const validation = validateStudent(normalizedStudent, this.data.trainingType)

    if (!validation.valid) {
      const errorMsg = Object.values(validation.errors)[0]
      wx.showModal({
        title: '信息不完整',
        content: errorMsg,
        showCancel: false
      })
      return
    }

    wx.showLoading({ title: '提交中...' })

    try {
      const result = await api.submitStudent([normalizedStudent], this.data.trainingType)
      wx.hideLoading()

      if (!result.success) {
        throw new Error(result.message || '提交失败')
      }

      let successContent = '学员信息已提交，等待审核'
      if (result.sync) {
        if (result.sync.enabled) {
          if (typeof result.sync.success === 'boolean') {
            successContent += result.sync.success
              ? '\n原系统同步：已完成'
              : `\n原系统同步：失败（${result.sync.message || '同步失败，请稍后重试'}）`
          } else {
            const successCount = result.sync.success_count || 0
            const failedCount = result.sync.failed_count || 0
            successContent += failedCount > 0
              ? `\n原系统同步：成功 ${successCount} 条，失败 ${failedCount} 条`
              : '\n原系统同步：已完成'
          }
        } else {
          successContent += `\n原系统同步：未启用（${result.sync.disabled_reason || '未启用'}）`
        }
      }

      wx.showModal({
        title: '提交成功',
        content: successContent,
        showCancel: false,
        success: () => {
          wx.switchTab({
            url: '/pages/user/list/list'
          })
        }
      })
    } catch (err) {
      wx.hideLoading()
      console.error('提交失败:', err)
      wx.showModal({
        title: '提交失败',
        content: err.message || '请检查网络连接后重试',
        showCancel: false
      })
    }
  }
})
