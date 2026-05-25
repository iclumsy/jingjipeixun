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
  const questionState = bank.questionState || bank.question_state || {}
  const hasQuestionState = Number(
    questionState.touchedCount ||
    questionState.touched_count ||
    questionState.answeredCount ||
    questionState.answered_count ||
    questionState.seenCount ||
    questionState.seen_count ||
    questionState.masteredCount ||
    questionState.mastered_count ||
    questionState.wrongCount ||
    questionState.wrong_count ||
    0
  ) > 0
  const questionCount = Math.max(0, Number(bank.questionCount || bank.question_count || 0))
  const wrongIdsFromState = Array.isArray(questionState.wrongQuestionIds)
    ? questionState.wrongQuestionIds
    : (Array.isArray(questionState.wrong_question_ids) ? questionState.wrong_question_ids : [])
  const wrongIdsFromProgress = Array.isArray(progress.wrongQuestionIds)
    ? progress.wrongQuestionIds
    : (Array.isArray(progress.wrong_question_ids) ? progress.wrong_question_ids : [])
  const wrongIds = wrongIdsFromState.length > 0 ? wrongIdsFromState : wrongIdsFromProgress
  const legacyDoneCount = Math.max(0, Number(progress.doneCount || progress.done_count || 0))
  const masteredCount = Math.max(0, Number(hasQuestionState ? (questionState.masteredCount || questionState.mastered_count || 0) : (progress.correctCount || progress.correct_count || 0)))
  const seenCount = Math.max(0, Number(hasQuestionState ? (questionState.seenCount || questionState.seen_count || 0) : 0))
  const wrongCount = Math.max(0, Number(hasQuestionState ? (questionState.wrongCount || questionState.wrong_count || 0) : (progress.wrongCount || progress.wrong_count || wrongIds.length || 0)))
  const answeredCount = Math.max(0, Number(hasQuestionState ? (questionState.answeredCount || questionState.answered_count || masteredCount + wrongCount) : legacyDoneCount))
  const touchedCount = Math.max(0, Number(hasQuestionState ? (questionState.touchedCount || questionState.touched_count || seenCount + masteredCount + wrongCount) : legacyDoneCount))
  const untouchedCount = Math.max(0, Number(
    questionState.untouchedCount !== undefined ? questionState.untouchedCount
      : (questionState.untouched_count !== undefined ? questionState.untouched_count : Math.max(0, questionCount - touchedCount))
  ))
  const lastQuestionId = progress.lastQuestionId || progress.last_question_id || null
  const progressPercent = hasQuestionState && questionState.studyProgressPercent !== undefined
    ? clampPercent(Number(questionState.studyProgressPercent))
    : (hasQuestionState && questionState.study_progress_percent !== undefined
      ? clampPercent(Number(questionState.study_progress_percent))
      : (questionCount > 0 ? clampPercent((touchedCount / questionCount) * 100) : 0))
  const answerProgressPercent = hasQuestionState && questionState.answerProgressPercent !== undefined
    ? clampPercent(Number(questionState.answerProgressPercent))
    : (hasQuestionState && questionState.answer_progress_percent !== undefined
      ? clampPercent(Number(questionState.answer_progress_percent))
      : (questionCount > 0 ? clampPercent((answeredCount / questionCount) * 100) : 0))
  const masteryPercent = hasQuestionState && questionState.masteryPercent !== undefined
    ? clampPercent(Number(questionState.masteryPercent))
    : (hasQuestionState && questionState.mastery_percent !== undefined
      ? clampPercent(Number(questionState.mastery_percent))
      : (questionCount > 0 ? clampPercent((masteredCount / questionCount) * 100) : 0))
  const correctRate = hasQuestionState && questionState.correctRate !== undefined
    ? clampPercent(Number(questionState.correctRate))
    : (hasQuestionState && questionState.correct_rate !== undefined
      ? clampPercent(Number(questionState.correct_rate))
      : (answeredCount > 0 ? clampPercent((masteredCount / answeredCount) * 100) : 0))
  const hasWrongQuestions = wrongCount > 0 || wrongIds.length > 0

  let recommendedMode = 'sequential'
  let recommendedTitle = '继续练习'
  let recommendedDetail = '按题库顺序稳步推进'

  if (touchedCount <= 0) {
    recommendedMode = 'memorize'
    recommendedTitle = '先背题'
    recommendedDetail = '先快速熟悉题目和答案'
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

module.exports = {
  normalizeQuestionType,
  normalizeAnswer,
  isCorrectAnswer,
  formatOptionList,
  shuffleQuestions,
  buildBankStudyState,
  findQuestionIndexById
}
