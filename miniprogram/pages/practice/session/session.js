const api = require('../../../utils/api')
const practice = require('../../../utils/practice')

const DRAFT_VERSION = 'v1'

const MODE_TITLES = {
  memorize: '题目浏览',
  sequential: '顺序练习',
  wrong: '错题练习',
  exam: '模拟考试'
}

Page({
  data: {
    bankId: '',
    mode: 'sequential',
    filter: '',
    activeQuestionType: '',
    showQuestionTypeFilter: false,
    questionTypeOptions: [
      { label: '全部', value: '' },
      { label: '单选', value: 'single' },
      { label: '多选', value: 'multi' },
      { label: '判断', value: 'judge' },
      { label: '案例', value: 'case' }
    ],
    lastQuestionId: '',
    title: '练习',
    loading: true,
    questions: [],
    currentIndex: 0,
    currentPosition: 0,
    questionTotal: 0,
    progressPercent: 0,
    answeredCount: 0,
    answeredLabel: '已答',
    modeHint: '',
    selectedKeys: [],
    submitted: false,
    isCorrect: false,
    correctAnswerText: '',
    optionList: [],
    wrongIds: '',
    answerMap: {},
    resultMap: {},
    questionImages: [],
    seenQuestionIds: {},
    answeredQuestionIds: {},
    masteredQuestionIds: {},
    summaryState: {},
    doneCount: 0,
    correctCount: 0,
    wrongQuestionIds: [],
    timeLeft: 3600,
    timerText: '60:00',
    showCard: false,
    submitId: ''
  },

  onLoad(options = {}) {
    const bankId = options.bankId || ''
    const mode = options.mode || 'sequential'
    const filter = options.filter || ''
    const title = decodeURIComponent(options.title || MODE_TITLES[mode] || '练习')
    this.setData({
      bankId,
      mode,
      filter,
      showQuestionTypeFilter: practice.shouldShowQuestionTypeFilter(mode),
      lastQuestionId: decodeURIComponent(options.lastQuestionId || ''),
      wrongIds: decodeURIComponent(options.wrongIds || ''),
      title: `${title} · ${this.modeTitle(mode, filter)}`,
      modeHint: this.modeHint(mode, filter)
    })

    if (mode === 'exam') {
      const draftKey = 'exam_draft_' + bankId
      const draft = wx.getStorageSync(draftKey)
      if (draft && draft.version === DRAFT_VERSION) {
        wx.showModal({
          title: '继续考试？',
          content: '检测到您有中途退出的模拟考试，是否继续？',
          confirmText: '继续',
          cancelText: '重新开始',
          success: (res) => {
            if (res.confirm) {
              this.restoreDraft(draft)
            } else {
              wx.removeStorageSync(draftKey)
              this.loadQuestions()
            }
          }
        })
        return
      } else if (draft) {
        // 版本号不匹配，旧草稿不可用，自动清理并重新加载
        wx.removeStorageSync(draftKey)
      }
    }
    this.loadQuestions()
  },

  restoreDraft(draft) {
    const questions = draft.questions || []
    const currentIndex = draft.currentIndex || 0
    const answerMap = draft.answerMap || {}
    const timeLeft = draft.timeLeft !== undefined ? draft.timeLeft : 3600
    const answeredQuestionIds = draft.answeredQuestionIds || {}
    const submitId = draft.submitId || ('sub_' + Date.now() + '_' + Math.random().toString(36).substring(2, 10))
    const questionTotal = questions.length
    const min = String(Math.floor(timeLeft / 60)).padStart(2, '0')
    const sec = String(timeLeft % 60).padStart(2, '0')

    const stateMaps = this.data.showQuestionTypeFilter
      ? practice.buildQuestionStateMaps(questions)
      : { seenQuestionIds: {}, answeredQuestionIds: {}, masteredQuestionIds: {} }
    this._seenQuestionIds = { ...stateMaps.seenQuestionIds }

    this.setData({
      submitId,
      questions,
      loading: false,
      currentIndex,
      currentPosition: currentIndex,
      questionTotal,
      answerMap,
      timeLeft,
      timerText: `${min}:${sec}`,
      answeredQuestionIds,
      seenQuestionIds: stateMaps.seenQuestionIds,
      masteredQuestionIds: stateMaps.masteredQuestionIds,
      summaryState: {},
      doneCount: 0,
      correctCount: 0,
      wrongQuestionIds: []
    })
    this.updateSessionMeta()
    this.prepareCurrentQuestion()
    this.startTimer()
  },

  saveExamDraft() {
    if (this._finishingSession) return
    if (this.data.mode !== 'exam') return
    if (!this.data.questions || this.data.questions.length === 0) return
    try {
      // 仅保留前端答题渲染的核心字段，避免 questions 数组携带大量数据库冗余字段导致 Storage 满或卡顿
      const cleanQuestions = this.data.questions.map(q => ({
        id: q.id,
        question: q.question,
        question_type: q.question_type,
        options: q.options,
        answer: q.answer,
        analysis: q.analysis,
        question_images: q.question_images,
        option_images: q.option_images
      }))
      wx.setStorageSync('exam_draft_' + this.data.bankId, {
        version: DRAFT_VERSION,
        submitId: this.data.submitId || '',
        questions: cleanQuestions,
        currentIndex: this.data.currentIndex,
        answerMap: this.data.answerMap,
        timeLeft: this.data.timeLeft,
        answeredQuestionIds: this.data.answeredQuestionIds
      })
    } catch (err) {
      console.error('保存考试草稿失败:', err)
    }
  },



  modeTitle(mode, filter) {
    return MODE_TITLES[mode] || '练习'
  },

  modeHint(mode, filter) {
    if (mode === 'memorize') return '题目浏览会优先展示未浏览题，并直接显示答案和解析'
    if (mode === 'exam') return '模拟考试可跳题，最后统一交卷'
    if (mode === 'wrong') return '集中处理上次练习留下的错题'
    return '每答一题都会立即记录掌握和错题状态'
  },

  async loadQuestions() {
    this.setData({ loading: true })
    try {
      const mode = this.data.mode

      if (mode === 'exam') {
        // 模拟考试：批量加载 100 题
        const res = await api.getPracticeQuestions(this.data.bankId, {
          mode: mode,
          page: 1,
          limit: 100,
          question_type: this.data.showQuestionTypeFilter ? this.data.activeQuestionType : ''
        })
        let questions = Array.isArray(res.list) ? res.list : []
        const currentIndex = practice.findQuestionIndexById(questions, this.data.lastQuestionId)
        const questionState = res.questionState || {}
        const questionTotal = questions.length  // 模拟考试：使用实际加载的题目数
        const summaryState = {}
        const stateMaps = this.data.showQuestionTypeFilter
          ? practice.buildQuestionStateMaps(questions)
          : { seenQuestionIds: {}, answeredQuestionIds: {}, masteredQuestionIds: {} }
        this._seenQuestionIds = { ...stateMaps.seenQuestionIds }
        
        // 随机生成一个本次模考的全局 submitId 供防重幂等校验使用
        const submitId = 'sub_' + Date.now() + '_' + Math.random().toString(36).substring(2, 10)

        this.setData({
          submitId,
          questions,
          loading: false,
          currentIndex,
          currentPosition: currentIndex,
          questionTotal,
          seenQuestionIds: stateMaps.seenQuestionIds,
          answeredQuestionIds: stateMaps.answeredQuestionIds,
          masteredQuestionIds: stateMaps.masteredQuestionIds,
          summaryState,
          doneCount: 0,
          correctCount: 0,
          wrongQuestionIds: []
        })
        this.updateSessionMeta()
        this.prepareCurrentQuestion()
        this.startTimer()
      } else {
        // 其他模式：单题加载
        const res = await api.getNextQuestion(this.data.bankId, {
          mode: mode,
          current_question_id: this.data.lastQuestionId || '',
          question_type: this.data.showQuestionTypeFilter ? this.data.activeQuestionType : ''
        })

        const question = res.question
        const questionState = res.questionState || {}
        const questionTotal = Number(res.total || 0)
        const currentPosition = Number(res.currentPosition || 0)
        const summaryState = questionState

        if (!question) {
          wx.showToast({ title: '没有更多题目了', icon: 'none' })
          this.setData({
            loading: false,
            questions: [],
            questionTotal: 0
          })
          return
        }

        const stateMaps = practice.buildQuestionStateMaps([question])
        this.setData({
          questions: [question],
          loading: false,
          currentIndex: 0,
          currentPosition,
          questionTotal,
          lastQuestionId: question.id,
          seenQuestionIds: stateMaps.seenQuestionIds,
          answeredQuestionIds: stateMaps.answeredQuestionIds,
          masteredQuestionIds: stateMaps.masteredQuestionIds,
          summaryState,
          doneCount: Number(summaryState.answeredCount || 0),
          correctCount: Number(summaryState.masteredCount || 0),
          wrongQuestionIds: []
        })
        this.updateSessionMeta()
        this.prepareCurrentQuestion()
      }
    } catch (err) {
      this.setData({ loading: false })
      wx.showToast({ title: err.message || '题目加载失败', icon: 'none' })
    }
  },

  switchQuestionType(e) {
    if (!this.data.showQuestionTypeFilter || this.data.loading) return
    const type = e.currentTarget.dataset.type || ''
    if (type === this.data.activeQuestionType) return
    this.setData({
      activeQuestionType: type,
      questions: [],
      currentIndex: 0,
      questionTotal: 0,
      progressPercent: 0,
      answeredCount: 0,
      selectedKeys: [],
      submitted: false,
      isCorrect: false,
      correctAnswerText: '',
      optionList: [],
      answerMap: {},
      resultMap: {},
      questionImages: [],
      seenQuestionIds: {},
      answeredQuestionIds: {},
      masteredQuestionIds: {},
      summaryState: {},
      doneCount: 0,
      correctCount: 0,
      wrongQuestionIds: [],
      lastQuestionId: '',
      currentPosition: 0
    })
    this.loadQuestions()
  },

  prepareCurrentQuestion() {
    const q = this.currentQuestion()
    if (!q) return
    const stored = this.data.answerMap[q.id] || []
    const answer = practice.normalizeAnswer(q.answer).join('、')
    this.setData({
      selectedKeys: stored,
      submitted: this.data.mode === 'memorize' ? true : !!this.data.resultMap[q.id],
      isCorrect: !!this.data.resultMap[q.id],
      correctAnswerText: answer,
      questionImages: this.buildQuestionImages(q),
      optionList: this.buildOptionList(q, stored)
    })
    if (this.data.mode === 'memorize') {
      this.markQuestionSeen(q)
    }
    this.updateSessionMeta()
  },

  buildOptionList(question, selectedKeys) {
    return practice.formatOptionList(
      question.options || {},
      question.option_images || {},
      value => this.resolveQuestionImageUrl(value)
    ).map(option => ({
      ...option,
      selected: selectedKeys.includes(option.key)
    }))
  },

  buildQuestionImages(question) {
    return (Array.isArray(question.question_images) ? question.question_images : [])
      .map(value => this.resolveQuestionImageUrl(value))
      .filter(Boolean)
  },

  resolveQuestionImageUrl(value) {
    const raw = String(value || '').trim()
    if (!raw) return ''
    if (/^https?:\/\//i.test(raw)) return raw
    if (raw.startsWith('/')) return api.toAbsoluteFileUrl(raw)
    return api.toAbsoluteFileUrl(`/static/images/junrui/${raw}`)
  },

  currentQuestion() {
    return this.data.questions[this.data.currentIndex] || null
  },

  selectOption(e) {
    if (this.data.mode !== 'exam' && this.data.submitted) return
    const key = e.currentTarget.dataset.key
    const q = this.currentQuestion()
    const type = practice.normalizeQuestionType(q)
    let selected = [...this.data.selectedKeys]
    if (type === 'multi' || type === 'case') {
      selected = selected.includes(key)
        ? selected.filter(item => item !== key)
        : [...selected, key]
    } else {
      selected = [key]
    }
    const answerMap = { ...this.data.answerMap, [q.id]: selected }
    
    let answeredQuestionIds = { ...this.data.answeredQuestionIds }
    if (this.data.mode === 'exam') {
      if (selected.length > 0) {
        answeredQuestionIds[q.id] = true
      } else {
        delete answeredQuestionIds[q.id]
      }
    }
    
    this.setData({
      selectedKeys: selected,
      answerMap,
      answeredQuestionIds,
      optionList: this.buildOptionList(q, selected)
    })
    this.updateSessionMeta()
  },

  async submitAnswer() {
    const q = this.currentQuestion()
    if (!q || this.data.selectedKeys.length === 0) {
      wx.showToast({ title: '请选择答案', icon: 'none' })
      return
    }
    if (this.data.mode === 'exam') {
      this.nextQuestion()
      return
    }
    const isCorrect = practice.isCorrectAnswer(q, this.data.selectedKeys)

    // 错题练习模式下：需要连续答对 2 次才视为已掌握
    let isMastered = isCorrect
    if (this.data.mode === 'wrong') {
      this._wrongStreaks = this._wrongStreaks || {}
      const prev = this._wrongStreaks[q.id] || 0
      const streak = isCorrect ? prev + 1 : 0
      this._wrongStreaks[q.id] = streak
      isMastered = streak >= 2
    }

    const wrongIds = isMastered
      ? this.data.wrongQuestionIds.filter(id => id !== q.id)
      : Array.from(new Set([...this.data.wrongQuestionIds, q.id]))
    const resultMap = { ...this.data.resultMap, [q.id]: isCorrect }
    const wasAnswered = !!this.data.answeredQuestionIds[q.id]
    const wasMastered = !!this.data.masteredQuestionIds[q.id]
    const wasSeen = !!this.data.seenQuestionIds[q.id]
    const answeredQuestionIds = { ...this.data.answeredQuestionIds, [q.id]: true }
    const masteredQuestionIds = isMastered
      ? { ...this.data.masteredQuestionIds, [q.id]: true }
      : { ...this.data.masteredQuestionIds }
    if (!isMastered) delete masteredQuestionIds[q.id]

    let seenQuestionIds = this.data.seenQuestionIds
    const summaryState = { ...this.data.summaryState }
    if (!wasSeen) {
      seenQuestionIds = { ...this.data.seenQuestionIds, [q.id]: true }
      summaryState.seenCount = Math.max(0, Number(summaryState.seenCount || 0)) + 1
    }

    if (!wasAnswered) {
      summaryState.answeredCount = Math.max(0, Number(summaryState.answeredCount || 0)) + 1
    }
    if (isMastered && !wasMastered) {
      summaryState.masteredCount = Math.max(0, Number(summaryState.masteredCount || 0)) + 1
    } else if (!isMastered && wasMastered) {
      summaryState.masteredCount = Math.max(0, Number(summaryState.masteredCount || 0) - 1)
    }
    this.setData({
      submitted: true,
      isCorrect,
      resultMap,
      answeredQuestionIds,
      masteredQuestionIds,
      seenQuestionIds,
      summaryState,
      doneCount: Number(summaryState.answeredCount || Object.keys(answeredQuestionIds).length),
      correctCount: Number(summaryState.masteredCount || Object.keys(masteredQuestionIds).length),
      wrongQuestionIds: wrongIds
    })
    await this.recordQuestionAnswer(q, this.data.selectedKeys, isCorrect)
    this.updateSessionMeta()
  },

  async nextQuestion() {
    const mode = this.data.mode

    if (mode === 'exam') {
      // 模拟考试：在已加载的题目中翻页
      if (this.data.currentIndex >= this.data.questions.length - 1) {
        this.finishSession()
        return
      }
      this.setData({
        currentIndex: this.data.currentIndex + 1,
        currentPosition: this.data.currentIndex + 1
      })
      this.prepareCurrentQuestion()
    } else {
      // 其他模式：加载下一题
      this.setData({ loading: true })
      try {
        const currentQuestion = this.currentQuestion()
        const res = await api.getNextQuestion(this.data.bankId, {
          mode: mode,
          current_question_id: currentQuestion ? currentQuestion.id : '',
          question_type: this.data.showQuestionTypeFilter ? this.data.activeQuestionType : ''
        })

        const question = res.question
        const questionState = res.questionState || {}
        const currentPosition = Number(res.currentPosition || 0)
        const questionTotal = Number(res.total || 0)

        if (!question) {
          this.finishSession()
          return
        }

        const prevPosition = this.data.currentPosition
        const prevTotal = this.data.questionTotal
        const stateMaps = practice.buildQuestionStateMaps([question])

        this.setData({
          questions: [question],
          currentIndex: 0,
          currentPosition: this.data.mode === 'wrong' ? prevPosition + 1 : currentPosition,
          questionTotal: this.data.mode === 'wrong' ? prevTotal : questionTotal,
          loading: false,
          lastQuestionId: question.id,
          seenQuestionIds: stateMaps.seenQuestionIds,
          answeredQuestionIds: stateMaps.answeredQuestionIds,
          masteredQuestionIds: stateMaps.masteredQuestionIds,
          summaryState: questionState,
          doneCount: Number(questionState.answeredCount || 0),
          correctCount: Number(questionState.masteredCount || 0)
        })
        this.prepareCurrentQuestion()
      } catch (err) {
        this.setData({ loading: false })
        wx.showToast({ title: '加载下一题失败', icon: 'none' })
      }
    }
  },

  prevQuestion() {
    if (this.data.mode !== 'exam') return
    if (this.data.currentIndex <= 0) return
    this.setData({
      currentIndex: this.data.currentIndex - 1,
      currentPosition: this.data.currentIndex - 1
    })
    this.prepareCurrentQuestion()
  },

  jumpQuestion(e) {
    if (this.data.mode !== 'exam') return
    const index = Number(e.currentTarget.dataset.index || 0)
    this.setData({
      currentIndex: index,
      currentPosition: index,
      showCard: false
    })
    this.prepareCurrentQuestion()
  },

  updateSessionMeta() {
    const total = this.data.questionTotal || this.data.questions.length || 0
    const position = this.data.mode === 'exam' ? this.data.currentIndex : this.data.currentPosition
    const progressPercent = total > 0
      ? Math.max(0, Math.min(100, Math.round(((position + 1) / total) * 100)))
      : 0
    const summaryState = this.data.mode === 'exam'
      ? { answeredCount: Object.values(this.data.answeredQuestionIds || {}).filter(Boolean).length }
      : this.data.summaryState
    const progressMeta = practice.resolveSessionProgressMeta(this.data.mode, summaryState)
    this.setData({
      progressPercent,
      answeredCount: progressMeta.count,
      answeredLabel: progressMeta.label
    })
  },

  toggleCard() {
    this.setData({ showCard: !this.data.showCard })
  },

  async saveQuestionState(payload = {}) {
    if (!this.data.bankId || !payload.questionId) return null
    try {
      return await api.saveQuestionState({
        bankId: this.data.bankId,
        ...payload
      })
    } catch (err) {
      console.warn('保存题目状态失败', err)
      return null
    }
  },

  markQuestionSeen(question) {
    if (!question || !question.id) return
    this._seenQuestionIds = this._seenQuestionIds || {}
    if (this._seenQuestionIds[question.id]) return
    this._seenQuestionIds[question.id] = true
    const summaryState = {
      ...this.data.summaryState,
      seenCount: Math.max(0, Number((this.data.summaryState || {}).seenCount || 0)) + 1
    }
    this.setData({
      seenQuestionIds: { ...this.data.seenQuestionIds, [question.id]: true },
      summaryState
    })
    this.updateSessionMeta()
    this.saveQuestionState({
      questionId: question.id,
      action: 'seen',
      mode: this.data.mode
    })
  },

  async recordQuestionAnswer(question, selectedKeys, isCorrect) {
    if (!question || !question.id) return
    await this.saveQuestionState({
      questionId: question.id,
      action: 'answer',
      mode: this.data.mode,
      answer: selectedKeys,
      isCorrect
    })
  },

  async recordExamQuestionStates(resultMap) {
    const answerMap = this.data.answerMap || {}
    const questions = this.data.questions
    const states = questions.map(q => ({
      questionId: q.id,
      action: 'answer',
      answer: answerMap[q.id] || [],
      isCorrect: !!resultMap[q.id]
    }))
    await api.saveBatchQuestionStates(this.data.bankId, {
      mode: this.data.mode,
      states
    })
  },

  async finishSession() {
    if (this._finishingSession) return
    this._finishingSession = true
    this.clearTimer()
    if (this.data.mode === 'exam') {
      const answerMap = this.data.answerMap
      const resultMap = {}
      const wrongIds = []
      this.data.questions.forEach(q => {
        const ok = practice.isCorrectAnswer(q, answerMap[q.id] || [])
        resultMap[q.id] = ok
        if (!ok) wrongIds.push(q.id)
      })
      const total = this.data.questions.length || 1
      const correct = Object.values(resultMap).filter(Boolean).length
      const score = Math.round((correct / total) * 100)
      this.setData({
        resultMap,
        doneCount: total,
        correctCount: correct,
        wrongQuestionIds: wrongIds
      })
      
      wx.showLoading({ title: '提交中...', mask: true })
      try {
        // 仅在答题状态尚未保存时提交，避免网络重试导致次数重复累加
        if (!this._questionStatesRecorded) {
          await this.recordExamQuestionStates(resultMap)
          this._questionStatesRecorded = true
        }
        await api.savePracticeExam({
          bankId: this.data.bankId,
          score,
          total,
          correctCount: correct,
          durationSeconds: 3600 - this.data.timeLeft,
          passed: score >= 70,
          answers: answerMap,
          submitId: this.data.submitId || '',
          questionOrder: this.data.questions.map(q => q.id)
        })
        // 只有在保存题目状态和考试记录都成功后，才清除本地草稿并跳转到结果页
        try {
          wx.removeStorageSync('exam_draft_' + this.data.bankId)
        } catch (storageErr) {
          console.error('清理考试草稿失败:', storageErr)
        }
        wx.redirectTo({
          url: `/pages/practice/result/result?score=${score}&total=${total}&correct=${correct}&duration=${3600 - this.data.timeLeft}`
        })
        return
      } catch (err) {
        console.warn('交卷失败，请重试', err)
        wx.showToast({ title: '提交失败，请检查网络后重试', icon: 'none' })
        // 重置 finishingSession 锁并重新开启定时器，允许用户再次点击交卷重试
        this._finishingSession = false
        this.startTimer()
        return
      } finally {
        wx.hideLoading()
      }
    }
    wx.navigateBack()
  },

  startTimer() {
    this.clearTimer()
    this.saveExamDraft()
    this._timer = setInterval(() => {
      const next = this.data.timeLeft - 1
      if (next <= 0) {
        this.setData({ timeLeft: 0, timerText: '00:00' })
        this.finishSession()
        return
      }
      const min = String(Math.floor(next / 60)).padStart(2, '0')
      const sec = String(next % 60).padStart(2, '0')
      this.setData({ timeLeft: next, timerText: `${min}:${sec}` })
      
      if (next % 10 === 0) {
        this.saveExamDraft()
      }
    }, 1000)
  },

  onHide() {
    this.saveExamDraft()
  },

  onUnload() {
    this.saveExamDraft()
    this.clearTimer()
  },

  clearTimer() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  }
})
