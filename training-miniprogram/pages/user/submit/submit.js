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
const EDIT_STUDENT_ID_KEY = 'submit_edit_student_id'
const JOB_CATEGORIES_CACHE_KEY = 'job_categories_cache_v1'
const JOB_CATEGORIES_CACHE_TTL_MS = 5 * 60 * 1000
let memoryJobCategories = null
let memoryJobCategoriesAt = 0

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

function readCachedJobCategories() {
  const now = Date.now()
  if (memoryJobCategories && now - memoryJobCategoriesAt < JOB_CATEGORIES_CACHE_TTL_MS) {
    return memoryJobCategories
  }

  const cached = wx.getStorageSync(JOB_CATEGORIES_CACHE_KEY)
  if (!cached || !cached.data || !cached.updatedAt) {
    return null
  }
  if (now - Number(cached.updatedAt) >= JOB_CATEGORIES_CACHE_TTL_MS) {
    return null
  }

  memoryJobCategories = cached.data
  memoryJobCategoriesAt = Number(cached.updatedAt)
  return memoryJobCategories
}

function writeCachedJobCategories(data) {
  if (!data || typeof data !== 'object') {
    return
  }
  const updatedAt = Date.now()
  memoryJobCategories = data
  memoryJobCategoriesAt = updatedAt
  wx.setStorageSync(JOB_CATEGORIES_CACHE_KEY, {
    data,
    updatedAt
  })
}

