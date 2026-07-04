const DOC_CONFIG = {
  id_card: {
    label: '身份证',
    title: '身份证调整',
    fields: [
      { key: 'id_card_front', label: '身份证正面', pointKey: 'front_points', rotateKey: 'front_rotate' },
      { key: 'id_card_back', label: '身份证反面', pointKey: 'back_points', rotateKey: 'back_rotate' }
    ]
  },
  hukou: {
    label: '户口本',
    title: '户口本调整',
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
  previewUrls: {}
};

const pillBase = 'display:inline-flex;align-items:center;padding:5px 12px;border:1px solid #CBD5E1;border-radius:6px;font-size:12px;cursor:pointer;transition:all .15s;margin:0 4px 4px 0;';
const pillOff = `${pillBase}background:#fff;color:#475569;`;
const pillOn = `${pillBase}background:#4F46E5;color:#fff;border-color:#4F46E5;`;

function $(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[ch]));
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

function revokePreviewUrls() {
  Object.values(state.previewUrls).forEach(item => {
    if (item && item.url) URL.revokeObjectURL(item.url);
  });
  state.previewUrls = {};
}

function setDocumentType(type) {
  state.documentType = DOC_CONFIG[type] ? type : 'id_card';
  state.task = null;
  state.points = {};
  revokePreviewUrls();
  document.querySelectorAll('.document-tool-type').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.type === state.documentType);
  });
  renderUploadFields();
  $('documentToolForm').reset();
  $('previewPanel').hidden = true;
  $('resultActions').hidden = true;
  showMessage('');
}

function renderUploadFields() {
  $('uploadFields').innerHTML = activeConfig().fields.map(field => `
    <label class="document-tool-upload">
      <span>${field.label}</span>
      <input type="file" name="${field.key}" accept="image/*" data-preview-field="${field.key}">
    </label>
  `).join('');
}

function selectedFileForField(fieldKey) {
  const input = document.querySelector(`input[name="${fieldKey}"]`);
  return input && input.files && input.files[0] ? input.files[0] : null;
}

function refreshSelectedPreviewUrl(fieldKey, file) {
  const previous = state.previewUrls[fieldKey];
  if (previous && previous.url) URL.revokeObjectURL(previous.url);
  if (!file) {
    delete state.previewUrls[fieldKey];
    return;
  }
  state.previewUrls[fieldKey] = {
    name: file.name || '本地图片',
    url: URL.createObjectURL(file)
  };
}

function renderSelectedPreviews() {
  const cfg = activeConfig();
  const cards = cfg.fields.map(field => {
    const item = state.previewUrls[field.key];
    const label = escapeHtml(field.label);
    if (!item) {
      return `<div class="document-tool-card empty"><div>${label}</div><small>未选择</small></div>`;
    }
    return `
      <div class="document-tool-card">
        <img src="${escapeHtml(item.url)}" alt="${label}">
        <div class="document-tool-card-foot">
          <span>${label}</span>
          <small>${escapeHtml(item.name)}</small>
        </div>
      </div>
    `;
  }).join('');
  const hasAny = cfg.fields.some(field => state.previewUrls[field.key]);
  $('inputList').innerHTML = cards;
  if (!state.task) {
    $('outputList').innerHTML = '<div class="document-tool-empty">生成后显示结果</div>';
    $('resultActions').hidden = true;
  }
  $('previewPanel').hidden = !hasAny && !state.task;
}

function fileByField(fieldKey) {
  return state.task && state.task.inputs ? state.task.inputs[fieldKey] : null;
}

function renderInputCardsFromTask() {
  $('inputList').innerHTML = activeConfig().fields.map(field => {
    const input = fileByField(field.key);
    const label = escapeHtml(field.label);
    if (!input) {
      return `<div class="document-tool-card empty"><div>${label}</div><small>未上传</small></div>`;
    }
    return `
      <div class="document-tool-card">
        <img src="${escapeHtml(input.url)}" alt="${label}">
        <div class="document-tool-card-foot">
          <span>${label}</span>
          <small>${escapeHtml(input.filename)}</small>
        </div>
      </div>
    `;
  }).join('');
}

