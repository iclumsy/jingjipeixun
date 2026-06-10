/**
 * 小程序常量定义。
 *
 * 集中管理业务使用的常量值，包括：
 * - 培训类型中英文标签映射
 * - 审核状态中英文标签映射
 * - 文化程度可选项列表
 * - 文件大小限制
 */

// 培训类型标签
const TRAINING_TYPE_LABELS = {
  special_operation: '特种作业',
  special_equipment: '特种设备'
}

// 审核状态标签（仅作为后端 statusText 字段缺失时的本地兜底）
// 状态新增/调整请改后端 services/student_serializer.py，前端无需发版
const STATUS_LABELS = {
  unreviewed: '待审核',
  reviewed: '已审核',
  registered: '已报名',
  rejected: '已驳回',
  exam_passed: '考试通过'
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
const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB

module.exports = {
  TRAINING_TYPE_LABELS,
  STATUS_LABELS,
  EDUCATION_OPTIONS,
  MAX_FILE_SIZE
}
