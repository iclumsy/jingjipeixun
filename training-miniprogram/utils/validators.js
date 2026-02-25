// utils/validators.js
// 表单验证工具函数

/**
 * 验证身份证号
 * @param {string} idCard - 身份证号
 * @returns {boolean}
 */
function validateIdCard(idCard) {
  if (!idCard) return false

  // 18位身份证号，最后一位可以是X或x
  const pattern = /^\d{17}[\dXx]$/
  return pattern.test(idCard)
}

/**
 * 验证手机号
 * @param {string} phone - 手机号
 * @returns {boolean}
 */
function validatePhone(phone) {
  if (!phone) return false

  // 11位数字
  const pattern = /^\d{11}$/
  return pattern.test(phone)
}

/**
 * 验证性别
 * @param {string} gender - 性别
 * @returns {boolean}
 */
function validateGender(gender) {
  return gender === '男' || gender === '女'
}

/**
 * 验证必填字段
 * @param {any} value - 字段值
 * @returns {boolean}
 */
function validateRequired(value) {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim().length > 0
  return true
}

/**
 * 验证学员数据
 * @param {object} student - 学员数据
 * @param {string} trainingType - 培训类型
 * @returns {object} { valid: boolean, errors: object }
 */
function validateStudent(student, trainingType) {
  const errors = {}

  // 必填字段验证
  if (!validateRequired(student.name)) {
    errors.name = '请输入姓名'
  }

  if (!validateGender(student.gender)) {
    errors.gender = '请选择性别'
  }

  if (!validateRequired(student.education)) {
    errors.education = '请选择文化程度'
  }

  if (!validateIdCard(student.id_card)) {
    errors.id_card = '请输入正确的身份证号（18位）'
  }

  if (!validatePhone(student.phone)) {
    errors.phone = '请输入正确的手机号（11位）'
  }

  if (!validateRequired(student.company)) {
    errors.company = '请输入单位名称'
  }

  if (!validateRequired(student.company_address)) {
    errors.company_address = '请输入单位地址'
  }

  if (!validateRequired(student.job_category)) {
    errors.job_category = '请选择作业类别'
  }

  // 附件验证
  const requiredFiles = getRequiredFiles(trainingType)
  requiredFiles.forEach(fileType => {
    if (!student.files || !student.files[fileType]) {
      errors[fileType] = `请上传${getFileLabel(fileType)}`
    }
  })

  return {
    valid: Object.keys(errors).length === 0,
    errors
  }
}

/**
 * 获取必填附件列表
 * @param {string} trainingType - 培训类型
 * @returns {array}
 */
function getRequiredFiles(trainingType) {
  if (trainingType === 'special_operation') {
    return ['diploma', 'id_card_front', 'id_card_back']
  } else if (trainingType === 'special_equipment') {
    return ['photo', 'diploma', 'id_card_front', 'id_card_back', 'hukou_residence', 'hukou_personal']
  }
  return []
}

/**
 * 获取文件类型标签
 * @param {string} fileType - 文件类型
 * @returns {string}
 */
function getFileLabel(fileType) {
  const labels = {
    photo: '个人照片',
    diploma: '学历证书',
    id_card_front: '身份证正面',
    id_card_back: '身份证反面',
    hukou_residence: '户口本户籍页',
    hukou_personal: '户口本个人页'
  }
  return labels[fileType] || fileType
}

/**
 * 验证文件大小
 * @param {number} size - 文件大小（字节）
 * @param {number} maxSize - 最大大小（字节）
 * @returns {boolean}
 */
function validateFileSize(size, maxSize = 10 * 1024 * 1024) {
  return size <= maxSize
}

/**
 * 验证文件类型
 * @param {string} filePath - 文件路径
 * @returns {boolean}
 */
function validateFileType(filePath) {
  const allowedTypes = ['.jpg', '.jpeg', '.png']
  const ext = filePath.substring(filePath.lastIndexOf('.')).toLowerCase()
  return allowedTypes.includes(ext)
}

module.exports = {
  validateIdCard,
  validatePhone,
  validateGender,
  validateRequired,
  validateStudent,
  getRequiredFiles,
  getFileLabel,
  validateFileSize,
  validateFileType
}
