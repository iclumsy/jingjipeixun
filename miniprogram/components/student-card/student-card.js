// components/student-card/student-card.js
const { STATUS_LABELS, TRAINING_TYPE_LABELS } = require('../../utils/constants')

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
    createTime: ''
  },

  observers: {
    'student': function(student) {
      if (student) {
        this.setData({
          statusText: STATUS_LABELS[student.status] || student.status,
          statusClass: student.status,
          trainingTypeText: TRAINING_TYPE_LABELS[student.training_type] || student.training_type,
          createTime: this.formatTime(student.created_at)
        })
      }
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
    },

    formatTime(time) {
      if (!time) return ''

      const raw = String(time).trim()
      const normalized = raw.includes(' ')
        ? raw.replace(/-/g, '/')
        : raw

      let date = new Date(normalized)
      if (Number.isNaN(date.getTime()) && raw.includes(' ')) {
        date = new Date(raw.replace(' ', 'T'))
      }
      if (Number.isNaN(date.getTime())) return ''
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hour = String(date.getHours()).padStart(2, '0')
      const minute = String(date.getMinutes()).padStart(2, '0')

      return `${year}-${month}-${day} ${hour}:${minute}`
    }
  }
})
