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

module.exports = {
  normalizeQuestionType,
  normalizeAnswer,
  isCorrectAnswer,
  formatOptionList,
  shuffleQuestions
}
