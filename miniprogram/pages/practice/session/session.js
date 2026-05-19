const api = require('../../../utils/api')
const practice = require('../../../utils/practice')

const MODE_TITLES = {
  sequential: '顺序练习',
  random: '随机练习',
  wrong: '错题练习',
  exam: '模拟考试'
}

Page({
  data: {
    bankId: '',
    mode: 'sequential',
    title: '练习',
    loading: true,
    questions: [],
    currentIndex: 0,
    selectedKeys: [],
    submitted: false,
    isCorrect: false,
    correctAnswerText: '',
    optionList: [],
    wrongIds: '',
    doneCount: 0,
    correctCount: 0,
    wrongQuestionIds: [],
    timeLeft: 3600,
    timerText: '60:00'
  },

  onLoad(options = {}) {
    const bankId = options.bankId || ''
    const mode = options.mode || 'sequential'
    const title = decodeURIComponent(options.title || MODE_TITLES[mode] || '练习')
    this.setData({
      bankId,
      mode,
      wrongIds: decodeURIComponent(options.wrongIds || ''),
      title: `${title} · ${MODE_TITLES[mode] || '练习'}`
    })
    this.loadQuestions()
  },

  onUnload() {
    this.clearTimer()
    this.saveProgress()
  },

  async loadQuestions() {
    this.setData({ loading: true })
    try {
      const limit = this.data.mode === 'exam' ? 100 : 50
      const res = await api.getPracticeQuestions(this.data.bankId, {
        mode: this.data.mode === 'wrong' ? 'sequential' : this.data.mode,
        page: 1,
        limit,
        wrong_ids: this.data.mode === 'wrong' ? this.data.wrongIds : ''
      })
      let questions = Array.isArray(res.list) ? res.list : []
      if (this.data.mode === 'random') {
        questions = practice.shuffleQuestions(questions)
      }
      this.setData({ questions, loading: false, currentIndex: 0 })
      this.prepareCurrentQuestion()
      if (this.data.mode === 'exam') this.startTimer()
    } catch (err) {
      this.setData({ loading: false })
      wx.showToast({ title: err.message || '题目加载失败', icon: 'none' })
    }
  },

  prepareCurrentQuestion() {
    const q = this.currentQuestion()
    if (!q) return
    const answer = practice.normalizeAnswer(q.answer).join('、')
    this.setData({
      selectedKeys: [],
      submitted: false,
      isCorrect: false,
      correctAnswerText: answer,
      optionList: this.buildOptionList(q, [])
    })
  },

  buildOptionList(question, selectedKeys) {
    return practice.formatOptionList(question.options || {}).map(option => ({
      ...option,
      selected: selectedKeys.includes(option.key)
    }))
  },

  currentQuestion() {
    return this.data.questions[this.data.currentIndex] || null
  },

  selectOption(e) {
    if (this.data.submitted) return
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
    this.setData({
      selectedKeys: selected,
      optionList: this.buildOptionList(q, selected)
    })
  },

  submitAnswer() {
    const q = this.currentQuestion()
    if (!q || this.data.selectedKeys.length === 0) {
      wx.showToast({ title: '请选择答案', icon: 'none' })
      return
    }
    const isCorrect = practice.isCorrectAnswer(q, this.data.selectedKeys)
    const wrongIds = isCorrect
      ? this.data.wrongQuestionIds
      : Array.from(new Set([...this.data.wrongQuestionIds, q.id]))
    this.setData({
      submitted: true,
      isCorrect,
      doneCount: this.data.doneCount + 1,
      correctCount: this.data.correctCount + (isCorrect ? 1 : 0),
      wrongQuestionIds: wrongIds
    })
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
    await this.saveProgress()
    if (this.data.mode === 'exam') {
      const total = this.data.questions.length || 1
      const score = Math.round((this.data.correctCount / total) * 100)
      try {
        await api.savePracticeExam({
          bankId: this.data.bankId,
          score,
          total,
          correctCount: this.data.correctCount,
          durationSeconds: 3600 - this.data.timeLeft,
          passed: score >= 80,
          answers: {}
        })
      } catch (err) {
        console.warn('保存考试记录失败', err)
      }
      wx.redirectTo({
        url: `/pages/practice/result/result?score=${score}&total=${total}&correct=${this.data.correctCount}&duration=${3600 - this.data.timeLeft}`
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
