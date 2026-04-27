/**
 * 管理后台前端脚本。
 *
 * 本文件处理管理后台的所有前端逻辑，包括：
 *
 * 1. 学员列表管理
 *    - 按状态（未审核/已审核）和培训类型（特种作业/特种设备）筛选
 *    - 按公司筛选、按姓名/身份证/手机号搜索
 *    - 动态渲染学员卡片列表
 *
 * 2. 学员详情查看/编辑
 *    - 动态渲染详情页面（基于 HTML template）
 *    - 行内编辑并自动保存（防抖动 1 秒）
 *    - 附件图片查看和替换上传
 *
 * 3. 审核流程
 *    - 审核通过：更新状态为 reviewed，自动生成体检表
 *    - 驳回：更新状态为 rejected，学员可修改后重新提交
 *    - 删除：彻底删除记录和关联文件
 *
 * 4. 数据导出
 *    - 导出当前筛选条件下的学员数据为 Excel
 *    - 单个学员附件打包下载为 ZIP
 *
 * 5. 响应式布局
 *    - 移动端侧边栏切换
 *    - 适配不同屏幕尺寸
 *
 * 全局状态:
 *    currentStatus       - 当前筛选的审核状态 ('unreviewed'/'reviewed')
 *    currentTrainingType - 当前筛选的培训类型 ('special_operation'/'special_equipment')
 *    currentStudentId    - 当前查看的学员 ID
 *    students            - 当前列表中的学员数据数组
 */

// ======================== 全局 fetch 拦截器 ========================
// 拦截所有 fetch 请求，当服务器返回 401（未认证）时自动跳转到登录页
const rawFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
    const response = await rawFetch(...args);
    if (response.status === 401) {
        const nextPath = `${window.location.pathname}${window.location.search || ''}`;
        window.location.href = `/auth/login?next=${encodeURIComponent(nextPath)}`;
        throw new Error('未登录或登录已过期');
    }
    return response;
};



// ======================== 全局存储配置 ========================
// COS 根地址，由 /api/config/storage 接口在页面加载时赋值
// 形如: "https://mybucket-123.cos.ap-beijing.myqcloud.com"
// 未配置时为空字符串，toFileUrl() 自动降级为 Flask 本地路由
let COS_BASE_URL = '';

/**
 * 页面加载时的固定时间戳。
 * 用于附件图片 URL 的缓存破坏参数，驱逐浏览器缓存旧版本。
 * 优势：同一会话内同一张图只下载一次（浏览器会缓存）；刺新页面时时间戳变更，强制重载最新图片。
 * 上传新图后用 Date.now() 单独刷新那张图，不受此值影响。
 */
const PAGE_LOAD_TS = Date.now();

/**
 * 将相对存储路径转换为可访问 URL。
 * 若已获取到 COS_BASE_URL，返回直接 COS 公网 URL；
 * 否则降级为 Flask 路由（/students/...）。
 *
 * @param {string} relativePath - 数据库中的相对路径，如 'students/xxx/yyy.jpg'
 * @returns {string} 完整 URL
 */
function toFileUrl(relativePath) {
    if (!relativePath) return '';
    if (COS_BASE_URL) {
        return `${COS_BASE_URL}/${relativePath}`;
    }
    return '/' + relativePath;
}

// ======================== 图片灯箱预览 ========================
/**
 * 在页面内弹出图片预览层（灯箱）。
 * 点击图片本身会在新窗口全屏打开；点击遮罩或按 ESC 关闭。
 *
 * @param {string} url      - 图片 URL
 * @param {string} [label]  - 可选标题
 */
function showImagePreview(url, label) {
    // 移除已存在的预览层
    const existing = document.getElementById('_lightbox_overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = '_lightbox_overlay';
    overlay.style.cssText = [
        'position:fixed', 'inset:0', 'z-index:99999',
        'background:rgba(0,0,0,0.82)',
        'display:flex', 'flex-direction:column',
        'align-items:center', 'justify-content:center',
        'cursor:zoom-out', 'animation:_lb_fadein 0.18s ease',
    ].join(';');

    // 注入淡入动画（只注入一次）
    if (!document.getElementById('_lightbox_style')) {
        const style = document.createElement('style');
        style.id = '_lightbox_style';
        style.textContent = [
            '@keyframes _lb_fadein{from{opacity:0}to{opacity:1}}',
            '@keyframes _lb_imgpop{from{transform:scale(0.88)}to{transform:scale(1)}}',
        ].join('');
        document.head.appendChild(style);
    }

    // 顶部工具栏
    const toolbar = document.createElement('div');
    toolbar.style.cssText = [
        'display:flex', 'align-items:center', 'justify-content:space-between',
        'width:min(90vw,900px)', 'padding:0 4px 10px',
    ].join(';');
    toolbar.innerHTML = `
        <span style="color:#e2e8f0;font-size:0.92rem;max-width:70%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
            ${label || ''}
        </span>
        <div style="display:flex;gap:10px;">
            <button id="_lb_newwin" title="在新窗口打开"
                style="background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);color:#fff;
                       border-radius:6px;padding:4px 12px;cursor:pointer;font-size:0.85rem;">↗ 新窗口</button>
            <button id="_lb_close" title="关闭 (ESC)"
                style="background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);color:#fff;
                       border-radius:6px;padding:4px 12px;cursor:pointer;font-size:0.85rem;">✕ 关闭</button>
        </div>
    `;

    // 图片
    const img = document.createElement('img');
    img.src = url;
    img.title = '点击在新窗口打开';
    img.style.cssText = [
        'max-width:min(90vw,1000px)', 'max-height:80vh',
        'border-radius:8px', 'box-shadow:0 8px 40px rgba(0,0,0,0.6)',
        'cursor:zoom-in', 'animation:_lb_imgpop 0.18s ease',
        'object-fit:contain',
    ].join(';');
    img.onclick = (e) => { e.stopPropagation(); window.open(url, '_blank'); };

    overlay.appendChild(toolbar);
    overlay.appendChild(img);
    document.body.appendChild(overlay);

    const close = () => overlay.remove();
    overlay.addEventListener('click', close);                            // 点遮罩关闭
    document.getElementById('_lb_close').addEventListener('click', (e) => { e.stopPropagation(); close(); });
    document.getElementById('_lb_newwin').addEventListener('click', (e) => { e.stopPropagation(); window.open(url, '_blank'); });
    const onKey = (e) => { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); } };
    document.addEventListener('keydown', onKey);
}

