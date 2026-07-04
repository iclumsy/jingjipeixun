const DOC_CONFIG = {
  id_card: {
    label: '身份证',
    fields: [
      { key: 'id_card_front', label: '身份证正面', pointKey: 'front_points', rotateKey: 'front_rotate' },
      { key: 'id_card_back', label: '身份证反面', pointKey: 'back_points', rotateKey: 'back_rotate' }
    ]
  },
  hukou: {
    label: '户口本',
    fields: [
      { key: 'hukou_residence', label: '户口本首页', pointKey: 'home_points', rotateKey: 'home_rotate' },
      { key: 'hukou_personal', label: '户口本本人页', pointKey: 'personal_points', rotateKey: 'personal_rotate' }
    ]
  }
};

const state = {
  documentType: 'id_card',
  task: null,
  points: {},
  crop: {
    field: null,
    pointKey: '',
    image: null,
    imageUrl: '',
    points: []
  }
};

function $(id) {
  return document.getElementById(id);
}

function showMessage(text, type = '') {
  const el = $('toolMessage');
  el.textContent = text || '';
  el.className = `exam-bank-message ${type}`;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.success === false) {
    throw new Error(data.message || `请求失败（${response.status}）`);
  }
  return data;
}

function activeConfig() {
  return DOC_CONFIG[state.documentType];
}

function setDocumentType(type) {
  state.documentType = DOC_CONFIG[type] ? type : 'id_card';
  state.task = null;
  state.points = {};
  document.querySelectorAll('.document-tool-type').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.type === state.documentType);
  });
  renderUploadFields();
  renderAdjustControls();
  $('adjustPanel').hidden = true;
  $('previewPanel').hidden = true;
  showMessage('');
}

function renderUploadFields() {
  $('uploadFields').innerHTML = activeConfig().fields.map(field => `
    <label class="document-tool-upload">
      <span>${field.label}</span>
      <input type="file" name="${field.key}" accept="image/*">
    </label>
  `).join('');
}

function optionButtons(name, values, selected) {
  return values.map(item => `
    <button type="button" class="document-tool-choice ${item.value === selected ? 'active' : ''}" data-group="${name}" data-value="${item.value}">
      ${item.label}
    </button>
  `).join('');
}

function renderAdjustControls() {
  const cfg = activeConfig();
  $('adjustControls').innerHTML = `
    <div class="document-tool-control">
      <span>裁剪模式</span>
      <div class="document-tool-choice-row">
        ${optionButtons('crop_mode', [
          { value: 'auto', label: '自动' },
          { value: 'rect_only', label: '仅矩形' },
          { value: 'none', label: '不裁剪' }
        ], 'auto')}
      </div>
    </div>
    <div class="document-tool-control">
      <span>裁剪边距</span>
      <div class="document-tool-choice-row">
        ${optionButtons('expand_level', [
          { value: 'tight', label: '紧凑' },
          { value: 'normal', label: '标准' },
          { value: 'loose', label: '宽松' },
          { value: 'x-loose', label: '超宽松' }
        ], 'normal')}
      </div>
    </div>
    <div class="document-tool-control">
      <span>比例修剪</span>
      <div class="document-tool-choice-row">
        ${optionButtons('ratio_trim', [
          { value: 'on', label: '开启' },
          { value: 'off', label: '关闭' }
        ], 'on')}
      </div>
    </div>
    <div class="document-tool-control">
      <span>边缘灵敏度</span>
      <div class="document-tool-choice-row">
        ${optionButtons('canny_scale', [
          { value: '1.5', label: '低' },
          { value: '1.0', label: '标准' },
          { value: '0.6', label: '高' },
          { value: '0.35', label: '极高' }
        ], '1.0')}
      </div>
    </div>
    ${cfg.fields.map(field => `
      <div class="document-tool-control">
        <span>${field.label}旋转</span>
        <div class="document-tool-choice-row">
          ${optionButtons(field.rotateKey, [
            { value: '0', label: '0°' },
            { value: '90', label: '90°' },
            { value: '180', label: '180°' },
            { value: '270', label: '270°' }
          ], '0')}
        </div>
      </div>
    `).join('')}
  `;
}

function groupValue(name) {
  const el = document.querySelector(`.document-tool-choice[data-group="${name}"].active`);
  return el ? el.dataset.value : '';
}

function collectAdjustments() {
  const adjustments = {};
  const cropMode = groupValue('crop_mode') || 'auto';
  adjustments.crop_mode = cropMode;
  const expandLevel = groupValue('expand_level');
  if (expandLevel && expandLevel !== 'normal') adjustments.expand_level = expandLevel;
  if (groupValue('ratio_trim') === 'off') adjustments.skip_ratio_trim = true;
  const cannyScale = groupValue('canny_scale');
  if (cannyScale && Number(cannyScale) !== 1) adjustments.canny_scale = Number(cannyScale);
  activeConfig().fields.forEach(field => {
    const rotate = Number(groupValue(field.rotateKey) || '0');
    if (rotate) adjustments[field.rotateKey] = rotate;
  });
  return adjustments;
}

