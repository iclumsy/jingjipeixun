const assert = require('assert')
const fs = require('fs')
const path = require('path')

function read(name) {
  return fs.readFileSync(path.join(__dirname, name), 'utf8')
}

function run() {
  const wxml = read('student-form.wxml')
  const js = read('student-form.js')
  const wxss = read('student-form.wxss')

  assert(
    /data:\s*\{\s*trainingTypeExpanded:\s*false/s.test(js),
    'training type controls should default to collapsed'
  )
  assert(
    wxml.includes('class="type-summary"') && wxml.includes('bindtap="toggleTrainingType"'),
    'training type section should expose a compact summary that can expand controls'
  )
  assert(
    /<view class="type-options" wx:if="\{\{trainingTypeExpanded\}\}">/.test(wxml),
    'training type option buttons should only render when expanded'
  )
  assert(
    /<view class="form-item mt-24" wx:if="\{\{trainingTypeExpanded && trainingType === 'special_equipment'\}\}">/.test(wxml),
    'application type option buttons should stay collapsed with training type controls'
  )
  assert(
    wxml.indexOf('作业类别') < wxml.indexOf('基本信息'),
    'job category picker should remain visible before basic information'
  )
  assert(
    wxml.includes('class="identity-row"') &&
      wxml.indexOf('data-field="name"') < wxml.indexOf('class="gender-selector compact"'),
    'name and gender should be grouped into one row'
  )
  assert(
    wxss.includes('.identity-row') && wxss.includes('.type-summary'),
    'new compact layout classes should be styled'
  )
}

run()
