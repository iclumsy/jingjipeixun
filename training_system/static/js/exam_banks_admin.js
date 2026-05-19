const state = {
  projects: [],
  banks: []
};

function $(id) {
  return document.getElementById(id);
}

function showMessage(text, type = '') {
  const el = $('bankMessage');
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

function renderProjects() {
  const select = $('projectSelect');
  select.innerHTML = state.projects.map(project => {
    const label = `${project.training_type === 'special_equipment' ? '特种设备' : '特种作业'} / ${project.job_category} / ${project.exam_project}${project.project_code ? ` (${project.project_code})` : ''}`;
    return `<option value="${project.id}">${label}</option>`;
  }).join('');
}

function renderBanks() {
  const body = $('bankTableBody');
  if (!state.banks.length) {
    body.innerHTML = '<tr><td colspan="6">暂无题库</td></tr>';
    return;
  }
  body.innerHTML = state.banks.map(bank => `
    <tr>
      <td>
        <strong>${bank.display_name || bank.bank_key}</strong>
        <small>${bank.source_filename || ''}</small>
      </td>
      <td>${bank.project_code || '-'} · ${bank.exam_project || '-'}</td>
      <td>${bank.question_count || 0}</td>
      <td><span class="exam-bank-status ${bank.is_active ? 'active' : 'inactive'}">${bank.is_active ? '启用' : '停用'}</span></td>
      <td>${bank.imported_at || '-'}</td>
      <td class="exam-bank-actions">
        <label class="exam-bank-file-action">
          重导
          <input type="file" accept=".json,application/json" data-reimport="${bank.id}">
        </label>
        <button data-toggle="${bank.id}" data-active="${bank.is_active ? 0 : 1}">${bank.is_active ? '停用' : '启用'}</button>
      </td>
    </tr>
  `).join('');
}

async function loadProjects() {
  const data = await requestJson('/api/admin/exam_banks/projects?include_inactive=1');
  state.projects = data.projects || [];
  renderProjects();
}

async function loadBanks() {
  const data = await requestJson('/api/admin/exam_banks');
  state.banks = data.banks || [];
  renderBanks();
}

async function importBank(event) {
  event.preventDefault();
  showMessage('正在导入...', 'info');
  const form = $('importBankForm');
  const formData = new FormData(form);
  formData.set('is_active', $('activeInput').checked ? '1' : '0');
  try {
    await requestJson('/api/admin/exam_banks/import', {
      method: 'POST',
      body: formData
    });
    form.reset();
    $('activeInput').checked = true;
    showMessage('题库导入成功', 'success');
    await loadBanks();
  } catch (err) {
    showMessage(err.message, 'error');
  }
}

async function reimportBank(bankId, file) {
  const bank = state.banks.find(item => String(item.id) === String(bankId));
  if (!bank || !file) return;
  const formData = new FormData();
  formData.append('training_project_id', bank.training_project_id);
  formData.append('display_name', bank.display_name || bank.bank_key || '');
  formData.append('is_active', bank.is_active ? '1' : '0');
  formData.append('file', file);
  showMessage('正在重新导入...', 'info');
  try {
    await requestJson(`/api/admin/exam_banks/${bankId}/reimport`, {
      method: 'POST',
      body: formData
    });
    showMessage('重新导入成功', 'success');
    await loadBanks();
  } catch (err) {
    showMessage(err.message, 'error');
  }
}

async function toggleBank(bankId, active) {
  showMessage('正在更新状态...', 'info');
  try {
    await requestJson(`/api/admin/exam_banks/${bankId}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: Number(active) })
    });
    showMessage('状态已更新', 'success');
    await loadBanks();
  } catch (err) {
    showMessage(err.message, 'error');
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  $('importBankForm').addEventListener('submit', importBank);
  $('refreshBanksBtn').addEventListener('click', loadBanks);
  $('bankTableBody').addEventListener('click', event => {
    const toggle = event.target.dataset.toggle;
    if (toggle) {
      toggleBank(toggle, event.target.dataset.active);
    }
  });
  $('bankTableBody').addEventListener('change', event => {
    const bankId = event.target.dataset.reimport;
    if (bankId) {
      reimportBank(bankId, event.target.files[0]);
      event.target.value = '';
    }
  });

  try {
    await loadProjects();
    await loadBanks();
  } catch (err) {
    showMessage(err.message, 'error');
  }
});
