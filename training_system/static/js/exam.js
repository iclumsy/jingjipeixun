/* ===== 阳泉精技培训 在线练习系统 ===== */

const STORAGE_VERSION = 2;
const EXAM_DURATION = 60 * 60;       // 60 分钟
const EXAM_QUESTION_COUNT = 100;
const EXAM_PASS_SCORE = 80;
const HISTORY_LIMIT = 50;

const BANK_NAMES = {
  'N1_叉车司机': '叉车司机 (N1)',
  'A_电梯管理': '电梯管理 (A)',
  'G3_锅炉水处理': '锅炉水处理 (G3)',
  'G1_工业锅炉司炉': '工业锅炉司炉 (G1)',
  'Q3_起重机指挥': '起重机指挥 (Q3)',
  'Q2_门式起重机': '门式起重机 (Q2)',
  'Q2_桥式起重机': '桥式起重机 (Q2)',
  'N1_叉车司机_备选': '叉车司机 (备选库)'
};

let currentBank = 'N1_叉车司机';
let allQuestions = [];        // 经过清洗的可练习题
let droppedCount = 0;         // 因无答案被剔除的题数
let currentQuestions = [];
let currentIndex = 0;
let currentMode = '';
let userAnswers = {};
let answered = {};            // { idx: true/false }
let selectedOptions = [];
let isSubmitted = false;

let practiceProgress = 0;
let wrongSet = new Set();
let totalDone = 0;
let totalCorrect = 0;
let examHistory = [];

let examTimer = null;
let examTimeLeft = EXAM_DURATION;
let toastTimer = null;

// ===== 题型适配（不同题库 type_code 不一致） =====
function isJudge(q) {
  if (!q) return false;
  if (q.type === '判断题') return true;
  if (q.type_code === 3) return true;
  return false;
}
function isMulti(q) {
  if (!q) return false;
  if (q.type === '多选题') return true;
  return q.type_code === 2;
}
function isSingle(q) {
  if (!q) return false;
  if (q.type === '单选题') return true;
  return q.type_code === 1;
}
function isCase(q) {
  return q && (q.type === '案例分析题' || q.type_code === 4);
}

// 备选库判断题答案是 true/false 字符串/布尔；其它题库判断题用 ['A']/['a'] 等
function getJudgeBool(q) {
  if (q.answer === true || q.answer === 'true') return true;
  if (q.answer === false || q.answer === 'false') return false;
  if (Array.isArray(q.answer) && q.answer.length > 0) {
    const first = String(q.answer[0]).toLowerCase();
    // 一般 a 表示"正确"
    return first === 'a' || first === 'true' || first === '1' || first === '正确';
  }
  return null;
}
function hasAnswer(q) {
  if (q.answer === true || q.answer === false) return true;
  if (typeof q.answer === 'string') return q.answer.length > 0;
  if (Array.isArray(q.answer)) return q.answer.length > 0;
  return false;
}

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', async () => {
  bindEvents();
  try {
    currentBank = localStorage.getItem('ex_last_bank') || 'N1_叉车司机';
    if (!BANK_NAMES[currentBank]) currentBank = 'N1_叉车司机';
    updateBankUI();
    loadStorage();
    await loadQuestions();
    updateHomeStats();
  } catch (err) {
    console.error('初始化失败:', err);
    showToast('系统初始化失败：' + err.message, 'error');
  } finally {
    hideLoading();
  }
});

function bindEvents() {
  // 题库切换
  document.querySelectorAll('.bank-btn').forEach(btn => {
    btn.addEventListener('click', () => switchBank(btn.dataset.bank));
  });
  // 模式卡片
  document.querySelectorAll('.mode-card').forEach(card => {
    card.addEventListener('click', () => startMode(card.dataset.mode));
  });
  // 题型筛选
  document.querySelectorAll('.filter-chips .chip').forEach(chip => {
    chip.addEventListener('click', () => startMode('type', chip.dataset.filter));
  });
  // 顶部按钮
  document.getElementById('btn-back-home').addEventListener('click', () => goHome(true));
  document.getElementById('btn-header-finish').addEventListener('click', () => finishExam(false));
  document.getElementById('btn-prev').addEventListener('click', prevQuestion);
  document.getElementById('btn-next').addEventListener('click', nextQuestion);
  document.getElementById('btn-submit').addEventListener('click', () => submitAnswer(true));
  // 答题卡
  document.getElementById('btn-card-toggle').addEventListener('click', toggleAnswerCard);
  document.getElementById('btn-card-close').addEventListener('click', toggleAnswerCard);
  document.getElementById('answer-card-overlay').addEventListener('click', toggleAnswerCard);
  // 背题模式
  document.querySelectorAll('[data-action="home"]').forEach(b => b.addEventListener('click', () => goHome(false)));
  document.querySelectorAll('[data-action="reroll"]').forEach(b => b.addEventListener('click', () => startMode('memorize')));
  // 结果页
  document.getElementById('btn-result-home').addEventListener('click', () => goHome(false));
  document.getElementById('btn-result-review').addEventListener('click', reviewExam);
  // 数据维护
  document.getElementById('btn-reset-progress').addEventListener('click', resetCurrentBank);
  document.getElementById('btn-clear-history').addEventListener('click', clearHistory);
  // 键盘快捷键
  document.addEventListener('keydown', handleKeyboard);
}

