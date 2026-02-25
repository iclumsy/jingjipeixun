// utils/constants.js
// 常量定义

// 培训类型
const TRAINING_TYPES = {
  SPECIAL_OPERATION: 'special_operation',
  SPECIAL_EQUIPMENT: 'special_equipment'
}

// 培训类型标签
const TRAINING_TYPE_LABELS = {
  special_operation: '特种作业',
  special_equipment: '特种设备'
}

// 审核状态
const STUDENT_STATUS = {
  UNREVIEWED: 'unreviewed',
  REVIEWED: 'reviewed',
  REJECTED: 'rejected'
}

// 审核状态标签
const STATUS_LABELS = {
  unreviewed: '未审核',
  reviewed: '已审核',
  rejected: '已驳回'
}

// 性别选项
const GENDER_OPTIONS = ['男', '女']

// 文化程度选项
const EDUCATION_OPTIONS = [
  '初中',
  '高中或同等学历',
  '中专或同等学历',
  '专科或同等学历',
  '本科或同等学历',
  '研究生及以上'
]

// 文件类型
const FILE_TYPES = {
  PHOTO: 'photo',
  DIPLOMA: 'diploma',
  ID_CARD_FRONT: 'id_card_front',
  ID_CARD_BACK: 'id_card_back',
  HUKOU_RESIDENCE: 'hukou_residence',
  HUKOU_PERSONAL: 'hukou_personal'
}

// 文件类型标签
const FILE_TYPE_LABELS = {
  photo: '个人照片',
  diploma: '学历证书',
  id_card_front: '身份证正面',
  id_card_back: '身份证反面',
  hukou_residence: '户口本户籍页',
  hukou_personal: '户口本个人页'
}

// 文件大小限制（字节）
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

// 允许的文件类型
const ALLOWED_FILE_TYPES = ['image/jpeg', 'image/png', 'image/jpg']

// 分页配置
const PAGE_SIZE = 20

// 云存储路径前缀
const CLOUD_STORAGE_PREFIX = 'cloud://'

// 需要生成体检表的项目代码
const HEALTH_CHECK_PROJECTS = ['N1', 'G3']

module.exports = {
  TRAINING_TYPES,
  TRAINING_TYPE_LABELS,
  STUDENT_STATUS,
  STATUS_LABELS,
  GENDER_OPTIONS,
  EDUCATION_OPTIONS,
  FILE_TYPES,
  FILE_TYPE_LABELS,
  MAX_FILE_SIZE,
  ALLOWED_FILE_TYPES,
  PAGE_SIZE,
  CLOUD_STORAGE_PREFIX,
  HEALTH_CHECK_PROJECTS
}
