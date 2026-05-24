const assert = require('assert')
const practice = require('./practice')

function testBuildBankStudyStateForNewBank() {
  const state = practice.buildBankStudyState({
    questionCount: 120,
    progress: {
      doneCount: 0,
      correctCount: 0,
      wrongCount: 0,
      wrongQuestionIds: [],
      lastQuestionId: null
    }
  })

  assert.strictEqual(state.progressPercent, 0)
  assert.strictEqual(state.correctRate, 0)
  assert.strictEqual(state.correctRateText, '--')
  assert.strictEqual(state.canContinue, false)
  assert.strictEqual(state.hasWrongQuestions, false)
  assert.strictEqual(state.recommendedMode, 'memorize')
  assert.strictEqual(state.recommendedTitle, '先背题')
  assert.strictEqual(state.recommendedDetail, '先快速熟悉题目和答案')
}

function testBuildBankStudyStateForOngoingBank() {
  const state = practice.buildBankStudyState({
    questionCount: 100,
    progress: {
      doneCount: 42,
      correctCount: 31,
      wrongCount: 8,
      wrongQuestionIds: [1, 2, 3, 4, 5, 6, 7, 8],
      lastQuestionId: 88
    }
  })

  assert.strictEqual(state.progressPercent, 42)
  assert.strictEqual(state.correctRate, 74)
  assert.strictEqual(state.correctRateText, '74%')
  assert.strictEqual(state.canContinue, true)
  assert.strictEqual(state.continueQuestionId, 88)
  assert.strictEqual(state.hasWrongQuestions, true)
  assert.strictEqual(state.recommendedMode, 'wrong')
  assert.strictEqual(state.recommendedTitle, '先看错题')
  assert.strictEqual(state.recommendedDetail, '已有 8 道错题，先补薄弱点')
}

function testBuildBankStudyStateForExamReadyBank() {
  const state = practice.buildBankStudyState({
    questionCount: 100,
    progress: {
      doneCount: 85,
      correctCount: 78,
      wrongCount: 0,
      wrongQuestionIds: [],
      lastQuestionId: 100
    }
  })

  assert.strictEqual(state.progressPercent, 85)
  assert.strictEqual(state.correctRate, 92)
  assert.strictEqual(state.hasWrongQuestions, false)
  assert.strictEqual(state.recommendedMode, 'exam')
  assert.strictEqual(state.recommendedTitle, '做模拟考试')
  assert.strictEqual(state.recommendedDetail, '练习量够了，检验通过率')
}

function testFindQuestionIndexById() {
  const questions = [
    { id: 10 },
    { id: 22 },
    { id: 35 }
  ]

  assert.strictEqual(practice.findQuestionIndexById(questions, '22'), 1)
  assert.strictEqual(practice.findQuestionIndexById(questions, 35), 2)
  assert.strictEqual(practice.findQuestionIndexById(questions, 'missing'), 0)
  assert.strictEqual(practice.findQuestionIndexById([], 22), 0)
}

function run() {
  testBuildBankStudyStateForNewBank()
  testBuildBankStudyStateForOngoingBank()
  testBuildBankStudyStateForExamReadyBank()
  testFindQuestionIndexById()
}

run()