function showLoading() {
  document.getElementById('loading-overlay').classList.remove('hidden');
}
function hideLoading() {
  document.getElementById('loading-overlay').classList.add('hidden');
}

function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast show ' + type;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.className = 'toast ' + type; }, 2400);
}

async function switchBank(bank) {
  if (bank === currentBank) return;
  if (examTimer) {
    if (!confirm('当前正在模拟考试中，切换题库会丢失答题进度，是否继续？')) return;
    clearExamTimer();
  }
  showLoading();
  currentBank = bank;
  localStorage.setItem('ex_last_bank', bank);
  updateBankUI();
  resetSessionState();
  loadStorage();
  await loadQuestions();
  updateHomeStats();
  goHome(false);
  hideLoading();
}

function updateBankUI() {
  document.querySelectorAll('.bank-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.bank === currentBank);
  });
  document.getElementById('hero-badge').textContent = BANK_NAMES[currentBank] || currentBank;
}

function resetSessionState() {
  userAnswers = {};
  answered = {};
  selectedOptions = [];
  isSubmitted = false;
  currentIndex = 0;
  currentQuestions = [];
}

async function loadQuestions() {
  try {
    const resp = await fetch(`/static/data/${encodeURIComponent(currentBank)}.json`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const raw = await resp.json();
    const valid = raw.filter(hasAnswer);
    droppedCount = raw.length - valid.length;
    allQuestions = valid;

    document.getElementById('stat-total').textContent = allQuestions.length;
    let subtitle = `专业题库 · ${allQuestions.length} 道真题`;
    if (droppedCount > 0) subtitle += `（已自动过滤 ${droppedCount} 道暂无答案的题目）`;
    document.getElementById('hero-subtitle').textContent = subtitle;

    updateFilterCounts();
    console.log(`题库[${currentBank}]加载成功：${allQuestions.length} 道（剔除 ${droppedCount} 道）`);
  } catch (e) {
    console.error('加载题库失败:', e);
    showToast('题库加载失败：' + e.message, 'error');
    allQuestions = [];
    document.getElementById('stat-total').textContent = '0';
    document.getElementById('hero-subtitle').textContent = '题库加载失败，请刷新重试';
    updateFilterCounts();
  }
}

function updateFilterCounts() {
  const counts = { all: allQuestions.length, single: 0, multi: 0, judge: 0, case: 0 };
  allQuestions.forEach(q => {
    if (isJudge(q)) counts.judge++;
    else if (isMulti(q)) counts.multi++;
    else if (isCase(q)) counts.case++;
    else counts.single++;
  });
  document.querySelectorAll('[data-count]').forEach(el => {
    const k = el.dataset.count;
    el.textContent = counts[k] || 0;
  });
  document.getElementById('chip-case').style.display = counts.case > 0 ? 'inline-flex' : 'none';
  // 默认激活"全部"
  document.querySelectorAll('.filter-chips .chip').forEach(c => {
    c.classList.toggle('active', c.dataset.filter === 'all');
  });
}

// ===== localStorage =====
function storageKey(suffix) {
  return `ex_v${STORAGE_VERSION}_${currentBank}_${suffix}`;
}

function loadStorage() {
  try {
    practiceProgress = parseInt(localStorage.getItem(storageKey('progress')) || '0');
    wrongSet = new Set(JSON.parse(localStorage.getItem(storageKey('wrong')) || '[]'));
    totalDone = parseInt(localStorage.getItem(storageKey('done')) || '0');
    totalCorrect = parseInt(localStorage.getItem(storageKey('correct')) || '0');
    examHistory = JSON.parse(localStorage.getItem(storageKey('history')) || '[]');
  } catch (e) {
    console.warn('读取本地存储失败:', e);
    practiceProgress = 0; wrongSet = new Set(); totalDone = 0; totalCorrect = 0; examHistory = [];
  }
}

function saveStorage() {
  try {
    localStorage.setItem(storageKey('progress'), practiceProgress);
    localStorage.setItem(storageKey('wrong'), JSON.stringify([...wrongSet]));
    localStorage.setItem(storageKey('done'), totalDone);
    localStorage.setItem(storageKey('correct'), totalCorrect);
    localStorage.setItem(storageKey('history'), JSON.stringify(examHistory.slice(-HISTORY_LIMIT)));
  } catch (e) {
    console.warn('保存本地存储失败:', e);
  }
}

function resetCurrentBank() {
  if (!confirm(`确定清空"${BANK_NAMES[currentBank]}"的所有进度、错题和考试记录吗？此操作不可恢复。`)) return;
  ['progress', 'wrong', 'done', 'correct', 'history'].forEach(k => {
    localStorage.removeItem(storageKey(k));
  });
  loadStorage();
  updateHomeStats();
  showToast('已清空当前题库的全部进度', 'success');
}

function clearHistory() {
  if (!confirm('确定清空考试记录吗？')) return;
  examHistory = [];
  saveStorage();
  updateHomeStats();
  showToast('已清空考试记录', 'success');
}

function updateHomeStats() {
  document.getElementById('stat-done').textContent = totalDone;
  document.getElementById('stat-correct-rate').textContent =
    totalDone > 0 ? Math.round(totalCorrect / totalDone * 100) + '%' : '0%';
  document.getElementById('stat-wrong').textContent = wrongSet.size;
  document.getElementById('wrong-detail').textContent = wrongSet.size + ' 道错题';

  const total = allQuestions.length;
  const seqPct = total > 0 ? Math.min(100, practiceProgress / total * 100) : 0;
  document.getElementById('seq-progress-bar').style.width = seqPct + '%';
  document.getElementById('seq-detail').textContent = `${Math.min(practiceProgress, total)} / ${total}`;

  const section = document.getElementById('history-section');
  const list = document.getElementById('history-list');
  if (examHistory.length > 0) {
    section.style.display = 'block';
    list.innerHTML = examHistory.slice(-10).reverse().map(h => {
      const cls = h.score >= EXAM_PASS_SCORE ? 'pass' : 'fail';
      return `<div class="history-item">
        <div><span class="hi-score ${cls}">${h.score}分</span></div>
        <div>${h.correct}/${h.total} 正确</div>
        <div class="hi-date">${escapeHTML(h.date)}</div>
      </div>`;
    }).join('');
  } else {
    section.style.display = 'none';
    list.innerHTML = '';
  }
}

// ===== 模式切换 =====
function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo(0, 0);
}

