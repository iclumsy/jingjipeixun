const api = require('../../../utils/api')
const practice = require('../../../utils/practice')

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
    showCard: false
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
    this.loadQuestions()
  },

  onUnload() {
    this.clearTimer()
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
        this.setData({
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

        this.setData({
          questions: [question],
          loading: false,
          currentIndex: 0,
          currentPosition,
          questionTotal,
          seenQuestionIds: {},
          answeredQuestionIds: {},
          masteredQuestionIds: {},
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
    const answeredQuestionIds = { ...this.data.answeredQuestionIds, [q.id]: true }
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
    const wrongIds = isCorrect
      ? this.data.wrongQuestionIds.filter(id => id !== q.id)
      : Array.from(new Set([...this.data.wrongQuestionIds, q.id]))
    const resultMap = { ...this.data.resultMap, [q.id]: isCorrect }
    const wasAnswered = !!this.data.answeredQuestionIds[q.id]
    const wasMastered = !!this.data.masteredQuestionIds[q.id]
    const answeredQuestionIds = { ...this.data.answeredQuestionIds, [q.id]: true }
    const masteredQuestionIds = isCorrect
      ? { ...this.data.masteredQuestionIds, [q.id]: true }
      : { ...this.data.masteredQuestionIds }
    if (!isCorrect) delete masteredQuestionIds[q.id]
    const summaryState = { ...this.data.summaryState }
    if (!wasAnswered) {
      summaryState.answeredCount = Math.max(0, Number(summaryState.answeredCount || 0)) + 1
    }
    if (isCorrect && !wasMastered) {
      summaryState.masteredCount = Math.max(0, Number(summaryState.masteredCount || 0)) + 1
    } else if (!isCorrect && wasMastered) {
      summaryState.masteredCount = Math.max(0, Number(summaryState.masteredCount || 0) - 1)
    }
    this.setData({
      submitted: true,
      isCorrect,
      resultMap,
      answeredQuestionIds,
      masteredQuestionIds,
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

        this.setData({
          questions: [question],
          currentIndex: 0,
          currentPosition,
          questionTotal,
          loading: false,
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
      ? { answeredCount: Object.keys(this.data.answeredQuestionIds || {}).length }
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
    const batchSize = 10
    for (let i = 0; i < questions.length; i += batchSize) {
      const batch = questions.slice(i, i + batchSize)
      await Promise.all(
        batch.map(q =>
          this.recordQuestionAnswer(q, answerMap[q.id] || [], !!resultMap[q.id])
        )
      )
    }
  },

  async finishSession() {
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
      await this.recordExamQuestionStates(resultMap)
      try {
        await api.savePracticeExam({
          bankId: this.data.bankId,
          score,
          total,
          correctCount: correct,
          durationSeconds: 3600 - this.data.timeLeft,
          passed: score >= 80,
          answers: answerMap
        })
      } catch (err) {
        console.warn('保存考试记录失败', err)
      }
      wx.redirectTo({
        url: `/pages/practice/result/result?score=${score}&total=${total}&correct=${correct}&duration=${3600 - this.data.timeLeft}`
      })
      return
    }
    wx.navigateBack()
  },

  startTimer() {
    this.clearTimer()
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
    }, 1000)
  },

  clearTimer() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  }
})
