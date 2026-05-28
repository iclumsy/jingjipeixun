const api = require('../../../utils/api')
const practice = require('../../../utils/practice')

Page({
  data: {
    loading: true,
    record: null,
    questions: [],
    displayQuestions: [],
    onlyWrong: false,
    showCard: false
  },

  onLoad(options) {
    const recordId = Number(options.recordId || 0)
    this.loadDetail(recordId)
  },

  async loadDetail(recordId) {
    this.setData({ loading: true })
    try {
      const res = await api.getExamRecordDetail(recordId)
      if (res && res.success) {
        const record = res.record || {}
        const dur = record.duration_seconds || 0
        const min = Math.floor(dur / 60)
        const sec = dur % 60
        record.durationText = min > 0 ? `${min}分${sec}秒` : `${sec}秒`
        
        if (record.created_at && record.created_at.length > 16) {
          record.dateText = record.created_at.substring(0, 16)
        } else {
          record.dateText = record.created_at || ''
        }

        const answers = res.answers || {}
        const rawQuestions = res.questions || []
        
        const formattedQuestions = rawQuestions.map((q, idx) => {
          const type = practice.normalizeQuestionType(q)
          const studentAns = answers[String(q.id)] || []
          const correctAns = practice.normalizeAnswer(q.answer)
          
          const isCorrect = practice.isCorrectAnswer(q, studentAns)
          
          const rawOptions = practice.formatOptionList(
            q.options || {},
            q.option_images || {},
            url => this.resolveQuestionImageUrl(url)
          )
          
          const optionsList = rawOptions.map(opt => {
            const isSelected = studentAns.includes(opt.key)
            const isAns = correctAns.includes(opt.key)
            let statusClass = ''
            if (isSelected) {
              statusClass = isAns ? 'opt-correct-selected' : 'opt-wrong-selected'
            } else if (isAns) {
              statusClass = 'opt-correct-unselected'
            }
            return {
              ...opt,
              selected: isSelected,
              isAnswer: isAns,
              statusClass
            }
          })
          
          const correctAnswerText = correctAns.join('、')
          const studentAnswerText = studentAns.length > 0 ? studentAns.join('、') : '未作答'

          let typeLabel = '单选题'
          if (type === 'multi') typeLabel = '多选题'
          else if (type === 'judge') typeLabel = '判断题'
          else if (type === 'case') typeLabel = '案例题'

          const questionImages = this.buildQuestionImages(q)

          return {
            ...q,
            index: idx + 1,
            type,
            typeLabel,
            optionsList,
            studentAnswerText,
            correctAnswerText,
            isCorrect,
            questionImages,
            hasImages: questionImages.length > 0
          }
        })
        
        this.setData({
          record,
          questions: formattedQuestions,
          displayQuestions: formattedQuestions
        })
      }
    } catch (err) {
      wx.showToast({ title: err.message || '加载详情失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  resolveQuestionImageUrl(value) {
    const raw = String(value || '').trim()
    if (!raw) return ''
    if (/^https?:\/\//i.test(raw)) return raw
    if (raw.startsWith('/')) return api.toAbsoluteFileUrl(raw)
    return api.toAbsoluteFileUrl(`/static/images/junrui/${raw}`)
  },

  buildQuestionImages(question) {
    let rawVal = question.question_images
    let images = []
    if (Array.isArray(rawVal)) {
      images = rawVal
    } else if (typeof rawVal === 'string') {
      try {
        images = JSON.parse(rawVal || '[]')
      } catch (err) {
        images = []
      }
    }
    return images.map(img => this.resolveQuestionImageUrl(img)).filter(Boolean)
  },

  previewImage(e) {
    const { url, urls } = e.currentTarget.dataset
    if (!url) return
    wx.previewImage({
      current: url,
      urls: urls || [url]
    })
  },

  toggleWrongOnly(e) {
    const onlyWrong = e.detail.value
    const filtered = onlyWrong
      ? this.data.questions.filter(q => !q.isCorrect)
      : this.data.questions
    
    this.setData({
      onlyWrong,
      displayQuestions: filtered
    })
  },

  toggleCard() {
    this.setData({ showCard: !this.data.showCard })
  },

  jumpToQuestion(e) {
    const id = e.currentTarget.dataset.id
    this.setData({ showCard: false })
    
    const targetQ = this.data.questions.find(q => String(q.id) === String(id))
    if (this.data.onlyWrong && targetQ && targetQ.isCorrect) {
      this.setData({
        onlyWrong: false,
        displayQuestions: this.data.questions
      })
    }
    
    setTimeout(() => {
      wx.pageScrollTo({
        selector: '#q-' + id,
        duration: 300,
        offsetTop: -60
      })
    }, 50)
  }
})