function closeAnswerCard() {
  document.getElementById('answer-card').classList.remove('show');
  document.getElementById('answer-card-overlay').classList.remove('show');
}

function goHome(askIfExam = false) {
  if (examTimer) {
    if (askIfExam && !confirm('正在模拟考试中，确定返回首页吗？答题进度会丢失。')) return;
    clearExamTimer();
  }
  document.getElementById('exam-timer').style.display = 'none';
  document.getElementById('btn-header-finish').style.display = 'none';
  closeAnswerCard();
  resetSessionState();
  updateHomeStats();
  showView('home-view');
}

function clearExamTimer() {
  if (examTimer) { clearInterval(examTimer); examTimer = null; }
  document.getElementById('exam-timer').classList.remove('warning');
}

function startMode(mode, filterKey) {
  if (allQuestions.length === 0) {
    showToast('题库为空或加载失败', 'error');
    return;
  }
  currentMode = mode;
  userAnswers = {};
  answered = {};
  selectedOptions = [];
  isSubmitted = false;

  if (mode === 'memorize') {
    currentQuestions = shuffle(allQuestions.slice()).slice(0, 100);
    renderMemorizeList();
    showView('memorize-view');
    return;
  }

  if (mode === 'sequential') {
    currentQuestions = allQuestions.slice();
    if (practiceProgress >= currentQuestions.length) {
      if (confirm('您已练完全部题目，是否从头开始？')) {
        practiceProgress = 0;
        saveStorage();
        currentIndex = 0;
      } else {
        currentIndex = currentQuestions.length - 1;
      }
    } else {
      currentIndex = practiceProgress;
    }
    document.getElementById('practice-title').textContent = '顺序练习';
  } else if (mode === 'random') {
    currentQuestions = shuffle(allQuestions.slice());
    currentIndex = 0;
    document.getElementById('practice-title').textContent = '随机练习';
  } else if (mode === 'exam') {
    if (allQuestions.length < EXAM_QUESTION_COUNT) {
      if (!confirm(`题库仅有 ${allQuestions.length} 道，少于 ${EXAM_QUESTION_COUNT} 题，仍要开始模拟考试吗？`)) return;
    }
    currentQuestions = shuffle(allQuestions.slice()).slice(0, EXAM_QUESTION_COUNT);
    currentIndex = 0;
    examTimeLeft = EXAM_DURATION;
    document.getElementById('practice-title').textContent = '模拟考试';
    document.getElementById('exam-timer').style.display = 'flex';
    startExamTimer();
  } else if (mode === 'wrong') {
    if (wrongSet.size === 0) {
      showToast('暂无错题，先去练习吧！', 'warn');
      return;
    }
    currentQuestions = shuffle(allQuestions.filter(q => wrongSet.has(q.id)));
    if (currentQuestions.length === 0) {
      showToast('错题已不在当前题库（题库可能已更新）', 'warn');
      return;
    }
    currentIndex = 0;
    document.getElementById('practice-title').textContent = '错题回顾';
  } else if (mode === 'type') {
    document.querySelectorAll('.filter-chips .chip').forEach(c => {
      c.classList.toggle('active', c.dataset.filter === filterKey);
    });
    if (filterKey === 'all') currentQuestions = allQuestions.slice();
    else if (filterKey === 'single') currentQuestions = allQuestions.filter(isSingle);
    else if (filterKey === 'multi') currentQuestions = allQuestions.filter(isMulti);
    else if (filterKey === 'judge') currentQuestions = allQuestions.filter(isJudge);
    else if (filterKey === 'case') currentQuestions = allQuestions.filter(isCase);
    if (currentQuestions.length === 0) {
      showToast('该题型在当前题库下暂无题目', 'warn');
      return;
    }
    currentQuestions = shuffle(currentQuestions);
    currentIndex = 0;
    const titleMap = { all: '全部题型', single: '单选题', multi: '多选题', judge: '判断题', case: '案例分析题' };
    document.getElementById('practice-title').textContent = (titleMap[filterKey] || '题型练习') + ' 练习';
  }

  if (mode !== 'exam') {
    document.getElementById('exam-timer').style.display = 'none';
    document.getElementById('btn-header-finish').style.display = 'none';
    clearExamTimer();
  } else {
    document.getElementById('btn-header-finish').style.display = 'inline-block';
  }

  showView('practice-view');
  syncSelectedFromAnswers();
  renderQuestion();
  buildAnswerCard();
}