function fileByField(fieldKey) {
  return state.task && state.task.inputs ? state.task.inputs[fieldKey] : null;
}

function renderTask(task) {
  state.task = task;
  $('adjustPanel').hidden = false;
  $('previewPanel').hidden = false;
  $('zipDownloadLink').href = task.zip_url || '#';

  $('inputList').innerHTML = activeConfig().fields.map(field => {
    const input = fileByField(field.key);
    if (!input) {
      return `<div class="document-tool-card empty"><div>${field.label}</div><small>未上传</small></div>`;
    }
    return `
      <div class="document-tool-card">
        <img src="${input.url}" alt="${field.label}">
        <div class="document-tool-card-foot">
          <span>${field.label}</span>
          <button type="button" data-crop="${field.key}">调整裁剪框</button>
        </div>
      </div>
    `;
  }).join('');

  const outputs = task.outputs || [];
  $('outputList').innerHTML = outputs.length ? outputs.map(output => `
    <div class="document-tool-card">
      <img src="${output.url}?v=${Date.now()}" alt="${output.filename}">
      <div class="document-tool-card-foot">
        <span>${output.filename}</span>
        <a href="${output.download_url}" target="_blank" rel="noopener">下载</a>
      </div>
    </div>
  `).join('') : '<div class="document-tool-empty">暂无生成结果</div>';
}

async function createTask(event) {
  event.preventDefault();
  const form = $('documentToolForm');
  const formData = new FormData(form);
  formData.set('document_type', state.documentType);
  showMessage('正在生成...', 'info');
  $('generateBtn').disabled = true;
  try {
    const data = await requestJson('/api/admin/document_tools/tasks', {
      method: 'POST',
      body: formData
    });
    state.points = {};
    renderTask(data.task);
    showMessage('生成完成', 'success');
  } catch (err) {
    showMessage(err.message, 'error');
  } finally {
    $('generateBtn').disabled = false;
  }
}

