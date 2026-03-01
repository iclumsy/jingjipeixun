// utils/constants.js
// 仅保留当前业务实际使用的常量

// 培训类型标签
const TRAINING_TYPE_LABELS = {
  special_operation: '特种作业',
  special_equipment: '特种设备'
}

// 审核状态标签
const STATUS_LABELS = {
  unreviewed: '未审核',
  reviewed: '已审核',
  rejected: '已驳回'
}

// 文化程度选项
const EDUCATION_OPTIONS = [
  '初中',
  '高中或同等学历',
  '中专或同等学历',
  '专科或同等学历',
  '本科或同等学历',
  '研究生及以上'
]

// 文件大小限制（字节）
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

module.exports = {
  TRAINING_TYPE_LABELS,
  STATUS_LABELS,
  EDUCATION_OPTIONS,
  MAX_FILE_SIZE
}