// ===== 考试计时 =====
function startExamTimer() {
  updateTimerDisplay();
  examTimer = setInterval(() => {
    examTimeLeft--;
    updateTimerDisplay();
    if (examTimeLeft <= 300) document.getElementById('exam-timer').classList.add('warning');
    if (examTimeLeft <= 0) {
      clearExamTimer();
      showToast('考试时间到，自动交卷', 'warn');
      finishExam(true);
    }
  }, 1000);
}

function updateTimerDisplay() {
  const m = Math.floor(examTimeLeft / 60);
  const s = examTimeLeft % 60;
  document.getElementById('timer-text').textContent =
    String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
}

// ===== 渲染题目 =====
function renderQuestion() {
  const q = currentQuestions[currentIndex];
  if (!q) return;

  isSubmitted = Object.prototype.hasOwnProperty.call(answered, currentIndex);
  // 注意：selectedOptions 的同步由切题函数（nextQuestion/prevQuestion/jumpTo/startMode）负责，
  // 这里不再覆盖，避免破坏多选题中途的勾选状态。

  document.getElementById('practice-counter').textContent =
    (currentIndex + 1) + ' / ' + currentQuestions.length;
  document.getElementById('global-progress-bar').style.width =
    ((currentIndex + 1) / currentQuestions.length * 100) + '%';

  const badge = document.getElementById('q-type-badge');
  badge.textContent = q.type || (isJudge(q) ? '判断题' : isMulti(q) ? '多选题' : '单选题');
  badge.className = 'q-badge' + (isMulti(q) ? ' multi' : isJudge(q) ? ' judge' : '');
  document.getElementById('q-number').textContent = '第 ' + (currentIndex + 1) + ' 题';

  // 题目文字
  const textEl = document.getElementById('q-text');
  let txt = (q.question || '').replace(/\[图片\]/g, '');
  if (isMulti(q)) txt = '【多选】' + txt;
  textEl.textContent = txt;

  // 题目图片
  const imgEl = document.getElementById('q-image');
  if (q.question_images && q.question_images.length > 0) {
    const baseDir = (currentBank === 'N1_叉车司机_备选') ? '/static/images/yibaifen/' : '/static/images/junrui/';
    imgEl.innerHTML = `<img src="${baseDir}${encodeURI(q.question_images[0])}" alt="题目图片" onerror="this.style.display='none'">`;
  } else {
    imgEl.innerHTML = '';
  }

  // 选项
  const optEl = document.getElementById('q-options');
  const showResult = isSubmitted && currentMode !== 'exam';
  const judgeStyle = isJudge(q) && (!q.options || Object.keys(q.options).length === 0);

  if (judgeStyle) {
    const correctBool = getJudgeBool(q);
    const userA = isSubmitted ? userAnswers[currentIndex] : null;
    optEl.innerHTML = `<div class="judge-options">
      ${renderJudgeBtn(true, '✓ 正确', selectedOptions, showResult, correctBool, userA)}
      ${renderJudgeBtn(false, '✗ 错误', selectedOptions, showResult, correctBool, userA)}
    </div>`;
    optEl.querySelectorAll('.judge-btn').forEach(btn => {
      btn.addEventListener('click', () => selectJudge(btn.dataset.val === 'true'));
    });
  } else {
    const keys = Object.keys(q.options || {}).sort();
    const correctSet = new Set((q.answer || []).map(String));
    optEl.innerHTML = keys.map(k => {
      let cls = 'option-item';
      if (selectedOptions.includes(k)) cls += ' selected';
      if (showResult) {
        cls += ' disabled';
        if (correctSet.has(k)) cls += ' correct';
        else if (selectedOptions.includes(k)) cls += ' wrong';
      }
      return `<div class="${cls}" data-key="${escapeAttr(k)}">
        <span class="option-key">${escapeHTML(k.toUpperCase())}</span>
        <span class="option-val">${escapeHTML(q.options[k])}</span>
      </div>`;
    }).join('');
    optEl.querySelectorAll('.option-item').forEach(item => {
      item.addEventListener('click', () => selectOption(item.dataset.key));
    });
  }

  // 结果面板
  const resultPanel = document.getElementById('result-panel');
  if (showResult) {
    resultPanel.style.display = 'block';
    let correctText = '';
    if (judgeStyle) {
      correctText = getJudgeBool(q) ? '正确' : '错误';
    } else if (Array.isArray(q.answer)) {
      correctText = q.answer.map(a => String(a).toUpperCase()).join(', ');
    } else {
      correctText = String(q.answer);
    }
    const verdict = answered[currentIndex]
      ? '<span class="correct-msg">✓ 回答正确</span>'
      : '<span class="wrong-msg">✗ 回答错误</span>';
    document.getElementById('result-answer').innerHTML =
      `${verdict} ｜ 正确答案：<strong>${escapeHTML(correctText)}</strong>`;
    const analysisEl = document.getElementById('result-analysis');
    if (q.analysis) {
      analysisEl.style.display = 'block';
      analysisEl.innerHTML = '<strong>解析：</strong>' + escapeHTML(q.analysis);
    } else {
      analysisEl.style.display = 'none';
    }
  } else {
    resultPanel.style.display = 'none';
  }

  // 按钮状态
  const submitBtn = document.getElementById('btn-submit');
  const isMultiQ = isMulti(q);
  if (showResult || currentMode === 'review') {
    submitBtn.style.display = 'none';
  } else if (currentMode === 'exam') {
    submitBtn.style.display = isMultiQ ? 'inline-block' : 'none';
  } else {
    submitBtn.style.display = isMultiQ ? 'inline-block' : 'none';
    submitBtn.disabled = selectedOptions.length === 0;
  }

  document.getElementById('btn-prev').style.display = currentIndex > 0 ? 'inline-block' : 'none';

  const nextBtn = document.getElementById('btn-next');
  nextBtn.style.display = 'inline-block';
  if (currentMode === 'exam') {
    nextBtn.textContent = currentIndex < currentQuestions.length - 1 ? '下一题' : '交卷';
  } else if (currentMode === 'review') {
    nextBtn.textContent = currentIndex < currentQuestions.length - 1 ? '下一题' : '返回首页';
  } else {
    nextBtn.textContent = currentIndex < currentQuestions.length - 1 ? '下一题' : '完成练习';
  }

  updateCardCell(currentIndex);
}