async function regenerateTask() {
  if (!state.task) return;
  showMessage('正在重新生成...', 'info');
  $('regenerateBtn').disabled = true;
  try {
    const data = await requestJson(`/api/admin/document_tools/tasks/${state.task.id}/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        adjustments: collectAdjustments(),
        points: state.points
      })
    });
    renderTask(data.task);
    showMessage('已重新生成', 'success');
  } catch (err) {
    showMessage(err.message, 'error');
  } finally {
    $('regenerateBtn').disabled = false;
  }
}

async function reanalyzePoints() {
  if (!state.task) return;
  showMessage('正在识别裁剪框...', 'info');
  try {
    const data = await requestJson(`/api/admin/document_tools/tasks/${state.task.id}/analyze_points`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ adjustments: collectAdjustments() })
    });
    state.points = Object.assign({}, state.points, data.points || {});
    showMessage('已更新裁剪框', 'success');
  } catch (err) {
    showMessage(err.message, 'error');
  }
}

function getFieldConfig(fieldKey) {
  return activeConfig().fields.find(field => field.key === fieldKey);
}

function initDefaultCropPoints(img) {
  const insetX = Math.round(img.naturalWidth * 0.04);
  const insetY = Math.round(img.naturalHeight * 0.04);
  return [
    [insetX, insetY],
    [img.naturalWidth - insetX, insetY],
    [img.naturalWidth - insetX, img.naturalHeight - insetY],
    [insetX, img.naturalHeight - insetY]
  ];
}

function openCropModal(fieldKey) {
  const field = getFieldConfig(fieldKey);
  const input = fileByField(fieldKey);
  if (!field || !input) return;
  const modal = $('cropModal');
  const img = new Image();
  img.onload = () => {
    state.crop = {
      field,
      pointKey: field.pointKey,
      image: img,
      imageUrl: input.url,
      points: (state.points[field.pointKey] || initDefaultCropPoints(img)).map(point => [...point])
    };
    $('cropModalTitle').textContent = field.label;
    modal.hidden = false;
    drawCropCanvas();
  };
  img.src = input.url;
}

function cropTransform(resizeCanvas = false) {
  const canvas = $('cropCanvas');
  const img = state.crop.image;
  const maxW = canvas.parentElement.clientWidth || 900;
  const maxH = canvas.parentElement.clientHeight || 620;
  const scale = Math.min(maxW / img.naturalWidth, maxH / img.naturalHeight);
  const width = Math.max(1, Math.round(img.naturalWidth * scale));
  const height = Math.max(1, Math.round(img.naturalHeight * scale));
  if (resizeCanvas) {
    canvas.width = width;
    canvas.height = height;
  }
  return { scale, width, height };
}

function drawCropCanvas() {
  const canvas = $('cropCanvas');
  const ctx = canvas.getContext('2d');
  const img = state.crop.image;
  if (!img) return;
  const { scale, width, height } = cropTransform(true);
  ctx.clearRect(0, 0, width, height);
  ctx.drawImage(img, 0, 0, width, height);
  const pts = state.crop.points.map(([x, y]) => [x * scale, y * scale]);
  ctx.fillStyle = 'rgba(15,23,42,0.36)';
  ctx.fillRect(0, 0, width, height);
  ctx.save();
  ctx.beginPath();
  pts.forEach(([x, y], index) => index ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.closePath();
  ctx.clip();
  ctx.drawImage(img, 0, 0, width, height);
  ctx.restore();
  ctx.strokeStyle = '#2563eb';
  ctx.lineWidth = 3;
  ctx.beginPath();
  pts.forEach(([x, y], index) => index ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.closePath();
  ctx.stroke();
  pts.forEach(([x, y]) => {
    ctx.beginPath();
    ctx.arc(x, y, 8, 0, Math.PI * 2);
    ctx.fillStyle = '#fff';
    ctx.fill();
    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 3;
    ctx.stroke();
  });
}

function canvasPoint(event) {
  const rect = $('cropCanvas').getBoundingClientRect();
  return [event.clientX - rect.left, event.clientY - rect.top];
}

function nearestHandle(x, y) {
  const canvas = $('cropCanvas');
  const scale = canvas.width / Math.max(1, state.crop.image.naturalWidth);
  let best = -1;
  let bestDist = 9999;
  state.crop.points.forEach(([ox, oy], index) => {
    const dx = ox * scale - x;
    const dy = oy * scale - y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < bestDist && dist <= 18) {
      best = index;
      bestDist = dist;
    }
  });
  return best;
}

function setupCropCanvasDrag() {
  const canvas = $('cropCanvas');
  let dragging = -1;
  canvas.addEventListener('mousedown', event => {
    const [x, y] = canvasPoint(event);
    dragging = nearestHandle(x, y);
  });
  canvas.addEventListener('mousemove', event => {
    const [x, y] = canvasPoint(event);
    if (dragging < 0) {
      canvas.style.cursor = nearestHandle(x, y) >= 0 ? 'grab' : 'default';
      return;
    }
    const scale = canvas.width / Math.max(1, state.crop.image.naturalWidth);
    state.crop.points[dragging] = [
      Math.round(Math.max(0, Math.min(state.crop.image.naturalWidth, x / scale))),
      Math.round(Math.max(0, Math.min(state.crop.image.naturalHeight, y / scale)))
    ];
    drawCropCanvas();
  });
  const stop = () => { dragging = -1; };
  canvas.addEventListener('mouseup', stop);
  canvas.addEventListener('mouseleave', stop);
}

function closeCropModal() {
  $('cropModal').hidden = true;
}

function saveCropPoints() {
  if (state.crop.pointKey) {
    state.points[state.crop.pointKey] = state.crop.points.map(point => [...point]);
  }
  closeCropModal();
  showMessage('裁剪框已保存，点击重新生成应用', 'info');
}

function resetCropPoints() {
  if (!state.crop.image) return;
  state.crop.points = initDefaultCropPoints(state.crop.image);
  drawCropCanvas();
}

document.addEventListener('DOMContentLoaded', () => {
  renderUploadFields();
  renderAdjustControls();
  setupCropCanvasDrag();

  document.querySelectorAll('.document-tool-type').forEach(btn => {
    btn.addEventListener('click', () => setDocumentType(btn.dataset.type));
  });
  $('documentToolForm').addEventListener('submit', createTask);
  $('resetBtn').addEventListener('click', () => {
    $('documentToolForm').reset();
    state.task = null;
    state.points = {};
    $('adjustPanel').hidden = true;
    $('previewPanel').hidden = true;
    showMessage('');
  });
  $('adjustControls').addEventListener('click', event => {
    const btn = event.target.closest('.document-tool-choice');
    if (!btn) return;
    document.querySelectorAll(`.document-tool-choice[data-group="${btn.dataset.group}"]`).forEach(item => {
      item.classList.toggle('active', item === btn);
    });
  });
  $('inputList').addEventListener('click', event => {
    const btn = event.target.closest('[data-crop]');
    if (btn) openCropModal(btn.dataset.crop);
  });
  $('regenerateBtn').addEventListener('click', regenerateTask);
  $('reanalyzeBtn').addEventListener('click', reanalyzePoints);
  $('cropModalClose').addEventListener('click', closeCropModal);
  $('cropSaveBtn').addEventListener('click', saveCropPoints);
  $('cropResetBtn').addEventListener('click', resetCropPoints);
  $('cropModal').addEventListener('click', event => {
    if (event.target === $('cropModal')) closeCropModal();
  });
  window.addEventListener('resize', () => {
    if (!$('cropModal').hidden) drawCropCanvas();
  });
});
