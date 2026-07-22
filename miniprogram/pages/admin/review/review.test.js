const assert = require('assert')
const fs = require('fs')
const path = require('path')

function read(name) {
  return fs.readFileSync(path.join(__dirname, name), 'utf8')
}

function getStatusBlock(wxml, status, nextMarker) {
  const start = wxml.indexOf(`item.status === '${status}'`)
  const end = wxml.indexOf(nextMarker, start)
  assert(start >= 0 && end > start, `missing ${status} action block`)
  return wxml.slice(start, end)
}

function setByPath(target, key, value) {
  const parts = key.replace(/\[(\d+)\]/g, '.$1').split('.')
  let cursor = target
  parts.slice(0, -1).forEach(part => {
    if (!cursor[part] || typeof cursor[part] !== 'object') cursor[part] = {}
    cursor = cursor[part]
  })
  cursor[parts[parts.length - 1]] = value
}

function createPage(definition) {
  const page = {
    ...definition,
    data: JSON.parse(JSON.stringify(definition.data)),
    setData(updates, callback) {
      Object.entries(updates).forEach(([key, value]) => setByPath(this.data, key, value))
      if (callback) callback()
    }
  }
  return page
}

async function run() {
  const js = read('review.js')
  const wxml = read('review.wxml')
  const wxss = read('review.wxss')

  const unreviewedBlock = getStatusBlock(wxml, 'unreviewed', '<!-- 已审核')
  const registeredBlock = getStatusBlock(wxml, 'registered', '<!-- 考试通过')
  assert(unreviewedBlock.includes('catchtap="onMoreActionsTap"'), 'unreviewed records need a more-actions button')
  assert(registeredBlock.includes('catchtap="onMoreActionsTap"'), 'registered records need a more-actions button')
  assert(wxml.includes('class="more-action-item more-action-delete"'))
  assert(wxml.includes('catchtap="onMoreDelete"'))
  assert(wxml.includes('删除学员'))
  assert(wxml.includes('moreActionsStudent.canDeleteFromList'))

  assert(js.includes("const DELETE_ALLOWED_STATUSES = ['unreviewed', 'reviewed', 'registered']"))
  assert(js.includes('canDeleteFromList'))
  assert(js.includes('api.deleteStudent(id)'))
  assert(js.includes('此操作不会撤销或修改省网报名数据。'))
  assert(js.includes('await this.refreshAll(true)'))
  assert(js.includes('all: true'), 'admin student requests should opt into full-list mode')

  ;['onReachBottom', 'reportPage', 'reportLimit', 'reportHasMore', 'loadRecords(false)', 'loadReportRecords(false)'].forEach(text => {
    assert(!js.includes(text), `review page should not retain pagination reference: ${text}`)
  })
  assert(!wxml.includes('已显示全部记录'))
  assert(!wxml.includes('已显示全部学习记录'))
  assert(!js.includes('this.data.records.concat'))
  assert(!js.includes('this.data.reportList.concat'))
  assert(!wxss.includes('.load-more-tip'))
  assert(!wxss.includes('.no-more'))

  const learningStatsCall = js.match(/api\.getLearningStats\(\{([\s\S]*?)\}\)/)
  assert(learningStatsCall, 'missing learning statistics request')
  assert(!/\bpage\s*:|\blimit\s*:/.test(learningStatsCall[1]), 'learning statistics request must omit pagination')

  const deleteCalls = []
  let studentQuery = null
  let learningStatsQuery = null
  let deleteBehavior = async id => {
    deleteCalls.push(id)
    return { success: true }
  }
  const apiPath = require.resolve('../../../utils/api')
  require.cache[apiPath] = {
    exports: {
      deleteStudent(id) {
        return deleteBehavior(id)
      },
      async getStudents(params) {
        studentQuery = params
        return {
          list: [{ _id: 'fresh-student', name: 'Fresh', status: 'reviewed', actions: { canDelete: true } }],
          projects: ['叉车司机'],
          projectCounts: { 叉车司机: 1 },
          totalMatching: 1
        }
      },
      async getLearningStats(params) {
        learningStatsQuery = params
        return {
          list: [{ id: 'fresh-report', name: 'Fresh', studyDurationSeconds: 0 }],
          projects: ['叉车司机'],
          project_counts: { 叉车司机: 1 },
          total_matching_count: 1
        }
      }
    }
  }
  require.cache[require.resolve('../../../utils/constants')] = {
    exports: { TRAINING_TYPE_LABELS: {}, STATUS_LABELS: {} }
  }
  require.cache[require.resolve('../../../utils/page-helpers')] = {
    exports: { hasAdminAccess: () => true, formatDateTime: value => value || '-' }
  }

  let modalConfirm = false
  let lastModal = null
  let lastToast = null
  global.wx = {
    showModal(options) {
      lastModal = options
      options.success({ confirm: modalConfirm })
    },
    showToast(options) {
      lastToast = options
    },
    showLoading() {},
    hideLoading() {},
    stopPullDownRefresh() {}
  }
  let pageDefinition = null
  global.Page = definition => {
    pageDefinition = definition
  }
  delete require.cache[require.resolve('./review')]
  require('./review')
  assert(pageDefinition, 'review page should register with Page')

  const loadPage = createPage(pageDefinition)
  loadPage.data.records = [{ _id: 'stale-student' }]
  loadPage.data.reportList = [{ id: 'stale-report' }]
  await loadPage.loadRecords(true)
  await loadPage.loadReportRecords(true)
  assert.deepStrictEqual(loadPage.data.records.map(item => item._id), ['fresh-student'])
  assert.deepStrictEqual(loadPage.data.reportList.map(item => item.id), ['fresh-report'])
  assert.strictEqual(studentQuery.all, true)
  assert.strictEqual(studentQuery.page, undefined)
  assert.strictEqual(studentQuery.limit, undefined)
  assert.strictEqual(learningStatsQuery.page, undefined)
  assert.strictEqual(learningStatsQuery.limit, undefined)

  const cancelledPage = createPage(pageDefinition)
  cancelledPage.data.moreActionsStudent = {
    _id: 'student-1',
    name: '张三',
    status: 'reviewed',
    canDeleteFromList: true
  }
  cancelledPage.refreshAll = async () => {
    throw new Error('cancelled delete must not refresh')
  }
  modalConfirm = false
  await cancelledPage.onMoreDelete()
  assert.strictEqual(deleteCalls.length, 0, 'cancelled delete must not call the API')

  const successPage = createPage(pageDefinition)
  let refreshedWith = null
  successPage.data.moreActionsStudent = {
    _id: 'student-2',
    name: '白进元',
    status: 'registered',
    canDeleteFromList: true
  }
  successPage.data.reportInitialized = true
  successPage.refreshAll = async force => {
    refreshedWith = force
  }
  modalConfirm = true
  await successPage.onMoreDelete()
  assert.deepStrictEqual(deleteCalls, ['student-2'])
  assert(lastModal.content.includes('白进元'))
  assert(lastModal.content.includes('此操作不会撤销或修改省网报名数据。'))
  assert.strictEqual(refreshedWith, true)
  assert.strictEqual(successPage.data.reportInitialized, false, 'deletion should invalidate cached learning statistics')
  assert.strictEqual(successPage.data.deletingStudentId, '')

  const failurePage = createPage(pageDefinition)
  const originalRecords = [{ _id: 'student-3', name: '李四' }]
  failurePage.data.records = originalRecords.slice()
  failurePage.data.moreActionsStudent = {
    _id: 'student-3',
    name: '李四',
    status: 'unreviewed',
    canDeleteFromList: true
  }
  failurePage.refreshAll = async () => {
    throw new Error('failed delete must not refresh')
  }
  deleteBehavior = async id => {
    deleteCalls.push(id)
    throw new Error('服务端删除失败')
  }
  lastToast = null
  await failurePage.onMoreDelete()
  assert.deepStrictEqual(failurePage.data.records, originalRecords)
  assert.strictEqual(failurePage.data.deletingStudentId, '')
  assert.strictEqual(lastToast.title, '服务端删除失败')
}

run().catch(error => {
  console.error(error)
  process.exitCode = 1
})
