const assert = require('assert')
const {
  detectMaterialType,
  normalizeGeneratedMaterials,
  buildManualCropPayload,
  getOffsetTouchPoint
} = require('./materials')

function run() {
  const raw = [
    { name: '110101199001010011-张三-个人照片.jpg', url: 'students/a/photo.jpg', mtime: 10, version: 'photo-v2' },
    { name: '110101199001010011-张三-身份证.jpg', url: 'students/a/id.jpg', mtime: 20 },
    { name: '110101199001010011-张三-户口本.jpg', url: 'students/a/hukou.jpg', mtime: 30 },
    { name: '110101199001010011-张三-学历证书.jpg', url: 'students/a/diploma.jpg', mtime: 40 },
    { name: '110101199001010011-张三-体检表.docx', url: 'students/a/health.docx', mtime: 50, version: 'health-v2', material_type: 'training_form' },
    { name: '110101199001010011-张三-报名申请表.pdf', url: 'students/a/apply.pdf', mtime: 60, version: 'apply-v2' }
  ]

  assert.strictEqual(detectMaterialType('110101199001010011-张三-身份证.jpg'), 'id_card')
  assert.strictEqual(detectMaterialType('110101199001010011-张三-户口本.jpg'), 'hukou')
  assert.strictEqual(detectMaterialType('110101199001010011-张三-学历证书.jpg'), 'diploma')
  assert.strictEqual(detectMaterialType('110101199001010011-张三-个人照片.jpg'), 'photo')
  assert.strictEqual(detectMaterialType('110101199001010011-张三-报名申请表.pdf'), 'registration_form')

  const normalized = normalizeGeneratedMaterials(raw, '/api/')
  assert.deepStrictEqual(
    normalized.map(item => ({
      title: item.title,
      materialType: item.materialType,
      adjustable: item.adjustable,
      fullWidth: item.fullWidth,
      isDownloadCard: item.isDownloadCard,
      downloadCardTone: item.downloadCardTone,
      downloadIcon: item.downloadIcon
    })),
    [
      { title: '个人照片', materialType: 'photo', adjustable: true, fullWidth: false, isDownloadCard: false, downloadCardTone: '', downloadIcon: '' },
      { title: '学历证书', materialType: 'diploma', adjustable: true, fullWidth: false, isDownloadCard: false, downloadCardTone: '', downloadIcon: '' },
      { title: '身份证', materialType: 'id_card', adjustable: true, fullWidth: false, isDownloadCard: false, downloadCardTone: '', downloadIcon: '' },
      { title: '户口本', materialType: 'hukou', adjustable: true, fullWidth: false, isDownloadCard: false, downloadCardTone: '', downloadIcon: '' },
      { title: '报名表', materialType: 'registration_form', adjustable: false, fullWidth: false, isDownloadCard: true, downloadCardTone: 'blue', downloadIcon: '✏️' },
      { title: '体检表', materialType: 'training_form', adjustable: false, fullWidth: false, isDownloadCard: true, downloadCardTone: 'purple', downloadIcon: '📄' }
    ]
  )
  assert.strictEqual(normalized[0].previewUrl, '/api/students/a/photo.jpg?v=photo-v2')
  assert.strictEqual(normalized[4].previewUrl, '/api/students/a/apply.pdf')
  assert.strictEqual(normalized[5].previewUrl, '/api/students/a/health.docx')

  const withSyntheticRegForm = normalizeGeneratedMaterials([], '/api/', {
    student: {
      status: 'registered',
      name: '李四',
      id_card: '140101199001010022'
    }
  })
  assert.deepStrictEqual(
    withSyntheticRegForm.map(item => ({
      title: item.title,
      materialType: item.materialType,
      isDocument: item.isDocument,
      canDownloadRegForm: item.canDownloadRegForm,
      isDownloadCard: item.isDownloadCard,
      downloadCardTone: item.downloadCardTone,
      downloadIcon: item.downloadIcon,
      fullWidth: item.fullWidth
    })),
    [
      {
        title: '报名表',
        materialType: 'registration_form',
        isDocument: true,
        canDownloadRegForm: true,
        isDownloadCard: true,
        downloadCardTone: 'blue',
        downloadIcon: '✏️',
        fullWidth: false
      }
    ]
  )

  assert.deepStrictEqual(
    buildManualCropPayload('id_card', {
      front_points: [[0, 0], [100, 0], [100, 60], [0, 60]],
      front_rotate: 90,
      back_rotate: 0
    }),
    {
      material_type: 'id_card',
      adjustments: { front_rotate: 90 },
      front_points: [[0, 0], [100, 0], [100, 60], [0, 60]]
    }
  )

  assert.deepStrictEqual(
    buildManualCropPayload('photo', {
      points: [[10, 10], [60, 10], [60, 80], [10, 80]],
      rotate: 270
    }),
    {
      material_type: 'photo',
      adjustments: { rotate: 270 },
      points: [[10, 10], [60, 10], [60, 80], [10, 80]]
    }
  )

  assert.deepStrictEqual(
    getOffsetTouchPoint({ clientX: 160, clientY: 260 }, { left: 20, top: 40 }, 70),
    { x: 140, y: 150 }
  )
}

run()
