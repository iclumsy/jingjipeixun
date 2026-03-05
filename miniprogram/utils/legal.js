/**
 * 隐私政策与用户协议管理模块。
 *
 * 管理用户对隐私政策和用户协议的同意状态：
 * - 使用版本号跟踪协议更新，协议更新后用户需重新同意
 * - 同意状态持久化到本地存储
 * - 同时记录同意时间用于审计
 */

const LEGAL_AGREEMENT_VERSION = '2026-02-27'  // 当前协议版本号

/** 本地存储键名 */
const STORAGE_KEYS = {
  privacyAgreed: 'privacy_agreed',                       // 隐私政策是否已同意
  privacyAgreedTime: 'privacy_agreed_time',              // 同意时间
  userAgreementAgreed: 'user_agreement_agreed',           // 用户协议是否已同意
  userAgreementAgreedTime: 'user_agreement_agreed_time',  // 同意时间
  legalAgreed: 'legal_agreed',                           // 总体是否已同意
  legalAgreementVersion: 'legal_agreement_version'        // 已同意的版本号
}

/**
 * 检查用户是否已同意最新版本的协议。
 *
 * 必须同时满足：隐私政策已同意 + 用户协议已同意 + 版本号匹配
 * @returns {boolean}
 */
function hasAcceptedLatestAgreement() {
  const legalAgreed = wx.getStorageSync(STORAGE_KEYS.legalAgreed) === true
  const privacyAgreed = wx.getStorageSync(STORAGE_KEYS.privacyAgreed) === true
  const userAgreementAgreed = wx.getStorageSync(STORAGE_KEYS.userAgreementAgreed) === true
  const version = String(wx.getStorageSync(STORAGE_KEYS.legalAgreementVersion) || '')

  return legalAgreed && privacyAgreed && userAgreementAgreed && version === LEGAL_AGREEMENT_VERSION
}

/**
 * 记录用户已同意当前版本的协议。
 * 将同意状态和时间持久化到本地存储。
 */
function markAgreementAccepted() {
  const now = new Date().toISOString()
  wx.setStorageSync(STORAGE_KEYS.privacyAgreed, true)
  wx.setStorageSync(STORAGE_KEYS.privacyAgreedTime, now)
  wx.setStorageSync(STORAGE_KEYS.userAgreementAgreed, true)
  wx.setStorageSync(STORAGE_KEYS.userAgreementAgreedTime, now)
  wx.setStorageSync(STORAGE_KEYS.legalAgreed, true)
  wx.setStorageSync(STORAGE_KEYS.legalAgreementVersion, LEGAL_AGREEMENT_VERSION)
}

module.exports = {
  LEGAL_AGREEMENT_VERSION,
  STORAGE_KEYS,
  hasAcceptedLatestAgreement,
  markAgreementAccepted
}
