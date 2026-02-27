const LEGAL_AGREEMENT_VERSION = '2026-02-27'

const STORAGE_KEYS = {
  privacyAgreed: 'privacy_agreed',
  privacyAgreedTime: 'privacy_agreed_time',
  userAgreementAgreed: 'user_agreement_agreed',
  userAgreementAgreedTime: 'user_agreement_agreed_time',
  legalAgreed: 'legal_agreed',
  legalAgreementVersion: 'legal_agreement_version'
}

function hasAcceptedLatestAgreement() {
  const legalAgreed = wx.getStorageSync(STORAGE_KEYS.legalAgreed) === true
  const privacyAgreed = wx.getStorageSync(STORAGE_KEYS.privacyAgreed) === true
  const userAgreementAgreed = wx.getStorageSync(STORAGE_KEYS.userAgreementAgreed) === true
  const version = String(wx.getStorageSync(STORAGE_KEYS.legalAgreementVersion) || '')

  return legalAgreed && privacyAgreed && userAgreementAgreed && version === LEGAL_AGREEMENT_VERSION
}

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
