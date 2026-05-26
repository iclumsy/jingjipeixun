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
  assert.strictEqual(state.recommendedTitle, '先浏览题目')
  assert.strictEqual(state.recommendedDetail, '先熟悉题目、答案和解析')
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
  assert.strictEqual(state.recommendedTitle, '先练错题')
  assert.strictEqual(state.recommendedDetail, '已有 8 道错题，先补薄弱点')
}

function testBuildBankStudyStateUsesQuestionState() {
  const state = practice.buildBankStudyState({
    questionCount: 100,
    progress: {
      doneCount: 0,
      correctCount: 0,
      wrongCount: 0,
      wrongQuestionIds: []
    },
    questionState: {
      seenCount: 12,
      masteredCount: 30,
      wrongCount: 5,
      untouchedCount: 53,
      answeredCount: 35,
      studyProgressPercent: 47,
      answerProgressPercent: 35,
      masteryPercent: 30,
      correctRate: 86,
      wrongQuestionIds: [8, 9, 10, 11, 12]
    }
  })

  assert.strictEqual(state.progressPercent, 47)
  assert.strictEqual(state.answerProgressPercent, 35)
  assert.strictEqual(state.masteryPercent, 30)
  assert.strictEqual(state.correctRate, 86)
  assert.strictEqual(state.correctRateText, '86%')
  assert.strictEqual(state.seenCount, 12)
  assert.strictEqual(state.masteredCount, 30)
  assert.strictEqual(state.wrongCount, 5)
  assert.strictEqual(state.untouchedCount, 53)
  assert.strictEqual(state.recommendedMode, 'wrong')
}

function testBuildBankStudyStateFallsBackToProgressWhenQuestionStateIsEmpty() {
  const state = practice.buildBankStudyState({
    questionCount: 100,
    progress: {
      doneCount: 42,
      correctCount: 31,
      wrongCount: 8,
      wrongQuestionIds: [1, 2, 3, 4, 5, 6, 7, 8],
      lastQuestionId: 88
    },
    questionState: {
      seenCount: 0,
      masteredCount: 0,
      wrongCount: 0,
      untouchedCount: 100,
      answeredCount: 0,
      studyProgressPercent: 0,
      answerProgressPercent: 0,
      masteryPercent: 0,
      correctRate: 0,
      wrongQuestionIds: []
    }
  })

  assert.strictEqual(state.progressPercent, 42)
  assert.strictEqual(state.correctRate, 74)
  assert.strictEqual(state.wrongCount, 8)
  assert.strictEqual(state.recommendedMode, 'wrong')
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

function testResolveStartQuestionIdUsesResumeForSequentialMode() {
  const state = { continueQuestionId: 88 }

  assert.strictEqual(practice.resolveStartQuestionId('sequential', '', state), '88')
  assert.strictEqual(practice.resolveStartQuestionId('sequential', '22', state), '22')
  assert.strictEqual(practice.resolveStartQuestionId('exam', '', state), '')
}

function testQuestionTypeFilterOnlyShowsForBrowseAndSequentialModes() {
  assert.strictEqual(practice.shouldShowQuestionTypeFilter('memorize'), true)
  assert.strictEqual(practice.shouldShowQuestionTypeFilter('sequential'), true)
  assert.strictEqual(practice.shouldShowQuestionTypeFilter('exam'), false)
  assert.strictEqual(practice.shouldShowQuestionTypeFilter('wrong'), false)
}

function testBuildQuestionStateMapsKeepsBrowsedAnsweredAndMasteredSeparate() {
  const maps = practice.buildQuestionStateMaps([
    { id: 1, state: { seenAt: '2026-05-26 10:00:00', status: 'seen', answerCount: 0 } },
    { id: 2, state: { seenAt: '', status: 'mastered', answerCount: 1 } },
    { id: 3, state: { seenAt: '2026-05-26 10:05:00', status: 'wrong', answerCount: 2 } },
    { id: 4, state: null }
  ])

  assert.deepStrictEqual(maps.seenQuestionIds, { 1: true, 3: true })
  assert.deepStrictEqual(maps.answeredQuestionIds, { 2: true, 3: true })
  assert.deepStrictEqual(maps.masteredQuestionIds, { 2: true })
}

function testResolveSessionProgressMetaUsesSummaryCounts() {
  assert.deepStrictEqual(
    practice.resolveSessionProgressMeta('memorize', {
      seenCount: 12,
      masteredCount: 8,
      answeredCount: 20
    }),
    { label: '已浏览', count: 12 }
  )
  assert.deepStrictEqual(
    practice.resolveSessionProgressMeta('sequential', {
      seenCount: 12,
      masteredCount: 8,
      answeredCount: 20
    }),
    { label: '已掌握', count: 8 }
  )
  assert.deepStrictEqual(
    practice.resolveSessionProgressMeta('wrong', {
      seenCount: 12,
      masteredCount: 8,
      answeredCount: 20
    }),
    { label: '已掌握', count: 8 }
  )
  assert.deepStrictEqual(
    practice.resolveSessionProgressMeta('exam', {
      seenCount: 12,
      masteredCount: 8,
      answeredCount: 20
    }),
    { label: '已答', count: 20 }
  )
}

function run() {
  testBuildBankStudyStateForNewBank()
  testBuildBankStudyStateForOngoingBank()
  testBuildBankStudyStateUsesQuestionState()
  testBuildBankStudyStateFallsBackToProgressWhenQuestionStateIsEmpty()
  testBuildBankStudyStateForExamReadyBank()
  testFindQuestionIndexById()
  testResolveStartQuestionIdUsesResumeForSequentialMode()
  testQuestionTypeFilterOnlyShowsForBrowseAndSequentialModes()
  testBuildQuestionStateMapsKeepsBrowsedAnsweredAndMasteredSeparate()
  testResolveSessionProgressMetaUsesSummaryCounts()
}

run()
