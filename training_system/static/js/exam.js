/* ===== 叉车司机N1 在线练习系统 ===== */

let currentBank = 'N1_叉车司机'; // 当前题库
let allQuestions = [];
let currentQuestions = [];
let currentIndex = 0;
let currentMode = '';
let userAnswers = {};      // { questionIndex: userAnswer }
let answered = {};         // { questionIndex: true/false (correct) }
let selectedOptions = [];  // 当前题目选中的选项
let isSubmitted = false;

// 持久化数据
let practiceProgress = 0;  // 顺序练习进度
let wrongSet = new Set();  // 错题ID集合
let totalDone = 0;
let totalCorrect = 0;
let examHistory = [];

// 考试模式
let examTimer = null;
let examTimeLeft = 3600; // 60分钟

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', async () => {
  try {
    // 恢复上一次使用的题库
    currentBank = localStorage.getItem('ex_last_bank') || 'N1_叉车司机';
    updateBankUI();

    loadStorage();
    await loadQuestions();
    updateHomeStats();
  } catch (err) {
    console.error('初始化失败:', err);
  } finally {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.classList.add('hidden');
  }
});

async function switchBank(bank) {
  if (bank === currentBank) return;

  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.classList.remove('hidden');

  currentBank = bank;
  localStorage.setItem('ex_last_bank', bank);
  updateBankUI();

  // 重置状态
  userAnswers = {};
  answered = {};
  selectedOptions = [];

  loadStorage();
  await loadQuestions();
  updateHomeStats();

  if (overlay) overlay.classList.add('hidden');
}

function updateBankUI() {
  document.querySelectorAll('.bank-btn').forEach(btn => btn.classList.remove('active'));
  document.getElementById('bank-' + currentBank).classList.add('active');

  const names = {
    'N1_叉车司机': '叉车司机 (N1)',
    'A_电梯管理': '电梯管理 (A)',
    'G3_锅炉水处理': '锅炉水处理 (G3)',
    'G1_工业锅炉司炉': '工业锅炉司炉 (G1)',
    'Q3_起重机指挥': '起重机指挥 (Q3)',
    'Q2_门式起重机': '门式起重机 (Q2)',
    'Q2_桥式起重机': '桥式起重机 (Q2)',
    'N1_叉车司机_备选': '叉车司机 (备用题库)'
  };
  document.getElementById('hero-badge').textContent = names[currentBank];
}

async function loadQuestions() {
  try {
    const resp = await fetch(`/static/data/${currentBank}.json`);
    if (!resp.ok) throw new Error(`HTTP error! status: ${resp.status}`);
    allQuestions = await resp.json();

    const totalEl = document.getElementById('stat-total');
    if (totalEl) totalEl.textContent = allQuestions.length;

    document.getElementById('hero-subtitle').textContent = `专业题库 · ${allQuestions.length} 道真题`;

    // 更新题型练习里的数字（如果是电梯管理，可能数量不同）
    updateFilterCounts();

    console.log(`题库[${currentBank}]加载成功，共`, allQuestions.length, '题');
  } catch (e) {
    console.error('加载题库失败:', e);
  }
}

function updateFilterCounts() {
  const counts = { 0: allQuestions.length, 1: 0, 2: 0, 3: 0 };
  allQuestions.forEach(q => {
    if (counts[q.type_code] !== undefined) counts[q.type_code]++;
  });

  const chips = document.querySelectorAll('.filter-chips .chip span');
  if (chips.length >= 4) {
    chips[0].textContent = counts[0];
    chips[1].textContent = counts[1];
    chips[2].textContent = counts[2];
    chips[3].textContent = counts[3];
  }
}

// ===== localStorage =====
function loadStorage() {
  const prefix = `ex_${currentBank}_`;
  try {
    practiceProgress = parseInt(localStorage.getItem(prefix + 'progress') || '0');
    wrongSet = new Set(JSON.parse(localStorage.getItem(prefix + 'wrong') || '[]'));
    totalDone = parseInt(localStorage.getItem(prefix + 'done') || '0');
    totalCorrect = parseInt(localStorage.getItem(prefix + 'correct') || '0');
    examHistory = JSON.parse(localStorage.getItem(prefix + 'history') || '[]');
  } catch (e) { console.warn('读取存储失败'); }
}