document.addEventListener('DOMContentLoaded', async () => {
    // 最先获取存储配置，确保后续所有 URL 都能直接用 COS 地址
    try {
        const storageRes = await fetch('/api/config/storage');
        if (storageRes.ok) {
            const storageData = await storageRes.json();
            COS_BASE_URL = storageData.cos_base_url || '';
        }
    } catch (e) {
        console.warn('获取存储配置失败，降级为本地路由', e);
    }

    // ======================== 全局状态 ========================
    let currentStatus = 'unreviewed';                  // 当前筛选的审核状态
    let currentStudentId = null;                        // 当前查看的学员 ID
    let currentTrainingType = 'special_equipment';      // 当前筛选的培训类型
    let students = [];                                  // 学员数据数组
    let jobCategoriesConfig = null;                     // 作业类别配置数据

    // ======================== DOM 元素引用 ========================
    const listContainer = document.getElementById('studentList');       // 学员列表容器
    const mainContent = document.getElementById('mainContent');         // 右侧详情内容区域
    const searchInput = document.getElementById('searchInput');         // 搜索输入框
    const detailTemplate = document.getElementById('detail-template');  // 学员详情 HTML 模板

    // 当前活动的筛选条件
    let currentFilters = {
        company: ''  // 公司名称筛选
    };

    // 从 URL 参数或全局变量初始化培训类型
    if (window.trainingType) {
        currentTrainingType = window.trainingType;
    } else {
        const urlParams = new URLSearchParams(window.location.search);
        const urlTrainingType = urlParams.get('training_type');
        if (urlTrainingType) {
            currentTrainingType = urlTrainingType;
        }
    }

    /**
     * 同步全局管理状态到 window 和 DOM 属性。
     * 便于 CSS 和其他脚本根据当前状态调整显示。
     */
    function syncGlobalAdminState() {
        window.trainingType = currentTrainingType;
        window.currentStatus = currentStatus;
        if (document.body) {
            document.body.dataset.trainingType = currentTrainingType;
            document.body.dataset.status = currentStatus;
        }
    }

    /** 构建状态查询参数（'unreviewed' 映射为 'pending'）。 */
    function buildStatusQueryParam(status) {
        return status === 'unreviewed' ? 'pending' : status;
    }

    /** 获取状态的中文标签和 CSS 类名。 */
    function getStatusMeta(status) {
        if (status === 'reviewed') {
            return { label: '已审核', className: 'reviewed' };
        }
        if (status === 'rejected') {
            return { label: '已驳回', className: 'rejected' };
        }
        if (status === 'registered') {
            return { label: '已报名', className: 'registered' };
        }
        return { label: '未审核', className: 'unreviewed' };
    }

    const MATERIAL_LOG_SCOPE_LABELS = {
        global: '整体流程',
        photo: '个人照片',
        diploma: '学历证书',
        id_card: '身份证',
        id_card_front: '身份证正面',
        id_card_back: '身份证反面',
        hukou: '户口本',
        hukou_home: '户口本首页',
        hukou_personal: '户口本人页',
        training_form: '体检表',
    };

    function getMaterialLogHeadline(logData) {
        const summary = logData?.log_summary || {};
        const outputCount = Array.isArray(summary.output_files) ? summary.output_files.length : 0;
        return `共处理 ${summary.material_count || 0} 项，成功 ${summary.success_count || 0}，警告 ${summary.warning_count || 0}，失败 ${summary.error_count || 0}，输出 ${outputCount} 个文件`;
    }

    function escapeHtml(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function storeMaterialLog(student, payload) {
        student._lastMaterialLog = {
            logs: payload.logs || '',
            log_summary: payload.log_summary || {},
            log_events: Array.isArray(payload.log_events) ? payload.log_events : [],
            message: payload.message || '',
            capturedAt: new Date().toISOString(),
        };
        if (typeof student._renderMaterialLog === 'function') {
            student._renderMaterialLog();
        }
        return student._lastMaterialLog;
    }

    function buildMaterialLogBody(logData) {
        const wrapper = document.createElement('div');
        wrapper.style.cssText = 'display:flex;flex-direction:column;gap:12px;';

        const summary = logData?.log_summary || {};
        const summaryCard = document.createElement('div');
        summaryCard.style.cssText = 'border:1px solid #E2E8F0;border-radius:10px;background:#F8FAFC;padding:12px 14px;';
        summaryCard.innerHTML = `
            <div style="font-size:13px;font-weight:700;color:#0F172A;margin-bottom:4px;">本次处理摘要</div>
            <div style="font-size:12px;color:#475569;line-height:1.7;">${getMaterialLogHeadline(logData)}</div>
        `;
        wrapper.appendChild(summaryCard);

        const events = Array.isArray(logData?.log_events) ? logData.log_events : [];
        const grouped = new Map();
        events.forEach(event => {
            const scopeKey = event.scope || 'global';
            if (!grouped.has(scopeKey)) grouped.set(scopeKey, []);
            grouped.get(scopeKey).push(event);
        });

        grouped.forEach((groupEvents, scopeKey) => {
            const groupBox = document.createElement('div');
            groupBox.style.cssText = 'border:1px solid #E5E7EB;border-radius:10px;overflow:hidden;background:#fff;';

            const header = document.createElement('div');
            header.style.cssText = 'padding:10px 14px;background:#F8FAFC;border-bottom:1px solid #E5E7EB;font-size:13px;font-weight:700;color:#1F2937;';
            header.textContent = MATERIAL_LOG_SCOPE_LABELS[scopeKey] || scopeKey;
            groupBox.appendChild(header);

            const list = document.createElement('div');
            list.style.cssText = 'padding:10px 12px;display:flex;flex-direction:column;gap:10px;';

            groupEvents.forEach(event => {
                const tone = event.level === 'error'
                    ? { border: '#FECACA', bg: '#FEF2F2', title: '#B91C1C', dot: '#EF4444' }
                    : event.level === 'warning'
                        ? { border: '#FDE68A', bg: '#FFFBEB', title: '#92400E', dot: '#F59E0B' }
                        : event.level === 'success'
                            ? { border: '#BBF7D0', bg: '#F0FDF4', title: '#166534', dot: '#22C55E' }
                            : { border: '#CBD5E1', bg: '#F8FAFC', title: '#334155', dot: '#64748B' };

                const card = document.createElement('div');
                card.style.cssText = `border:1px solid ${tone.border};background:${tone.bg};border-radius:8px;padding:10px 12px;`;

                const titleRow = document.createElement('div');
                titleRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:4px;';
                titleRow.innerHTML = `
                    <span style="width:8px;height:8px;border-radius:999px;background:${tone.dot};display:inline-block;"></span>
                    <span style="font-size:12.5px;font-weight:700;color:${tone.title};">${event.title || '处理日志'}</span>
                `;
                card.appendChild(titleRow);

                const msg = document.createElement('div');
                msg.style.cssText = 'font-size:12px;color:#475569;line-height:1.65;';
                msg.textContent = event.message || '';
                card.appendChild(msg);

                const details = event.details && Object.keys(event.details).length > 0
                    ? Object.entries(event.details)
                    : [];
                if (details.length > 0) {
                    const detailBox = document.createElement('div');
                    detailBox.style.cssText = 'margin-top:8px;display:flex;flex-wrap:wrap;gap:6px;';
                    details.forEach(([key, value]) => {
                        const chip = document.createElement('span');
                        chip.style.cssText = 'font-size:11px;color:#475569;background:rgba(255,255,255,0.7);border:1px solid rgba(148,163,184,0.35);border-radius:999px;padding:3px 8px;';
                        chip.textContent = `${key}: ${value}`;
                        detailBox.appendChild(chip);
                    });
                    card.appendChild(detailBox);
                }

                list.appendChild(card);
            });

            groupBox.appendChild(list);
            wrapper.appendChild(groupBox);
        });

        if (logData?.logs) {
            const rawDetails = document.createElement('details');
            rawDetails.style.cssText = 'border:1px solid #CBD5E1;border-radius:10px;overflow:hidden;background:#fff;';
            rawDetails.innerHTML = `
                <summary style="padding:10px 14px;background:#F8FAFC;cursor:pointer;font-size:12.5px;font-weight:700;color:#334155;">查看原始技术日志</summary>
                <pre style="margin:0;padding:12px 14px;background:#0F172A;color:#CBD5E1;font-size:11px;line-height:1.7;white-space:pre-wrap;word-break:break-word;max-height:320px;overflow:auto;">${escapeHtml(logData.logs)}</pre>
            `;
            wrapper.appendChild(rawDetails);
        }

        return wrapper;
    }

    function renderLatestMaterialLog(container, logData) {
        if (!container) return;
        container.innerHTML = '';
        if (!logData) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';
        const panel = document.createElement('details');
        panel.style.cssText = 'margin-top:14px;border:1px solid #CBD5E1;border-radius:10px;overflow:hidden;background:#fff;';
        const capturedLabel = logData.capturedAt
            ? new Date(logData.capturedAt).toLocaleString()
            : '刚刚';
        panel.innerHTML = `
            <summary style="padding:12px 14px;background:#F8FAFC;cursor:pointer;display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:13px;font-weight:700;color:#1F2937;">最近一次生成日志</span>
                <span style="font-size:11.5px;color:#64748B;">${capturedLabel} · ${getMaterialLogHeadline(logData)}</span>
            </summary>
        `;
        const body = document.createElement('div');
        body.style.cssText = 'padding:14px;';
        body.appendChild(buildMaterialLogBody(logData));
        panel.appendChild(body);
        container.appendChild(panel);
    }

    function showMaterialLogModal(logData) {
        const existing = document.getElementById('material-log-modal');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'material-log-modal';
        overlay.style.cssText = 'position:fixed;inset:0;z-index:100000;background:rgba(15,23,42,0.5);display:flex;align-items:center;justify-content:center;padding:18px;box-sizing:border-box;';

        const modal = document.createElement('div');
        modal.style.cssText = 'width:min(980px,100%);max-height:90vh;background:#fff;border-radius:16px;box-shadow:0 24px 60px rgba(0,0,0,0.25);display:flex;flex-direction:column;overflow:hidden;';
        modal.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid #E5E7EB;">
                <div>
                    <div style="font-size:15px;font-weight:700;color:#111827;">报名材料处理日志</div>
                    <div style="margin-top:4px;font-size:12px;color:#64748B;">${getMaterialLogHeadline(logData)}</div>
                </div>
                <button id="material-log-modal-close" style="border:none;background:none;font-size:24px;line-height:1;color:#94A3B8;cursor:pointer;">×</button>
            </div>
        `;
        const body = document.createElement('div');
        body.style.cssText = 'padding:18px;overflow:auto;';
        body.appendChild(buildMaterialLogBody(logData));
        modal.appendChild(body);
        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // 重新设计滚动，加入时间缓冲使其一定能够被浏览器触发
        const forceScroll = () => { if (body) body.scrollTop = body.scrollHeight; };
        forceScroll();
        requestAnimationFrame(forceScroll);
        setTimeout(forceScroll, 50);
        setTimeout(forceScroll, 200);

        const close = () => overlay.remove();
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
        modal.querySelector('#material-log-modal-close').onclick = close;
    }

    syncGlobalAdminState();

    /** 从服务器加载作业类别配置数据（用于编辑时的下拉选项）。 */
    async function loadJobCategories() {
        try {
            const response = await fetch('/api/config/job_categories');
            if (!response.ok) {
                throw new Error('Failed to load job categories');
            }
            jobCategoriesConfig = await response.json();
        } catch (error) {
            console.error('Error loading job categories:', error);
        }
    }

    // ======================== 附件配置 ========================
    // 客户端文件校验规则
    const ATTACHMENT_RULES = {
        maxSizeMb: 10,
        allowedExtensions: ['jpg', 'jpeg', 'png'],
        allowedMimeTypes: ['image/jpeg', 'image/png']
    };

    // 各培训类型的附件字段配置（与服务端 student_routes.py 中的 REQUIRED_ATTACHMENTS 对应）
    const ATTACHMENT_CONFIG = {
        special_operation: [
            { dbKey: 'diploma_path', fieldName: 'diploma', label: '学历证书' },
            { dbKey: 'id_card_front_path', fieldName: 'id_card_front', label: '身份证正面' },
            { dbKey: 'id_card_back_path', fieldName: 'id_card_back', label: '身份证反面' }
        ],
        special_equipment: [
            { dbKey: 'photo_path', fieldName: 'photo', label: '个人照片' },
            { dbKey: 'diploma_path', fieldName: 'diploma', label: '学历证书' },
            { dbKey: 'id_card_front_path', fieldName: 'id_card_front', label: '身份证正面' },
            { dbKey: 'id_card_back_path', fieldName: 'id_card_back', label: '身份证反面' },
            { dbKey: 'hukou_residence_path', fieldName: 'hukou_residence', label: '户口本户籍页' },
            { dbKey: 'hukou_personal_path', fieldName: 'hukou_personal', label: '户口本个人页' }
        ]
    };

    /** 获取指定培训类型的附件字段配置列表。 */
    function getAttachmentConfig(trainingType) {
        return ATTACHMENT_CONFIG[trainingType] || ATTACHMENT_CONFIG.special_operation;
    }

    /**
     * 根据作业类别下拉框的选中值推断培训类型。
     * 遍历配置数据，查找该作业类别属于哪个培训类型。
     *
     * @param {HTMLSelectElement} categorySelect - 作业类别下拉框
     * @returns {string} 培训类型
     */
    function inferTrainingTypeFromCategorySelect(categorySelect) {
        if (!categorySelect) {
            return '';
        }

        const selectedOption = categorySelect.options[categorySelect.selectedIndex];
        if (selectedOption && selectedOption.dataset.trainingType) {
            return selectedOption.dataset.trainingType;
        }

        const selectedCategory = categorySelect.value;
        if (!selectedCategory || !jobCategoriesConfig) {
            return '';
        }

        let inferred = '';
        Object.keys(jobCategoriesConfig).forEach(trainingType => {
            const categories = jobCategoriesConfig[trainingType]?.job_categories || [];
            if (categories.some(category => category.name === selectedCategory)) {
                inferred = trainingType;
            }
        });
        return inferred;
    }

    /**
     * 校验上传的附件文件（扩展名、MIME 类型、大小）。
     *
     * @param {File} file - 文件对象
     * @param {string} label - 文件标签（用于错误提示）
     * @returns {{valid: boolean, error?: string}} 校验结果
     */
    function validateAttachmentFile(file, label) {
        const ext = (file.name.split('.').pop() || '').toLowerCase();
        if (!ATTACHMENT_RULES.allowedExtensions.includes(ext)) {
            return `${label}仅支持 JPG/PNG 格式`;
        }
        if (file.type && !ATTACHMENT_RULES.allowedMimeTypes.includes(file.type)) {
            return `${label}格式无效，请上传 JPG/PNG 图片`;
        }
        if (file.size > ATTACHMENT_RULES.maxSizeMb * 1024 * 1024) {
            return `${label}大小不能超过 ${ATTACHMENT_RULES.maxSizeMb}MB`;
        }
        return '';
    }

    /**
     * 更新培训类型切换按钮的激活状态。
     * 当前选中的培训类型按钮添加 active 类。
     */
    function updateTrainingTypeButtons() {
        const btnSpecialOperation = document.getElementById('btnSpecialOperation');
        const btnSpecialEquipment = document.getElementById('btnSpecialEquipment');
        if (btnSpecialOperation && btnSpecialEquipment) {
            if (currentTrainingType === 'special_operation') {
                btnSpecialOperation.style.background = '#4f46e5';
                btnSpecialOperation.style.color = '#fff';
                btnSpecialOperation.style.borderColor = '#4f46e5';
                btnSpecialEquipment.style.background = '#fff';
                btnSpecialEquipment.style.color = '#333';
                btnSpecialEquipment.style.borderColor = '#ddd';
            } else {
                btnSpecialEquipment.style.background = '#4f46e5';
                btnSpecialEquipment.style.color = '#fff';
                btnSpecialEquipment.style.borderColor = '#4f46e5';
                btnSpecialOperation.style.background = '#fff';
                btnSpecialOperation.style.color = '#333';
                btnSpecialOperation.style.borderColor = '#ddd';
            }
        }
    }
    updateTrainingTypeButtons();

    loadJobCategories().then(() => {
        loadStudents();
        loadCompanies();
        showDashboard();
    });

    /**
     * 数据看板：在主内容区显示统计概览。
     */
    async function showDashboard() {
        try {
            const res = await fetch('/api/stats/dashboard');
            if (!res.ok) return;
            const d = await res.json();

            const statusLabels = {
                unreviewed: '待审核',
                reviewed: '已审核',
                rejected: '已驳回',
                registered: '已报名'
            };
            const statusColors = {
                unreviewed: { bg: '#FEF3C7', color: '#92400E', icon: '⏳' },
                reviewed:   { bg: '#D1FAE5', color: '#065F46', icon: '✅' },
                rejected:   { bg: '#FEE2E2', color: '#991B1B', icon: '↩️' },
                registered: { bg: '#E0E7FF', color: '#3730A3', icon: '🚀' }
            };

            // 状态卡片
            let statusCards = '';
            for (const [key, label] of Object.entries(statusLabels)) {
                const count = d.by_status[key] || 0;
                const c = statusColors[key];
                statusCards += `
                    <div style="flex:1;min-width:120px;background:${c.bg};border-radius:12px;padding:16px 18px;text-align:center;">
                        <div style="font-size:1.6rem;">${c.icon}</div>
                        <div style="font-size:1.5rem;font-weight:800;color:${c.color};margin:4px 0;">${count}</div>
                        <div style="font-size:0.82rem;color:${c.color};font-weight:500;">${label}</div>
                    </div>`;
            }

            // 培训类型分布
            let typeCards = '';
            for (const [typeName, count] of Object.entries(d.by_training_type)) {
                const isEquip = typeName === '特种设备';
                typeCards += `
                    <div style="flex:1;min-width:140px;background:${isEquip ? '#EDE9FE' : '#FCE7F3'};border-radius:12px;padding:16px 18px;text-align:center;">
                        <div style="font-size:1.3rem;">${isEquip ? '📦' : '⚡️'}</div>
                        <div style="font-size:1.4rem;font-weight:800;color:${isEquip ? '#5B21B6' : '#BE185D'};margin:4px 0;">${count}</div>
                        <div style="font-size:0.82rem;color:${isEquip ? '#5B21B6' : '#BE185D'};font-weight:500;">${typeName}</div>
                    </div>`;
            }

            // 月度趋势柱状图
            const maxCount = Math.max(...d.monthly_trend.map(m => m.count), 1);
            let trendBars = '';
            d.monthly_trend.forEach(m => {
                const pct = Math.max((m.count / maxCount) * 100, 4);
                const monthLabel = m.month.slice(5); // "04" from "2026-04"
                trendBars += `
                    <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;">
                        <div style="font-size:0.78rem;font-weight:700;color:#4F46E5;">${m.count}</div>
                        <div style="width:100%;max-width:36px;background:linear-gradient(180deg,#818CF8,#4F46E5);border-radius:6px 6px 2px 2px;height:${pct}px;min-height:4px;transition:height 0.5s ease;"></div>
                        <div style="font-size:0.72rem;color:#64748B;">${monthLabel}月</div>
                    </div>`;
            });

            // 最近学员
            const typeMap = { special_equipment: '特种设备', special_operation: '特种作业' };
            let recentRows = '';
            d.recent_students.forEach(s => {
                const statusMeta = statusColors[s.status] || statusColors.unreviewed;
                const sLabel = statusLabels[s.status] || s.status;
                recentRows += `
                    <div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #F1F5F9;gap:10px;">
                        <div style="flex:1;min-width:0;">
                            <div style="font-weight:600;font-size:0.88rem;color:#0F172A;">${s.name || '-'}</div>
                            <div style="font-size:0.76rem;color:#94A3B8;">${s.company || '-'} · ${typeMap[s.training_type] || ''}</div>
                        </div>
                        <span style="font-size:0.75rem;padding:3px 10px;border-radius:20px;background:${statusMeta.bg};color:${statusMeta.color};font-weight:600;white-space:nowrap;">${sLabel}</span>
                    </div>`;
            });

            mainContent.innerHTML = `
                <div style="max-width:800px;margin:0 auto;padding:10px 0;">
                    <h2 style="margin:0 0 20px;font-size:1.3rem;font-weight:700;color:#0F172A;">📊 数据看板</h2>

                    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px;">
                        <div style="flex:1;min-width:140px;background:linear-gradient(135deg,#4F46E5,#7C3AED);border-radius:14px;padding:18px 20px;color:#fff;">
                            <div style="font-size:0.82rem;opacity:0.85;">学员总数</div>
                            <div style="font-size:2rem;font-weight:800;margin:4px 0;">${d.total}</div>
                        </div>
                        <div style="flex:1;min-width:140px;background:linear-gradient(135deg,#0EA5E9,#0284C7);border-radius:14px;padding:18px 20px;color:#fff;">
                            <div style="font-size:0.82rem;opacity:0.85;">本月新增</div>
                            <div style="font-size:2rem;font-weight:800;margin:4px 0;">${d.this_month}</div>
                        </div>
                        ${statusCards}
                    </div>

                    <div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px;">
                        <div style="flex:2;min-width:280px;background:#fff;border:1px solid #E2E8F0;border-radius:14px;padding:18px 20px;">
                            <div style="font-size:0.88rem;font-weight:700;color:#0F172A;margin-bottom:14px;">📈 近 6 个月趋势</div>
                            <div style="display:flex;align-items:flex-end;gap:8px;height:110px;">
                                ${trendBars}
                            </div>
                        </div>
                        <div style="flex:1;min-width:180px;background:#fff;border:1px solid #E2E8F0;border-radius:14px;padding:18px 20px;">
                            <div style="font-size:0.88rem;font-weight:700;color:#0F172A;margin-bottom:12px;">📋 培训类型</div>
                            <div style="display:flex;flex-direction:column;gap:10px;">
                                ${typeCards}
                            </div>
                        </div>
                    </div>

                    <div style="background:#fff;border:1px solid #E2E8F0;border-radius:14px;padding:18px 20px;">
                        <div style="font-size:0.88rem;font-weight:700;color:#0F172A;margin-bottom:10px;">🕐 最近提交</div>
                        ${recentRows || '<div style="color:#94A3B8;font-size:0.88rem;text-align:center;padding:16px 0;">暂无数据</div>'}
                    </div>
                </div>`;
        } catch (e) {
            // 看板加载失败不影响正常使用
            console.warn('Dashboard load failed:', e);
        }
    }

    /**
     * 从服务器加载公司名称列表（用于公司筛选下拉框）。
     *
     * @param {string} status - 按学员状态筛选
     */
    async function loadCompanies(status = currentStatus) {
        const companyFilter = document.getElementById('companyFilter');
        if (!companyFilter) return;

        try {
            const queryParams = new URLSearchParams({
                status: buildStatusQueryParam(status),
                training_type: currentTrainingType
            });

            const res = await fetch(`/api/companies?${queryParams.toString()}`);
            if (!res.ok) {
                throw new Error(`网络错误: ${res.status}`);
            }
            const companiesWithData = await res.json();

            while (companyFilter.options.length > 1) {
                companyFilter.remove(1);
            }

            companiesWithData.forEach(company => {
                const option = document.createElement('option');
                option.value = company;
                option.textContent = company;
                companyFilter.appendChild(option);
            });
        } catch (err) {
            console.error('加载公司列表失败:', err);
        }
    }

    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const sidebar = document.getElementById('sidebar');

    if (mobileMenuToggle && sidebar) {
        mobileMenuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('mobile-open');
        });

        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 &&
                !sidebar.contains(e.target) &&
                !mobileMenuToggle.contains(e.target) &&
                sidebar.classList.contains('mobile-open')) {
                sidebar.classList.remove('mobile-open');
            }
        });
    }

    const btnSpecialOperation = document.getElementById('btnSpecialOperation');
    const btnSpecialEquipment = document.getElementById('btnSpecialEquipment');

    if (btnSpecialOperation) {
        btnSpecialOperation.addEventListener('click', () => {
            currentTrainingType = 'special_operation';
            syncGlobalAdminState();
            updateTrainingTypeButtons();
            loadStudents();
            loadCompanies(currentStatus);
            if (companyFilter) {
                companyFilter.value = '';
                currentFilters.company = '';
            }
            mainContent.innerHTML = '<div class="empty-state">请选择左侧学员查看详情</div>';
            currentStudentId = null;
        });
    }

    if (btnSpecialEquipment) {
        btnSpecialEquipment.addEventListener('click', () => {
            currentTrainingType = 'special_equipment';
            syncGlobalAdminState();
            updateTrainingTypeButtons();
            loadStudents();
            loadCompanies(currentStatus);
            if (companyFilter) {
                companyFilter.value = '';
                currentFilters.company = '';
            }
            mainContent.innerHTML = '<div class="empty-state">请选择左侧学员查看详情</div>';
            currentStudentId = null;
        });
    }

    function updateStatusButtons() {
        const btnUnreviewed = document.getElementById('btnUnreviewed');
        const btnReviewed = document.getElementById('btnReviewed');
        const btnRegistered = document.getElementById('btnRegistered');
        
        const buttons = {
            'unreviewed': btnUnreviewed,
            'reviewed': btnReviewed,
            'registered': btnRegistered
        };

        Object.keys(buttons).forEach(status => {
            const btn = buttons[status];
            if (btn) {
                if (currentStatus === status) {
                    btn.style.background = '#4f46e5';
                    btn.style.color = '#fff';
                    btn.style.borderColor = '#4f46e5';
                } else {
                    btn.style.background = '#fff';
                    btn.style.color = '#333';
                    btn.style.borderColor = '#ddd';
                }
            }
        });
    }
    updateStatusButtons();

    const btnUnreviewed = document.getElementById('btnUnreviewed');
    const btnReviewed = document.getElementById('btnReviewed');
    const btnRegistered = document.getElementById('btnRegistered');

    function setupStatusBtnEvent(btn, targetStatus) {
        if (btn) {
            btn.addEventListener('click', () => {
                currentStatus = targetStatus;
                syncGlobalAdminState();
                updateStatusButtons();
                loadStudents();
                loadCompanies(currentStatus);
                if (companyFilter) {
                    companyFilter.value = '';
                    currentFilters.company = '';
                }
                mainContent.innerHTML = '<div class="empty-state">请选择左侧学员查看详情</div>';
                currentStudentId = null;
            });
        }
    }

    setupStatusBtnEvent(btnUnreviewed, 'unreviewed');
    setupStatusBtnEvent(btnReviewed, 'reviewed');
    setupStatusBtnEvent(btnRegistered, 'registered');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const filtered = students.filter(s =>
                s.name.toLowerCase().includes(term) ||
                s.id_card.includes(term) ||
                s.phone.includes(term)
            );
            renderList(filtered);
        });
    }

    const companyFilter = document.getElementById('companyFilter');
    const resetFilters = document.getElementById('resetFilters');

    if (companyFilter) {
        companyFilter.addEventListener('change', (e) => {
            currentFilters.company = e.target.value;
            loadStudents();
        });
    }

    if (resetFilters) {
        resetFilters.addEventListener('click', () => {
            if (companyFilter) companyFilter.value = '';
            currentFilters = {
                company: ''
            };
            loadStudents();
            loadCompanies(currentStatus);
        });
    }

    /**
     * 从服务器加载学员列表。
     * 根据当前筛选条件（状态、培训类型、公司）查询。
     */
    async function loadStudents() {
        showListSkeleton();
        try {
            const queryParams = new URLSearchParams({
                status: buildStatusQueryParam(currentStatus),
                company: currentFilters.company,
                training_type: currentTrainingType
            });

            const res = await fetch(`/api/students?${queryParams.toString()}`);
            if (!res.ok) {
                throw new Error(`网络错误: ${res.status}`);
            }
            students = await res.json();
            renderList(students);
        } catch (err) {
            console.error(err);
            listContainer.innerHTML = `
                <div style="text-align:center;padding:30px 16px;color:#9ca3af;">
                    <div style="font-size:1.5rem;margin-bottom:10px;">⚠️</div>
                    <div style="font-weight:600;color:#ef4444;margin-bottom:6px;">加载失败</div>
                    <div style="font-size:0.78rem;margin-bottom:12px;">${err.message}</div>
                    <button onclick="loadStudents()" style="padding:6px 16px;border:1px solid #ddd;border-radius:6px;background:#fff;font-size:0.8rem;cursor:pointer;">重试</button>
                </div>`;
        }
    }

    /**
     * 在列表容器中显示骨架屏加载占位。
     * @param {number} count - 骨架卡片数量
     */
    function showListSkeleton(count = 4) {
        listContainer.innerHTML = Array(count).fill(`
            <div class="list-item skeleton">
                <div class="sk-line sk-w60"></div>
                <div class="sk-line sk-w80"></div>
                <div class="sk-line sk-w40"></div>
            </div>
        `).join('');
    }

    /**
     * 渲染学员列表卡片。
     * 点击卡片时加载该学员的详情。
     *
     * @param {Array} list - 学员数据数组
     */
    function renderList(list) {
        listContainer.innerHTML = '';
        if (!list || list.length === 0) {
            listContainer.innerHTML = `
                <div style="text-align:center;padding:40px 20px;color:#9ca3af;">
                    <div style="font-size:2rem;margin-bottom:12px;">📭</div>
                    <div style="font-weight:600;color:#6b7280;margin-bottom:8px;">暂无符合条件的记录</div>
                    <div style="font-size:0.78rem;">当前筛选：${currentStatus === 'unreviewed' ? '未审核/已驳回' : '已审核'}，尝试切换条件或清除搜索</div>
                </div>`;
            return;
        }

        list.forEach(student => {
            const rejectedMark = student.status === 'rejected'
                ? '<span class="list-rejected-tag">已驳回</span>'
                : '';
            const el = document.createElement('div');
            el.className = `list-item ${currentStudentId === student.id ? 'active' : ''}`;
            el.innerHTML = `
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                        <span style="font-size: 1rem; font-weight: 600; white-space: nowrap;">${student.name}</span>
                        ${rejectedMark}
                        ${student.training_type === 'special_equipment' && student.application_type === 'renewal' ? '<span style="font-size:0.68rem;padding:1px 8px;border-radius:10px;background:#FFF3E0;color:#E65100;font-weight:600;white-space:nowrap;">复审</span>' : ''}
                    </div>
                    <div style="font-size: 0.78rem; color: #555; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${student.company || ''}</div>
                    <div style="font-size: 0.72rem; color: #888; display: flex; justify-content: space-between; gap: 8px;">
                        <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${student.exam_project || student.job_category || ''}</span>
                        <span style="white-space: nowrap; flex-shrink: 0;">ID: ${student.id_card.slice(-4)}</span>
                    </div>
                </div>
            `;
            el.onclick = () => {
                showDetail(student);

                if (window.innerWidth <= 768 && sidebar) {
                    sidebar.classList.remove('mobile-open');
                }
            };
            listContainer.appendChild(el);
        });
    }

    /**
     * 防抖动函数（延迟执行，用于输入框输入时避免频繁请求）。
     *
     * @param {Function} func - 要延迟执行的函数
     * @param {number} wait - 延迟毫秒数
     * @returns {Function} 防抖动后的函数
     */
    function debounce(func, wait) {
        let timeout;
        let lastArgs;
        function executedFunction(...args) {
            lastArgs = args;
            const later = () => {
                timeout = null;
                func(...lastArgs);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        }
        executedFunction.cancel = () => {
            if (timeout) {
                clearTimeout(timeout);
                timeout = null;
            }
        };
        executedFunction.flush = () => {
            if (timeout) {
                clearTimeout(timeout);
                timeout = null;
                func(...lastArgs);
            }
        };
        return executedFunction;
    }

    window.saveStudent = async function () {
        if (!currentStudentId) return;

        showSaveStatus('保存中...', 'info');
        const saveBtn = document.getElementById('_save_student_btn');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';
        }

        try {
            const formData = new FormData();

            const allInputs = mainContent.querySelectorAll('input[data-key], select[data-key]');
            allInputs.forEach(input => {
                const key = input.getAttribute('data-key');
                if (key) {
                    formData.append(key, input.value.trim());
                }
            });

            const jobCategorySelect = mainContent.querySelector('select[data-key="job_category"]');
            const inferredTrainingType = inferTrainingTypeFromCategorySelect(jobCategorySelect);
            if (inferredTrainingType) {
                formData.set('training_type', inferredTrainingType);
            }

            // Bug 8/10 fix: 提交 training_project_id 外键，保证后端能通过外键重新推导 job_category/exam_project/project_code
            const detailGrid = mainContent.querySelector('.detail-grid');
            const trackedProjectId = detailGrid && detailGrid._trackedProjectId;
            if (trackedProjectId) {
                formData.set('training_project_id', trackedProjectId);
            }

            const res = await fetch(`/api/students/${currentStudentId}`, { method: 'PUT', body: formData });

            if (!res.ok) {
                throw new Error('保存失败');
            }

            const updated = await res.json();

            showSaveStatus('保存成功', 'success');

            const idx = students.findIndex(s => s.id === currentStudentId);
            if (idx >= 0) {
                const previousTrainingType = students[idx].training_type;
                students[idx] = updated;
                
                renderList(students);
                const listItems = document.querySelectorAll('.list-item');
                const viewIdx = students.filter(s => currentStatus === 'all' || s.status === currentStatus).findIndex(s => s.id === currentStudentId);
                if (viewIdx >= 0 && listItems[viewIdx]) {
                    listItems[viewIdx].classList.add('active');
                }

                if (currentStudentId === currentStudentId && previousTrainingType !== updated.training_type) {
                    showDetail(updated);
                }
            }

        } catch (e) {
            console.error('Save error:', e);
            showSaveStatus('保存失败', 'error');
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = '保存资料';
            }
        }
    };

    /**
     * 显示保存状态提示（在详情页面右上角显示保存成功/失败的提示）。
     *
     * @param {string} message - 提示消息
     * @param {string} type - 类型 ('info'/'success'/'error')
     */
    function showSaveStatus(message, type = 'info') {
        const existingStatus = mainContent.querySelector('.save-status');
        if (existingStatus) {
            existingStatus.remove();
        }

        const statusElement = document.createElement('div');
        statusElement.className = `save-status ${type}`;
        statusElement.style.position = 'fixed';
        statusElement.style.top = '20px';
        statusElement.style.right = '20px';
        statusElement.style.padding = '10px 15px';
        statusElement.style.borderRadius = '4px';
        statusElement.style.fontSize = '0.9rem';
        statusElement.style.zIndex = '1000';
        statusElement.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
        statusElement.style.transition = 'all 0.3s ease';

        if (type === 'success') {
            statusElement.style.backgroundColor = '#dcfce7';
            statusElement.style.color = '#166534';
            statusElement.style.border = '1px solid #bbf7d0';
        } else if (type === 'error') {
            statusElement.style.backgroundColor = '#fee2e2';
            statusElement.style.color = '#991b1b';
            statusElement.style.border = '1px solid #fecaca';
        } else {
            statusElement.style.backgroundColor = '#dbeafe';
            statusElement.style.color = '#1e40af';
            statusElement.style.border = '1px solid #bfdbfe';
        }

        statusElement.textContent = message;
        mainContent.appendChild(statusElement);

        setTimeout(() => {
            if (statusElement.parentNode) {
                statusElement.style.opacity = '0';
                statusElement.style.transform = 'translateX(100%)';
                setTimeout(() => {
                    statusElement.remove();
                }, 300);
            }
        }, 3000);
    }

    /**
     * 显示全屏模态提示框（审核/驳回/删除操作的确认和结果提示）。
     *
     * @param {string} message - 显示的消息
     * @param {string} type - 类型 ('info'/'success'/'error')
     */
    function showMessage(message, type = 'info', duration = 4000) {
        const existingMessage = document.querySelector('.custom-message');
        if (existingMessage) {
            existingMessage.remove();
        }

        const messageElement = document.createElement('div');
        messageElement.className = `custom-message ${type}`;
        messageElement.style.position = 'fixed';
        messageElement.style.top = '20px';
        messageElement.style.right = '20px';
        messageElement.style.padding = '15px 20px';
        messageElement.style.borderRadius = '8px';
        messageElement.style.fontSize = '0.95rem';
        messageElement.style.zIndex = '10000';
        messageElement.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
        messageElement.style.transition = 'all 0.3s ease';
        messageElement.style.maxWidth = '400px';
        messageElement.style.wordWrap = 'break-word';

        if (type === 'success') {
            messageElement.style.backgroundColor = '#dcfce7';
            messageElement.style.color = '#166534';
            messageElement.style.border = '1px solid #bbf7d0';
        } else if (type === 'error') {
            messageElement.style.backgroundColor = '#fee2e2';
            messageElement.style.color = '#991b1b';
            messageElement.style.border = '1px solid #fecaca';
        } else {
            messageElement.style.backgroundColor = '#dbeafe';
            messageElement.style.color = '#1e40af';
            messageElement.style.border = '1px solid #bfdbfe';
        }

        messageElement.textContent = message;
        document.body.appendChild(messageElement);

        setTimeout(() => {
            if (messageElement.parentNode) {
                messageElement.style.opacity = '0';
                messageElement.style.transform = 'translateY(-20px)';
                setTimeout(() => {
                    messageElement.remove();
                }, 300);
            }
        }, duration);
    }

    /**
     * 渲染学员详情页面。
     *
     * 这是管理后台最复杂的函数，包含：
     * - 基本信息字段的显示和行内编辑
     * - 作业类别/操作项目的联动下拉选择
     * - 附件图片的显示和替换上传
     * - 审核通过、驳回、删除按钮的事件处理
     * - 自动保存（防抖动 1 秒）
     * - 附件打包 ZIP 下载
     *
     * @param {Object} student - 学员数据对象
     */
    function showDetail(student) {
        currentStudentId = student.id;
        document.querySelectorAll('.list-item').forEach(el => el.classList.remove('active'));
        renderList(students);

        const clone = detailTemplate.content.cloneNode(true);

        clone.querySelector('.student-name').textContent = student.name;
        clone.querySelector('.student-id').textContent = student.id_card;
        const submitterOpenidNode = clone.querySelector('.submitter-openid');
        if (submitterOpenidNode) {
            // 已知小程序用户 openid → 姓名映射表
            const OPENID_NAME_MAP = {
                'oQRQz3VglMF63fWRtTCX8gbl21jo': '程超',
                'oQRQz3amHUiSlU5RYNqu-r4GBJlk': '单利亚',
                'oQRQz3SPn9tEiMy74NxfrzV1ZzJE': '霍玉萍',
            };
            const openid = student.submitter_openid || '';
            const knownName = openid && OPENID_NAME_MAP[openid];
            submitterOpenidNode.textContent = knownName
                ? `提交人：${knownName}（${openid}）`
                : `提交人 OpenID：${openid || '-'}`;
        }
        const statusBadge = clone.querySelector('.status-badge');
        if (statusBadge) {
            const statusMeta = getStatusMeta(student.status);
            statusBadge.innerHTML = `<span class="badge ${statusMeta.className}">${statusMeta.label}</span>`;
            statusBadge.style.display = 'flex';
            statusBadge.style.alignItems = 'center';

            // 仅特种设备且已审核（或已报名）学员在顶部显示「开卡」按钮
            if ((student.status === 'reviewed' || student.status === 'registered') && student.training_type === 'special_equipment') {
                const isActivated = !!student.card_activated;

                if (isActivated) {
                    const queryBtn = document.createElement('button');
                    queryBtn.style.cssText = 'background:linear-gradient(135deg,#0EA5E9,#6366F1);color:#fff;font-weight:600;font-size:0.8rem;padding:4px 14px;border-radius:6px;border:none;cursor:pointer;margin-left:12px;box-shadow:0 2px 6px rgba(99,102,241,0.25);white-space:nowrap;';
                    queryBtn.textContent = '🔍 学习卡信息';
                    queryBtn.onclick = async () => {
                        queryBtn.disabled = true;
                        queryBtn.textContent = '查询中...';
                        try {
                            const res = await fetch(`/api/students/${student.id}/query_card`, { method: 'POST' });
                            const data = await res.json();
                            if (res.ok && data.card_id) {
                                const stateBadge = data.state === '有效'
                                    ? '<span style="background:#DCFCE7;color:#15803D;padding:2px 10px;border-radius:99px;font-size:0.75rem;font-weight:600;">✅ 有效</span>'
                                    : `<span style="background:#FEF3C7;color:#92400E;padding:2px 10px;border-radius:99px;font-size:0.75rem;font-weight:600;">${data.state || '-'}</span>`;
                                const overlay = document.createElement('div');
                                overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(15,23,42,0.5);backdrop-filter:blur(4px);z-index:10000;display:flex;justify-content:center;align-items:center;animation:fadeIn .2s ease;';
                                overlay.innerHTML = `
                                <div style="background:#fff;border-radius:16px;max-width:400px;width:92%;box-shadow:0 25px 50px rgba(0,0,0,0.25);overflow:hidden;animation:slideUp .25s ease;">
                                    <div style="background:linear-gradient(135deg,#0EA5E9,#6366F1);padding:18px 22px;display:flex;align-items:center;gap:10px;">
                                        <span style="font-size:1.5rem;">🎓</span>
                                        <div>
                                            <div style="color:#fff;font-size:1rem;font-weight:700;">学习卡信息</div>
                                            <div style="color:rgba(255,255,255,0.8);font-size:0.72rem;margin-top:2px;">君瑞培训系统查询结果</div>
                                        </div>
                                        <div style="margin-left:auto;">${stateBadge}</div>
                                    </div>
                                    <div style="padding:16px 22px;">
                                        <div style="font-size:0.7rem;color:#94A3B8;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">个人信息</div>
                                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;">
                                            <div><span style="font-size:0.72rem;color:#94A3B8;">姓名</span><div style="font-size:0.85rem;color:#0F172A;font-weight:600;margin-top:1px;">${data.name || '-'}</div></div>
                                            <div><span style="font-size:0.72rem;color:#94A3B8;">性别</span><div style="font-size:0.85rem;color:#0F172A;font-weight:600;margin-top:1px;">${data.sex || '-'}</div></div>
                                            <div style="grid-column:span 2;"><span style="font-size:0.72rem;color:#94A3B8;">身份证号</span><div style="font-size:0.85rem;color:#0F172A;font-weight:500;margin-top:1px;font-variant-numeric:tabular-nums;">${data.id_card || '-'}</div></div>
                                            <div style="grid-column:span 2;"><span style="font-size:0.72rem;color:#94A3B8;">手机号</span><div style="font-size:0.85rem;color:#0F172A;font-weight:500;margin-top:1px;">${data.phone || '-'}</div></div>
                                        </div>
                                        <div style="height:1px;background:linear-gradient(90deg,transparent,#E2E8F0,transparent);margin:14px 0;"></div>
                                        <div style="font-size:0.7rem;color:#94A3B8;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">培训信息</div>
                                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;">
                                            <div style="grid-column:span 2;"><span style="font-size:0.72rem;color:#94A3B8;">考试项目</span><div style="font-size:0.85rem;color:#0F172A;font-weight:500;margin-top:1px;">${data.project_name || '-'}</div></div>
                                            <div><span style="font-size:0.72rem;color:#94A3B8;">开卡时间</span><div style="font-size:0.85rem;color:#0F172A;font-weight:500;margin-top:1px;">${data.card_time || '-'}</div></div>
                                        </div>
                                        <div style="height:1px;background:linear-gradient(90deg,transparent,#E2E8F0,transparent);margin:14px 0;"></div>
                                        <div style="font-size:0.7rem;color:#94A3B8;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">学习卡</div>
                                        <div style="background:linear-gradient(135deg,#F0F9FF,#EEF2FF);border:1px solid #BAE6FD;border-radius:10px;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;">
                                            <div><span style="font-size:0.7rem;color:#0369A1;">卡号</span><div style="font-size:0.95rem;color:#0C4A6E;font-weight:700;margin-top:2px;letter-spacing:0.5px;">${data.card_id || '-'}</div></div>
                                            <div style="width:1px;height:32px;background:#BAE6FD;"></div>
                                            <div style="text-align:right;"><span style="font-size:0.7rem;color:#0369A1;">密码</span><div style="font-size:0.95rem;color:#0C4A6E;font-weight:700;margin-top:2px;letter-spacing:1px;">${data.card_pwd || '-'}</div></div>
                                        </div>
                                    </div>
                                    <div style="padding:0 22px 18px;">
                                        <button onclick="this.closest('div[style*=fixed]').remove()" style="width:100%;padding:10px;border:none;border-radius:10px;background:linear-gradient(135deg,#6366F1,#8B5CF6);color:#fff;font-size:0.88rem;font-weight:600;cursor:pointer;transition:opacity .15s;" onmouseover="this.style.opacity='0.9'" onmouseout="this.style.opacity='1'">关 闭</button>
                                    </div>
                                </div>`;
                                document.body.appendChild(overlay);
                                overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
                            } else {
                                showMessage(data.message || data.error || '未查到卡号信息', 'error');
                            }
                        } catch (e) {
                            showMessage('查询失败: ' + e.message, 'error');
                        }
                        queryBtn.textContent = '🔍 学习卡信息';
                        queryBtn.disabled = false;
                    };
                    statusBadge.appendChild(queryBtn);
                } else {
                    const activateCardBtn = document.createElement('button');
                    activateCardBtn.style.cssText = 'background: linear-gradient(135deg, #0ea5e9, #0284c7); color: #fff; font-weight: 600; font-size: 0.8rem; padding: 4px 12px; border-radius: 6px; border: none; cursor: pointer; margin-left: 12px; box-shadow: 0 2px 6px rgba(14,165,233,0.25); white-space: nowrap;';
                    activateCardBtn.textContent = '🎓 开卡';
                    activateCardBtn.title = '为学员在培训考试系统开学习卡';
                    activateCardBtn.onclick = () => showActivateCardDialog(student);
                    statusBadge.appendChild(activateCardBtn);
                }
            }

            // 如果已驳回且有驳回原因，在徽章后插入提示块
            if (student.status === 'rejected' && student.reject_reason) {
                const reasonBox = document.createElement('div');
                reasonBox.style.cssText = [
                    'margin-top:10px', 'padding:10px 14px',
                    'background:#FEF2F2', 'border:1px solid #FECACA',
                    'border-radius:8px', 'font-size:0.85rem', 'line-height:1.6',
                ].join(';');
                reasonBox.innerHTML = `
                    <span style="font-weight:600;color:#B91C1C;">驳回原因：</span>
                    <span style="color:#7F1D1D;">${escapeHtml(student.reject_reason)}</span>
                `;
                statusBadge.after(reasonBox);
            }
        }

        const grid = clone.querySelector('.detail-grid');

        const editable = [
            { key: 'name', label: '姓名', required: true },
            { key: 'gender', label: '性别', required: true, pattern: '男|女', title: '请输入"男"或"女"' },
            {
                key: 'education', label: '文化程度', required: true, type: 'select', options: [
                    { value: '', text: '请选择' },
                    { value: '初中', text: '初中' },
                    { value: '高中或同等学历', text: '高中或同等学历' },
                    { value: '中专或同等学历', text: '中专或同等学历' },
                    { value: '专科或同等学历', text: '专科或同等学历' },
                    { value: '本科或同等学历', text: '本科或同等学历' },
                    { value: '研究生及以上', text: '研究生及以上' }
                ]
            },
            { key: 'id_card', label: '身份证号', required: true, pattern: '\\d{17}[\\dXx]', title: '请输入正确的18位身份证号' },
            { key: 'phone', label: '手机号', required: true, pattern: '\\d{11}', title: '请输入11位手机号' },
            { key: 'school', label: '毕业院校' },
            { key: 'major', label: '所学专业' },
            { key: 'company', label: '单位名称' },
            { key: 'company_address', label: '单位地址' },
            { key: 'job_category', label: '作业类别', required: true, type: 'select', options: [] },
            { key: 'exam_project', label: '操作项目', required: true, type: 'select', options: [] },
            { key: 'project_code', label: '项目代号', readonly: true },
            { key: 'application_type', label: '报名类型', readonly: true, format: v => v === 'renewal' ? '复审' : '新考证', showIf: s => s.training_type === 'special_equipment' }
        ];

        const originalData = { ...student };
        // 初始化 training_project_id 跟踪（后续 updateExamProjectOptions 会更新）
        grid._trackedProjectId = student.training_project_id || '';

        editable.forEach(f => {
            if (f.showIf && !f.showIf(student)) return;
            const item = document.createElement('div');
            item.className = 'detail-item';
            const rawVal = student[f.key] || '';
            const val = f.format ? f.format(rawVal) : rawVal;

            let input;
            if (f.type === 'select') {
                input = document.createElement('select');
                input.setAttribute('data-key', f.key);

                if (f.key === 'job_category') {
                    input.innerHTML = '<option value="">请选择</option>';
                    if (jobCategoriesConfig) {
                        Object.keys(jobCategoriesConfig).forEach(trainingType => {
                            const typeConfig = jobCategoriesConfig[trainingType];
                            const optgroup = document.createElement('optgroup');
                            optgroup.label = typeConfig.name;

                            typeConfig.job_categories.forEach(category => {
                                const option = document.createElement('option');
                                option.value = category.name;
                                option.textContent = category.name;
                                option.dataset.trainingType = trainingType;
                                if (category.name === val) {
                                    option.selected = true;
                                }
                                optgroup.appendChild(option);
                            });

                            input.appendChild(optgroup);
                        });
                    }

                    input.addEventListener('change', function () {
                        updateExamProjectOptions(this, '');
                    });

                    setTimeout(() => {
                        updateExamProjectOptions(input, originalData.exam_project);
                    }, 0);
                } else if (f.key === 'exam_project') {
                    input.innerHTML = '<option value="">请选择操作项目</option>';
                } else {
                    f.options.forEach(option => {
                        const optionElement = document.createElement('option');
                        optionElement.value = option.value;
                        optionElement.textContent = option.text;
                        if (option.value === val) {
                            optionElement.selected = true;
                        }
                        input.appendChild(optionElement);
                    });
                }
            } else {
                input = document.createElement('input');
                input.setAttribute('data-key', f.key);
                input.value = val;
                if (f.readonly) {
                    input.readOnly = true;
                    input.style.backgroundColor = '#f3f4f6';
                }
                if (f.required) input.required = true;
                if (f.pattern) input.pattern = f.pattern;
                if (f.title) input.title = f.title;
            }

            input.style.width = '100%';
            input.style.padding = '5px 8px';
            input.style.border = '1px solid #ddd';
            input.style.borderRadius = '4px';
            input.style.fontSize = '0.88rem';

            item.innerHTML = `<label>${f.label}</label>`;
            item.style.position = 'relative';
            item.appendChild(input);
            grid.appendChild(item);

            const showError = () => {
                input.classList.remove('error');
                const parent = item;
                const exist = parent.querySelector('.error-pop');
                if (exist) exist.remove();
                if (!input.checkValidity()) {
                    input.classList.add('error');
                    const msgText = input.validity.patternMismatch && input.title
                        ? input.title
                        : (input.validationMessage || input.title || '请填写此字段');
                    const pop = document.createElement('span');
                    pop.className = 'error-pop';
                    pop.textContent = msgText;
                    parent.appendChild(pop);
                }
            };
            input.addEventListener('input', showError);
            input.addEventListener('blur', showError);

            if (!f.readonly) {
                if (f.type === 'select') {
                    input.addEventListener('change', showError);
                }
            }
        });

        function updateExamProjectOptions(categorySelect, originalValue) {
            const projectSelect = Array.from(grid.querySelectorAll('select')).find(select => select.getAttribute('data-key') === 'exam_project');
            const projectCodeInput = Array.from(grid.querySelectorAll('input')).find(input => input.getAttribute('data-key') === 'project_code');
            if (!projectSelect) return;

            const selectedCategory = categorySelect.value;
            const selectedOption = categorySelect.options[categorySelect.selectedIndex];

            projectSelect.innerHTML = '<option value="">请选择操作项目</option>';
            if (projectCodeInput) projectCodeInput.value = '';

            if (selectedCategory && jobCategoriesConfig) {
                let foundProjects = null;

                Object.keys(jobCategoriesConfig).forEach(trainingType => {
                    const typeConfig = jobCategoriesConfig[trainingType];
                    const category = typeConfig.job_categories.find(c => c.name === selectedCategory);
                    if (category) {
                        foundProjects = category.exam_projects;
                    }
                });

                if (foundProjects) {
                    foundProjects.forEach(project => {
                        const option = document.createElement('option');
                        option.value = project.name;
                        option.textContent = project.code ? `${project.name} (${project.code})` : project.name;
                        option.dataset.code = project.code || '';
                        option.dataset.projectId = project.id || '';
                        if (originalValue && project.name === originalValue) {
                            option.selected = true;
                            if (projectCodeInput) projectCodeInput.value = project.code || '';
                            grid._trackedProjectId = project.id || '';
                        }
                        projectSelect.appendChild(option);
                    });
                }
            }

            projectSelect.onchange = function () {
                const selectedProjectOption = this.options[this.selectedIndex];
                if (projectCodeInput && selectedProjectOption && selectedProjectOption.dataset.code) {
                    projectCodeInput.value = selectedProjectOption.dataset.code;
                } else if (projectCodeInput) {
                    projectCodeInput.value = '';
                }
                grid._trackedProjectId = (selectedProjectOption && selectedProjectOption.dataset.projectId) || '';
            };
        }

        const filesContainer = clone.querySelector('.file-thumbs');
        filesContainer.style.display = 'flex';
        filesContainer.style.flexWrap = 'nowrap';
        filesContainer.style.gap = '15px';
        filesContainer.style.overflowX = 'auto';
        filesContainer.style.padding = '10px 0';

        const studentTrainingType = student.training_type || currentTrainingType || 'special_operation';
        const attachments = getAttachmentConfig(studentTrainingType);

        const createSwapBtnForWrapper = (pairType, label) => {
            const btn = document.createElement('button');
            btn.className = 'btn';
            btn.textContent = label;
            btn.title = pairType === 'id_card' ? '身份证正反面互换' : '户口本首页和本人页互换';
            
            // 设定专属的浅紫蓝次级操作色，区别于普通白底，高度紧凑
            btn.style.background = '#eef2ff';
            btn.style.color = '#4f46e5';
            btn.style.border = '1px solid #c7d2fe';
            btn.style.padding = '4px 14px'; 
            btn.style.fontSize = '12px';
            
            btn.onmouseover = () => {
                btn.style.background = '#e0e7ff';
            };
            btn.onmouseout = () => {
                btn.style.background = '#eef2ff';
            };
            
            btn.onclick = async (e) => {
                e.stopPropagation();
                const originalText = btn.textContent;
                btn.textContent = '⏳...';
                btn.disabled = true;
                try {
                    const res = await fetch(`/api/students/${student.id}/swap_materials`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ pair: pairType })
                    });
                    if (!res.ok) throw new Error('互换失败');
                    const data = await res.json();
                    const idx = students.findIndex(s => s.id === student.id);
                    if (idx >= 0) students[idx] = data.student;
                    showMessage('图片互换成功', 'success');
                    showDetail(data.student);
                } catch (err) {
                    showMessage(err.message, 'error');
                    btn.textContent = originalText;
                    btn.disabled = false;
                }
            };
            return btn;
        };

        let idCardGroup = null;
        let hukouGroup = null;

        attachments.forEach(attachment => {
            const existingPath = student[attachment.dbKey] || '';
            const wrapper = document.createElement('div');
            wrapper.className = 'file-item-wrapper';
            wrapper.style.display = 'flex';
            wrapper.style.flexDirection = 'column';
            wrapper.style.alignItems = 'center';
            wrapper.style.gap = '5px';
            wrapper.style.minWidth = '100px';

            const uploadBox = document.createElement('div');
            uploadBox.className = 'upload-box';
            uploadBox.style.width = '100px';
            uploadBox.style.height = '100px';
            uploadBox.style.border = '2px dashed #ddd';
            uploadBox.style.borderRadius = '8px';
            uploadBox.style.display = 'flex';
            uploadBox.style.alignItems = 'center';
            uploadBox.style.justifyContent = 'center';
            uploadBox.style.cursor = 'pointer';
            uploadBox.style.transition = 'all 0.3s ease';
            uploadBox.style.position = 'relative';
            uploadBox.style.overflow = 'hidden';

            uploadBox.onclick = (e) => {
                if (!e.target.closest('button')) {
                    if (img.style.display !== 'none') {
                        showImagePreview(img.src, attachment.label);
                    } else {
                        input.click();
                    }
                }
            };

            uploadBox.onmouseover = () => {
                uploadBox.style.borderColor = '#4f46e5';
                uploadBox.style.backgroundColor = 'rgba(79, 70, 229, 0.05)';
            };

            uploadBox.onmouseout = () => {
                uploadBox.style.borderColor = '#ddd';
                uploadBox.style.backgroundColor = 'transparent';
            };

            const placeholder = document.createElement('div');
            placeholder.className = 'upload-placeholder';
            placeholder.style.display = existingPath ? 'none' : 'flex';
            placeholder.style.flexDirection = 'column';
            placeholder.style.alignItems = 'center';
            placeholder.style.justifyContent = 'center';
            placeholder.style.gap = '8px';

            const icon = document.createElement('span');
            icon.className = 'icon';
            icon.textContent = '+';
            icon.style.fontSize = '20px';
            icon.style.color = '#999';

            const text = document.createElement('span');
            text.className = 'text';
            text.textContent = attachment.label;
            text.style.fontSize = '12px';
            text.style.color = '#666';
            text.style.textAlign = 'center';
            text.style.maxWidth = '80px';
            text.style.wordBreak = 'break-all';

            placeholder.appendChild(icon);
            placeholder.appendChild(text);

            const img = document.createElement('img');
            img.className = 'preview-img';
            img.style.display = existingPath ? 'block' : 'none';
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'cover';
            if (existingPath) {
                // 用页面加载时的固定时间戳，同一会话内浏览器可缓存，刷新页面后时间戳变更则强制重下
                img.src = toFileUrl(existingPath) + '?t=' + PAGE_LOAD_TS;
            }

            const input = document.createElement('input');
            input.type = 'file';
            input.name = attachment.fieldName;
            input.accept = '.jpg,.jpeg,.png,image/jpeg,image/png';
            input.style.display = 'none';
            input.title = `${attachment.label}（JPG/PNG，≤10MB）`;

            input.addEventListener('change', () => {
                if (input.files && input.files[0]) {
                    const file = input.files[0];
                    const validationError = validateAttachmentFile(file, attachment.label);
                    if (validationError) {
                        input.value = '';
                        showMessage(validationError, 'error');
                        return;
                    }

                    // 记录上传前的原始图片地址（用于上传失败时回滚）
                    const originalSrc = img.style.display !== 'none' ? img.src : '';

                    const reader = new FileReader();
                    reader.onload = function (ev) {
                        // 立即用本地 base64 更新小图预览，无需等待上传完成
                        const localDataUrl = ev.target.result;
                        img.src = localDataUrl;
                        img.style.display = 'block';
                        placeholder.style.display = 'none';
                        actionBtn.style.display = 'block';
                        actionBtn.textContent = '修改';

                        uploadFile(student.id, attachment.fieldName, file, attachment.dbKey, img, originalSrc);
                        // 清空 input，确保下次选同一文件时 change 事件仍能触发
                        input.value = '';
                    };
                    reader.readAsDataURL(file);
                }
            });

            const actionBtn = document.createElement('button');
            actionBtn.textContent = existingPath ? '修改' : '上传';
            actionBtn.style.marginTop = '5px';
            actionBtn.style.fontSize = '12px';
            actionBtn.style.padding = '2px 8px';
            actionBtn.style.border = '1px solid #ddd';
            actionBtn.style.borderRadius = '4px';
            actionBtn.style.background = '#fff';
            actionBtn.style.cursor = 'pointer';
            actionBtn.style.display = existingPath ? 'block' : 'none';
            actionBtn.onclick = () => {
                input.click();
            };

            const caption = document.createElement('div');
            caption.textContent = attachment.label;
            caption.style.marginTop = '6px';
            caption.style.fontSize = '12px';
            caption.style.color = '#374151';
            caption.style.textAlign = 'center';
            caption.style.lineHeight = '1.3';
            caption.style.width = '100px';
            caption.style.minHeight = '30px';
            caption.style.wordBreak = 'break-all';

            uploadBox.appendChild(placeholder);
            uploadBox.appendChild(img);
            // input 放在 wrapper 而非 uploadBox 内，避免 input.click() 冒泡触发 uploadBox 的预览逻辑
            wrapper.appendChild(uploadBox);
            wrapper.appendChild(input);
            wrapper.appendChild(caption);
            wrapper.appendChild(actionBtn);

            // 分组逻辑
            if (attachment.dbKey === 'id_card_front_path' || attachment.dbKey === 'id_card_back_path') {
                if (!idCardGroup) {
                    idCardGroup = document.createElement('div');
                    idCardGroup.style.display = 'flex';
                    idCardGroup.style.flexDirection = 'column';
                    idCardGroup.style.alignItems = 'center';
                    
                    const row = document.createElement('div');
                    row.className = 'pair-row';
                    row.style.display = 'flex';
                    row.style.gap = '15px';
                    idCardGroup.appendChild(row);
                    
                    filesContainer.appendChild(idCardGroup);
                }
                idCardGroup.querySelector('.pair-row').appendChild(wrapper);

                if (attachment.dbKey === 'id_card_back_path' && student.id_card_front_path && student.id_card_back_path) {
                    const btnWrap = document.createElement('div');
                    btnWrap.style.width = '100%';
                    btnWrap.style.display = 'flex';
                    btnWrap.style.justifyContent = 'center';
                    btnWrap.style.marginTop = '10px'; 
                    btnWrap.style.marginBottom = '-10px';
                    const btn = createSwapBtnForWrapper('id_card', '🔁 互换身份证');
                    btnWrap.appendChild(btn);
                    idCardGroup.appendChild(btnWrap);
                }
            } 
            else if (attachment.dbKey === 'hukou_residence_path' || attachment.dbKey === 'hukou_personal_path') {
                if (!hukouGroup) {
                    hukouGroup = document.createElement('div');
                    hukouGroup.style.display = 'flex';
                    hukouGroup.style.flexDirection = 'column';
                    hukouGroup.style.alignItems = 'center';
                    
                    const row = document.createElement('div');
                    row.className = 'pair-row';
                    row.style.display = 'flex';
                    row.style.gap = '15px';
                    hukouGroup.appendChild(row);
                    
                    filesContainer.appendChild(hukouGroup);
                }
                hukouGroup.querySelector('.pair-row').appendChild(wrapper);

                if (attachment.dbKey === 'hukou_personal_path' && student.hukou_residence_path && student.hukou_personal_path) {
                    const btnWrap = document.createElement('div');
                    btnWrap.style.width = '100%';
                    btnWrap.style.display = 'flex';
                    btnWrap.style.justifyContent = 'center';
                    btnWrap.style.marginTop = '10px'; 
                    btnWrap.style.marginBottom = '-10px';
                    const btn = createSwapBtnForWrapper('hukou', '🔁 互换户口页');
                    btnWrap.appendChild(btn);
                    hukouGroup.appendChild(btnWrap);
                }
            } 
            else {
                filesContainer.appendChild(wrapper);
            }
        });

        if ((student.status === 'reviewed' || student.status === 'registered') && student.training_form_path) {
            const healthCheckWrapper = document.createElement('div');
            healthCheckWrapper.className = 'file-item-wrapper';
            healthCheckWrapper.style.display = 'flex';
            healthCheckWrapper.style.flexDirection = 'column';
            healthCheckWrapper.style.alignItems = 'center';
            healthCheckWrapper.style.gap = '5px';
            healthCheckWrapper.style.minWidth = '100px';

            const healthCheckBox = document.createElement('div');
            healthCheckBox.className = 'upload-box health-check-doc';
            healthCheckBox.style.width = '100px';
            healthCheckBox.style.height = '100px';
            healthCheckBox.style.border = '2px solid #10B981';
            healthCheckBox.style.borderRadius = '8px';
            healthCheckBox.style.display = 'flex';
            healthCheckBox.style.flexDirection = 'column';
            healthCheckBox.style.alignItems = 'center';
            healthCheckBox.style.justifyContent = 'center';
            healthCheckBox.style.cursor = 'pointer';
            healthCheckBox.style.background = 'linear-gradient(135deg, #dcfce7 0%, #d1fae5 100%)';
            healthCheckBox.style.transition = 'all 0.3s ease';

            healthCheckBox.onmouseover = () => {
                healthCheckBox.style.transform = 'scale(1.05)';
                healthCheckBox.style.boxShadow = '0 4px 12px rgba(16, 185, 129, 0.3)';
            };

            healthCheckBox.onmouseout = () => {
                healthCheckBox.style.transform = 'scale(1)';
                healthCheckBox.style.boxShadow = 'none';
            };

            const docIcon = document.createElement('span');
            docIcon.textContent = '📄';
            docIcon.style.fontSize = '32px';

            const docLabel = document.createElement('span');
            docLabel.textContent = '体检表';
            docLabel.style.fontSize = '12px';
            docLabel.style.color = '#065F46';
            docLabel.style.fontWeight = '600';
            docLabel.style.marginTop = '5px';

            healthCheckBox.appendChild(docIcon);
            healthCheckBox.appendChild(docLabel);

            healthCheckBox.onclick = () => {
                window.open(toFileUrl(student.training_form_path), '_blank');
            };

            const downloadBtn = document.createElement('button');
            downloadBtn.textContent = '下载';
            downloadBtn.style.marginTop = '5px';
            downloadBtn.style.fontSize = '12px';
            downloadBtn.style.padding = '2px 8px';
            downloadBtn.style.border = '1px solid #10B981';
            downloadBtn.style.borderRadius = '4px';
            downloadBtn.style.background = '#dcfce7';
            downloadBtn.style.color = '#065F46';
            downloadBtn.style.cursor = 'pointer';
            downloadBtn.style.fontWeight = '500';

            downloadBtn.onclick = (e) => {
                e.stopPropagation();
                const link = document.createElement('a');
                link.href = toFileUrl(student.training_form_path);
                link.download = `${student.id_card}-${student.name}-体检表.docx`;
                link.click();
            };

            healthCheckWrapper.appendChild(healthCheckBox);
            healthCheckWrapper.appendChild(downloadBtn);

            const regenBtn = document.createElement('button');
            regenBtn.textContent = '重新生成';
            regenBtn.style.cssText = 'margin-top:4px;font-size:12px;padding:2px 8px;border:1px solid #6366f1;border-radius:4px;background:#eef2ff;color:#4338ca;cursor:pointer;font-weight:500;';
            regenBtn.onclick = async (e) => {
                e.stopPropagation();
                regenBtn.textContent = '生成中...';
                regenBtn.disabled = true;
                try {
                    const res = await fetch(`/api/students/${student.id}/regenerate_material`, {
                        method: 'POST', 
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ material_type: 'training_form' })
                    });
                    const result = await res.json();
                    if (!res.ok) throw new Error(result.error || '重新生成失败');
                    showMessage('体检表已重新生成', 'success');
                    if (reloadFn) reloadFn();
                } catch (err) {
                    showMessage(err.message, 'error');
                    regenBtn.textContent = '重新生成';
                    regenBtn.disabled = false;
                }
            };
            healthCheckWrapper.appendChild(regenBtn);
            filesContainer.appendChild(healthCheckWrapper);
        }

        // 已报名学员显示「报名申请表」独立下载卡片，按学员状态显示，不依赖当前筛选 tab
        if (student.status === 'registered') {
            const regFormWrapper = document.createElement('div');
            regFormWrapper.className = 'file-item-wrapper';
            regFormWrapper.style.display = 'flex';
            regFormWrapper.style.flexDirection = 'column';
            regFormWrapper.style.alignItems = 'center';
            regFormWrapper.style.gap = '5px';
            regFormWrapper.style.minWidth = '100px';

            const regFormBox = document.createElement('div');
            regFormBox.className = 'upload-box reg-form-doc';
            regFormBox.style.width = '100px';
            regFormBox.style.height = '100px';
            regFormBox.style.border = '2px solid #3B82F6';
            regFormBox.style.borderRadius = '8px';
            regFormBox.style.display = 'flex';
            regFormBox.style.flexDirection = 'column';
            regFormBox.style.alignItems = 'center';
            regFormBox.style.justifyContent = 'center';
            regFormBox.style.cursor = 'pointer';
            regFormBox.style.background = 'linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)';
            regFormBox.style.transition = 'all 0.3s ease';

            regFormBox.onmouseover = () => {
                regFormBox.style.transform = 'scale(1.05)';
                regFormBox.style.boxShadow = '0 4px 12px rgba(59, 130, 246, 0.3)';
            };
            regFormBox.onmouseout = () => {
                regFormBox.style.transform = 'scale(1)';
                regFormBox.style.boxShadow = 'none';
            };

            const regDocIcon = document.createElement('span');
            regDocIcon.textContent = '📄';
            regDocIcon.style.fontSize = '32px';

            const regDocLabel = document.createElement('span');
            regDocLabel.textContent = '报名申请表';
            regDocLabel.style.fontSize = '12px';
            regDocLabel.style.color = '#1E40AF';
            regDocLabel.style.fontWeight = '600';
            regDocLabel.style.marginTop = '5px';

            regFormBox.appendChild(regDocIcon);
            regFormBox.appendChild(regDocLabel);

            const regDownloadBtn = document.createElement('button');
            regDownloadBtn.textContent = '下载';
            regDownloadBtn.style.marginTop = '5px';
            regDownloadBtn.style.fontSize = '12px';
            regDownloadBtn.style.padding = '2px 8px';
            regDownloadBtn.style.border = '1px solid #3B82F6';
            regDownloadBtn.style.borderRadius = '4px';
            regDownloadBtn.style.background = '#dbeafe';
            regDownloadBtn.style.color = '#1E40AF';
            regDownloadBtn.style.cursor = 'pointer';
            regDownloadBtn.style.fontWeight = '500';

            // 下载流程：先查 BMID，再触发文件下载
            // 后端 /api/sxtsks/form/<bmid> 命中本地缓存秒返，未命中则现抓平台
            const triggerDownload = async () => {
                regDownloadBtn.disabled = true;
                regDownloadBtn.textContent = '查询中...';
                try {
                    const bmidRes = await fetch(`/api/sxtsks/bmid/${student.id}`);
                    const bmidData = await bmidRes.json();
                    if (!bmidData.success || !bmidData.bmid) {
                        showMessage(bmidData.message || '未找到该学员的报名记录，请先提交报名', 'warning');
                        return;
                    }
                    regDownloadBtn.textContent = '下载中...';
                    window.open(`/api/sxtsks/form/${bmidData.bmid}?student_id=${student.id}`, '_blank');
                    showMessage(`申请表下载已开始（BMID: ${bmidData.bmid}）`, 'success');
                } catch (e) {
                    showMessage('下载异常: ' + e.message, 'error');
                } finally {
                    regDownloadBtn.disabled = false;
                    regDownloadBtn.textContent = '下载';
                }
            };

            regFormBox.onclick = triggerDownload;
            regDownloadBtn.onclick = (e) => {
                e.stopPropagation();
                triggerDownload();
            };

            regFormWrapper.appendChild(regFormBox);
            regFormWrapper.appendChild(regDownloadBtn);
            filesContainer.appendChild(regFormWrapper);
        }

        if (student.status === 'reviewed' || student.status === 'registered') {
            const materialsSection = document.createElement('div');
            materialsSection.className = 'generated-materials-section';
            materialsSection.style.marginTop = '20px';
            materialsSection.style.borderTop = '1px dashed #ddd';
            materialsSection.style.paddingTop = '15px';
            materialsSection.style.display = 'none';

            const materialsTitle = document.createElement('h3');
            materialsTitle.textContent = '处理好的报名材料';
            materialsTitle.style.fontSize = '14px';
            materialsTitle.style.marginBottom = '10px';
            materialsTitle.style.color = '#333';
            materialsSection.appendChild(materialsTitle);

            const materialsContainer = document.createElement('div');
            materialsContainer.style.display = 'flex';
            materialsContainer.style.flexWrap = 'nowrap';
            materialsContainer.style.gap = '15px';
            materialsContainer.style.overflowX = 'auto';
            materialsContainer.style.padding = '10px 0';
            materialsSection.appendChild(materialsContainer);

            const latestLogSection = document.createElement('div');
            latestLogSection.style.display = 'none';

            filesContainer.parentNode.insertBefore(materialsSection, filesContainer.nextSibling);
            materialsSection.after(latestLogSection);

            const loadMaterials = async () => {
                try {
                    const res = await fetch(`/api/students/${student.id}/generated_materials`);
                    if (res.ok) {
                        const data = await res.json();
                        if (data.exists && data.materials && data.materials.length > 0) {
                            materialsSection.style.display = 'block';
                            materialsContainer.innerHTML = '';
                            data.materials.forEach(mat => {
                                const wrapper = document.createElement('div');
                                wrapper.style.display = 'flex';
                                wrapper.style.flexDirection = 'column';
                                wrapper.style.alignItems = 'center';
                                wrapper.style.gap = '5px';
                                wrapper.style.minWidth = '100px';

                                const imgBox = document.createElement('div');
                                imgBox.style.width = '100px';
                                imgBox.style.height = '100px';
                                imgBox.style.border = '1px solid #ddd';
                                imgBox.style.borderRadius = '8px';
                                imgBox.style.overflow = 'hidden';
                                imgBox.style.cursor = 'pointer';

                                if (mat.name.endsWith('.docx') || mat.name.endsWith('.doc')) {
                                    imgBox.innerHTML = '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:32px;background:#f9fafb;">📄</div>';
                                    imgBox.onclick = () => window.open(toFileUrl(mat.url), '_blank');
                                } else {
                                    const imgUrl = toFileUrl(mat.url) + '?v=' + (mat.mtime || '');
                                    imgBox.innerHTML = `<img src="${imgUrl}" style="width:100%;height:100%;object-fit:cover;">`;
                                    imgBox.onclick = () => showImagePreview(imgUrl, mat.name.replace(/^[^-]+-[^-]+-/, ''));
                                }

                                const caption = document.createElement('div');
                                caption.textContent = mat.name.replace(/^[^-]+-[^-]+-/, '');
                                caption.style.fontSize = '12px';
                                caption.style.color = '#666';
                                caption.style.textAlign = 'center';
                                caption.style.maxWidth = '100px';
                                caption.style.wordBreak = 'break-all';

                                wrapper.appendChild(imgBox);
                                wrapper.appendChild(caption);

                                const matType = detectMaterialType(mat.name);
                                if (matType) {
                                    const adjustBtn = document.createElement('button');
                                    adjustBtn.textContent = '调整';
                                    adjustBtn.style.cssText = 'font-size:11px;padding:2px 8px;border:1px solid #CBD5E1;border-radius:4px;background:#fff;color:#475569;cursor:pointer;';
                                    adjustBtn.onclick = (e) => {
                                        e.stopPropagation();
                                        showAdjustPanel(student, matType, adjustBtn, loadMaterials);
                                    };
                                    wrapper.appendChild(adjustBtn);
                                }

                                materialsContainer.appendChild(wrapper);
                            });
                        } else {
                            materialsSection.style.display = 'none';
                        }
                    }
                } catch (e) {
                    console.error('Failed to load generated materials', e);
                }
            };

            loadMaterials();
            student._reloadMaterials = loadMaterials;
            student._renderMaterialLog = () => renderLatestMaterialLog(latestLogSection, student._lastMaterialLog);
            student._renderMaterialLog();
        }

        const actionBar = clone.querySelector('.action-bar');
        if (actionBar) {
            const saveFormBtn = document.createElement('button');
            saveFormBtn.id = '_save_student_btn';
            saveFormBtn.className = 'btn primary';
            saveFormBtn.style.background = '#10B981';
            saveFormBtn.textContent = '💾 保存';
            saveFormBtn.onclick = () => window.saveStudent();
            // 先不 append，放到最后 append 就可以在居右布局中占最右边

            if (currentStatus === 'unreviewed') {
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn';
                deleteBtn.style.cssText = 'background: #FFF1F2; color: #BE123C;';
                deleteBtn.textContent = '🗑️ 删除学员';
                deleteBtn.onclick = () => {
                    showRejectDialog(null, true);
                };
                actionBar.appendChild(deleteBtn);

                const approveBtn = document.createElement('button');
                approveBtn.className = 'btn primary';
                approveBtn.textContent = '✅ 审核通过';
                approveBtn.onclick = () => approveStudent();
                actionBar.appendChild(approveBtn);
            } else {
                const generateMaterialsBtn = document.createElement('button');
                generateMaterialsBtn.className = 'btn primary';
                generateMaterialsBtn.textContent = '📋 生成报名材料';
                generateMaterialsBtn.style.marginRight = '8px';
                generateMaterialsBtn.style.background = '#4F46E5';
                generateMaterialsBtn.onclick = async () => {
                    const originalText = generateMaterialsBtn.textContent;
                    generateMaterialsBtn.textContent = '⏳ 生成中...';
                    generateMaterialsBtn.disabled = true;

                    try {
                        const res = await fetch(`/api/students/${student.id}/generate_materials`, { method: 'POST' });
                        const data = await res.json();
                        const latestLog = storeMaterialLog(student, data);
                        showMaterialLogModal(latestLog);
                        if (student._reloadMaterials) {
                            student._reloadMaterials();
                        }
                        if (!res.ok) throw new Error(data.message || data.error || '生成失败');
                        showMessage('报名材料生成成功', 'success');
                    } catch (e) {
                        showMessage(e.message, 'error');
                    } finally {
                        generateMaterialsBtn.textContent = originalText;
                        generateMaterialsBtn.disabled = false;
                    }
                };
                actionBar.appendChild(generateMaterialsBtn);

                const downloadMaterialsBtn = document.createElement('button');
                downloadMaterialsBtn.className = 'btn secondary';
                downloadMaterialsBtn.textContent = '📦 报名材料下载';
                downloadMaterialsBtn.style.marginRight = '8px';
                downloadMaterialsBtn.onclick = () => {
                    window.open(`/api/students/${student.id}/download_materials.zip`, '_blank');
                };
                actionBar.appendChild(downloadMaterialsBtn);

                const downloadZipBtn = document.createElement('button');
                downloadZipBtn.className = 'btn secondary';
                downloadZipBtn.textContent = '⬇️ 打包';
                downloadZipBtn.title = '仅下载原附件(剔除报名材料)';
                downloadZipBtn.style.marginRight = '8px';
                downloadZipBtn.onclick = () => {
                    window.open(`/api/students/${student.id}/attachments.zip`, '_blank');
                };
                actionBar.appendChild(downloadZipBtn);

                // ============ 报名平台操作按钮区（仅特种设备学员） ============
                if (student.training_type === 'special_equipment') {

                    // ---------- 日志弹窗公共方法 ----------
                    const _esc = t => String(t || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
                    const buildStepsHtml = (steps) => {
                        if (!steps || !steps.length) return '<div class="log-empty" style="padding:20px; color:#6B7280; text-align:center;">没有记录到执行日志</div>';
                        return steps.map((s, index) => {
                            const stepText = s.step || '';
                            const isSuccess = s.status === 'ok';
                            const isFail = s.status === 'fail';
                            const isWarn = s.status === 'warning';
                            
                            let icon = isSuccess ? `<span style="color:#10B981;">✓</span>` : isFail ? `<span style="color:#EF4444;">✗</span>` : `<span style="color:#F59E0B;">⚠</span>`;
                            if (stepText.includes('登录')) icon = '🔑';
                            if (stepText.includes('照片') || stepText.includes('附件')) icon = '🖼️';
                            if (stepText.includes('提交')) icon = '📤';
                            
                            const timeStr = s.time ? `<span style="color:#6B7280;font-family:monospace;font-size:12px;">[${_esc(s.time)}]</span>` : '';
                            const indexStr = `<span style="color:#4B5563;font-family:monospace;font-size:12px;margin-right:6px;">${String(index + 1).padStart(2, '0')}</span>`;
                            
                            let html = `
                            <div class="log-item" style="padding: 12px 16px; border-bottom: 1px solid #374151; background: ${isFail ? 'rgba(239, 68, 68, 0.05)' : 'transparent'};">
                                <div style="display: flex; align-items: flex-start; gap: 10px;">
                                    <div style="margin-top: 2px;">${icon}</div>
                                    <div style="flex: 1; min-width: 0;">
                                        <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 6px;">
                                            ${indexStr}
                                            ${timeStr}
                                            <strong style="color: ${isFail ? '#FCA5A5' : isWarn ? '#FDE047' : '#D1D5DB'}; font-size: 14px;">${_esc(stepText)}</strong>
                                        </div>
                                        ${s.detail ? `<div style="color: #9CA3AF; font-size: 13px; line-height: 1.5; word-wrap: break-word;">${_esc(s.detail)}</div>` : ''}
                                        
                                        ${s.http_status ? `<div style="display: inline-block; margin-top: 8px; padding: 2px 8px; border-radius: 4px; background: rgba(55, 65, 81, 0.5); color: #9CA3AF; font-size: 11px; font-family: monospace;">HTTP ${s.http_status}</div>` : ''}
                                        
                                        ${s.alerts && s.alerts.length ? `<div style="margin-top: 10px; padding: 8px 12px; border-left: 3px solid #F59E0B; background: rgba(245, 158, 11, 0.1); color: #FCD34D; font-size: 12px; border-radius: 0 4px 4px 0;">拦截警报：<br/>${s.alerts.map(a => _esc(a)).join('<br/>')}</div>` : ''}
                                        
                                        ${s.response ? `<details style="margin-top: 8px; cursor: pointer;">
                                            <summary style="font-size: 12px; color: #6B7280; user-select: none;">查看响应详情 (Trace)</summary>
                                            <div style="margin-top: 8px; padding: 12px; background: rgba(17, 24, 39, 0.8); border: 1px solid #374151; border-radius: 6px; color: #A78BFA; font-family: monospace; font-size: 11px; max-height: 120px; overflow-y: auto; white-space: pre-wrap; word-break: break-all;">${_esc(s.response)}</div>
                                        </details>` : ''}}
                                    </div>
                                </div>
                            </div>`;
                            return html;
                        }).join('');
                    };
                    
                    const showLogOverlay = (titleText, titleColor, data) => {
                        const oldOverlay = document.getElementById('sxtsks-log-overlay');
                        if (oldOverlay) oldOverlay.remove();
                    
                        const overlay = document.createElement('div');
                        overlay.id = 'sxtsks-log-overlay';
                        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.65);backdrop-filter:blur(4px);z-index:10000;display:flex;align-items:center;justify-content:center;animation:fadeIn 0.25s ease;';
                        
                        overlay.innerHTML = `
                            <div style="background:#1F2937; border:1px solid #374151; border-radius:12px; width:90%; max-width:760px; height:85vh; max-height:850px; display:flex; flex-direction:column; box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);">
                                <!-- Header -->
                                <div style="padding:16px 20px; border-bottom:1px solid #374151; display:flex; align-items:center; justify-content:space-between; background:linear-gradient(to right, #111827, #1F2937); border-radius:12px 12px 0 0;">
                                    <div style="display:flex; align-items:center; gap:12px;">
                                        <div style="display:flex; gap:6px;">
                                            <div style="width:12px; height:12px; border-radius:50%; background:#EF4444;"></div>
                                            <div style="width:12px; height:12px; border-radius:50%; background:#F59E0B;"></div>
                                            <div style="width:12px; height:12px; border-radius:50%; background:#10B981;"></div>
                                        </div>
                                        <span style="font-size:1.1rem; font-weight:600; color:${titleColor === '#DC2626' ? '#F87171' : titleColor === '#059669' ? '#34D399' : '#F3F4F6'}; line-height:1;">${titleText}</span>
                                    </div>
                                    <button id="sxtsks-log-close" style="background:rgba(255,255,255,0.1); border:none; width:30px; height:30px; border-radius:6px; cursor:pointer; color:#9CA3AF; display:flex; align-items:center; justify-content:center; transition:all 0.2s;">✕</button>
                                </div>
                                
                                <!-- Log Body -->
                                <div id="sxtsks-log-container" style="flex:1; overflow-y:auto; padding:0; background:#111827; scroll-behavior: smooth;">
                                    ${data.step_details ? buildStepsHtml(data.step_details) : ''}
                                    <div style="height: 40px;"></div> <!-- 占位确保滚动彻底 -->
                                </div>
                                
                                <!-- Footer Summary -->
                                <div style="padding:14px 20px; border-top:1px solid #374151; background:#1F2937; border-radius:0 0 12px 12px; display:flex; align-items:center; justify-content:space-between;">
                                    ${data.form_path ? `<span style="color:#A78BFA; font-size:13px; display:flex; align-items:center; gap:6px;">📄 <span style="font-family:monospace;">${data.form_path}</span></span>` : '<span style="color:#6B7280; font-size:13px;">没有产生可供下载的申请表输出</span>'}
                                    <span id="scroll-to-bottom-btn" style="color:#3B82F6; font-size:13px; cursor:pointer; padding:4px 10px; border-radius:6px; background:rgba(59,130,246,0.1);">⬇️ 滚至最新一行</span>
                                </div>
                            </div>`;
                            
                        document.body.appendChild(overlay);
                        
                        const logContainer = overlay.querySelector('#sxtsks-log-container');
                        const scrollFn = () => {
                            if (logContainer) {
                                logContainer.scrollTo({
                                    top: logContainer.scrollHeight,
                                    behavior: 'smooth'
                                });
                            }
                        };
                        
                        // 多重保障确保渲染贴图后滑动到底部
                        requestAnimationFrame(() => {
                            scrollFn();
                            setTimeout(scrollFn, 100);
                            setTimeout(scrollFn, 300);
                            setTimeout(scrollFn, 600);
                        });
                        
                        const closeBtn = overlay.querySelector('#sxtsks-log-close');
                        closeBtn.onmouseover = () => closeBtn.style.background = 'rgba(255,255,255,0.2)';
                        closeBtn.onmouseout = () => closeBtn.style.background = 'rgba(255,255,255,0.1)';
                        closeBtn.onclick = () => overlay.remove();
                        overlay.querySelector('#scroll-to-bottom-btn').onclick = scrollFn;
                        overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
                    };

                    // ========== 按钮 1：📤 提交报名（仅提交，不下载） ==========
                    if (currentStatus === 'reviewed') {
                        const submitRegBtn = document.createElement('button');
                        submitRegBtn.className = 'btn';
                    submitRegBtn.style.cssText = 'background:linear-gradient(135deg,#F59E0B,#D97706);color:#fff;font-weight:600;margin-right:8px;';
                    submitRegBtn.textContent = '📤 提交报名';
                    submitRegBtn.title = '提交到山西特种设备考试报名平台';
                    submitRegBtn.onclick = async () => {
                        const confirmed = await new Promise(resolve => {
                            const ov = document.createElement('div');
                            ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:10000;display:flex;align-items:center;justify-content:center;';
                            ov.innerHTML = `<div style="background:#fff;border-radius:12px;padding:24px 28px;max-width:400px;box-shadow:0 20px 60px rgba(0,0,0,0.3);text-align:center;">
                                <div style="font-size:1.1rem;font-weight:700;margin-bottom:8px;">📤 提交报名</div>
                                <div style="color:#555;font-size:0.9rem;margin-bottom:20px;">确认将「${student.name}」的信息提交到报名平台？</div>
                                <div style="display:flex;gap:12px;justify-content:center;">
                                    <button id="sxtsks-cancel" style="padding:8px 24px;border:1px solid #ddd;border-radius:8px;background:#fff;cursor:pointer;font-size:0.9rem;">取消</button>
                                    <button id="sxtsks-confirm" style="padding:8px 24px;border:none;border-radius:8px;background:linear-gradient(135deg,#F59E0B,#D97706);color:#fff;cursor:pointer;font-weight:600;font-size:0.9rem;">确认提交</button>
                                </div>
                            </div>`;
                            document.body.appendChild(ov);
                            ov.querySelector('#sxtsks-confirm').onclick = () => { ov.remove(); resolve(true); };
                            ov.querySelector('#sxtsks-cancel').onclick = () => { ov.remove(); resolve(false); };
                        });
                        if (!confirmed) return;
                        const origText = submitRegBtn.textContent;
                        submitRegBtn.textContent = '⏳ 提交中...';
                        submitRegBtn.disabled = true;
                        try {
                            const res = await fetch(`/api/sxtsks/submit/${student.id}`, { method: 'POST' });
                            const data = await res.json();

                            let titleText, titleColor;
                            if (data.success) {
                                titleText = `✅ ${data.message || '报名提交成功'}`;
                                titleColor = '#059669';
                                if (data.submitted_id_card) titleText += `（测试身份证: ${data.submitted_id_card}）`;
                            } else {
                                titleText = `❌ ${data.message || '提交失败'}`;
                                titleColor = '#DC2626';
                            }
                            showLogOverlay(titleText, titleColor, data);

                            if (data.step_details) {
                                console.group('📤 报名提交日志');
                                data.step_details.forEach(s => console.log(`[${s.status}] ${s.step}:`, s));
                                console.groupEnd();
                            }
                        } catch (e) {
                            showMessage('提交异常: ' + e.message, 'error');
                        } finally {
                            submitRegBtn.textContent = origText;
                            submitRegBtn.disabled = false;
                        }
                        };
                        actionBar.appendChild(submitRegBtn);
                    }

                    // ========== 按钮 2：📄 下载申请表 ==========
                    if (currentStatus === 'registered') {
                        const downloadFormBtn = document.createElement('button');
                        downloadFormBtn.className = 'btn';
                    downloadFormBtn.style.cssText = 'background:linear-gradient(135deg,#3B82F6,#2563EB);color:#fff;font-weight:600;margin-right:8px;';
                    downloadFormBtn.textContent = '📄 下载申请表';
                    downloadFormBtn.title = '从报名平台下载该学员的申请表';
                    downloadFormBtn.onclick = async () => {
                        const origText = downloadFormBtn.textContent;
                        downloadFormBtn.textContent = '⏳ 查询中...';
                        downloadFormBtn.disabled = true;
                        try {
                            // 先查询该学员在平台上的 BMID
                            const bmidRes = await fetch(`/api/sxtsks/bmid/${student.id}`);
                            const bmidData = await bmidRes.json();
                            if (!bmidData.success || !bmidData.bmid) {
                                showMessage(bmidData.message || '未找到该学员的报名记录，请先提交报名', 'warning');
                                return;
                            }
                            const bmid = bmidData.bmid;
                            downloadFormBtn.textContent = '⏳ 下载中...';
                            // 下载申请表（同时保存到学员目录）
                            window.open(`/api/sxtsks/form/${bmid}?student_id=${student.id}`, '_blank');
                            showMessage(`申请表下载已开始（BMID: ${bmid}）`, 'success');
                        } catch (e) {
                            showMessage('下载异常: ' + e.message, 'error');
                        } finally {
                            downloadFormBtn.textContent = origText;
                            downloadFormBtn.disabled = false;
                        }
                        };
                        actionBar.appendChild(downloadFormBtn);
                    }
                }


                const rejectBtn = document.createElement('button');
                rejectBtn.className = 'btn';
                rejectBtn.style.cssText = 'background: #FEE2E2; color: #EF4444; margin-right: 8px;';
                rejectBtn.textContent = '↩️ 驳回';
                rejectBtn.onclick = () => showRejectDialog();
                actionBar.appendChild(rejectBtn);
            }
            
            // 最后将保存追加进去，使其在最右侧
            actionBar.appendChild(saveFormBtn);
        }

        mainContent.innerHTML = '';
        mainContent.appendChild(clone);
    }

    async function uploadFile(studentId, fieldName, file, dbKey, previewImg, originalSrc) {
        const formData = new FormData();
        formData.append(fieldName, file);

        try {
            const res = await fetch(`/api/students/${studentId}/upload`, {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                throw new Error('上传失败');
            }

            const result = await res.json();
            showSaveStatus('文件上传成功', 'success');

            // 仅静默更新内存中的 students 缓存，不重绘整个详情页
            // 小图已在 FileReader.onload 里实时更新为本地 base64，无需重绘
            const idx = students.findIndex(s => s.id === studentId);
            if (idx >= 0) {
                if (result.student) {
                    students[idx] = result.student;
                } else if (dbKey || result.field) {
                    students[idx][dbKey || result.field] = result.path;
                }
            }

            // 上传成功后，将小图从 base64 切换为带时间戳的正式 URL（避免浏览器缓存旧图）
            if (previewImg && result.path) {
                previewImg.src = toFileUrl(result.path) + '?t=' + Date.now();
            }
        } catch (e) {
            console.error('Upload error:', e);
            showSaveStatus('文件上传失败', 'error');
            // 回滚预览图：恢复为上传前的原始图片（避免用户误以为已更新）
            if (previewImg) {
                if (originalSrc) {
                    previewImg.src = originalSrc;
                    previewImg.style.display = 'block';
                } else {
                    previewImg.style.display = 'none';
                }
            }
        }
    }

    window.approveStudent = async function () {
        if (!currentStudentId) return;
        try {
            const res = await fetch(`/api/students/${currentStudentId}/approve`, { method: 'POST' });
            if (!res.ok) throw new Error('操作失败');
            const data = await res.json();
            if (data.materials_auto_generated) {
                showMessage('审核通过，报名材料已自动生成 ✅', 'success');
            } else {
                showMessage('审核通过（材料自动生成未完成，可手动重试）', 'success');
            }
            loadStudents();
            loadCompanies(currentStatus);
            mainContent.innerHTML = '<div class="empty-state">请选择左侧学员查看详情</div>';
            currentStudentId = null;
        } catch (e) {
            showMessage('操作失败: ' + e.message, 'error');
        }
    };

    /**
     * 弹出开卡确认对话框，展示学员信息供管理员核对后提交。
     * @param {Object} student - 学员对象
     */
    function showActivateCardDialog(student) {
        const existing = document.getElementById('_activate_card_overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = '_activate_card_overlay';
        overlay.style.cssText = 'position:fixed;inset:0;z-index:99998;background:rgba(15,23,42,0.5);display:flex;align-items:center;justify-content:center;';

        const box = document.createElement('div');
        box.style.cssText = 'background:#fff;border-radius:16px;box-shadow:0 24px 64px rgba(0,0,0,0.28);padding:0;width:min(460px,94vw);box-sizing:border-box;overflow:hidden;';

        box.innerHTML = `
            <div style="background:linear-gradient(135deg,#0ea5e9,#0284c7);padding:20px 24px;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="font-size:17px;font-weight:700;color:#fff;margin-bottom:3px;">🎓 开学习卡确认</div>
                    <div style="font-size:12px;color:rgba(255,255,255,0.8);">请仔细核对以下学员信息，确认无误后点击确认开卡</div>
                </div>
                <button id="_acd_close" style="background:rgba(255,255,255,0.2);border:none;width:32px;height:32px;border-radius:50%;color:#fff;font-size:18px;cursor:pointer;line-height:1;display:flex;align-items:center;justify-content:center;">×</button>
            </div>
            <div style="padding:24px;">
                <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:16px 18px;margin-bottom:20px;">
                    <div style="display:grid;grid-template-columns:80px 1fr;gap:10px 8px;font-size:14px;">
                        <span style="color:#64748b;font-weight:500;">姓&emsp;&emsp;名</span>
                        <span style="color:#0f172a;font-weight:700;font-size:15px;">${student.name || '-'}</span>
                        <span style="color:#64748b;font-weight:500;">手&ensp;机&ensp;号</span>
                        <span style="color:#0369a1;font-weight:600;letter-spacing:1px;">${student.phone || '-'}</span>
                        <span style="color:#64748b;font-weight:500;">身份证号</span>
                        <span style="color:#0f172a;font-weight:600;letter-spacing:0.5px;">${student.id_card || '-'}</span>
                        <span style="color:#64748b;font-weight:500;">培训项目</span>
                        <span style="color:#0369a1;font-weight:600;">${student.exam_project || student.job_category || '-'}</span>
                    </div>
                </div>
                <div style="color:#f59e0b;font-size:13px;margin-bottom:20px;display:flex;align-items:flex-start;gap:6px;">
                    <span style="flex-shrink:0;margin-top:1px;">⚠️</span>
                    <span>开卡操作将把该学员信息提交至培训考试系统，请确认以上信息正确无误。</span>
                </div>
                <div style="display:flex;justify-content:flex-end;gap:10px;">
                    <button id="_acd_cancel" style="padding:9px 22px;border:1px solid #d1d5db;border-radius:8px;background:#fff;color:#374151;font-size:14px;cursor:pointer;font-weight:500;">取消</button>
                    <button id="_acd_confirm" style="padding:9px 22px;border:none;border-radius:8px;background:linear-gradient(135deg,#0ea5e9,#0284c7);color:#fff;font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 3px 8px rgba(14,165,233,0.35);">确认开卡</button>
                </div>
            </div>
        `;

        overlay.appendChild(box);
        document.body.appendChild(overlay);

        const close = () => overlay.remove();
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
        box.querySelector('#_acd_close').onclick = close;
        box.querySelector('#_acd_cancel').onclick = close;
        box.querySelector('#_acd_confirm').onclick = async () => {
            const confirmBtn = box.querySelector('#_acd_confirm');
            confirmBtn.disabled = true;
            confirmBtn.textContent = '开卡中...';
            try {
                const res = await fetch(`/api/students/${student.id}/activate_card`, { method: 'POST' });
                const data = await res.json();
                close();
                if (!res.ok) throw new Error(data.error || data.message || '开卡失败');
                showMessage(data.message || '开卡成功！学员已在培训考试系统创建学习卡', 'success');
                // 更新内存中的学员数据并刷新详情页
                if (data.student) {
                    const idx = students.findIndex(s => s.id === student.id);
                    if (idx >= 0) students[idx] = data.student;
                    showDetail(data.student);
                }
            } catch (e) {
                confirmBtn.disabled = false;
                confirmBtn.textContent = '确认开卡';
                showMessage('开卡失败：' + e.message, 'error');
            }
        };
    }

    /**
     * 弹出自定义驳回对话框（填写原因）。
     * @param {Event|null} _e - 事件对象（兼容用，不使用）
     * @param {boolean} [isDelete=false] - true 表示删除操作
     */
    function showRejectDialog(isDelete = false) {
        const existing = document.getElementById('_reject_dialog_overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = '_reject_dialog_overlay';
        overlay.style.cssText = 'position:fixed;inset:0;z-index:99998;background:rgba(15,23,42,0.45);display:flex;align-items:center;justify-content:center;';

        const box = document.createElement('div');
        box.style.cssText = 'background:#fff;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,0.25);padding:28px 28px 22px;width:min(420px,92vw);box-sizing:border-box;';

        if (isDelete) {
            box.innerHTML = `
                <div style="font-size:16px;font-weight:700;color:#111827;margin-bottom:10px;">⚠️ 确认删除学员</div>
                <div style="font-size:14px;color:#6B7280;margin-bottom:22px;line-height:1.6;">删除后记录和附件文件将不可恢复，请谨慎操作。</div>
                <div style="display:flex;justify-content:flex-end;gap:10px;">
                    <button id="_reject_cancel" style="padding:8px 20px;border:1px solid #D1D5DB;border-radius:8px;background:#fff;color:#374151;font-size:14px;cursor:pointer;">取消</button>
                    <button id="_reject_confirm" style="padding:8px 20px;border:none;border-radius:8px;background:#DC2626;color:#fff;font-size:14px;font-weight:600;cursor:pointer;">确认删除</button>
                </div>
            `;
        } else {
            box.innerHTML = `
                <div style="font-size:16px;font-weight:700;color:#111827;margin-bottom:6px;">驳回学员</div>
                <div style="font-size:13px;color:#6B7280;margin-bottom:14px;">请填写驳回原因，学员将在小程序中看到此原因。</div>
                <textarea id="_reject_reason_input"
                    placeholder="例如：个人照片不清晰，请重新上传正面免冠照..."
                    style="width:100%;box-sizing:border-box;height:100px;padding:10px 12px;border:1px solid #D1D5DB;border-radius:8px;font-size:13px;color:#1F2937;resize:vertical;outline:none;line-height:1.6;"
                ></textarea>
                <div style="font-size:12px;color:#9CA3AF;margin-top:4px;margin-bottom:18px;">原因可留空，但建议填写以便学员修改。</div>
                <div style="display:flex;justify-content:flex-end;gap:10px;">
                    <button id="_reject_cancel" style="padding:8px 20px;border:1px solid #D1D5DB;border-radius:8px;background:#fff;color:#374151;font-size:14px;cursor:pointer;">取消</button>
                    <button id="_reject_confirm" style="padding:8px 20px;border:none;border-radius:8px;background:#EF4444;color:#fff;font-size:14px;font-weight:600;cursor:pointer;">确认驳回</button>
                </div>
            `;
        }

        overlay.appendChild(box);
        document.body.appendChild(overlay);

        const close = () => overlay.remove();
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
        box.querySelector('#_reject_cancel').onclick = close;
        box.querySelector('#_reject_confirm').onclick = () => {
            close();
            if (isDelete) {
                rejectStudent(true, 'rejected', '');
            } else {
                const reason = (box.querySelector('#_reject_reason_input')?.value || '').trim();
                rejectStudent(false, 'rejected', reason);
            }
        };

        // 自动聚焦输入框
        setTimeout(() => box.querySelector('#_reject_reason_input')?.focus(), 50);
    }

    window.rejectStudent = async function (shouldDelete, targetStatus = 'rejected', rejectReason = '') {
        if (!currentStudentId) return;
        try {
            const payload = shouldDelete
                ? { delete: true }
                : { delete: false, status: targetStatus || 'rejected', reject_reason: rejectReason };
            const res = await fetch(`/api/students/${currentStudentId}/reject`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error('操作失败');
            const statusMessage = (payload.status === 'rejected') ? '已驳回学员' : '状态已更新';
            showMessage(shouldDelete ? '已删除学员' : statusMessage, 'success');
            loadStudents();
            loadCompanies(currentStatus);
            mainContent.innerHTML = '<div class="empty-state">请选择左侧学员查看详情</div>';
            currentStudentId = null;
        } catch (e) {
            showMessage('操作失败: ' + e.message, 'error');
        }
    };

    function detectMaterialType(filename) {
        if (filename.includes('个人照片')) return 'photo';
        if (filename.includes('学历证书')) return 'diploma';
        if (filename.includes('身份证')) return 'id_card';
        if (filename.includes('户口本')) return 'hukou';
        return null;
    }

    function showAdjustPanel(student, matType, anchorEl, reloadFn) {
        const existingPanel = document.getElementById('mat-adjust-panel');
        if (existingPanel) existingPanel.remove();

        const panel = document.createElement('div');
        panel.id = 'mat-adjust-panel';
        panel.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.35);padding:16px;box-sizing:border-box;';

        // ── 数据：各 material 类型对应的调整字段 & 图片面板 ─────────────────
        const configs = {
            photo: {
                title: '个人照片调整',
                rotateFields: [{
                    key: 'rotate', label: '旋转',
                    hint: '<span style="color:#6366f1;font-size:12px">📌 照片方向不对时旋转，每次 90°</span>'
                }],
                rotateKeyToPanel: { rotate: 'points' },
                imagePanels: [{ label: '个人照片', pathKey: 'photo_path', pointsKey: 'points' }],
                fixedRatio: 5 / 7,      // 1寸照片比例锁定 (25×35mm)
                cropMode: 'rect_fixed', // 固定比例矩形模式
            },
            diploma: {
                title: '学历证书调整',
                rotateFields: [{
                    key: 'rotate', label: '旋转',
                    hint: '<span style="color:#6366f1;font-size:12px">📌 证书横着显示 → 90° 或 270°｜倒置显示 → 180°｜无问题保持 0°</span>'
                }],
                rotateKeyToPanel: { rotate: 'points' },
                imagePanels: [{ label: '学历证书', pathKey: 'diploma_path', pointsKey: 'points' }]
            },
            id_card: {
                title: '身份证调整',
                rotateFields: [
                    { key: 'front_rotate', label: '正面旋转',
                      hint: '<span style="color:#6366f1;font-size:12px">📌 正面人像倒置或横置 → 选对应角度｜不影响反面，可独立设置</span>' },
                    { key: 'back_rotate', label: '反面旋转',
                      hint: '<span style="color:#6366f1;font-size:12px">📌 国徽倒置或横置 → 选对应角度｜不影响正面，可独立设置</span>' }
                ],
                rotateKeyToPanel: { front_rotate: 'front_points', back_rotate: 'back_points' },
                imagePanels: [
                    { label: '正面（信息面）', pathKey: 'id_card_front_path', pointsKey: 'front_points' },
                    { label: '反面（国徽面）', pathKey: 'id_card_back_path',  pointsKey: 'back_points'  }
                ]
            },
            hukou: {
                title: '户口本调整',
                rotateFields: [
                    { key: 'home_rotate',     label: '首页旋转',
                      hint: '<span style="color:#6366f1;font-size:12px">📌 首页方向不对 → 选对应角度｜本人页独立调整，互不影响</span>' },
                    { key: 'personal_rotate', label: '本人页旋转',
                      hint: '<span style="color:#6366f1;font-size:12px">📌 本人页方向不对 → 选对应角度｜首页独立调整，互不影响</span>' }
                ],
                rotateKeyToPanel: { home_rotate: 'home_points', personal_rotate: 'personal_points' },
                imagePanels: [
                    { label: '首页（户主页）', pathKey: 'hukou_residence_path', pointsKey: 'home_points'     },
                    { label: '本人页',         pathKey: 'hukou_personal_path',  pointsKey: 'personal_points' }
                ]
            },
        };
        const cfg = configs[matType];

        // ── Pill 组件 ─────────────────────────────────────────────────────
        const pillBase = 'display:inline-flex;align-items:center;padding:5px 12px;border:1px solid #CBD5E1;border-radius:6px;font-size:12px;cursor:pointer;transition:all .15s;margin:0 4px 4px 0;';
        const pillOff = pillBase + 'background:#fff;color:#475569;';
        const pillOn  = pillBase + 'background:#4F46E5;color:#fff;border-color:#4F46E5;';

        function pillGroup(groupName, options, defaultVal) {
            return options.map(opt =>
                `<span class="adj-pill" data-group="${groupName}" data-value="${opt.value}"${opt.value === defaultVal ? ' data-active="1"' : ''} style="${opt.value === defaultVal ? pillOn : pillOff}">${opt.label}</span>`
            ).join('');
        }

        function fieldRow(label, desc, groupName, options, defaultVal) {
            return `<div style="margin-bottom:14px;">
                <div style="font-size:13px;color:#333;font-weight:500;margin-bottom:4px;">${label}</div>
                <div style="font-size:12px;color:#555;margin-bottom:7px;line-height:1.55;">${desc}</div>
                <div>${pillGroup(groupName, options, defaultVal)}</div>
            </div>`;
        }

        const cropOptions   = [{ value:'auto',label:'自动'},{value:'rect_only',label:'仅矩形'},{value:'none',label:'不裁剪'}];
        const expandOptions = [{ value:'tight',label:'紧凑'},{value:'normal',label:'标准'},{value:'loose',label:'宽松'},{value:'x-loose',label:'超宽松'}];
        const trimOptions   = [{ value:'on',label:'开启'},{value:'off',label:'关闭'}];
        const rotateOptions = [{ value:'0',label:'0°'},{value:'90',label:'90°'},{value:'180',label:'180°'},{value:'270',label:'270°'}];
        const whiteOptions  = [{ value:'on',label:'开启'},{value:'off',label:'关闭'}];

        const tip = t => `<span style="color:#6366f1;font-size:12px">${t}</span>`;
        const cropDesc   = tip('📌 裁出来变形/拉伸 → 改用「仅矩形」｜全部失败/背景极复杂 → 选「不裁剪」');
        const expandDesc = tip('📌 角落被截断/内容丢失 → 选「宽松」或「超宽松」｜包含大量背景 → 选「紧凑」');
        const ratioDesc  = tip('📌 比例明显异常（过扁或过高）→ 尝试「关闭」｜多数情况保持「开启」');
        const whiteBgDesc = tip('📌 使用 AI 去除背景并替换为纯白色｜如照片已是白底可关闭');

        let leftHtml;
        if (matType === 'photo') {
            // photo 简化版：只有白底开关 + 旋转
            leftHtml = fieldRow('白底处理', whiteBgDesc, 'white_bg', whiteOptions, 'on');
            cfg.rotateFields.forEach(f => {
                leftHtml += fieldRow(f.label, f.hint || tip('📌 方向颠倒或横置时使用，每次旋转 90°'), f.key, rotateOptions, '0');
            });
        } else {
            leftHtml = fieldRow('裁剪模式', cropDesc, 'crop_mode', cropOptions, 'auto')
                     + fieldRow('裁剪边距', expandDesc, 'expand_level', expandOptions, 'normal')
                     + fieldRow('比例修剪', ratioDesc, 'ratio_trim', trimOptions, 'on');

            if (matType === 'id_card' || matType === 'hukou') {
                const cannyOptions = [{value:'1.5',label:'低灵敏'},{value:'1.0',label:'标准'},{value:'0.6',label:'高灵敏'},{value:'0.35',label:'极高灵敏'}];
                const cannyDesc = matType === 'id_card'
                    ? tip('📌 纯黑背景+白色卡片 → 极高灵敏｜深色背景/边缘模糊 → 高灵敏｜被误识到背景纹理噪点 → 低灵敏｜不确定先试「高灵敏」')
                    : tip('📌 户口本放在深色桌面上拍 → 高灵敏｜扫描件/白底书页 → 标准｜识别到装订线等多余边缘 → 低灵敏');
                leftHtml += fieldRow('边缘灵敏度', cannyDesc, 'canny_scale', cannyOptions, '1.0');
            }
            cfg.rotateFields.forEach(f => {
                leftHtml += fieldRow(f.label, f.hint || tip('📌 方向颠倒或横置时使用，每次旋转 90°'), f.key, rotateOptions, '0');
            });
        }

        // ── 画框区：状态和 canvas 数据 ────────────────────────────────────
        const cropState = {}; // pointsKey → { displayPts[], originalPts[] }
        cfg.imagePanels.forEach(p => { cropState[p.pointsKey] = { displayPts: [], originalPts: [] }; });

        // 当前激活的 tab（多图时用）
        let activeTab = cfg.imagePanels[0].pointsKey;

        function buildImagePanel(ip) {
            const url = toFileUrl(student[ip.pathKey]);
            const wrap = document.createElement('div');
            wrap.style.cssText = 'display:flex;flex-direction:column;gap:8px;height:100%;';

            const imgWrap = document.createElement('div');
            imgWrap.style.cssText = 'position:relative;flex:1;min-height:0;background:#1e1e2e;border-radius:8px;overflow:hidden;border:1.5px solid #e5e7eb;line-height:0;';

            // img 仅用于加载图像数据，不参与布局显示
            const img = document.createElement('img');
            img.src = url || '';
            img.style.cssText = 'display:none;';
            img.draggable = false;

            // canvas 负责所有渲染：旋转后的图像 + 裁剪遮罩 + 角点把手
            const cvs = document.createElement('canvas');
            cvs.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;cursor:default;';

            const statusEl = document.createElement('div');
            statusEl.style.cssText = 'font-size:11.5px;color:#6b7280;flex-shrink:0;height:16px;';
            statusEl.textContent = '图片加载中...';

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

            // ── 状态 ──────────────────────────────────────────────────────
            const HANDLE_R = 8;
            let originalPts = null;  // 4×[ox,oy] 原始图像像素坐标（主状态）
            let dispPts    = null;   // 4×[cx,cy] canvas 坐标（由 origToDisp 动态派生）
            let dragging   = -1;
            let userDragged = false; // 用户真正手动拖动过
            let hasConfirmedPoints = false; // 仅用户确认过的点位才参与提交
            let rotationDeg = 0;     // 当前旋转角度（0/90/180/270）

            // ── photo 固定比例矩形框状态 ──────────────────────────────────
            const isFixedRatio = !!cfg.fixedRatio;
            const FIXED_RATIO = cfg.fixedRatio || 1;  // w/h，例如 5/7≈0.714
            // cropRect: {x, y, w, h} 原图像素坐标
            let cropRect = null;
            let dispRect = null;  // canvas 坐标
            let dragMode = null;  // 'move' | 'resize-tl' | 'resize-tr' | 'resize-br' | 'resize-bl'
            let dragStart = null; // {mx, my, rect: {...cropRect}}

            // ── 坐标变换（含旋转矩阵）──────────────────────────────────────
            function getTransform() {
                const W = cvs.clientWidth  || 1;
                const H = cvs.clientHeight || 1;
                const rad = rotationDeg * Math.PI / 180;
                const cos = Math.abs(Math.cos(rad));
                const sin = Math.abs(Math.sin(rad));
                const nw = img.naturalWidth  || 1;
                const nh = img.naturalHeight || 1;
                // 旋转后图像的有效边界尺寸
                const effW = nw * cos + nh * sin;
                const effH = nw * sin + nh * cos;
                const scale = Math.min(W / effW, H / effH);
                return { W, H, rad, scale, nw, nh, cx: W / 2, cy: H / 2 };
            }

            // 原图像素坐标 → canvas 坐标（含旋转）
            function origToDisp([ox, oy]) {
                const { rad, scale, nw, nh, cx, cy } = getTransform();
                const dx = (ox - nw / 2) * scale;
                const dy = (oy - nh / 2) * scale;
                return [
                    Math.round(cx + dx * Math.cos(rad) - dy * Math.sin(rad)),
                    Math.round(cy + dx * Math.sin(rad) + dy * Math.cos(rad)),
                ];
            }

            // canvas 坐标 → 原图像素坐标（逆旋转）
            function dispToOrig([mx, my]) {
                const { rad, scale, nw, nh, cx, cy } = getTransform();
                const dx = mx - cx, dy = my - cy;
                return [
                    Math.max(0, Math.min(nw, Math.round((dx * Math.cos(-rad) - dy * Math.sin(-rad)) / scale + nw / 2))),
                    Math.max(0, Math.min(nh, Math.round((dx * Math.sin(-rad) + dy * Math.cos(-rad)) / scale + nh / 2))),
                ];
            }

            // 从 originalPts 重新计算 dispPts（旋转改变或图像尺寸改变后调用）
            function refreshDispPts() {
                if (isFixedRatio && cropRect) {
                    refreshDispRect();
                    return;
                }
                if (originalPts) dispPts = originalPts.map(p => origToDisp(p));
            }

            // ── 固定比例矩形：坐标刷新 ─────────────────────────────────────
            function refreshDispRect() {
                if (!cropRect) return;
                const tl = origToDisp([cropRect.x, cropRect.y]);
                const br = origToDisp([cropRect.x + cropRect.w, cropRect.y + cropRect.h]);
                dispRect = { x: tl[0], y: tl[1], w: br[0] - tl[0], h: br[1] - tl[1] };
                // 同步到 originalPts/dispPts 以兼容提交流程
                originalPts = [
                    [cropRect.x, cropRect.y],
                    [cropRect.x + cropRect.w, cropRect.y],
                    [cropRect.x + cropRect.w, cropRect.y + cropRect.h],
                    [cropRect.x, cropRect.y + cropRect.h],
                ];
                dispPts = originalPts.map(p => origToDisp(p));
            }

            // 用整张图的四角初始化 originalPts（自由角点模式）
            // 或用最大内切矩形初始化 cropRect（固定比例模式）
            function initRect() {
                const nw = img.naturalWidth, nh = img.naturalHeight;
                if (!nw) return;
                if (isFixedRatio) {
                    // 在原图中心放置最大的固定比例矩形
                    let rw, rh;
                    if (nw / nh > FIXED_RATIO) {
                        rh = nh * 0.85;
                        rw = rh * FIXED_RATIO;
                    } else {
                        rw = nw * 0.85;
                        rh = rw / FIXED_RATIO;
                    }
                    cropRect = {
                        x: Math.round((nw - rw) / 2),
                        y: Math.round((nh - rh) / 2),
                        w: Math.round(rw),
                        h: Math.round(rh),
                    };
                    refreshDispRect();
                } else {
                    originalPts = [[0, 0], [nw, 0], [nw, nh], [0, nh]];
                    refreshDispPts();
                }
                syncCropState();
            }

            function syncCropState() {
                if (!originalPts || !hasConfirmedPoints) {
                    cropState[ip.pointsKey] = { displayPts: [], originalPts: [] };
                    return;
                }
                cropState[ip.pointsKey] = {
                    displayPts:  dispPts   ? dispPts.map(p => [...p])    : [],
                    originalPts: originalPts.map(p => [...p]),
                };
            }

            // ── Canvas 渲染 ────────────────────────────────────────────────
            function redraw() {
                const { W, H, rad, scale, nw, nh, cx, cy } = getTransform();
                cvs.width = W; cvs.height = H;
                const ctx = cvs.getContext('2d');
                ctx.clearRect(0, 0, W, H);

                // 1. 绘制旋转后的图像
                if (img.complete && nw > 1) {
                    const drawW = nw * scale, drawH = nh * scale;
                    ctx.save();
                    ctx.translate(cx, cy);
                    ctx.rotate(rad);
                    ctx.drawImage(img, -drawW / 2, -drawH / 2, drawW, drawH);
                    ctx.restore();
                }

                if (isFixedRatio) {
                    // ── 固定比例矩形渲染 ──
                    if (!dispRect) return;
                    const { x: rx, y: ry, w: rw, h: rh } = dispRect;

                    // 2. 半透明遮罩
                    ctx.fillStyle = 'rgba(0,0,0,0.42)';
                    ctx.fillRect(0, 0, W, H);
                    // 3. 镂空矩形
                    ctx.save();
                    ctx.globalCompositeOperation = 'destination-out';
                    ctx.fillRect(rx, ry, rw, rh);
                    ctx.restore();
                    // 4. 矩形边框
                    ctx.strokeStyle = '#6366f1';
                    ctx.lineWidth = 2;
                    ctx.setLineDash([]);
                    ctx.strokeRect(rx, ry, rw, rh);

                    // 5. 四角缩放手柄（方形）
                    const corners = [[rx, ry], [rx + rw, ry], [rx + rw, ry + rh], [rx, ry + rh]];
                    corners.forEach(([hx, hy]) => {
                        ctx.fillStyle = '#fff';
                        ctx.fillRect(hx - 6, hy - 6, 12, 12);
                        ctx.strokeStyle = '#6366f1';
                        ctx.lineWidth = 2;
                        ctx.strokeRect(hx - 6, hy - 6, 12, 12);
                    });
                    // 6. 中心移动提示
                    ctx.fillStyle = 'rgba(255,255,255,0.6)';
                    ctx.beginPath();
                    ctx.arc(rx + rw / 2, ry + rh / 2, 12, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.fillStyle = '#4f46e5';
                    ctx.font = 'bold 14px sans-serif';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText('✛', rx + rw / 2, ry + rh / 2);
                    // 7. 比例提示
                    ctx.fillStyle = 'rgba(99,102,241,0.85)';
                    ctx.font = '11px sans-serif';
                    ctx.textAlign = 'left';
                    ctx.fillText('1寸 (5:7)', rx + 4, ry - 6);
                    return;
                }

                if (!dispPts) return;

                // 2. 半透明遮罩（裁剪区外）
                ctx.fillStyle = 'rgba(0,0,0,0.42)';
                ctx.fillRect(0, 0, W, H);

                // 3. 镂空裁剪区（destination-out）
                ctx.save();
                ctx.beginPath();
                ctx.moveTo(dispPts[0][0], dispPts[0][1]);
                dispPts.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
                ctx.closePath();
                ctx.globalCompositeOperation = 'destination-out';
                ctx.fill();
                ctx.restore();

                // 4. 裁剪框边线
                ctx.beginPath();
                ctx.moveTo(dispPts[0][0], dispPts[0][1]);
                dispPts.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
                ctx.closePath();
                ctx.strokeStyle = '#6366f1';
                ctx.lineWidth = 2;
                ctx.setLineDash([]);
                ctx.stroke();

                // 5. 角点把手
                dispPts.forEach(([x, y], i) => {
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
                    ctx.fillText(String(i + 1), x, y);
                });
            }

            function hitTest(mx, my) {
                if (!dispPts) return -1;
                let best = -1, bestD = HANDLE_R * 2;
                dispPts.forEach(([x, y], i) => {
                    const d = Math.hypot(mx - x, my - y);
                    if (d < bestD) { bestD = d; best = i; }
                });
                return best;
            }

            // ── 固定比例矩形：命中测试 ─────────────────────────────────────
            function hitTestRect(mx, my) {
                if (!dispRect) return null;
                const { x, y, w, h } = dispRect;
                const HR = 10;
                // 四角
                if (Math.hypot(mx - x, my - y) < HR) return 'resize-tl';
                if (Math.hypot(mx - (x + w), my - y) < HR) return 'resize-tr';
                if (Math.hypot(mx - (x + w), my - (y + h)) < HR) return 'resize-br';
                if (Math.hypot(mx - x, my - (y + h)) < HR) return 'resize-bl';
                // 框内
                if (mx >= x && mx <= x + w && my >= y && my <= y + h) return 'move';
                return null;
            }

            function getCursorForMode(mode) {
                if (!mode) return 'default';
                if (mode === 'move') return 'move';
                if (mode === 'resize-tl' || mode === 'resize-br') return 'nwse-resize';
                return 'nesw-resize';
            }

            // 限制 cropRect 不超出原图边界
            function clampCropRect() {
                const nw = img.naturalWidth, nh = img.naturalHeight;
                if (cropRect.x < 0) cropRect.x = 0;
                if (cropRect.y < 0) cropRect.y = 0;
                if (cropRect.x + cropRect.w > nw) cropRect.x = nw - cropRect.w;
                if (cropRect.y + cropRect.h > nh) cropRect.y = nh - cropRect.h;
            }

            // ── 鼠标事件 ──────────────────────────────────────────────────
            if (isFixedRatio) {
                // ── photo 固定比例矩形交互 ──
                cvs.addEventListener('mousedown', e => {
                    if (!cropRect) { initRect(); redraw(); }
                    const rect = cvs.getBoundingClientRect();
                    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
                    dragMode = hitTestRect(mx, my);
                    if (dragMode) {
                        e.preventDefault();
                        dragStart = { mx, my, rect: { ...cropRect } };
                        cvs.style.cursor = getCursorForMode(dragMode);
                    }
                });

                cvs.addEventListener('mousemove', e => {
                    const bRect = cvs.getBoundingClientRect();
                    const mx = e.clientX - bRect.left, my = e.clientY - bRect.top;
                    if (dragMode && dragStart) {
                        const { scale } = getTransform();
                        const dxPx = (mx - dragStart.mx) / scale;
                        const dyPx = (my - dragStart.my) / scale;
                        const s = dragStart.rect;

                        if (dragMode === 'move') {
                            cropRect.x = Math.round(s.x + dxPx);
                            cropRect.y = Math.round(s.y + dyPx);
                            clampCropRect();
                        } else {
                            // 角缩放：保持比例，根据拖动距离决定大小
                            let newW, newH;
                            if (dragMode === 'resize-br') {
                                newW = Math.max(40, Math.round(s.w + dxPx));
                            } else if (dragMode === 'resize-bl') {
                                newW = Math.max(40, Math.round(s.w - dxPx));
                            } else if (dragMode === 'resize-tr') {
                                newW = Math.max(40, Math.round(s.w + dxPx));
                            } else { // resize-tl
                                newW = Math.max(40, Math.round(s.w - dxPx));
                            }
                            newH = Math.round(newW / FIXED_RATIO);
                            const nw = img.naturalWidth, nh = img.naturalHeight;
                            // 限制不超出图片
                            if (newW > nw) { newW = nw; newH = Math.round(newW / FIXED_RATIO); }
                            if (newH > nh) { newH = nh; newW = Math.round(newH * FIXED_RATIO); }

                            if (dragMode === 'resize-br') {
                                cropRect.w = newW; cropRect.h = newH;
                            } else if (dragMode === 'resize-bl') {
                                cropRect.x = Math.round(s.x + s.w - newW);
                                cropRect.w = newW; cropRect.h = newH;
                            } else if (dragMode === 'resize-tr') {
                                cropRect.y = Math.round(s.y + s.h - newH);
                                cropRect.w = newW; cropRect.h = newH;
                            } else { // resize-tl
                                cropRect.x = Math.round(s.x + s.w - newW);
                                cropRect.y = Math.round(s.y + s.h - newH);
                                cropRect.w = newW; cropRect.h = newH;
                            }
                            clampCropRect();
                        }
                        refreshDispRect();
                        syncCropState();
                        redraw();
                    } else {
                        cvs.style.cursor = getCursorForMode(hitTestRect(mx, my));
                    }
                });

                const stopDragRect = () => {
                    if (dragMode) {
                        userDragged = true;
                        hasConfirmedPoints = true;
                        syncCropState();
                        statusEl.style.color = '#059669';
                        statusEl.textContent = '✓ 已手动调整裁剪区域，点击「重新生成」确认';
                    }
                    dragMode = null;
                    dragStart = null;
                    cvs.style.cursor = 'default';
                };
                cvs.addEventListener('mouseup', stopDragRect);
                cvs.addEventListener('mouseleave', stopDragRect);

                resetBtn.onclick = () => {
                    userDragged = false;
                    hasConfirmedPoints = false;
                    cropRect = null;
                    dispRect = null;
                    originalPts = null;
                    dispPts = null;
                    initRect();
                    redraw();
                    statusEl.textContent = '拖动框选区域或角手柄调整裁剪范围';
                    statusEl.style.color = '#6b7280';
                };
            } else {
                // ── 现有4角点自由交互 ──
                cvs.addEventListener('mousedown', e => {
                    if (!dispPts) { initRect(); redraw(); }
                    const rect = cvs.getBoundingClientRect();
                    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
                    dragging = hitTest(mx, my);
                    if (dragging >= 0) { e.preventDefault(); cvs.style.cursor = 'grabbing'; }
                });

                cvs.addEventListener('mousemove', e => {
                    const rect = cvs.getBoundingClientRect();
                    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
                    if (dragging >= 0) {
                        dispPts[dragging]    = [mx, my];
                        originalPts[dragging] = dispToOrig([mx, my]); // 同步回原图坐标
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
                        statusEl.style.color   = '#059669';
                        statusEl.textContent   = '✓ 已手动调整裁剪区域，点击「重新生成」确认';
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
                    dispPts     = null;
                    initRect();
                    redraw();
                    statusEl.textContent = '拖动角点调整裁剪区域';
                    statusEl.style.color = '#6b7280';
                };
            }

            // ── 暴露接口 ──────────────────────────────────────────────────
            wrap.applyServerPoints = (pts_orig) => {
                if (userDragged) return; // 用户手动拖过，不覆盖
                originalPts = pts_orig.map(p => [...p]);
                hasConfirmedPoints = false;
                refreshDispPts();
                syncCropState();
                redraw();
                statusEl.style.color = '#059669';
                statusEl.textContent = '✓ 已加载预识别裁剪区域，可拖动角点微调';
            };

            wrap.getHasDragged = () => userDragged;

            wrap.setStatus = (text, color) => {
                statusEl.textContent = text;
                statusEl.style.color = color || '#6b7280';
            };

            // 旋转预览：更新旋转角度并重绘（角点坐标存于 originalPts 不变，dispPts 重新映射）
            wrap.setRotation = (deg) => {
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

            // 兼容旧接口（新设计不再使用 serverPoints 缓存）
            wrap.getServerPoints = () => null;

            // ── 图片加载 ──────────────────────────────────────────────────
            function onImgReady() {
                if (!img.complete || img.naturalWidth === 0) return;
                if (cvs.clientWidth === 0) return;
                if (isFixedRatio) {
                    initRect();
                    statusEl.textContent = '拖动选框调整裁剪范围（不标记默认处理整张图）';
                    statusEl.style.color = '#6b7280';
                } else if (!hasConfirmedPoints && !originalPts) {
                    initRect();
                    statusEl.textContent = '拖动角点调整裁剪区域（不标记默认按左侧参数运行自动处理）';
                    statusEl.style.color = '#6b7280';
                } else {
                    refreshDispPts();
                }
                redraw();
            }

            img.onload = () => setTimeout(onImgReady, 60);

            const ro = new ResizeObserver(() => {
                if (cvs.clientWidth > 0) { refreshDispPts(); redraw(); }
            });
            ro.observe(imgWrap);

            if (!url) {
                imgWrap.innerHTML = '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#9ca3af;font-size:13px;">未上传</div>';
                statusEl.textContent = '未上传原图';
            } else {
                imgWrap.appendChild(img);
                imgWrap.appendChild(cvs);
            }

            wrap.appendChild(imgWrap);
            wrap.appendChild(statusEl);
            wrap.appendChild(bottomRow);
            return wrap;
        }


        // ── 构建右侧内容（Tab 或单面板）────────────────────────────────
        let rightContent;
        const panelEls = {};
        const multiPanel = cfg.imagePanels.length > 1;

        if (multiPanel) {
            rightContent = document.createElement('div');
            rightContent.style.cssText = 'display:flex;flex-direction:column;height:100%;';

            const tabBar = document.createElement('div');
            tabBar.style.cssText = 'display:flex;gap:6px;margin-bottom:10px;flex-shrink:0;';

            const panelContainer = document.createElement('div');
            panelContainer.style.cssText = 'flex:1;min-height:0;overflow:hidden;';

            cfg.imagePanels.forEach((ip, idx) => {
                const activeStyle = 'padding:5px 14px;border:none;border-radius:7px;font-size:12px;cursor:pointer;background:#4F46E5;color:#fff;font-weight:600;';
                const inactiveStyle = 'padding:5px 14px;border:1px solid #e5e7eb;border-radius:7px;font-size:12px;cursor:pointer;background:#fff;color:#475569;';
                const tab = document.createElement('button');
                tab.textContent = ip.label;
                tab.dataset.key = ip.pointsKey;
                tab.style.cssText = idx === 0 ? activeStyle : inactiveStyle;
                tab.onclick = () => {
                    tabBar.querySelectorAll('button').forEach(b => {
                        b.style.cssText = b.dataset.key === ip.pointsKey ? activeStyle : inactiveStyle;
                    });
                    Object.entries(panelEls).forEach(([k, el]) => {
                        el.style.display = k === ip.pointsKey ? 'flex' : 'none';
                    });
                };
                tabBar.appendChild(tab);

                const el = buildImagePanel(ip);
                el.style.display = idx === 0 ? 'flex' : 'none';
                el.style.height = '100%';
                panelEls[ip.pointsKey] = el;
                panelContainer.appendChild(el);
            });

            rightContent.appendChild(tabBar);
            rightContent.appendChild(panelContainer);
        } else {
            const ip = cfg.imagePanels[0];
            const el = buildImagePanel(ip);
            panelEls[ip.pointsKey] = el;
            rightContent = el;
        }

        // ── Modal 框架 ───────────────────────────────────────────────────
        const modal = document.createElement('div');
        modal.style.cssText = 'background:#fff;border-radius:14px;width:100%;max-width:1100px;min-height:60vh;max-height:90vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.25);overflow:hidden;';

        const header = document.createElement('div');
        header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:14px 22px;border-bottom:1px solid #e5e7eb;flex-shrink:0;';
        header.innerHTML = `<div style="font-size:15px;font-weight:700;color:#111;">${cfg.title}</div>
            <button id="adj-close" style="border:none;background:none;font-size:22px;cursor:pointer;color:#9ca3af;line-height:1;">×</button>`;

        const body = document.createElement('div');
        body.style.cssText = 'display:flex;flex:1;min-height:0;overflow:hidden;';

        const leftPane = document.createElement('div');
        leftPane.style.cssText = 'width:380px;flex-shrink:0;border-right:1px solid #f0f0f0;overflow-y:auto;padding:18px 24px;';
        leftPane.innerHTML = leftHtml;

        const rightPane = document.createElement('div');
        rightPane.style.cssText = 'flex:1;min-width:0;padding:16px 20px;overflow:hidden;display:flex;flex-direction:column;';
        const rightTitle = document.createElement('div');
        rightTitle.style.cssText = 'font-size:12px;color:#6b7280;margin-bottom:10px;flex-shrink:0;';
        rightTitle.textContent = matType === 'photo'
            ? '拖动矩形框调整裁剪范围（固定 1 寸照片 5:7 比例）'
            : '可选：拖动角点调整裁剪区域（直接点「重新生成」则按左侧参数自动裁剪）';
        rightContent.style.flex = '1';
        rightContent.style.minHeight = '0';
        rightPane.appendChild(rightTitle);
        rightPane.appendChild(rightContent);

        body.appendChild(leftPane);
        body.appendChild(rightPane);

        const footer = document.createElement('div');
        footer.style.cssText = 'display:flex;gap:10px;justify-content:flex-end;align-items:center;padding:12px 22px;border-top:1px solid #e5e7eb;flex-shrink:0;background:#fafafa;';
        footer.innerHTML = `
            <button id="adj-cancel" style="padding:7px 20px;border:1px solid #CBD5E1;border-radius:7px;background:#fff;cursor:pointer;font-size:13px;color:#475569;">取消</button>
            <button id="adj-submit" style="padding:7px 22px;border:none;border-radius:7px;background:#4F46E5;color:#fff;cursor:pointer;font-size:13px;font-weight:600;">重新生成</button>`;

        modal.appendChild(header);
        modal.appendChild(body);
        modal.appendChild(footer);
        panel.appendChild(modal);
        document.body.appendChild(panel);

        // ── 实时重分析逻辑 ─────────────────────────────────────────────────

        function getGroupVal(name) {
            const el = panel.querySelector(`.adj-pill[data-group="${name}"][data-active="1"]`);
            return el ? el.dataset.value : null;
        }

        // 从当前 pill 状态构建非旋转调整参数
        function buildCurrentAdjustments() {
            const adj = {};
            const cropMode = getGroupVal('crop_mode');
            if (cropMode && cropMode !== 'auto') adj.crop_mode = cropMode;
            const expandLevel = getGroupVal('expand_level');
            if (expandLevel && expandLevel !== 'normal') adj.expand_level = expandLevel;
            if (getGroupVal('ratio_trim') === 'off') adj.skip_ratio_trim = true;
            const cannyVal = getGroupVal('canny_scale');
            if (cannyVal && parseFloat(cannyVal) !== 1.0) adj.canny_scale = parseFloat(cannyVal);
            return adj;
        }

        // 调用后端分析角点，更新未被用户手动拖动过的面板
        function reanalyzePoints(adjustments) {
            if (adjustments.crop_mode === 'none') {
                cfg.imagePanels.forEach(ip => {
                    const el = panelEls[ip.pointsKey];
                    if (el) el.clearMarkedPoints('「不裁剪」模式：将保留全图');
                });
                return;
            }
            cfg.imagePanels.forEach(ip => {
                const el = panelEls[ip.pointsKey];
                if (el && !el.getHasDragged()) el.setStatus('⏳ 计算中...', '#9ca3af');
            });
            fetch(`/api/students/${student.id}/analyze_material_points`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ material_type: matType, adjustments })
            }).then(r => r.json()).then(data => {
                if (!data || data.error) return;
                cfg.imagePanels.forEach(ip => {
                    const el = panelEls[ip.pointsKey];
                    if (!el) return;
                    if (el.getHasDragged()) return; // 用户手动拖过，不覆盖
                    const pts = data[ip.pointsKey] || data.points;
                    if (pts && pts.length === 4) {
                        el.applyServerPoints(pts);
                    } else {
                        el.setStatus('未识别到边缘，将自动处理', '#9ca3af');
                    }
                });
            }).catch(() => {
                cfg.imagePanels.forEach(ip => {
                    const el = panelEls[ip.pointsKey];
                    if (el && !el.getHasDragged()) el.setStatus('计算失败', '#ef4444');
                });
            });
        }

        // 防抖：400ms 后触发重分析
        let _reanalyzeTimer = null;
        function scheduleReanalyze() {
            clearTimeout(_reanalyzeTimer);
            _reanalyzeTimer = setTimeout(() => reanalyzePoints(buildCurrentAdjustments()), 400);
        }

        // 打开面板后立即分析一次（photo 不需要后端角点分析）
        if (matType !== 'photo') {
            reanalyzePoints({});
        }

        // ── Pill 交互（区分旋转 vs 裁剪参数）────────────────────────────────
        const rotateFieldKeySet = new Set(cfg.rotateFields.map(f => f.key));

        panel.addEventListener('click', e => {
            const pill = e.target.closest('.adj-pill');
            if (!pill) return;
            const group = pill.dataset.group;
            panel.querySelectorAll(`.adj-pill[data-group="${group}"]`).forEach(p => {
                p.style.cssText = pillOff; p.removeAttribute('data-active');
            });
            pill.style.cssText = pillOn; pill.setAttribute('data-active', '1');

            if (rotateFieldKeySet.has(group)) {
                // 旋转预览：不影响角点，实时旋转图像
                const deg = parseInt(pill.dataset.value) || 0;
                const panelKey = cfg.rotateKeyToPanel[group];
                if (panelKey && panelEls[panelKey]) panelEls[panelKey].setRotation(deg);
            } else if (group === 'crop_mode' && pill.dataset.value === 'none') {
                cfg.imagePanels.forEach(ip => {
                    const el = panelEls[ip.pointsKey];
                    if (!el) return;
                    el.clearMarkedPoints('「不裁剪」模式：将保留全图');
                });
            } else {
                // 裁剪参数变化：触发防抖重分析
                scheduleReanalyze();
            }
        });


        const close = () => panel.remove();
        panel.querySelector('#adj-close').onclick = close;
        panel.querySelector('#adj-cancel').onclick = close;
        panel.addEventListener('click', e => { if (e.target === panel) close(); });

        // ── 提交 ─────────────────────────────────────────────────────────

        panel.querySelector('#adj-submit').onclick = async () => {
            const adjustments = {};

            if (matType === 'photo') {
                // photo 专属参数
                if (getGroupVal('white_bg') === 'off') adjustments.skip_white_bg = true;
            } else {
                // 文档类材料参数
                const cropMode = getGroupVal('crop_mode');
                if (cropMode) adjustments.crop_mode = cropMode;
                const expandLevel = getGroupVal('expand_level');
                if (expandLevel && expandLevel !== 'normal') adjustments.expand_level = expandLevel;
                if (getGroupVal('ratio_trim') === 'off') adjustments.skip_ratio_trim = true;
                const cannyVal = getGroupVal('canny_scale');
                if (cannyVal && parseFloat(cannyVal) !== 1.0) adjustments.canny_scale = parseFloat(cannyVal);
            }
            cfg.rotateFields.forEach(f => {
                const val = parseInt(getGroupVal(f.key) || '0', 10);
                if (val) adjustments[f.key] = val;
            });

            // 只收集用户真正手动确认过的角点。
            const markedPoints = {};
            cfg.imagePanels.forEach(ip => {
                const s = cropState[ip.pointsKey];
                if (s && s.originalPts && s.originalPts.length === 4) {
                    markedPoints[ip.pointsKey] = s.originalPts;
                }
            });

            const submitBtn = panel.querySelector('#adj-submit');
            submitBtn.textContent = '生成中...'; submitBtn.disabled = true;

            try {
                let res;
                if (Object.keys(markedPoints).length > 0) {
                    const payload = { material_type: matType, adjustments, ...markedPoints };
                    res = await fetch(`/api/students/${student.id}/manual_crop_material`, {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        credentials: 'include', body: JSON.stringify(payload),
                    });
                } else {
                    res = await fetch(`/api/students/${student.id}/regenerate_material`, {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ material_type: matType, adjustments }),
                    });
                }
                const result = await res.json();
                const latestLog = storeMaterialLog(student, result);
                showMaterialLogModal(latestLog);
                if (reloadFn) reloadFn();
                if (!res.ok) throw new Error(result.message || result.error || '重新生成失败');
                showMessage('重新生成成功', 'success');
                panel.remove();
            } catch (e) {
                showMessage(e.message, 'error');
                submitBtn.textContent = '重新生成'; submitBtn.disabled = false;
            }
        };
    }
});
