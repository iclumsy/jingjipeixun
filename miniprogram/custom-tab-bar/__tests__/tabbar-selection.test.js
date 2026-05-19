const assert = require('assert')
const fs = require('fs')
const path = require('path')

let capturedOptions = null
global.Component = options => {
  capturedOptions = options
}

const tabbar = require('../index')

function createTabBar(route, isAdmin = true) {
  global.getCurrentPages = () => [{ route }]
  global.getApp = () => ({
    ensureLogin: () => Promise.resolve(),
    globalData: {
      isAdmin,
      practiceEnabled: false
    }
  })

  const componentOptions = tabbar.__getOptions ? tabbar.__getOptions() : capturedOptions
  const instance = {
    data: { list: [], selected: 0 },
    setDataCalls: [],
    setData(patch) {
      this.setDataCalls.push(patch)
      this.data = { ...this.data, ...patch }
    }
  }
  Object.keys(componentOptions.methods).forEach(name => {
    instance[name] = componentOptions.methods[name].bind(instance)
  })
  return instance
}

function createTapEvent(path, index) {
  return {
    currentTarget: {
      dataset: { path, index }
    }
  }
}

async function testAdminReviewSelectedByRoute() {
  const instance = createTabBar('pages/admin/review/review')

  await instance.updateTabBar()

  assert.strictEqual(instance.data.list[instance.data.selected].text, '审核管理')
}

async function testSwitchingRoutesDoesNotPreselectOnOldTabBar() {
  const instance = createTabBar('pages/practice/index/index')
  let switchedTo = ''
  global.wx = {
    switchTab({ url }) {
      switchedTo = url
    },
    setStorageSync() {}
  }

  instance.switchTab(createTapEvent('/pages/admin/review/review', 3))

  assert.strictEqual(switchedTo, '/pages/admin/review/review')
  assert.strictEqual(
    instance.setDataCalls.some(patch => Object.prototype.hasOwnProperty.call(patch, 'selected')),
    false,
    'switching to another tab must not pre-highlight the old tabbar instance'
  )
}

async function run() {
  await testAdminReviewSelectedByRoute()
  await testSwitchingRoutesDoesNotPreselectOnOldTabBar()
  const reviewSource = fs.readFileSync(
    path.join(__dirname, '../../pages/admin/review/review.js'),
    'utf8'
  )
  assert(
    !/getTabBar\(\)\.setData\(\{\s*selected:\s*2\s*\}\)/.test(reviewSource),
    'admin review page must not hard-code tab index 2 because practice tab shifts admin index'
  )
}

run().catch(err => {
  console.error(err)
  process.exit(1)
})
