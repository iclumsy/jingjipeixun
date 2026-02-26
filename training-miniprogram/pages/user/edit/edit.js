// pages/user/edit/edit.js
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
    files: {}
  }
}

Page({
  data: {
    studentId: '',
    trainingType: 'special_equipment',
    educationOptions: EDUCATION_OPTIONS,
    fieldErrors: {
      id_card: '',
      phone: ''
    },
    jobCategories: {},
    jobCategoryNames: [],
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
      studentId
    })

    await this.loadJobCategories()
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

      this.setData({
        trainingType: student.training_type
      })
      this.updateJobCategoryNames()

      const categories = this.data.jobCategories[student.training_type]
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
          examProjects,
          files: {
            photo: downloadUrls.photo_path || student.photo_path || student.files?.photo || student.files?.photo_path || '',
            diploma: downloadUrls.diploma_path || student.diploma_path || student.files?.diploma || student.files?.diploma_path || '',
            id_card_front: downloadUrls.id_card_front_path || student.id_card_front_path || student.files?.id_card_front || student.files?.id_card_front_path || '',
            id_card_back: downloadUrls.id_card_back_path || student.id_card_back_path || student.files?.id_card_back || student.files?.id_card_back_path || '',
            hukou_residence: downloadUrls.hukou_residence_path || student.hukou_residence_path || student.files?.hukou_residence || student.files?.hukou_residence_path || '',
            hukou_personal: downloadUrls.hukou_personal_path || student.hukou_personal_path || student.files?.hukou_personal || student.files?.hukou_personal_path || ''
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

  updateJobCategoryNames() {
    const categories = this.data.jobCategories[this.data.trainingType]
    if (categories && categories.job_categories) {
      const names = categories.job_categories.map(c => c.name)
      this.setData({
        jobCategoryNames: names
      })
    }
  },

  selectTrainingType(e) {
    const type = e.currentTarget.dataset.type
    this.setData({
      trainingType: type
    })
    this.updateJobCategoryNames()
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
    const files = { ...this.data.student.files }
    delete files[fileType]
    this.setData({
      'student.files': files
    })
  },

  async submitForm() {
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
    }
  }
})