function renderJudgeBtn(val, label, sel, showResult, correctBool, userA) {
  const isSel = sel.includes(val);
  let cls = 'judge-btn';
  if (isSel) cls += ' selected';
  if (showResult) {
    cls += ' disabled';
    if (correctBool === val) cls += ' correct';
    else if (userA === val) cls += ' wrong';
  }
  return `<div class="${cls}" data-val="${val}">${label}</div>`;
}

// ===== 选项交互 =====
function selectOption(key) {
  if (currentMode === 'review') return;
  if (isSubmitted && currentMode !== 'exam') return;
  const q = currentQuestions[currentIndex];

  if (isMulti(q)) {
    const idx = selectedOptions.indexOf(key);
    if (idx > -1) selectedOptions.splice(idx, 1);
    else selectedOptions.push(key);
    if (currentMode === 'exam') {
      if (selectedOptions.length > 0) submitAnswer(false);
      else {
        delete answered[currentIndex];
        delete userAnswers[currentIndex];
        isSubmitted = false;
        renderQuestion();
      }
    } else {
      renderQuestion();
    }
  } else {
    selectedOptions = [key];
    submitAnswer(false);
  }
}

function selectJudge(val) {
  if (currentMode === 'review') return;
  if (isSubmitted && currentMode !== 'exam') return;
  selectedOptions = [val];
  submitAnswer(false);
}

