const assert = require('assert')
const {
  detectMaterialType,
  normalizeGeneratedMaterials,
  buildManualCropPayload
} = require('./materials')

function run() {
  const raw = [
    { name: '110101199001010011-张三-个人照片.jpg', url: 'students/a/photo.jpg', mtime: 10 },
    { name: '110101199001010011-张三-身份证.jpg', url: 'students/a/id.jpg', mtime: 20 },
    { name: '110101199001010011-张三-户口本.jpg', url: 'students/a/hukou.jpg', mtime: 30 },
    { name: '110101199001010011-张三-学历证书.jpg', url: 'students/a/diploma.jpg', mtime: 40 },
    { name: '110101199001010011-张三-报名表.docx', url: 'students/a/form.docx', mtime: 50 }
  ]

  assert.strictEqual(detectMaterialType('110101199001010011-张三-身份证.jpg'), 'id_card')
  assert.strictEqual(detectMaterialType('110101199001010011-张三-户口本.jpg'), 'hukou')
  assert.strictEqual(detectMaterialType('110101199001010011-张三-学历证书.jpg'), 'diploma')
  assert.strictEqual(detectMaterialType('110101199001010011-张三-个人照片.jpg'), 'photo')
  assert.strictEqual(detectMaterialType('110101199001010011-张三-报名表.docx'), '')

  const normalized = normalizeGeneratedMaterials(raw, '/api/')
  assert.deepStrictEqual(
    normalized.map(item => ({ title: item.title, materialType: item.materialType, adjustable: item.adjustable })),
    [
      { title: '个人照片', materialType: 'photo', adjustable: true },
      { title: '身份证', materialType: 'id_card', adjustable: true },
      { title: '户口本', materialType: 'hukou', adjustable: true },
      { title: '学历证书', materialType: 'diploma', adjustable: true },
      { title: '报名表', materialType: '', adjustable: false }
    ]
  )
  assert.strictEqual(normalized[0].previewUrl, '/api/students/a/photo.jpg?v=10')

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
}

run()
