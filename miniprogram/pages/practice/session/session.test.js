const assert = require('assert')
const fs = require('fs')
const path = require('path')

function read(name) {
  return fs.readFileSync(path.join(__dirname, name), 'utf8')
}

function run() {
  const js = read('session.js')
  const wxml = read('session.wxml')
  const wxss = read('session.wxss')

  assert(
    js.includes("showQuestionTypeFilter: practice.shouldShowQuestionTypeFilter(mode)"),
    'session page should only show type filters for supported practice modes'
  )
  assert(
    js.includes("question_type: this.data.showQuestionTypeFilter ? this.data.activeQuestionType : ''"),
    'question requests should pass the active question type only when the filter is visible'
  )
  assert(
    js.includes('practice.buildQuestionStateMaps(questions)') &&
      js.includes('practice.resolveSessionProgressMeta') &&
      js.includes('questionTotal') &&
      js.includes('Number(res.total || questions.length || 0)') &&
      js.includes('this.data.showQuestionTypeFilter') &&
      js.includes('answeredLabel') &&
      js.includes('summaryState'),
    'session page should initialize supported practice progress text from saved question state'
  )
  assert(
    /switchQuestionType\(e\)/.test(js),
    'session page should handle question type changes'
  )
  assert(
    wxml.includes('class="type-filter"') &&
      wxml.includes('wx:for="{{questionTypeOptions}}"') &&
      wxml.includes('bindtap="switchQuestionType"') &&
      !/<button[\s\S]*class="type-filter-btn/.test(wxml),
    'session page should render a question type segmented control'
  )
  assert(
    wxss.includes('.type-filter') && wxss.includes('.type-filter-btn.active'),
    'question type segmented control should be styled'
  )
}

run()