// ===== 提交答案 =====
function submitAnswer(fromButton) {
  if (selectedOptions.length === 0) return;
  const q = currentQuestions[currentIndex];
  const wasAnswered = Object.prototype.hasOwnProperty.call(answered, currentIndex);
  let isCorrect = false;

  const judgeStyle = isJudge(q) && (!q.options || Object.keys(q.options).length === 0);

  if (judgeStyle) {
    const correctBool = getJudgeBool(q);
    isCorrect = selectedOptions[0] === correctBool;
    userAnswers[currentIndex] = selectedOptions[0];
  } else {
    const correctSet = new Set((q.answer || []).map(String));
    const userSet = new Set(selectedOptions.map(String));
    isCorrect = correctSet.size === userSet.size && [...correctSet].every(v => userSet.has(v));
    userAnswers[currentIndex] = selectedOptions.slice();
  }

  answered[currentIndex] = isCorrect;

  // 统计：仅在练习类模式且本题首次提交时计入
  if (currentMode !== 'exam' && currentMode !== 'review' && !wasAnswered) {
    totalDone++;
    if (isCorrect) {
      totalCorrect++;
      wrongSet.delete(q.id);
    } else {
      wrongSet.add(q.id);
    }
    if (currentMode === 'sequential') {
      practiceProgress = Math.max(practiceProgress, currentIndex + 1);
    }
    saveStorage();
  }

  isSubmitted = true;
  renderQuestion();
}

function syncSelectedFromAnswers() {
  if (Object.prototype.hasOwnProperty.call(answered, currentIndex)) {
    const stored = userAnswers[currentIndex];
    selectedOptions = Array.isArray(stored) ? stored.slice() : [stored];
  } else {
    selectedOptions = [];
  }
}

// ===== 导航 =====
function nextQuestion() {
  if (currentIndex < currentQuestions.length - 1) {
    currentIndex++;
    syncSelectedFromAnswers();
    renderQuestion();
    window.scrollTo(0, 0);
  } else {
    if (currentMode === 'exam') finishExam(false);
    else if (currentMode === 'wrong') {
      showToast('错题已练习完毕！', 'success');
      goHome(false);
    } else {
      goHome(false);
    }
  }
}

