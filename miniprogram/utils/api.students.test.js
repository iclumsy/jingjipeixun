const assert = require('assert')

const serverStudents = Array.from({ length: 120 }, (_, index) => ({
  id: index + 1,
  name: `Student ${index + 1}`,
  exam_project: index % 2 === 0 ? '叉车司机' : '起重机指挥'
}))

const requests = []

global.getApp = () => ({
  globalData: {
    apiBaseUrl: 'https://example.test'
  }
})

require.cache[require.resolve('./cos-wx-sdk-v5')] = {
  exports: function MockCos() {}
}

global.wx = {
  getStorageSync() {
    return ''
  },
  request(options) {
    requests.push(options)
    options.success({
      statusCode: 200,
      data: serverStudents
    })
  }
}

const api = require('./api')

async function run() {
  const fullResult = await api.getStudents({ all: true, status: 'reviewed' })

  assert.strictEqual(fullResult.list.length, 120, 'all mode should return every matching student')
  assert.strictEqual(fullResult.hasMore, false)
  assert.strictEqual(fullResult.projectCounts['叉车司机'], 60)
  assert.strictEqual(fullResult.projectCounts['起重机指挥'], 60)
  assert.strictEqual(requests[0].data.all, undefined, 'all is a client-only option')

  const pagedResult = await api.getStudents({ page: 2, limit: 20, status: 'reviewed' })

  assert.strictEqual(pagedResult.list.length, 20, 'default mode should preserve pagination')
  assert.strictEqual(pagedResult.list[0]._id, '21')
  assert.strictEqual(pagedResult.page, 2)
  assert.strictEqual(pagedResult.limit, 20)
  assert.strictEqual(pagedResult.hasMore, true)
}

run().catch(error => {
  console.error(error)
  process.exitCode = 1
})
