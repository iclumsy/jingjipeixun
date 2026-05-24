const api = require('../../../utils/api')
const practice = require('../../../utils/practice')

const MODE_TITLES = {
  memorize: '背题模式',
  sequential: '顺序练习',
  random: '随机练习',
  wrong: '错题练习',
  exam: '模拟考试',
  type: '题型练习'
}

const FILTER_TYPE_MAP = {
  single: 'single',
  multi: 'multi',
  judge: 'judge'
}

Page({
  data: {
    bankId: '',
    mode: 'sequential',
    filter: '',
    lastQuestionId: '',
    title: '练习',
    loading: true,
    questions: [],
    currentIndex: 0,
    progressPercent: 0,
    answeredCount: 0,
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
      lastQuestionId: decodeURIComponent(options.lastQuestionId || ''),
      wrongIds: decodeURIComponent(options.wrongIds || ''),
      title: `${title} · ${this.modeTitle(mode, filter)}`,
      modeHint: this.modeHint(mode, filter)
    })
    this.loadQuestions()
  },

  onUnload() {
    this.clearTimer()
    this.saveProgress()
  },

  modeTitle(mode, filter) {
    if (mode !== 'type') return MODE_TITLES[mode] || '练习'
    const labels = { all: '全部题型', single: '单选题', multi: '多选题', judge: '判断题' }
    return labels[filter] || '题型练习'
  },

  modeHint(mode, filter) {
    if (mode === 'memorize') return '背题模式会直接显示答案和解析'
    if (mode === 'exam') return '模拟考试可跳题，最后统一交卷'
    if (mode === 'wrong') return '集中处理上次练习留下的错题'
    if (mode === 'type') return `${this.modeTitle(mode, filter)}，适合专项强化`
    return '答题后会自动记录进度和错题'
  },

  async loadQuestions() {
    this.setData({ loading: true })
    try {
      const mode = this.data.mode
      const limit = mode === 'exam' || mode === 'memorize' ? 100 : 100
      const res = await api.getPracticeQuestions(this.data.bankId, {
        mode: mode === 'wrong' || mode === 'type' || mode === 'memorize' ? 'sequential' : mode,
        page: 1,
        limit,
        wrong_ids: mode === 'wrong' ? this.data.wrongIds : '',
        question_type: mode === 'type' ? (FILTER_TYPE_MAP[this.data.filter] || '') : ''
      })
      let questions = Array.isArray(res.list) ? res.list : []
      if (mode === 'random' || mode === 'memorize') {
        questions = practice.shuffleQuestions(questions)
      }
      const currentIndex = practice.findQuestionIndexById(questions, this.data.lastQuestionId)
      this.setData({ questions, loading: false, currentIndex })
      this.updateSessionMeta()
      this.prepareCurrentQuestion()
      if (mode === 'exam') this.startTimer()
    } catch (err) {
      this.setData({ loading: false })
      wx.showToast({ title: err.message || '题目加载失败', icon: 'none' })
    }
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
    if (type === 'multi') {
      selected = selected.includes(key)
        ? selected.filter(item => item !== key)
        : [...selected, key]
    } else {
      selected = [key]
    }
    const answerMap = { ...this.data.answerMap, [q.id]: selected }
    this.setData({
      selectedKeys: selected,
      answerMap,
      optionList: this.buildOptionList(q, selected)
    })
    this.updateSessionMeta()
  },

  submitAnswer() {
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
    this.setData({
      submitted: true,
      isCorrect,
      resultMap,
      doneCount: Object.keys(resultMap).length,
      correctCount: Object.values(resultMap).filter(Boolean).length,
      wrongQuestionIds: wrongIds
    })
    this.updateSessionMeta()
  },

  nextQuestion() {
    if (this.data.currentIndex >= this.data.questions.length - 1) {
      this.finishSession()
      return
    }
    this.setData({ currentIndex: this.data.currentIndex + 1 })
    this.prepareCurrentQuestion()
  },

  prevQuestion() {
    if (this.data.currentIndex <= 0) return
    this.setData({ currentIndex: this.data.currentIndex - 1 })
    this.prepareCurrentQuestion()
  },

  jumpQuestion(e) {
    const index = Number(e.currentTarget.dataset.index || 0)
    this.setData({ currentIndex: index, showCard: false })
    this.prepareCurrentQuestion()
  },

  updateSessionMeta() {
    const total = this.data.questions.length || 0
    const progressPercent = total > 0
      ? Math.max(0, Math.min(100, Math.round(((this.data.currentIndex + 1) / total) * 100)))
      : 0
    const answeredCount = Object.keys(this.data.answerMap || {}).length
    this.setData({ progressPercent, answeredCount })
  },

  toggleCard() {
    this.setData({ showCard: !this.data.showCard })
  },

  async saveProgress() {
    if (!this.data.bankId) return
    try {
      await api.savePracticeProgress({
        bankId: this.data.bankId,
        mode: 'practice',
        doneCount: this.data.doneCount,
        correctCount: this.data.correctCount,
        wrongQuestionIds: this.data.wrongQuestionIds,
        lastQuestionId: (this.currentQuestion() || {}).id || null
      })
    } catch (err) {
      console.warn('保存练习进度失败', err)
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
      await this.saveProgress()
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
    await this.saveProgress()
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
