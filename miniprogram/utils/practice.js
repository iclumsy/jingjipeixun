function normalizeQuestionType(question = {}) {
  const type = String(question.question_type || question.type || '').trim()
  const code = Number(question.type_code)
  if (type === 'judge' || type === '判断题' || code === 0 || code === 3) return 'judge'
  if (type === 'multi' || type === '多选题' || code === 2) return 'multi'
  if (type === 'case' || type === '案例题' || code === 4) return 'case'
  return 'single'
}

function normalizeAnswer(answer) {
  if (answer === true) return ['A']
  if (answer === false) return ['B']
  if (Array.isArray(answer)) return answer.map(item => String(item).trim().toUpperCase()).filter(Boolean)
  if (typeof answer === 'string') {
    const text = answer.trim()
    if (!text) return []
    if (text.includes(',')) return text.split(',').map(item => item.trim().toUpperCase()).filter(Boolean)
    return [text.toUpperCase()]
  }
  return []
}

function sameSet(left = [], right = []) {
  if (left.length !== right.length) return false
  const a = [...left].sort()
  const b = [...right].sort()
  return a.every((item, index) => item === b[index])
}

function isCorrectAnswer(question = {}, selectedKeys = []) {
  return sameSet(normalizeAnswer(question.answer), normalizeAnswer(selectedKeys))
}

function firstImageValue(value) {
  if (Array.isArray(value)) return value[0] || ''
  return value || ''
}

function formatOptionList(options = {}, optionImages = {}, resolveImageUrl = null) {
  return Object.keys(options || {})
    .sort()
    .map(key => ({
      key,
      text: options[key],
      image: typeof resolveImageUrl === 'function' ? resolveImageUrl(firstImageValue(optionImages[key])) : ''
    }))
}

function clampPercent(value) {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, Math.round(value)))
}

function buildBankStudyState(bank = {}) {
  const progress = bank.progress || {}
  const questionState = bank.questionState || {}
  const questionCount = Math.max(0, Number(bank.questionCount || 0))

  const wrongIds = Array.isArray(questionState.wrongQuestionIds) ? questionState.wrongQuestionIds : []

  const masteredCount = Math.max(0, Number(questionState.masteredCount || progress.correctCount || 0))
  const seenCount = Math.max(0, Number(questionState.seenCount || 0))
  const wrongCount = Math.max(0, Number(questionState.wrongCount || progress.wrongCount || 0))
  const answeredCount = Math.max(0, Number(questionState.answeredCount || progress.doneCount || 0))
  const touchedCount = Math.max(0, Number(
    questionState.touchedCount !== undefined ? questionState.touchedCount : Math.max(answeredCount, seenCount)
  ))
  const untouchedCount = Math.max(0, Number(
    questionState.untouchedCount !== undefined ? questionState.untouchedCount : Math.max(0, questionCount - touchedCount)
  ))
  const lastQuestionId = progress.lastQuestionId || null

  const progressPercent = questionState.studyProgressPercent !== undefined && questionState.studyProgressPercent > 0
    ? clampPercent(Number(questionState.studyProgressPercent))
    : (questionCount > 0 ? clampPercent((touchedCount / questionCount) * 100) : 0)

  const answerProgressPercent = questionState.answerProgressPercent !== undefined && questionState.answerProgressPercent > 0
    ? clampPercent(Number(questionState.answerProgressPercent))
    : (questionCount > 0 ? clampPercent((answeredCount / questionCount) * 100) : 0)

  const masteryPercent = questionState.masteryPercent !== undefined && questionState.masteryPercent > 0
    ? clampPercent(Number(questionState.masteryPercent))
    : (questionCount > 0 ? clampPercent((masteredCount / questionCount) * 100) : 0)

  const correctRate = questionState.correctRate !== undefined && questionState.correctRate > 0
    ? clampPercent(Number(questionState.correctRate))
    : (answeredCount > 0 ? clampPercent((masteredCount / answeredCount) * 100) : 0)
  const hasWrongQuestions = wrongCount > 0 || wrongIds.length > 0

  let recommendedMode = 'sequential'
  let recommendedTitle = '继续练习'
  let recommendedDetail = '按题库顺序稳步推进'

  if (touchedCount <= 0) {
    recommendedMode = 'memorize'
    recommendedTitle = '先浏览题目'
    recommendedDetail = '先熟悉题目、答案和解析'
  } else if (hasWrongQuestions) {
    recommendedMode = 'wrong'
    recommendedTitle = '先练错题'
    recommendedDetail = `已有 ${wrongCount || wrongIds.length} 道错题，先补薄弱点`
  } else if (progressPercent >= 80 && correctRate >= 75) {
    recommendedMode = 'exam'
    recommendedTitle = '做模拟考试'
    recommendedDetail = '练习量够了，检验通过率'
  }

  return {
    progressPercent,
    answerProgressPercent,
    masteryPercent,
    progressText: `${Math.min(touchedCount, questionCount || touchedCount)} / ${questionCount}`,
    correctRate,
    correctRateText: answeredCount > 0 ? `${correctRate}%` : '--',
    canContinue: !!lastQuestionId,
    continueQuestionId: lastQuestionId,
    hasWrongQuestions,
    wrongQuestionIds: wrongIds,
    seenCount,
    masteredCount,
    answeredCount,
    touchedCount,
    untouchedCount,
    wrongCount,
    recommendedMode,
    recommendedTitle,
    recommendedDetail
  }
}

