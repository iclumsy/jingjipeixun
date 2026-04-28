Component({
  options: {
    styleIsolation: 'shared'
  },

  properties: {
    trainingType: {
      type: String,
      value: 'special_equipment'
    },
    applicationType: {
      type: String,
      value: 'new_exam'
    },
    formData: {
      type: Object,
      value: {}
    },
    educationOptions: {
      type: Array,
      value: []
    },
    jobCategoryNames: {
      type: Array,
      value: []
    },
    fieldErrors: {
      type: Object,
      value: {}
    },
    showAgreement: {
      type: Boolean,
      value: false
    },
    agreementChecked: {
      type: Boolean,
      value: false
    },
    showSubmit: {
      type: Boolean,
      value: false
    },
    submitFixed: {
      type: Boolean,
      value: false
    },
    submitText: {
      type: String,
      value: '提交信息'
    },
    trainingCardTitle: {
      type: String,
      value: '培训类型'
    },
    attachmentsTip: {
      type: String,
      value: '请上传清晰、完整的原件照片，避免反光和裁切。'
    },
    // 当前培训类型已启用的附件列表，由父页面从后台拉取后传入
    // 格式: [{key: 'photo', label: '个人照片'}, ...]
    enabledAttachments: {
      type: Array,
      value: []
    },
    // 是否禁止切换培训类型（驳回记录编辑时使用）
    disableTrainingType: {
      type: Boolean,
      value: false
    }
  },

  observers: {
    'enabledAttachments': function (attachments) {
      if (!attachments) return
      
      const idCardAttachments = attachments.filter(a => a.key === 'id_card_front' || a.key === 'id_card_back')
      const hukouAttachments = attachments.filter(a => a.key === 'hukou_residence' || a.key === 'hukou_personal')
      const educationAttachments = attachments.filter(a => a.key === 'diploma')
      const otherAttachments = attachments.filter(a => 
        a.key !== 'id_card_front' && a.key !== 'id_card_back' && 
        a.key !== 'hukou_residence' && a.key !== 'hukou_personal' && 
        a.key !== 'diploma'
      )

      this.setData({
        idCardAttachments,
        hukouAttachments,
        educationAttachments,
        otherAttachments
      })
    }
  },

  methods: {
    onSelectTrainingType(e) {
      if (this.data.disableTrainingType) return
      const type = e.currentTarget?.dataset?.type || ''
      this.triggerEvent('trainingtypechange', { type })
    },

    onSelectApplicationType(e) {
      if (this.data.disableTrainingType) return
      const type = e.currentTarget?.dataset?.type || 'new_exam'
      this.triggerEvent('applicationtypechange', { type })
    },

    onSelectGender(e) {
      const gender = e.currentTarget?.dataset?.gender || ''
      this.triggerEvent('genderchange', { gender })
    },

    onInputChange(e) {
      const field = e.currentTarget?.dataset?.field || ''
      const value = e.detail?.value
      this.triggerEvent('inputchange', { field, value })
    },

    onIdCardBlur() {
      this.triggerEvent('idcardblur')
    },

    onPhoneBlur() {
      this.triggerEvent('phoneblur')
    },

    onEducationChange(e) {
      const index = Number(e.detail?.value)
      this.triggerEvent('educationchange', { index })
    },

    onJobCategoryChange(e) {
      if (this.data.disableTrainingType) return
      const index = Number(e.detail?.value)
      this.triggerEvent('jobcategorychange', { index })
    },

    onExamProjectChange(e) {
      if (this.data.disableTrainingType) return
      const index = Number(e.detail?.value)
      this.triggerEvent('examprojectchange', { index })
    },

    onFileUploaded(e) {
      this.triggerEvent('fileuploaded', e.detail || {})
    },

    onFileDeleted(e) {
      this.triggerEvent('filedeleted', e.detail || {})
    },

    onAgreementChange(e) {
      const values = e.detail?.value || []
      this.triggerEvent('agreementchange', {
        values,
        checked: values.includes('agree')
      })
    },

    openUserAgreement() {
      this.triggerEvent('openagreement')
    },

    openPrivacyPolicy() {
      this.triggerEvent('openprivacy')
    },

    onSwapTap(e) {
      const pair = e.currentTarget?.dataset?.pair || ''
      this.triggerEvent('swapmaterials', { pair })
    },

    onSubmitTap() {
      this.triggerEvent('submit')
    }
  }
})
