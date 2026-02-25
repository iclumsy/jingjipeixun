// pages/admin/export/export.js
const api = require('../../../utils/api')

Page({
  data: {
    statusOptions: ['全部', '未审核', '已审核', '已驳回'],
    statusValues: ['', 'unreviewed', 'reviewed', 'rejected'],
    statusIndex: 0,
    trainingTypeOptions: ['全部', '特种作业', '特种设备'],
    trainingTypeValues: ['', 'special_operation', 'special_equipment'],
    trainingTypeIndex: 0,
    companies: ['全部'],
    companyIndex: 0,
    estimatedCount: 0
  },

  onLoad() {
    this.loadCompanies()
    this.loadEstimatedCount()
  },

  async loadCompanies() {
    try {
      const result = await api.getCompanies()
      if (result.companies) {
        this.setData({
          companies: ['全部', ...result.companies]
        })
      }
    } catch (err) {
      console.error('加载公司列表失败:', err)
    }
  },

  async loadEstimatedCount() {
    try {
      const params = {
        status: this.data.statusValues[this.data.statusIndex],
        training_type: this.data.trainingTypeValues[this.data.trainingTypeIndex],
        company: this.data.companyIndex === 0 ? '' : this.data.companies[this.data.companyIndex],
        limit: 1
      }

      const result = await api.getStudents(params)
      this.setData({
        estimatedCount: result.total || 0
      })
    } catch (err) {
      console.error('加载数量失败:', err)
    }
  },

  onStatusChange(e) {
    this.setData({ statusIndex: parseInt(e.detail.value) })
    this.loadEstimatedCount()
  },

  onTrainingTypeChange(e) {
    this.setData({ trainingTypeIndex: parseInt(e.detail.value) })
    this.loadEstimatedCount()
  },

  onCompanyChange(e) {
    this.setData({ companyIndex: parseInt(e.detail.value) })
    this.loadEstimatedCount()
  },

  async onExport() {
    if (this.data.estimatedCount === 0) {
      wx.showToast({
        title: '没有数据可导出',
        icon: 'none'
      })
      return
    }

    wx.showLoading({ title: '导出中...' })

    try {
      const params = {
        status: this.data.statusValues[this.data.statusIndex],
        training_type: this.data.trainingTypeValues[this.data.trainingTypeIndex],
        company: this.data.companyIndex === 0 ? '' : this.data.companies[this.data.companyIndex]
      }

      const result = await api.exportExcel(params)

      wx.hideLoading()

      if (result.success && result.downloadUrl) {
        wx.showModal({
          title: '导出成功',
          content: `成功导出 ${result.count} 条记录。点击确定下载文件。`,
          success: (res) => {
            if (res.confirm) {
              // 复制下载链接到剪贴板
              wx.setClipboardData({
                data: result.downloadUrl,
                success: () => {
                  wx.showToast({
                    title: '链接已复制',
                    icon: 'success'
                  })
                }
              })
            }
          }
        })
      }
    } catch (err) {
      wx.hideLoading()
      console.error('导出失败:', err)
      wx.showToast({
        title: '导出失败',
        icon: 'none'
      })
    }
  }
})