function findQuestionIndexById(questions = [], questionId = '') {
  const target = String(questionId || '').trim()
  if (!target) return 0
  const index = (Array.isArray(questions) ? questions : [])
    .findIndex(question => String(question && question.id || '') === target)
  return index >= 0 ? index : 0
}

function resolveStartQuestionId(mode = '', explicitQuestionId = '', studyState = {}) {
  const explicit = String(explicitQuestionId || '').trim()
  if (explicit) return explicit
  if (mode !== 'sequential') return ''
  return String((studyState || {}).continueQuestionId || '').trim()
}

function shouldShowQuestionTypeFilter(mode = '') {
  return mode === 'memorize' || mode === 'sequential'
}

function buildQuestionStateMaps(questions = []) {
  return (Array.isArray(questions) ? questions : []).reduce((maps, question) => {
    const id = question && question.id
    const state = question && question.state
    if (!id || !state) return maps

    const status = String(state.status || '').trim()
    const answerCount = Number(state.answerCount || state.answer_count || 0)
    const seenAt = String(state.seenAt || state.seen_at || '').trim()
    if (seenAt) {
      maps.seenQuestionIds[id] = true
    }
    if (answerCount > 0 || status === 'mastered' || status === 'wrong') {
      maps.answeredQuestionIds[id] = true
    }
    if (status === 'mastered') {
      maps.masteredQuestionIds[id] = true
    }
    return maps
  }, {
    seenQuestionIds: {},
    answeredQuestionIds: {},
    masteredQuestionIds: {}
  })
}

function resolveSessionProgressMeta(mode = '', summaryState = {}) {
  if (mode === 'memorize') {
    return {
      label: '已浏览',
      count: Math.max(0, Number((summaryState || {}).seenCount || (summaryState || {}).seen_count || 0))
    }
  }
  if (mode === 'exam') {
    return {
      label: '已答',
      count: Math.max(0, Number((summaryState || {}).answeredCount || (summaryState || {}).answered_count || 0))
    }
  }
  if (mode === 'wrong') {
    return {
      label: '剩余错题',
      count: Math.max(0, Number((summaryState || {}).wrongCount || (summaryState || {}).wrong_count || 0))
    }
  }
  return {
    label: '已掌握',
    count: Math.max(0, Number((summaryState || {}).masteredCount || (summaryState || {}).mastered_count || 0))
  }
}

module.exports = {
  normalizeQuestionType,
  normalizeAnswer,
  isCorrectAnswer,
  formatOptionList,
  buildBankStudyState,
  findQuestionIndexById,
  resolveStartQuestionId,
  shouldShowQuestionTypeFilter,
  buildQuestionStateMaps,
  resolveSessionProgressMeta
}