function prevQuestion() {
  if (currentIndex > 0) {
    currentIndex--;
    syncSelectedFromAnswers();
    renderQuestion();
    window.scrollTo(0, 0);
  }
}

function jumpTo(idx) {
  if (idx < 0 || idx >= currentQuestions.length) return;
  currentIndex = idx;
  syncSelectedFromAnswers();
  renderQuestion();
  closeAnswerCard();
  window.scrollTo(0, 0);
}

// ===== 考试结束 =====
function finishExam(forced) {
  if (!forced && currentMode === 'exam') {
    const answeredCount = Object.keys(answered).length;
    const unanswered = currentQuestions.length - answeredCount;
    if (unanswered > 0) {
      if (!confirm(`还有 ${unanswered} 题未作答（按错处理），确定交卷吗？`)) return;
    }
  }
  clearExamTimer();
  document.getElementById('exam-timer').style.display = 'none';
  document.getElementById('btn-header-finish').style.display = 'none';

  // 未答题判错并入错题集
  for (let i = 0; i < currentQuestions.length; i++) {
    if (!Object.prototype.hasOwnProperty.call(answered, i)) {
      answered[i] = false;
    }
    if (!answered[i]) {
      wrongSet.add(currentQuestions[i].id);
    }
  }

  const total = currentQuestions.length;
  const correct = Object.values(answered).filter(v => v).length;
  const wrong = total - correct;
  const score = total > 0 ? Math.round(correct / total * 100) : 0;
  const pass = score >= EXAM_PASS_SCORE;

  examHistory.push({
    score, correct, wrong, total,
    date: new Date().toLocaleString('zh-CN', { hour12: false })
  });
  saveStorage();

  document.getElementById('result-score').textContent = score;
  const ring = document.getElementById('result-ring');
  const circumference = 339.29;
  ring.style.stroke = pass ? '#22c55e' : '#ef4444';
  ring.style.strokeDashoffset = circumference - (score / 100) * circumference;

  const verdict = document.getElementById('result-verdict');
  verdict.textContent = pass ? '🎉 恭喜通过！' : '😔 未通过';
  verdict.className = 'result-verdict ' + (pass ? 'pass' : 'fail');

  document.getElementById('result-stats').innerHTML = `
    <div class="rs-item"><div class="rs-num" style="color:var(--green)">${correct}</div><div class="rs-label">答对</div></div>
    <div class="rs-item"><div class="rs-num" style="color:var(--red)">${wrong}</div><div class="rs-label">答错</div></div>
    <div class="rs-item"><div class="rs-num">${total}</div><div class="rs-label">总题数</div></div>`;

  showView('result-view');
}

function reviewExam() {
  currentMode = 'review';
  currentIndex = 0;
  document.getElementById('btn-header-finish').style.display = 'none';
  document.getElementById('exam-timer').style.display = 'none';
  document.getElementById('practice-title').textContent = '考试解析';
  showView('practice-view');
  syncSelectedFromAnswers();
  renderQuestion();
  buildAnswerCard();
}

// ===== 答题卡 =====
function toggleAnswerCard() {
  document.getElementById('answer-card').classList.toggle('show');
  document.getElementById('answer-card-overlay').classList.toggle('show');
}

function buildAnswerCard() {
  const grid = document.getElementById('card-grid');
  const inExam = currentMode === 'exam';
  grid.innerHTML = currentQuestions.map((_, i) => {
    let cls = 'card-cell';
    if (i === currentIndex) cls += ' c-current';
    if (Object.prototype.hasOwnProperty.call(answered, i)) {
      if (inExam) cls += ' c-answered';
      else cls += answered[i] ? ' c-correct' : ' c-wrong';
    } else {
      cls += ' c-todo';
    }
    return `<div class="${cls}" data-idx="${i}">${i + 1}</div>`;
  }).join('');
  grid.querySelectorAll('.card-cell').forEach(cell => {
    cell.addEventListener('click', () => jumpTo(parseInt(cell.dataset.idx)));
  });

  const footer = document.getElementById('card-footer');
  if (currentMode === 'exam') {
    const answeredCount = Object.keys(answered).length;
    footer.innerHTML = `<p style="color:var(--text2);font-size:13px;margin-bottom:12px">
      已答 ${answeredCount}/${currentQuestions.length} 题</p>
      <button class="btn-action btn-submit btn-primary" id="btn-card-finish" style="width:100%">交卷</button>`;
    document.getElementById('btn-card-finish').addEventListener('click', () => {
      closeAnswerCard();
      finishExam(false);
    });
  } else {
    footer.innerHTML = '';
  }
}

