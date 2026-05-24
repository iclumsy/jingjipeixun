function normalizeQuestionType(question = {}) {
  const type = String(question.question_type || question.type || '').trim()
  const code = Number(question.type_code)
  if (type === 'judge' || type === '判断题' || code === 0 || code === 3) return 'judge'
  if (type === 'multi' || type === '多选题' || code === 2) return 'multi'
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

function shuffleQuestions(questions = []) {
  const list = [...questions]
  for (let i = list.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    const tmp = list[i]
    list[i] = list[j]
    list[j] = tmp
  }
  return list
}

function clampPercent(value) {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, Math.round(value)))
}

function buildBankStudyState(bank = {}) {
  const progress = bank.progress || {}
  const questionCount = Math.max(0, Number(bank.questionCount || bank.question_count || 0))
  const doneCount = Math.max(0, Number(progress.doneCount || progress.done_count || 0))
  const correctCount = Math.max(0, Number(progress.correctCount || progress.correct_count || 0))
  const wrongIds = Array.isArray(progress.wrongQuestionIds)
    ? progress.wrongQuestionIds
    : (Array.isArray(progress.wrong_question_ids) ? progress.wrong_question_ids : [])
  const wrongCount = Math.max(0, Number(progress.wrongCount || progress.wrong_count || wrongIds.length || 0))
  const lastQuestionId = progress.lastQuestionId || progress.last_question_id || null
  const progressPercent = questionCount > 0 ? clampPercent((doneCount / questionCount) * 100) : 0
  const correctRate = doneCount > 0 ? clampPercent((correctCount / doneCount) * 100) : 0
  const hasWrongQuestions = wrongCount > 0 || wrongIds.length > 0

  let recommendedMode = 'sequential'
  let recommendedTitle = '继续练习'
  let recommendedDetail = '按题库顺序稳步推进'

  if (doneCount <= 0) {
    recommendedMode = 'memorize'
    recommendedTitle = '先背题'
    recommendedDetail = '先快速熟悉题目和答案'
  } else if (hasWrongQuestions && doneCount >= Math.min(20, Math.max(1, questionCount))) {
    recommendedMode = 'wrong'
    recommendedTitle = '先看错题'
    recommendedDetail = `已有 ${wrongCount || wrongIds.length} 道错题，先补薄弱点`
  } else if (progressPercent >= 80 && correctRate >= 75) {
    recommendedMode = 'exam'
    recommendedTitle = '做模拟考试'
    recommendedDetail = '练习量够了，检验通过率'
  }

  return {
    progressPercent,
    progressText: `${Math.min(doneCount, questionCount || doneCount)} / ${questionCount}`,
    correctRate,
    correctRateText: doneCount > 0 ? `${correctRate}%` : '--',
    canContinue: !!lastQuestionId,
    continueQuestionId: lastQuestionId,
    hasWrongQuestions,
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

module.exports = {
  normalizeQuestionType,
  normalizeAnswer,
  isCorrectAnswer,
  formatOptionList,
  shuffleQuestions,
  buildBankStudyState,
  findQuestionIndexById
}