function renderTask(task) {
  state.task = task;
  $('previewPanel').hidden = false;
  $('resultActions').hidden = false;
  $('zipDownloadLink').href = task.zip_url || '#';
  renderInputCardsFromTask();

  const outputs = task.outputs || [];
  $('outputList').innerHTML = outputs.length ? outputs.map(output => `
    <div class="document-tool-card">
      <img src="${escapeHtml(output.url)}?v=${Date.now()}" alt="${escapeHtml(output.filename)}">
      <div class="document-tool-card-foot">
        <span>${escapeHtml(output.filename)}</span>
        <a href="${escapeHtml(output.download_url)}" target="_blank" rel="noopener">下载</a>
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

function fieldRow(label, name, options, defaultValue) {
  return `
    <div style="margin-bottom:16px;">
      <div style="font-size:12px;font-weight:700;color:#334155;margin-bottom:8px;">${label}</div>
      <div>
        ${options.map(opt => `
          <span class="adj-pill" data-group="${name}" data-value="${opt.value}"${String(opt.value) === String(defaultValue) ? ' data-active="1"' : ''} style="${String(opt.value) === String(defaultValue) ? pillOn : pillOff}">${opt.label}</span>
        `).join('')}
      </div>
    </div>
  `;
}

function buildAdjustmentControlsHtml() {
  const cfg = activeConfig();
  let html = fieldRow('裁剪模式', 'crop_mode', [
    { value: 'auto', label: '自动' },
    { value: 'rect_only', label: '仅矩形' },
    { value: 'none', label: '不裁剪' }
  ], 'auto');
  html += fieldRow('裁剪边距', 'expand_level', [
    { value: 'tight', label: '紧凑' },
    { value: 'normal', label: '标准' },
    { value: 'loose', label: '宽松' },
    { value: 'x-loose', label: '超宽松' }
  ], 'normal');
  html += fieldRow('比例修剪', 'ratio_trim', [
    { value: 'on', label: '开启' },
    { value: 'off', label: '关闭' }
  ], 'on');
  html += fieldRow('边缘灵敏度', 'canny_scale', [
    { value: '1.5', label: '低灵敏' },
    { value: '1.0', label: '标准' },
    { value: '0.6', label: '高灵敏' },
    { value: '0.35', label: '极高灵敏' }
  ], '1.0');
  cfg.fields.forEach(field => {
    html += fieldRow(`${field.label}旋转`, field.rotateKey, [
      { value: '0', label: '0°' },
      { value: '90', label: '90°' },
      { value: '180', label: '180°' },
      { value: '270', label: '270°' }
    ], '0');
  });
  return html;
}

function getPanelGroupValue(panel, name) {
  const el = panel.querySelector(`.adj-pill[data-group="${name}"][data-active="1"]`);
  return el ? el.dataset.value : '';
}

function collectModalAdjustments(panel) {
  const adjustments = {};
  const cropMode = getPanelGroupValue(panel, 'crop_mode') || 'auto';
  adjustments.crop_mode = cropMode;
  const expandLevel = getPanelGroupValue(panel, 'expand_level');
  if (expandLevel && expandLevel !== 'normal') adjustments.expand_level = expandLevel;
  if (getPanelGroupValue(panel, 'ratio_trim') === 'off') adjustments.skip_ratio_trim = true;
  const cannyScale = getPanelGroupValue(panel, 'canny_scale');
  if (cannyScale && Number(cannyScale) !== 1) adjustments.canny_scale = Number(cannyScale);
  activeConfig().fields.forEach(field => {
    const rotate = Number(getPanelGroupValue(panel, field.rotateKey) || '0');
    if (rotate) adjustments[field.rotateKey] = rotate;
  });
  return adjustments;
}

function canvasPoint(canvas, event) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / Math.max(1, rect.width);
  const scaleY = canvas.height / Math.max(1, rect.height);
  return [
    Math.round((event.clientX - rect.left) * scaleX),
    Math.round((event.clientY - rect.top) * scaleY)
  ];
}

function createTaskRequestGuard(getCurrentTaskId) {
  let sequence = 0;
  let active = true;
  return {
    next(taskId) {
      sequence += 1;
      return { taskId, sequence };
    },
    isCurrent(token, taskId) {
      return active && token && token.sequence === sequence && token.taskId === taskId && getCurrentTaskId() === taskId;
    },
    invalidate() {
      sequence += 1;
    },
    close() {
      active = false;
      sequence += 1;
    }
  };
}

function buildAdjustImagePanel(field, cropState) {
  const input = fileByField(field.key);
  const wrap = document.createElement('div');
  wrap.style.cssText = 'display:flex;flex-direction:column;gap:8px;height:100%;';

  const imgWrap = document.createElement('div');
  imgWrap.style.cssText = 'position:relative;flex:1;min-height:0;background:#1e1e2e;border-radius:8px;overflow:hidden;border:1.5px solid #e5e7eb;line-height:0;';

  const img = document.createElement('img');
  img.src = input ? input.url : '';
  img.style.cssText = 'display:none;';
  img.draggable = false;

  const cvs = document.createElement('canvas');
  cvs.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;cursor:default;';

  const statusEl = document.createElement('div');
  statusEl.style.cssText = 'font-size:11.5px;color:#6b7280;flex-shrink:0;height:16px;';
  statusEl.textContent = input ? '图片加载中...' : '未上传原图';

  const bottomRow = document.createElement('div');
  bottomRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;flex-shrink:0;';
  const hintEl = document.createElement('div');
  hintEl.style.cssText = 'font-size:11px;color:#9ca3af;';
  hintEl.textContent = '不标记则按左侧参数自动裁剪';
  const resetBtn = document.createElement('button');
  resetBtn.textContent = '重置为整张图';
  resetBtn.style.cssText = 'font-size:11px;padding:2px 10px;border:1px solid #d1d5db;border-radius:5px;background:#f9fafb;color:#374151;cursor:pointer;';
  bottomRow.appendChild(hintEl);
  bottomRow.appendChild(resetBtn);

  const HANDLE_R = 8;
  let originalPts = state.points[field.pointKey] ? state.points[field.pointKey].map(point => [...point]) : null;
  let dispPts = null;
  let dragging = -1;
  let userDragged = false;
  let hasConfirmedPoints = !!originalPts;
  let rotationDeg = 0;

  function getTransform() {
    const W = cvs.clientWidth || cvs.parentElement.clientWidth || 1;
    const H = cvs.clientHeight || cvs.parentElement.clientHeight || 1;
    const rad = rotationDeg * Math.PI / 180;
    const cos = Math.abs(Math.cos(rad));
    const sin = Math.abs(Math.sin(rad));
    const nw = img.naturalWidth || 1;
    const nh = img.naturalHeight || 1;
    const effW = nw * cos + nh * sin;
    const effH = nw * sin + nh * cos;
    const scale = Math.min(W / effW, H / effH) * 0.88;
    return { W, H, rad, scale, nw, nh, cx: W / 2, cy: H / 2 };
  }

  function origToDisp([ox, oy]) {
    const { rad, scale, nw, nh, cx, cy } = getTransform();
    const dx = (ox - nw / 2) * scale;
    const dy = (oy - nh / 2) * scale;
    return [
      Math.round(cx + dx * Math.cos(rad) - dy * Math.sin(rad)),
      Math.round(cy + dx * Math.sin(rad) + dy * Math.cos(rad))
    ];
  }

  function dispToOrig([mx, my]) {
    const { rad, scale, nw, nh, cx, cy } = getTransform();
    const dx = mx - cx;
    const dy = my - cy;
    const ox = Math.round((dx * Math.cos(-rad) - dy * Math.sin(-rad)) / scale + nw / 2);
    const oy = Math.round((dx * Math.sin(-rad) + dy * Math.cos(-rad)) / scale + nh / 2);
    return [ox, oy];
  }

  function refreshDispPts() {
    if (originalPts) dispPts = originalPts.map(point => origToDisp(point));
  }

  function syncCropState() {
    cropState[field.pointKey] = {
      displayPts: dispPts ? dispPts.map(point => [...point]) : [],
      originalPts: originalPts ? originalPts.map(point => [...point]) : []
    };
  }

  function initRect() {
    const nw = img.naturalWidth;
    const nh = img.naturalHeight;
    if (!nw || !nh) return;
    if (!originalPts) {
      originalPts = [[0, 0], [nw, 0], [nw, nh], [0, nh]];
    }
    refreshDispPts();
    syncCropState();
  }

  function redraw() {
    const { W, H, rad, scale, nw, nh, cx, cy } = getTransform();
    cvs.width = W;
    cvs.height = H;
    const ctx = cvs.getContext('2d');
    ctx.clearRect(0, 0, W, H);

    if (img.complete && nw > 1) {
      const drawW = nw * scale;
      const drawH = nh * scale;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(rad);
      ctx.drawImage(img, -drawW / 2, -drawH / 2, drawW, drawH);
      ctx.restore();
    }
    if (!dispPts) return;

    ctx.fillStyle = 'rgba(0,0,0,0.42)';
    ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(dispPts[0][0], dispPts[0][1]);
    dispPts.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
    ctx.closePath();
    ctx.globalCompositeOperation = 'destination-out';
    ctx.fill();
    ctx.restore();

    ctx.save();
    const imgTL = origToDisp([0, 0]);
    const imgTR = origToDisp([nw, 0]);
    const imgBR = origToDisp([nw, nh]);
    const imgBL = origToDisp([0, nh]);
    ctx.strokeStyle = 'rgba(255,255,255,0.55)';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    ctx.moveTo(imgTL[0], imgTL[1]);
    ctx.lineTo(imgTR[0], imgTR[1]);
    ctx.lineTo(imgBR[0], imgBR[1]);
    ctx.lineTo(imgBL[0], imgBL[1]);
    ctx.closePath();
    ctx.stroke();
    ctx.restore();

    ctx.beginPath();
    ctx.moveTo(dispPts[0][0], dispPts[0][1]);
    dispPts.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
    ctx.closePath();
    ctx.strokeStyle = '#6366f1';
    ctx.lineWidth = 2;
    ctx.setLineDash([]);
    ctx.stroke();

    dispPts.forEach(([x, y], index) => {
      ctx.beginPath();
      ctx.arc(x, y, HANDLE_R, 0, Math.PI * 2);
      ctx.fillStyle = '#fff';
      ctx.fill();
      ctx.strokeStyle = '#6366f1';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = '#4f46e5';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(index + 1), x, y);
    });
  }

  function hitTest(mx, my) {
    if (!dispPts) return -1;
    let best = -1;
    let bestD = HANDLE_R * 2;
    dispPts.forEach(([x, y], index) => {
      const d = Math.hypot(mx - x, my - y);
      if (d < bestD) {
        bestD = d;
        best = index;
      }
    });
    return best;
  }

  cvs.addEventListener('mousedown', event => {
    if (!dispPts) {
      initRect();
      redraw();
    }
    const [mx, my] = canvasPoint(cvs, event);
    dragging = hitTest(mx, my);
    if (dragging >= 0) {
      event.preventDefault();
      cvs.style.cursor = 'grabbing';
    }
  });

  cvs.addEventListener('mousemove', event => {
    const [mx, my] = canvasPoint(cvs, event);
    if (dragging >= 0) {
      dispPts[dragging] = [mx, my];
      originalPts[dragging] = dispToOrig([mx, my]);
      syncCropState();
      redraw();
    } else {
      cvs.style.cursor = hitTest(mx, my) >= 0 ? 'grab' : 'default';
    }
  });

  const stopDrag = () => {
    if (dragging >= 0) {
      userDragged = true;
      hasConfirmedPoints = true;
      syncCropState();
      statusEl.style.color = '#059669';
      statusEl.textContent = '✓ 已手动调整裁剪区域，点击「重新生成」确认';
    }
    dragging = -1;
    cvs.style.cursor = 'default';
  };
  cvs.addEventListener('mouseup', stopDrag);
  cvs.addEventListener('mouseleave', stopDrag);

  resetBtn.onclick = () => {
    userDragged = false;
    hasConfirmedPoints = false;
    originalPts = null;
    dispPts = null;
    initRect();
    redraw();
    statusEl.textContent = '拖动角点调整裁剪区域';
    statusEl.style.color = '#6b7280';
  };

  wrap.applyServerPoints = points => {
    if (userDragged || hasConfirmedPoints) return;
    originalPts = points.map(point => [...point]);
    hasConfirmedPoints = false;
    refreshDispPts();
    syncCropState();
    redraw();
    statusEl.style.color = '#059669';
    statusEl.textContent = '✓ 已加载预识别裁剪区域，可拖动角点微调';
  };
  wrap.getHasDragged = () => userDragged;
  wrap.getHasConfirmed = () => hasConfirmedPoints;
  wrap.setStatus = (text, color) => {
    statusEl.textContent = text;
    statusEl.style.color = color || '#6b7280';
  };
  wrap.setRotation = deg => {
    rotationDeg = deg;
    refreshDispPts();
    syncCropState();
    redraw();
  };
  wrap.clearMarkedPoints = (statusText = '已清空手动裁剪点位，将按当前模式自动处理') => {
    userDragged = false;
    hasConfirmedPoints = false;
    originalPts = null;
    dispPts = null;
    initRect();
    syncCropState();
    redraw();
    statusEl.textContent = statusText;
    statusEl.style.color = '#6b7280';
  };

  function onImgReady() {
    if (!img.complete || img.naturalWidth === 0) return;
    if (cvs.clientWidth === 0) return;
    initRect();
    if (hasConfirmedPoints) {
      statusEl.textContent = '✓ 已加载历史裁剪区域，可拖动角点微调';
      statusEl.style.color = '#059669';
    } else {
      statusEl.textContent = '拖动角点调整裁剪区域（直接重新生成则按当前参数处理）';
      statusEl.style.color = '#6b7280';
    }
    redraw();
  }

  img.onload = () => setTimeout(onImgReady, 60);
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => {
      if (cvs.clientWidth > 0) {
        refreshDispPts();
        redraw();
      }
    });
    ro.observe(imgWrap);
  } else {
    window.addEventListener('resize', () => {
      refreshDispPts();
      redraw();
    });
  }

  if (!input) {
    imgWrap.innerHTML = '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#9ca3af;font-size:13px;">未上传</div>';
  } else {
    imgWrap.appendChild(img);
    imgWrap.appendChild(cvs);
  }
  wrap.appendChild(imgWrap);
  wrap.appendChild(statusEl);
  wrap.appendChild(bottomRow);
  return wrap;
}

function openAdjustmentModal() {
  if (!state.task) return;
  const cfg = activeConfig();
  const cropState = {};
  cfg.fields.forEach(field => {
    cropState[field.pointKey] = { displayPts: [], originalPts: [] };
  });

  const panel = document.createElement('div');
  panel.style.cssText = 'position:fixed;inset:0;z-index:5000;background:rgba(15,23,42,.62);display:flex;align-items:center;justify-content:center;padding:20px;';

  const modal = document.createElement('div');
  modal.style.cssText = 'background:#fff;border-radius:14px;width:100%;max-width:1500px;height:94vh;max-height:94vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.25);overflow:hidden;';

  const header = document.createElement('div');
  header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:14px 22px;border-bottom:1px solid #e5e7eb;flex-shrink:0;';
  header.innerHTML = `<div style="font-size:15px;font-weight:700;color:#111;">${cfg.title}</div>
    <button id="doc-adjust-close" style="border:none;background:none;font-size:22px;cursor:pointer;color:#9ca3af;line-height:1;">×</button>`;

  const body = document.createElement('div');
  body.style.cssText = 'display:flex;flex:1;min-height:0;overflow:hidden;';

  const leftPane = document.createElement('div');
  leftPane.style.cssText = 'width:320px;flex-shrink:0;border-right:1px solid #f0f0f0;overflow-y:auto;padding:18px 20px;';
  leftPane.innerHTML = buildAdjustmentControlsHtml();

  const rightPane = document.createElement('div');
  rightPane.style.cssText = 'flex:1;min-width:0;padding:16px 20px;overflow:hidden;display:flex;flex-direction:column;';
  const rightTitle = document.createElement('div');
  rightTitle.style.cssText = 'font-size:12px;color:#6b7280;margin-bottom:10px;flex-shrink:0;';
  rightTitle.textContent = '可选：拖动角点调整裁剪区域（直接点「重新生成」则按左侧参数自动裁剪）';

  const rightContent = document.createElement('div');
  rightContent.style.cssText = 'display:flex;flex-direction:column;flex:1;min-height:0;';
  const tabBar = document.createElement('div');
  tabBar.style.cssText = 'display:flex;gap:6px;margin-bottom:10px;flex-shrink:0;';
  const panelContainer = document.createElement('div');
  panelContainer.style.cssText = 'flex:1;min-height:0;overflow:hidden;';
  const panelEls = {};
  const activeStyle = 'padding:5px 14px;border:none;border-radius:7px;font-size:12px;cursor:pointer;background:#4F46E5;color:#fff;font-weight:600;';
  const inactiveStyle = 'padding:5px 14px;border:1px solid #e5e7eb;border-radius:7px;font-size:12px;cursor:pointer;background:#fff;color:#475569;';

  cfg.fields.forEach((field, index) => {
    const tab = document.createElement('button');
    tab.textContent = field.label;
    tab.dataset.key = field.pointKey;
    tab.style.cssText = index === 0 ? activeStyle : inactiveStyle;
    tab.onclick = () => {
      tabBar.querySelectorAll('button').forEach(btn => {
        btn.style.cssText = btn.dataset.key === field.pointKey ? activeStyle : inactiveStyle;
      });
      Object.entries(panelEls).forEach(([key, el]) => {
        el.style.display = key === field.pointKey ? 'flex' : 'none';
      });
    };
    tabBar.appendChild(tab);

    const el = buildAdjustImagePanel(field, cropState);
    el.style.display = index === 0 ? 'flex' : 'none';
    el.style.height = '100%';
    panelEls[field.pointKey] = el;
    panelContainer.appendChild(el);
  });

  rightContent.appendChild(tabBar);
  rightContent.appendChild(panelContainer);
  rightPane.appendChild(rightTitle);
  rightPane.appendChild(rightContent);
  body.appendChild(leftPane);
  body.appendChild(rightPane);

  const footer = document.createElement('div');
  footer.style.cssText = 'display:flex;gap:10px;justify-content:flex-end;align-items:center;padding:12px 22px;border-top:1px solid #e5e7eb;flex-shrink:0;background:#fafafa;';
  footer.innerHTML = `
    <button id="doc-adjust-cancel" style="padding:7px 20px;border:1px solid #CBD5E1;border-radius:7px;background:#fff;cursor:pointer;font-size:13px;color:#475569;">取消</button>
    <button id="doc-adjust-submit" style="padding:7px 22px;border:none;border-radius:7px;background:#4F46E5;color:#fff;cursor:pointer;font-size:13px;font-weight:600;">重新生成</button>`;

  modal.appendChild(header);
  modal.appendChild(body);
  modal.appendChild(footer);
  panel.appendChild(modal);
  document.body.appendChild(panel);

  const taskIdAtOpen = state.task.id;
  const reanalyzeGuard = createTaskRequestGuard(() => state.task && state.task.id);
  let reanalyzeController = null;
  let reanalyzeTimer = null;

  function abortReanalyze() {
    if (reanalyzeController) {
      reanalyzeController.abort();
      reanalyzeController = null;
    }
  }

  function buildNonRotationAdjustments() {
    const adjustments = collectModalAdjustments(panel);
    activeConfig().fields.forEach(field => {
      delete adjustments[field.rotateKey];
    });
    return adjustments;
  }

  function reanalyzePoints(adjustments) {
    if (adjustments.crop_mode === 'none') {
      reanalyzeGuard.invalidate();
      abortReanalyze();
      cfg.fields.forEach(field => {
        const el = panelEls[field.pointKey];
        if (el) el.clearMarkedPoints('「不裁剪」模式：将保留全图');
      });
      return;
    }
    cfg.fields.forEach(field => {
      const el = panelEls[field.pointKey];
      if (el && !el.getHasDragged() && !el.getHasConfirmed()) el.setStatus('⏳ 计算中...', '#9ca3af');
    });
    const token = reanalyzeGuard.next(taskIdAtOpen);
    abortReanalyze();
    reanalyzeController = window.AbortController ? new AbortController() : null;
    const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ adjustments })
    };
    if (reanalyzeController) requestOptions.signal = reanalyzeController.signal;

    requestJson(`/api/admin/document_tools/tasks/${taskIdAtOpen}/analyze_points`, requestOptions).then(data => {
      if (!reanalyzeGuard.isCurrent(token, taskIdAtOpen) || !panel.isConnected) return;
      cfg.fields.forEach(field => {
        const el = panelEls[field.pointKey];
        if (!el || el.getHasDragged() || el.getHasConfirmed()) return;
        const pts = data.points ? data.points[field.pointKey] : null;
        if (pts && pts.length === 4) {
          el.applyServerPoints(pts);
        } else {
          el.setStatus('未识别到边缘，将自动处理', '#9ca3af');
        }
      });
    }).catch(err => {
      if (err && err.name === 'AbortError') return;
      if (!reanalyzeGuard.isCurrent(token, taskIdAtOpen) || !panel.isConnected) return;
      cfg.fields.forEach(field => {
        const el = panelEls[field.pointKey];
        if (el && !el.getHasDragged() && !el.getHasConfirmed()) el.setStatus('计算失败', '#ef4444');
      });
    });
  }

  function scheduleReanalyze() {
    clearTimeout(reanalyzeTimer);
    reanalyzeTimer = setTimeout(() => reanalyzePoints(buildNonRotationAdjustments()), 400);
  }

  panel.addEventListener('click', event => {
    const pill = event.target.closest('.adj-pill');
    if (!pill) return;
    const group = pill.dataset.group;
    panel.querySelectorAll(`.adj-pill[data-group="${group}"]`).forEach(item => {
      item.style.cssText = pillOff;
      item.removeAttribute('data-active');
    });
    pill.style.cssText = pillOn;
    pill.setAttribute('data-active', '1');

    const field = activeConfig().fields.find(item => item.rotateKey === group);
    if (field && panelEls[field.pointKey]) {
      panelEls[field.pointKey].setRotation(parseInt(pill.dataset.value, 10) || 0);
    } else if (group === 'crop_mode' && pill.dataset.value === 'none') {
      clearTimeout(reanalyzeTimer);
      reanalyzeGuard.invalidate();
      abortReanalyze();
      cfg.fields.forEach(item => {
        const el = panelEls[item.pointKey];
        if (el) el.clearMarkedPoints('「不裁剪」模式：将保留全图');
      });
    } else {
      scheduleReanalyze();
    }
  });

  const close = () => {
    clearTimeout(reanalyzeTimer);
    reanalyzeGuard.close();
    abortReanalyze();
    panel.remove();
  };
  panel.querySelector('#doc-adjust-close').onclick = close;
  panel.querySelector('#doc-adjust-cancel').onclick = close;
  panel.addEventListener('click', event => {
    if (event.target === panel) close();
  });

  panel.querySelector('#doc-adjust-submit').onclick = async () => {
    const adjustments = collectModalAdjustments(panel);
    const markedPoints = {};
    cfg.fields.forEach(field => {
      const saved = cropState[field.pointKey];
      const panelEl = panelEls[field.pointKey];
      const shouldSubmitPoints = panelEl && (panelEl.getHasDragged() || panelEl.getHasConfirmed());
      if (shouldSubmitPoints && saved && saved.originalPts && saved.originalPts.length === 4) {
        markedPoints[field.pointKey] = saved.originalPts;
      }
    });

    const submitBtn = panel.querySelector('#doc-adjust-submit');
    submitBtn.textContent = '生成中...';
    submitBtn.disabled = true;
    showMessage('正在重新生成...', 'info');
    try {
      const data = await requestJson(`/api/admin/document_tools/tasks/${state.task.id}/regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ adjustments, points: markedPoints })
      });
      state.points = markedPoints;
      renderTask(data.task);
      showMessage('已重新生成', 'success');
      close();
    } catch (err) {
      showMessage(err.message, 'error');
      submitBtn.textContent = '重新生成';
      submitBtn.disabled = false;
    }
  };

  reanalyzePoints({});
}

document.addEventListener('DOMContentLoaded', () => {
  renderUploadFields();

  document.querySelectorAll('.document-tool-type').forEach(btn => {
    btn.addEventListener('click', () => setDocumentType(btn.dataset.type));
  });
  $('uploadFields').addEventListener('change', event => {
    const input = event.target.closest('input[type="file"][data-preview-field]');
    if (!input) return;
    state.task = null;
    state.points = {};
    refreshSelectedPreviewUrl(input.dataset.previewField, selectedFileForField(input.dataset.previewField));
    renderSelectedPreviews();
    showMessage('');
  });
  $('documentToolForm').addEventListener('submit', createTask);
  $('resetBtn').addEventListener('click', () => {
    $('documentToolForm').reset();
    state.task = null;
    state.points = {};
    revokePreviewUrls();
    $('previewPanel').hidden = true;
    $('resultActions').hidden = true;
    showMessage('');
  });
  $('openAdjustBtn').addEventListener('click', openAdjustmentModal);
});