function saveStorage() {
  const prefix = `ex_${currentBank}_`;
  localStorage.setItem(prefix + 'progress', practiceProgress);
  localStorage.setItem(prefix + 'wrong', JSON.stringify([...wrongSet]));
  localStorage.setItem(prefix + 'done', totalDone);
  localStorage.setItem(prefix + 'correct', totalCorrect);
  localStorage.setItem(prefix + 'history', JSON.stringify(examHistory));
}

function updateHomeStats() {
  document.getElementById('stat-done').textContent = totalDone;
  document.getElementById('stat-correct-rate').textContent =
    totalDone > 0 ? Math.round(totalCorrect / totalDone * 100) + '%' : '0%';
  document.getElementById('stat-wrong').textContent = wrongSet.size;
  document.getElementById('wrong-detail').textContent = wrongSet.size + ' 道错题';

  // 顺序练习进度
  const seqPct = allQuestions.length > 0 ? (practiceProgress / allQuestions.length * 100) : 0;
  document.getElementById('seq-progress-bar').style.width = seqPct + '%';
  document.getElementById('seq-detail').textContent = practiceProgress + ' / ' + allQuestions.length;

  // 历史记录
  const section = document.getElementById('history-section');
  const list = document.getElementById('history-list');
  if (examHistory.length > 0) {
    section.style.display = 'block';
    list.innerHTML = examHistory.slice(-10).reverse().map(h => {
      const cls = h.score >= 80 ? 'pass' : 'fail';
      return `<div class="history-item">
        <div><span class="hi-score ${cls}">${h.score}分</span></div>
        <div>${h.correct}/${h.total} 正确</div>
        <div class="hi-date">${h.date}</div>
      </div>`;
    }).join('');
  }
}

// ===== 模式切换 =====
function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo(0, 0);
}

function goHome() {
  if (examTimer) { clearInterval(examTimer); examTimer = null; }
  document.getElementById('exam-timer').style.display = 'none';
  document.getElementById('btn-header-finish').style.display = 'none';
  updateHomeStats();
  showView('home-view');
}

function startMode(mode, typeCode) {
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
    currentIndex = Math.min(practiceProgress, currentQuestions.length - 1);
    document.getElementById('practice-title').textContent = '顺序练习';
  } else if (mode === 'random') {
    currentQuestions = shuffle(allQuestions.slice());
    currentIndex = 0;
    document.getElementById('practice-title').textContent = '随机练习';
  } else if (mode === 'exam') {
    currentQuestions = shuffle(allQuestions.slice()).slice(0, 100);
    currentIndex = 0;
    examTimeLeft = 3600;
    document.getElementById('practice-title').textContent = '模拟考试';
    document.getElementById('exam-timer').style.display = 'flex';
    startExamTimer();
  } else if (mode === 'wrong') {
    if (wrongSet.size === 0) { alert('暂无错题！'); return; }
    currentQuestions = allQuestions.filter(q => wrongSet.has(q.id));
    currentQuestions = shuffle(currentQuestions);
    currentIndex = 0;
    document.getElementById('practice-title').textContent = '错题回顾';
  } else if (mode === 'type') {
    // 更新 UI 状态
    document.querySelectorAll('.filter-chips .chip').forEach((c, idx) => {
      c.classList.toggle('active', idx === typeCode);
    });

    if (typeCode === 0) {
      currentQuestions = allQuestions.slice();
    } else {
      currentQuestions = allQuestions.filter(q => q.type_code === typeCode);
    }
    currentQuestions = shuffle(currentQuestions);
    currentIndex = 0;
    const names = { 0: '全部题型', 1: '单选题', 2: '多选题', 3: '判断题' };
    document.getElementById('practice-title').textContent = names[typeCode] + ' 练习';
  }

  if (mode !== 'exam') {
    document.getElementById('exam-timer').style.display = 'none';
    document.getElementById('btn-header-finish').style.display = 'none';
  } else {
    document.getElementById('btn-header-finish').style.display = 'block';
  }

  showView('practice-view');
  renderQuestion();
  buildAnswerCard();
}

