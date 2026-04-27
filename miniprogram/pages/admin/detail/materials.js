const MATERIAL_LABELS = {
  photo: '个人照片',
  id_card: '身份证',
  hukou: '户口本',
  diploma: '学历证书',
  training_form: '体检表'
}

function stripGeneratedPrefix(filename = '') {
  const raw = String(filename || '').trim()
  if (!raw) return ''
  const parts = raw.split('-')
  return parts.length >= 3 ? parts.slice(2).join('-') : raw
}

function stripExtension(filename = '') {
  return String(filename || '').replace(/\.[^.]+$/, '')
}

function detectMaterialType(filename = '') {
  const name = String(filename || '')
  if (/个人照片/.test(name)) return 'photo'
  if (/身份证/.test(name)) return 'id_card'
  if (/户口/.test(name)) return 'hukou'
  if (/学历|毕业证/.test(name)) return 'diploma'
  if (/体检表/.test(name)) return 'training_form'
  return ''
}

function appendCacheBust(url = '', mtime) {
  const raw = String(url || '').trim()
  if (!raw || !mtime) return raw
  return `${raw}${raw.includes('?') ? '&' : '?'}v=${encodeURIComponent(String(mtime))}`
}

function toPreviewUrl(rawUrl = '', toAbsoluteFileUrl) {
  const value = String(rawUrl || '').trim()
  if (!value) return ''
  if (typeof toAbsoluteFileUrl === 'function') {
    return toAbsoluteFileUrl(value)
  }
  if (/^https?:\/\//i.test(value) || value.startsWith('/')) return value
  const base = String(toAbsoluteFileUrl || '')
  return `${base}${value}`
}

function normalizeGeneratedMaterials(materials = [], toAbsoluteFileUrl) {
  return (Array.isArray(materials) ? materials : []).map(item => {
    const name = String(item && item.name ? item.name : '').trim()
    const materialType = detectMaterialType(name)
    const title = MATERIAL_LABELS[materialType] || stripExtension(stripGeneratedPrefix(name)) || '报名材料'
    const url = toPreviewUrl(item && item.url, toAbsoluteFileUrl)
    const isDocument = /\.docx?$/i.test(name)
    const adjustableTypes = ['photo', 'id_card', 'hukou', 'diploma']
    return {
      ...item,
      title,
      materialType,
      adjustable: adjustableTypes.includes(materialType),
      canRegenForm: materialType === 'training_form',
      isDocument,
      previewUrl: appendCacheBust(url, item && item.mtime)
    }
  })
}

function pushRotation(adjustments, key, value) {
  const rotate = parseInt(value || 0, 10)
  if (rotate) adjustments[key] = rotate
}

function pushPoints(payload, key, points) {
  if (Array.isArray(points) && points.length === 4) {
    payload[key] = points
  }
}

function buildManualCropPayload(materialType, state = {}) {
  const payload = {
    material_type: materialType,
    adjustments: {}
  }

  if (materialType === 'photo') {
    pushRotation(payload.adjustments, 'rotate', state.rotate)
    pushPoints(payload, 'points', state.points)
  } else if (materialType === 'id_card') {
    pushRotation(payload.adjustments, 'front_rotate', state.front_rotate)
    pushRotation(payload.adjustments, 'back_rotate', state.back_rotate)
    pushPoints(payload, 'front_points', state.front_points)
    pushPoints(payload, 'back_points', state.back_points)
  } else if (materialType === 'hukou') {
    pushRotation(payload.adjustments, 'home_rotate', state.home_rotate)
    pushRotation(payload.adjustments, 'personal_rotate', state.personal_rotate)
    pushPoints(payload, 'home_points', state.home_points)
    pushPoints(payload, 'personal_points', state.personal_points)
  } else if (materialType === 'diploma') {
    pushRotation(payload.adjustments, 'rotate', state.rotate)
    pushPoints(payload, 'points', state.points)
  }

  return payload
}

module.exports = {
  MATERIAL_LABELS,
  detectMaterialType,
  normalizeGeneratedMaterials,
  buildManualCropPayload
}
