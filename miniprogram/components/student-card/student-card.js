// components/student-card/student-card.js
// 渲染优先读后端 enrich 字段（statusText/statusClass/tags），
// 字段缺失时回退到本地常量映射，保证旧响应仍可显示。
const { STATUS_LABELS, TRAINING_TYPE_LABELS } = require('../../utils/constants')
const { formatDateTime } = require('../../utils/page-helpers')

Component({
  properties: {
    student: {
      type: Object,
      value: {}
    }
  },

  data: {
    statusText: '',
    statusClass: '',
    trainingTypeText: '',
    createTime: '',
    tags: []
  },

  observers: {
    'student': function(student) {
      if (!student) return
      const localTags = []
      if (
        student.training_type === 'special_equipment' &&
        student.application_type === 'renewal'
      ) {
        localTags.push({ text: '复审', color: '#e65100', bg: '#fff3e0' })
      }
      this.setData({
        statusText: student.statusText || STATUS_LABELS[student.status] || student.status || '-',
        statusClass: student.statusClass || student.status || '',
        trainingTypeText: student.trainingTypeText || TRAINING_TYPE_LABELS[student.training_type] || student.training_type || '-',
        createTime: formatDateTime(student.created_at),
        tags: Array.isArray(student.tags) ? student.tags : localTags
      })
    }
  },

  methods: {
    onTap() {
      const student = this.data.student || {}
      const studentId = student._id || student.id || ''
      this.triggerEvent('cardtap', {
        student,
        id: studentId
      })
    }
  }
})
