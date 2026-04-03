// components/student-card/student-card.js
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
    createTime: ''
  },

  observers: {
    'student': function(student) {
      if (student) {
        this.setData({
          statusText: STATUS_LABELS[student.status] || student.status,
          statusClass: student.status,
          trainingTypeText: TRAINING_TYPE_LABELS[student.training_type] || student.training_type,
          createTime: formatDateTime(student.created_at)
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
    }
  }
})