// ===== 考试计时 =====
function startExamTimer() {
  updateTimerDisplay();
  examTimer = setInterval(() => {
    examTimeLeft--;
    updateTimerDisplay();
    if (examTimeLeft <= 300) {
      document.getElementById('exam-timer').classList.add('warning');
    }
    if (examTimeLeft <= 0) {
      clearInterval(examTimer);
      examTimer = null;
      finishExam();
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

  isSubmitted = !!answered.hasOwnProperty(currentIndex);
  if (isSubmitted) {
    selectedOptions = Array.isArray(userAnswers[currentIndex]) ? userAnswers[currentIndex] : [userAnswers[currentIndex]];
  }

  // 计数
  document.getElementById('practice-counter').textContent =
    (currentIndex + 1) + ' / ' + currentQuestions.length;
  document.getElementById('global-progress-bar').style.width =
    ((currentIndex + 1) / currentQuestions.length * 100) + '%';

  // 类型标识
  const badge = document.getElementById('q-type-badge');
  badge.textContent = q.type;
  badge.className = 'q-badge' + (q.type_code === 2 ? ' multi' : q.type_code === 3 ? ' judge' : '');
  document.getElementById('q-number').textContent = '第 ' + (currentIndex + 1) + ' 题';

  // 题目文字
  const textEl = document.getElementById('q-text');
  let txt = q.question.replace(/\[图片\]/g, '');
  if (q.type_code === 2) txt = '【多选】' + txt;
  textEl.textContent = txt;

  // 图片
  const imgEl = document.getElementById('q-image');
  if (q.question_images && q.question_images.length > 0) {
    const baseDir = (currentBank === 'N1_叉车司机_备选') ? '/static/images/yibaifen/' : '/static/images/junrui/';
    const imgSrc = baseDir + q.question_images[0];
    imgEl.innerHTML = `<img src="${imgSrc}" alt="题目图片" onerror="this.style.display='none'">`;
  } else {
    imgEl.innerHTML = '';
  }

  // 选项
  const optEl = document.getElementById('q-options');
  const showResult = isSubmitted && currentMode !== 'exam';

  if (q.type_code === 3) {
    // 判断题
    const correctAnswer = q.answer === 'true' || q.answer === true;
    const userA = isSubmitted ? userAnswers[currentIndex] : null;
    optEl.innerHTML = `<div class="judge-options">
      <div class="judge-btn ${selectedOptions.includes(true) ? 'selected' : ''} ${showResult ? (correctAnswer === true ? 'correct' : (userA === true ? 'wrong' : '')) : ''} ${showResult ? 'disabled' : ''}"
        onclick="selectJudge(true)">✓ 正确</div>
      <div class="judge-btn ${selectedOptions.includes(false) ? 'selected' : ''} ${showResult ? (correctAnswer === false ? 'correct' : (userA === false ? 'wrong' : '')) : ''} ${showResult ? 'disabled' : ''}"
        onclick="selectJudge(false)">✗ 错误</div>
    </div>`;
  } else {
    // 选择题
    const keys = Object.keys(q.options).sort();
    const correctSet = new Set(q.answer);
    optEl.innerHTML = keys.map(k => {
      let cls = 'option-item';
      if (selectedOptions.includes(k)) cls += ' selected';
      if (showResult) {
        cls += ' disabled';
        if (correctSet.has(k)) cls += ' correct';
        else if (selectedOptions.includes(k)) cls += ' wrong';
      }
      return `<div class="${cls}" onclick="selectOption('${k}')">
        <span class="option-key">${k.toUpperCase()}</span>
        <span class="option-val">${q.options[k]}</span>
      </div>`;
    }).join('');
  }

  // 结果面板
  const resultPanel = document.getElementById('result-panel');
  if (showResult && q.analysis) {
    resultPanel.style.display = 'block';
    const isCorrect = answered[currentIndex];

    let correctText = '';
    if (q.type_code === 3) {
      correctText = (q.answer === 'true' || q.answer === true) ? '正确' : '错误';
    } else {
      correctText = q.answer.map(a => a.toUpperCase()).join(', ');
    }
    document.getElementById('result-answer').innerHTML = '正确答案：<strong>' + correctText + '</strong>';
    document.getElementById('result-analysis').textContent = q.analysis || '';
    document.getElementById('result-analysis').style.display = q.analysis ? 'block' : 'none';
  } else {
    resultPanel.style.display = 'none';
  }

  // 按钮状态
  const isMulti = q.type_code === 2;
  const submitBtn = document.getElementById('btn-submit');

  if (showResult || currentMode === 'exam') {
    submitBtn.style.display = 'none';
  } else {
    // 只有多选题且未提交时显示确认按钮
    submitBtn.style.display = isMulti ? 'block' : 'none';
    submitBtn.disabled = selectedOptions.length === 0;
  }

  document.getElementById('btn-prev').style.display = currentIndex > 0 ? 'inline-block' : 'none';

  // 始终显示下一题/完成按钮，方便翻页
  const nextBtn = document.getElementById('btn-next');
  nextBtn.style.display = 'inline-block';

  if (currentMode === 'exam') {
    nextBtn.textContent = currentIndex < currentQuestions.length - 1 ? '下一题' : '交卷';
  } else {
    nextBtn.textContent = currentIndex < currentQuestions.length - 1 ? '下一题' : '完成练习';
  }

  // 更新答题卡
  updateCardCell(currentIndex);
}

// ===== 选项交互 =====
function selectOption(key) {
  if (isSubmitted && currentMode !== 'exam') return;
  const q = currentQuestions[currentIndex];

  if (q.type_code === 2) {
    // 多选：点击切换选中状态
    const idx = selectedOptions.indexOf(key);
    if (idx > -1) selectedOptions.splice(idx, 1);
    else selectedOptions.push(key);

    if (currentMode === 'exam') {
      if (selectedOptions.length > 0) submitAnswer();
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
    // 单选：直接选中并提交
    selectedOptions = [key];
    submitAnswer();
  }
}

function selectJudge(val) {
  if (isSubmitted && currentMode !== 'exam') return;
  selectedOptions = [val];
  submitAnswer();
}

// ===== 提交答案 =====
function submitAnswer() {
  if (selectedOptions.length === 0) return;
  const q = currentQuestions[currentIndex];
  let isCorrect = false;

  if (q.type_code === 3) {
    const correctAnswer = q.answer === 'true' || q.answer === true;
    isCorrect = selectedOptions[0] === correctAnswer;
    userAnswers[currentIndex] = selectedOptions[0];
  } else {
    const correctSet = new Set(q.answer);
    const userSet = new Set(selectedOptions);
    isCorrect = correctSet.size === userSet.size && [...correctSet].every(v => userSet.has(v));
    userAnswers[currentIndex] = [...selectedOptions];
  }

  answered[currentIndex] = isCorrect;

  // 统计
  if (currentMode !== 'exam') {
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

// ===== 导航 =====
function nextQuestion() {
  if (currentIndex < currentQuestions.length - 1) {
    currentIndex++;
    isSubmitted = false;
    selectedOptions = [];
    renderQuestion();
    window.scrollTo(0, 0);
  } else {
    if (currentMode === 'exam') {
      finishExam();
    } else {
      goHome();
    }
  }
}

function prevQuestion() {
  if (currentIndex > 0) {
    currentIndex--;
    selectedOptions = [];
    renderQuestion();
    window.scrollTo(0, 0);
  }
}

function jumpTo(idx) {
  currentIndex = idx;
  selectedOptions = [];
  renderQuestion();
  toggleAnswerCard();
  window.scrollTo(0, 0);
}

// ===== 考试结束 =====
function finishExam() {
  if (examTimer) { clearInterval(examTimer); examTimer = null; }

  // 未答题自动判错
  for (let i = 0; i < currentQuestions.length; i++) {
    if (!answered.hasOwnProperty(i)) {
      answered[i] = false;
      totalDone++;
      wrongSet.add(currentQuestions[i].id);
    }
  }

  const total = currentQuestions.length;
  const correct = Object.values(answered).filter(v => v).length;
  const wrong = total - correct;
  const score = Math.round(correct / total * 100);
  const pass = score >= 80;

  // 记录历史
  examHistory.push({
    score, correct, wrong, total,
    date: new Date().toLocaleString('zh-CN')
  });
  saveStorage();

  // 渲染结果页
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
  // 回到练习页查看已答题目
  currentMode = 'review';
  currentIndex = 0;
  document.getElementById('btn-header-finish').style.display = 'none';
  showView('practice-view');
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
  grid.innerHTML = currentQuestions.map((_, i) => {
    let cls = 'card-cell';
    if (i === currentIndex) cls += ' c-current';
    else if (answered.hasOwnProperty(i)) cls += answered[i] ? ' c-correct' : ' c-wrong';
    return `<div class="${cls}" onclick="jumpTo(${i})">${i + 1}</div>`;
  }).join('');

  const footer = document.getElementById('card-footer');
  if (currentMode === 'exam') {
    const answeredCount = Object.keys(answered).length;
    footer.innerHTML = `<p style="color:var(--text2);font-size:13px;margin-bottom:12px">
      已答 ${answeredCount}/${currentQuestions.length} 题</p>
      <button class="btn-action btn-submit" onclick="finishExam()">交卷</button>`;
  } else {
    footer.innerHTML = '';
  }
}

function updateCardCell(idx) {
  const cells = document.querySelectorAll('.card-cell');
  cells.forEach((cell, i) => {
    cell.className = 'card-cell';
    if (i === idx) cell.classList.add('c-current');
    else if (answered.hasOwnProperty(i)) cell.classList.add(answered[i] ? 'c-correct' : 'c-wrong');
  });
}

// ===== 工具函数 =====
function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// ===== 背题模式渲染 =====
function renderMemorizeList() {
  const listEl = document.getElementById('memorize-list');
  listEl.innerHTML = currentQuestions.map((q, idx) => {
    let optionsHtml = '';
    if (q.type_code !== 3) {
      optionsHtml = Object.keys(q.options).sort().map(k =>
        `<div style="font-size:14px; margin:4px 0; color:var(--text2)">${k.toUpperCase()}. ${q.options[k]}</div>`
      ).join('');
    }

    let answerText = '';
    if (q.type_code === 3) {
      answerText = (q.answer === 'true' || q.answer === true) ? '正确' : '错误';
    } else {
      answerText = q.answer.map(a => a.toUpperCase()).join(', ');
    }

    const baseDir = (currentBank === 'N1_叉车司机_备选') ? '/static/images/yibaifen/' : '/static/images/junrui/';
    const imgSrc = (q.question_images && q.question_images.length > 0)
      ? `<div style="margin:10px 0"><img src="${baseDir}${q.question_images[0]}" style="max-height:150px; border-radius:8px; border:1px solid var(--border)"></div>`
      : '';

    return `
      <div class="memorize-item">
        <div class="mem-header">
          <span>${q.type}</span>
          <span>第 ${idx + 1} / 100 题</span>
        </div>
        <div style="font-weight:600; font-size:16px; margin-bottom:10px">${q.question.replace(/\[图片\]/g, '')}</div>
        ${imgSrc}
        <div class="mem-options">${optionsHtml}</div>
        <div class="mem-ans">正确答案：${answerText}</div>
        ${q.analysis ? `<div class="mem-analysis"><strong>解析：</strong>${q.analysis}</div>` : ''}
      </div>
    `;
  }).join('');
}
