// utils/api.js
// API 封装

const app = getApp()

/**
 * 调用云函数
 * @param {string} name - 云函数名称
 * @param {object} data - 参数
 * @returns {Promise}
 */
function callFunction(name, data = {}) {
  return new Promise((resolve, reject) => {
    wx.cloud.callFunction({
      name,
      data,
      success: res => {
        if (res.result && res.result.error) {
          reject(res.result)
        } else {
          resolve(res.result)
        }
      },
      fail: err => {
        console.error(`云函数 ${name} 调用失败:`, err)
        reject(err)
      }
    })
  })
}

/**
 * 用户登录
 * @returns {Promise}
 */
function login() {
  return callFunction('login')
}

/**
 * 提交学员信息
 * @param {array} students - 学员数组
 * @param {string} trainingType - 培训类型
 * @returns {Promise}
 */
function submitStudent(students, trainingType) {
  return callFunction('submitStudent', {
    students,
    training_type: trainingType
  })
}

/**
 * 获取学员列表
 * @param {object} params - 查询参数
 * @returns {Promise}
 */
function getStudents(params = {}) {
  return callFunction('getStudents', params)
}

/**
 * 获取学员详情
 * @param {string} studentId - 学员ID
 * @returns {Promise}
 */
function getStudentDetail(studentId) {
  return callFunction('getStudentDetail', {
    student_id: studentId
  })
}

/**
 * 审核学员
 * @param {string} studentId - 学员ID
 * @param {string} action - 操作（approve/reject）
 * @returns {Promise}
 */
function reviewStudent(studentId, action) {
  return callFunction('reviewStudent', {
    student_id: studentId,
    action
  })
}

/**
 * 批量审核
 * @param {array} studentIds - 学员ID数组
 * @param {string} action - 操作（approve/reject）
 * @returns {Promise}
 */
function batchReview(studentIds, action) {
  return callFunction('batchReview', {
    student_ids: studentIds,
    action
  })
}

/**
 * 导出Excel
 * @param {object} params - 筛选参数
 * @returns {Promise}
 */
function exportExcel(params = {}) {
  return callFunction('exportExcel', params)
}

/**
 * 生成体检表
 * @param {string} studentId - 学员ID
 * @returns {Promise}
 */
function generateHealthCheck(studentId) {
  return callFunction('generateHealthCheck', {
    student_id: studentId
  })
}

/**
 * 下载附件压缩包
 * @param {string} studentId - 学员ID
 * @returns {Promise}
 */
function downloadAttachments(studentId) {
  return callFunction('downloadAttachments', {
    student_id: studentId
  })
}

/**
 * 更新学员信息
 * @param {string} studentId - 学员ID
 * @param {object} updates - 更新数据
 * @returns {Promise}
 */
function updateStudent(studentId, updates) {
  return callFunction('updateStudent', {
    student_id: studentId,
    updates
  })
}

/**
 * 删除学员
 * @param {string} studentId - 学员ID
 * @returns {Promise}
 */
function deleteStudent(studentId) {
  return callFunction('deleteStudent', {
    student_id: studentId
  })
}

/**
 * 获取公司列表
 * @param {object} params - 筛选参数
 * @returns {Promise}
 */
function getCompanies(params = {}) {
  return callFunction('getCompanies', params)
}

/**
 * 上传文件到云存储
 * @param {string} cloudPath - 云存储路径
 * @param {string} filePath - 本地文件路径
 * @param {function} onProgress - 进度回调
 * @returns {Promise}
 */
function uploadFile(cloudPath, filePath, onProgress) {
  return new Promise((resolve, reject) => {
    const uploadTask = wx.cloud.uploadFile({
      cloudPath,
      filePath,
      success: res => {
        resolve(res)
      },
      fail: err => {
        console.error('文件上传失败:', err)
        reject(err)
      }
    })

    if (onProgress) {
      uploadTask.onProgressUpdate(onProgress)
    }
  })
}

/**
 * 下载文件
 * @param {string} fileID - 云文件ID
 * @returns {Promise}
 */
function downloadFile(fileID) {
  return new Promise((resolve, reject) => {
    wx.cloud.downloadFile({
      fileID,
      success: res => {
        resolve(res)
      },
      fail: err => {
        console.error('文件下载失败:', err)
        reject(err)
      }
    })
  })
}

/**
 * 获取临时文件链接
 * @param {array} fileList - 文件ID数组
 * @returns {Promise}
 */
function getTempFileURL(fileList) {
  return new Promise((resolve, reject) => {
    wx.cloud.getTempFileURL({
      fileList,
      success: res => {
        resolve(res)
      },
      fail: err => {
        console.error('获取临时链接失败:', err)
        reject(err)
      }
    })
  })
}

module.exports = {
  callFunction,
  login,
  submitStudent,
  getStudents,
  getStudentDetail,
  reviewStudent,
  batchReview,
  exportExcel,
  generateHealthCheck,
  downloadAttachments,
  updateStudent,
  deleteStudent,
  getCompanies,
  uploadFile,
  downloadFile,
  getTempFileURL
}