function updateCardCell(idx) {
  const cells = document.querySelectorAll('.card-cell');
  if (cells.length !== currentQuestions.length) {
    buildAnswerCard();
    return;
  }
  const inExam = currentMode === 'exam';
  cells.forEach((cell, i) => {
    cell.className = 'card-cell';
    if (i === idx) cell.classList.add('c-current');
    if (Object.prototype.hasOwnProperty.call(answered, i)) {
      cell.classList.add(inExam ? 'c-answered' : (answered[i] ? 'c-correct' : 'c-wrong'));
    } else {
      cell.classList.add('c-todo');
    }
  });
  // 同步答题卡 footer 已答数
  if (currentMode === 'exam') {
    const footer = document.getElementById('card-footer');
    const p = footer.querySelector('p');
    if (p) p.textContent = `已答 ${Object.keys(answered).length}/${currentQuestions.length} 题`;
  }
}

// ===== 键盘快捷键 =====
function handleKeyboard(e) {
  const inPractice = document.getElementById('practice-view').classList.contains('active');
  if (!inPractice) return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowLeft') { prevQuestion(); e.preventDefault(); }
  else if (e.key === 'ArrowRight' || e.key === 'Enter') { nextQuestion(); e.preventDefault(); }
  else if (e.key === 'Escape') { goHome(true); e.preventDefault(); }
  else {
    const q = currentQuestions[currentIndex];
    if (!q || isSubmitted && currentMode !== 'exam') return;
    const judgeStyle = isJudge(q) && (!q.options || Object.keys(q.options).length === 0);
    if (judgeStyle) {
      if (e.key === 't' || e.key === 'T' || e.key === '1') selectJudge(true);
      else if (e.key === 'f' || e.key === 'F' || e.key === '2') selectJudge(false);
    } else if (q.options) {
      const keys = Object.keys(q.options).sort();
      const upper = e.key.toUpperCase();
      const found = keys.find(k => k.toUpperCase() === upper);
      if (found) selectOption(found);
    }
  }
}

// ===== 工具函数 =====
function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function escapeHTML(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function escapeAttr(str) {
  return escapeHTML(str);
}

// ===== 背题模式渲染 =====
function renderMemorizeList() {
  const listEl = document.getElementById('memorize-list');
  listEl.innerHTML = currentQuestions.map((q, idx) => {
    const judgeStyle = isJudge(q) && (!q.options || Object.keys(q.options).length === 0);
    let optionsHtml = '';
    if (!judgeStyle && q.options) {
      optionsHtml = Object.keys(q.options).sort().map(k =>
        `<div style="font-size:14px; margin:4px 0; color:var(--text2)">${escapeHTML(k.toUpperCase())}. ${escapeHTML(q.options[k])}</div>`
      ).join('');
    }

    let answerText = '';
    if (judgeStyle) {
      answerText = getJudgeBool(q) ? '正确' : '错误';
    } else if (Array.isArray(q.answer)) {
      answerText = q.answer.map(a => String(a).toUpperCase()).join(', ');
    } else {
      answerText = String(q.answer || '');
    }

    const baseDir = (currentBank === 'N1_叉车司机_备选') ? '/static/images/yibaifen/' : '/static/images/junrui/';
    const imgSrc = (q.question_images && q.question_images.length > 0)
      ? `<div style="margin:10px 0"><img src="${baseDir}${encodeURI(q.question_images[0])}" style="max-height:150px; border-radius:8px; border:1px solid var(--border)" onerror="this.style.display='none'"></div>`
      : '';

    return `
      <div class="memorize-item">
        <div class="mem-header">
          <span>${escapeHTML(q.type || '')}</span>
          <span>第 ${idx + 1} / ${currentQuestions.length} 题</span>
        </div>
        <div style="font-weight:600; font-size:16px; margin-bottom:10px">${escapeHTML((q.question || '').replace(/\[图片\]/g, ''))}</div>
        ${imgSrc}
        <div class="mem-options">${optionsHtml}</div>
        <div class="mem-ans">正确答案：${escapeHTML(answerText)}</div>
        ${q.analysis ? `<div class="mem-analysis"><strong>解析：</strong>${escapeHTML(q.analysis)}</div>` : ''}
      </div>
    `;
  }).join('');
}
