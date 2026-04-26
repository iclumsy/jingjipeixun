// pages/user/detail/detail.js
// 状态文案/提示/培训类型文案优先读后端 enrich 字段，缺失时回退到本地常量
const api = require('../../../utils/api')
const { STATUS_LABELS, TRAINING_TYPE_LABELS } = require('../../../utils/constants')
const { formatDateTime } = require('../../../utils/page-helpers')

// 仅作为后端 statusHint 字段缺失时的本地兜底；状态/文案变更请改后端
const STATUS_HINTS_FALLBACK = {
  unreviewed: '资料已提交，正在等待管理员审核',
  reviewed: '资料已审核通过，可在后台继续办理',
  registered: '已提交报名到省网平台',
  rejected: '资料已被驳回，可修改后重新提交'
}

const ATTACHMENT_FIELDS = [
  'photo_path',
  'diploma_path',
  'id_card_front_path',
  'id_card_back_path',
  'hukou_residence_path',
  'hukou_personal_path',
  'certificate_info_page_path',
  'certificate_records_page_path'
]

function isSafePreviewUrl(value = '') {
  const raw = String(value || '').trim()
  if (!raw) return false
  return (
    /^https?:\/\//i.test(raw) ||
    /^wxfile:\/\//i.test(raw) ||
    /^data:image\//i.test(raw) ||
    /^\/(?!\/)/.test(raw)
  )
}

async function resolvePreviewPath(url) {
  const raw = String(url || '').trim()
  if (!raw) return ''
  return isSafePreviewUrl(raw) ? raw : ''
}

Page({
  data: {
    studentId: '',
    student: null,
    downloadUrls: {},
    previewUrls: {},
    statusText: '',
    statusHint: '',
    statusClass: '',
    trainingTypeText: '',
    applicationTypeText: '',
    tags: [],
    canEdit: false,
    createTime: '',
    loading: true
  },

  onLoad(options) {
    if (options.id) {
      this.setData({ studentId: options.id })
      this.loadDetail()
    }
  },

  async loadDetail() {
    this.setData({ loading: true })

    try {
      const result = await api.getStudentDetail(this.data.studentId)

      if (result.student) {
        const downloadUrls = result.downloadUrls || {}
        const previewUrls = await this.buildPreviewUrls(downloadUrls)
        const s = result.student
        // 编辑权限优先取后端 actions.canEdit
        const canEdit = (s.actions && typeof s.actions.canEdit === 'boolean')
          ? s.actions.canEdit
          : (s.status === 'rejected')

        this.setData({
          student: s,
          downloadUrls,
          previewUrls,
          // 全部派生字段优先读后端，缺失时回退本地映射
          statusText: s.statusText || STATUS_LABELS[s.status] || s.status || '-',
          statusHint: (typeof s.statusHint === 'string' ? s.statusHint : '') || STATUS_HINTS_FALLBACK[s.status] || '',
          statusClass: s.statusClass || s.status || '',
          trainingTypeText: s.trainingTypeText || TRAINING_TYPE_LABELS[s.training_type] || s.training_type || '-',
          applicationTypeText: s.applicationTypeText || (s.application_type === 'renewal' ? '复审' : '新考证'),
          tags: Array.isArray(s.tags) ? s.tags : [],
          canEdit,
          createTime: formatDateTime(s.created_at),
          loading: false
        })
      }
    } catch (err) {
      console.error('加载详情失败:', err)
      this.setData({ loading: false })
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    }
  },

  async buildPreviewUrls(downloadUrls) {
    const previewUrls = {}
    for (const field of ATTACHMENT_FIELDS) {
      const url = downloadUrls[field]
      if (!url) continue
      try {
        previewUrls[field] = await resolvePreviewPath(url)
      } catch (err) {
        previewUrls[field] = ''
      }
    }
    return previewUrls
  },

  previewImage(e) {
    const { url } = e.currentTarget.dataset
    const urls = Object.values(this.data.downloadUrls)
      .map(item => String(item || '').trim())
      .filter(isSafePreviewUrl)
    const current = isSafePreviewUrl(url) ? url : (urls[0] || '')

    if (!current || urls.length === 0) {
      wx.showToast({
        title: '附件地址不可用',
        icon: 'none'
      })
      return
    }

    wx.previewImage({
      urls,
      current
    })
  },

  editStudent() {
    wx.navigateTo({
      url: `/pages/user/edit/edit?id=${this.data.studentId}`,
      fail: () => {
        wx.showToast({
          title: '跳转失败，请重试',
          icon: 'none'
        })
      }
    })
  }
})