Page({
  data: {
    editMode: false,
    showBackButton: false,
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

  onLoad(options) {
    if (options.id) {
      // 编辑模式
      this.setData({
        editMode: true,
        showBackButton: true,
        studentId: options.id
      })
    }
    this.loadJobCategories()
  },

  async onShow() {
    // 更新 TabBar 选中状态
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 0
      })
    }

    const handled = await this.handlePendingEditStudent()
    if (handled) {
      return
    }

    // 不在 onShow 中自动重置表单，避免选择/上传附件后触发页面恢复时清空已选文件。
  },

  async handlePendingEditStudent() {
    const studentId = wx.getStorageSync(EDIT_STUDENT_ID_KEY)
    if (!studentId) return false

    wx.removeStorageSync(EDIT_STUDENT_ID_KEY)

    this.setData({
      editMode: true,
      showBackButton: true,
      studentId: String(studentId)
    })

    const hasJobCategories = this.data.jobCategories && Object.keys(this.data.jobCategories).length > 0
    if (!hasJobCategories) {
      await this.loadJobCategories()
      return true
    }

    await this.loadStudentData()
    return true
  },

  resetToCreateMode() {
    this.setData({
      editMode: false,
      showBackButton: false,
      studentId: '',
      trainingType: 'special_equipment',
      fieldErrors: {
        id_card: '',
        phone: ''
      },
      student: createEmptyStudent()
    })
    this.updateJobCategoryNames()
  },

  backToList() {
    wx.switchTab({
      url: '/pages/user/list/list'
    })
  },

  async loadJobCategories() {
    try {
      const cachedCategories = readCachedJobCategories()
      if (cachedCategories) {
        this.setData({
          jobCategories: cachedCategories
        })
        this.updateJobCategoryNames()
        if (this.data.editMode) {
          await this.loadStudentData()
        }
        return
      }

      const db = wx.cloud.database()
      const res = await db.collection('config').doc('job_categories').get()

      if (res.data && res.data.data) {
        writeCachedJobCategories(res.data.data)
        this.setData({
          jobCategories: res.data.data
        })
        this.updateJobCategoryNames()

        // 如果是编辑模式，加载学员数据
        if (this.data.editMode) {
          await this.loadStudentData()
        }
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

      if (result.student) {
        const student = result.student

        // 设置培训类型
        this.setData({
          trainingType: student.training_type
        })
        this.updateJobCategoryNames()

        // 查找作业类别索引
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

        // 查找学历索引
        const educationIndex = this.data.educationOptions.indexOf(student.education)
        const normalizedIdCard = normalizeIdCard(student.id_card)
        const normalizedPhone = normalizePhone(student.phone)

        // 设置学员数据
        this.setData({
          fieldErrors: {
            id_card: getIdCardError(normalizedIdCard),
            phone: getPhoneError(normalizedPhone)
          },
          student: {
            name: student.name,
            gender: student.gender,
            education: student.education,
            educationIndex: educationIndex,
            school: student.school || '',
            major: student.major || '',
            id_card: normalizedIdCard,
            phone: normalizedPhone,
            company: student.company,
            company_address: student.company_address,
            job_category: student.job_category,
            jobCategoryIndex: jobCategoryIndex,
            exam_project: student.exam_project || '',
            examProjectIndex: examProjectIndex,
            project_code: student.project_code || '',
            examProjects: examProjects,
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
      }

      wx.hideLoading()
    } catch (err) {
      wx.hideLoading()
      console.error('加载学员数据失败:', err)
      wx.showToast({
        title: '加载失败',
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

  // 选择培训类型
  selectTrainingType(e) {
    const type = e.currentTarget.dataset.type
    this.setData({
      trainingType: type
    })
    this.updateJobCategoryNames()
  },

  // 选择性别
  selectGender(e) {
    const gender = e.currentTarget.dataset.gender
    this.setData({
      'student.gender': gender
    })
  },

  // 输入框变化
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

  // 选择器变化
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

  // 作业类别变化
  onJobCategoryChange(e) {
    const categoryIndex = parseInt(e.detail.value)
    const categories = this.data.jobCategories[this.data.trainingType]

    if (categories && categories.job_categories) {
      const category = categories.job_categories[categoryIndex]
      const examProjects = category.exam_projects || []

      // 如果只有一个操作项目,自动选中
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

  // 操作项目变化
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

  // 文件上传成功
  onFileUploaded(e) {
    const { fileType, cloudPath } = e.detail
    this.setData({
      [`student.files.${fileType}`]: cloudPath
    })
  },

  // 文件删除
  onFileDeleted(e) {
    const { fileType } = e.detail
    const files = { ...this.data.student.files }
    delete files[fileType]
    this.setData({
      'student.files': files
    })
  },

  // 提交表单
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

    // 验证数据
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

    wx.showLoading({ title: this.data.editMode ? '更新中...' : '提交中...' })

    try {
      let result

      if (this.data.editMode) {
        // 编辑模式：更新现有记录
        result = await api.updateStudent(this.data.studentId, {
          ...normalizedStudent,
          training_type: this.data.trainingType,
          status: 'unreviewed' // 重新提交后状态改为未审核
        })
      } else {
        // 新建模式：创建新记录
        result = await api.submitStudent([normalizedStudent], this.data.trainingType)
      }

      wx.hideLoading()

      if (result.success) {
        let successContent = this.data.editMode ? '学员信息已更新,等待重新审核' : '学员信息已提交,等待审核'

        if (result.sync) {
          if (result.sync.enabled) {
            if (typeof result.sync.success === 'boolean') {
              if (result.sync.success) {
                successContent += '\n原系统同步：已完成'
              } else {
                const syncMessage = result.sync.message || '同步失败，请稍后重试'
                successContent += `\n原系统同步：失败（${syncMessage}）`
              }
            } else {
              const successCount = result.sync.success_count || 0
              const failedCount = result.sync.failed_count || 0
              if (failedCount > 0) {
                successContent += `\n原系统同步：成功 ${successCount} 条，失败 ${failedCount} 条`
              } else {
                successContent += '\n原系统同步：已完成'
              }
            }
          } else {
            const reason = result.sync.disabled_reason || '未启用'
            successContent += `\n原系统同步：未启用（${reason}）`
          }
        }

        wx.showModal({
          title: this.data.editMode ? '更新成功' : '提交成功',
          content: successContent,
          showCancel: false,
          success: () => {
            // 跳转到列表页
            wx.switchTab({
              url: '/pages/user/list/list'
            })
          }
        })
      } else {
        throw new Error(result.message || (this.data.editMode ? '更新失败' : '提交失败'))
      }
    } catch (err) {
      wx.hideLoading()
      console.error(this.data.editMode ? '更新失败:' : '提交失败:', err)
      wx.showModal({
        title: this.data.editMode ? '更新失败' : '提交失败',
        content: err.message || '请检查网络连接后重试',
        showCancel: false
      })
    }
  }
})
