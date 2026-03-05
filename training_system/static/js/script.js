/**
 * 学员信息采集表单前端脚本。
 *
 * 本文件处理学员数据采集表单的所有前端逻辑，包括：
 *
 * 1. 表单管理
 *    - 动态添加/删除学员条目（基于 HTML template 克隆）
 *    - 表单提交时逐个发送学员数据
 *
 * 2. 客户端校验
 *    - 必填字段检查（姓名、性别、身份证号、手机号等）
 *    - 格式检查（身份证号 18 位、手机号 11 位）
 *    - 附件文件格式和大小校验
 *    - 实时字段校验（失焦和输入时触发）
 *
 * 3. 文件上传
 *    - 图片预览（上传后展示缩略图）
 *    - 个人照片自动裁剪为一寸证件照比例（2.5cm×3.5cm）
 *
 * 4. 提交流程
 *    - 校验所有表单 -> 验证码校验 -> 逐个提交 -> 显示结果模态框
 *    - 提交成功的条目自动移除，失败的高亮显示
 *
 * 5. 培训类型推断
 *    - 根据作业类别自动推断培训类型（特种作业/特种设备）
 */
document.addEventListener('DOMContentLoaded', async () => {
    // ======================== DOM 元素引用 ========================
    const container = document.getElementById('students-container');  // 学员条目容器
    const template = document.getElementById('student-template');      // 学员条目 HTML 模板
    const addBtn = document.getElementById('addStudentBtn');           // 添加学员按钮
    const submitBtn = document.getElementById('submitBtn');            // 提交所有按钮
    const form = document.getElementById('collectionForm');            // 表单元素
    const actions = document.querySelector('.actions');                // 操作按钮区域

    /**
     * 显示结果模态框（提交成功/失败后的提示）。
     *
     * @param {string} message - 显示的消息内容
     * @param {string} type - 模态框类型：'success' 或 'error'
     */
    function showModal(message, type = 'success') {
        const existingModal = document.querySelector('.result-modal');
        if (existingModal) {
            existingModal.remove();
        }

        const modalOverlay = document.createElement('div');
        modalOverlay.className = 'result-modal';
        modalOverlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
        `;

        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
            background: white;
            padding: 30px 40px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            max-width: 400px;
            animation: modalIn 0.3s ease;
        `;

        const icon = document.createElement('div');
        icon.style.cssText = `
            font-size: 48px;
            margin-bottom: 15px;
        `;
        icon.textContent = type === 'success' ? '✓' : '✗';

        const title = document.createElement('div');
        title.style.cssText = `
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 10px;
            color: ${type === 'success' ? '#166534' : '#991b1b'};
        `;
        title.textContent = type === 'success' ? '提交成功' : '提交失败';

        const messageEl = document.createElement('div');
        messageEl.style.cssText = `
            color: #666;
            margin-bottom: 20px;
            line-height: 1.5;
        `;
        messageEl.textContent = message;

        const closeBtn = document.createElement('button');
        closeBtn.textContent = '确定';
        closeBtn.style.cssText = `
            padding: 10px 40px;
            background: ${type === 'success' ? '#10B981' : '#EF4444'};
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 1rem;
            cursor: pointer;
            transition: transform 0.2s;
        `;
        closeBtn.onmouseover = () => closeBtn.style.transform = 'scale(1.05)';
        closeBtn.onmouseout = () => closeBtn.style.transform = 'scale(1)';
        closeBtn.onclick = () => modalOverlay.remove();

        modalContent.appendChild(icon);
        modalContent.appendChild(title);
        modalContent.appendChild(messageEl);
        modalContent.appendChild(closeBtn);
        modalOverlay.appendChild(modalContent);
        document.body.appendChild(modalOverlay);

        modalOverlay.onclick = (e) => {
            if (e.target === modalOverlay) {
                modalOverlay.remove();
            }
        };
    }

    // ======================== 附件上传配置 ========================
    // 客户端文件校验规则（与服务端 validators.py 保持一致）
    const ATTACHMENT_RULES = {
        maxSizeMb: 10,                                    // 单文件最大 10MB
        allowedExtensions: ['jpg', 'jpeg', 'png'],        // 允许的文件扩展名
        allowedMimeTypes: ['image/jpeg', 'image/png']     // 允许的 MIME 类型
    };

    /**
     * 根据作业类别名称查找对应的培训类型。
     *
     * 遍历配置数据中的所有培训类型，查找包含该作业类别的培训类型。
     * 配置数据来自 /api/config/job_categories 接口。
     *
     * @param {string} categoryName - 作业类别名称
     * @returns {string} 培训类型（'special_operation' 或 'special_equipment'）
     */
    function findTrainingTypeByCategory(categoryName) {
        if (!categoryName || !window.jobCategoriesConfigRaw) {
            return '';
        }
        let found = '';
        Object.keys(window.jobCategoriesConfigRaw).forEach(trainingType => {
            const categories = window.jobCategoriesConfigRaw?.[trainingType]?.job_categories || [];
            if (categories.some(category => category.name === categoryName)) {
                found = trainingType;
            }
        });
        return found;
    }

    /**
     * 解析当前学员条目的培训类型。
     *
     * 优先级：
     * 1. 作业类别下拉框的 data-training-type 属性
     * 2. 根据作业类别名称从配置数据推断
     * 3. 默认回退到 'special_operation'
     *
     * @param {HTMLElement} entry - 学员条目 DOM 元素
     * @returns {string} 培训类型
     */
    function resolveTrainingType(entry) {
        const jobCategorySelect = entry.querySelector('select[name="job_category"]');
        if (jobCategorySelect) {
            const selectedOption = jobCategorySelect.options[jobCategorySelect.selectedIndex];
            if (selectedOption && selectedOption.dataset.trainingType) {
                return selectedOption.dataset.trainingType;
            }
            const inferredType = findTrainingTypeByCategory(jobCategorySelect.value);
            if (inferredType) {
                return inferredType;
            }
        }

        return 'special_operation';
    }

    /**
     * 重置上传框的预览状态（隐藏缩略图，显示占位符）。
     *
     * @param {HTMLElement} box - 上传框 DOM 元素
     */
    function resetUploadPreview(box) {
        const img = box.querySelector('.preview-img');
        const placeholder = box.querySelector('.upload-placeholder');
        if (img) {
            img.style.display = 'none';
            img.src = '';
        }
        if (placeholder) {
            placeholder.style.display = 'block';
        }
    }

    /**
     * 校验上传的附件文件（扩展名、MIME类型、文件大小）。
     *
     * @param {HTMLInputElement} input - 文件输入框
     * @param {File} file - 用户选择的文件对象
     * @returns {{valid: boolean, error?: string}} 校验结果
     */
    function validateAttachmentFile(input, file) {
        const ext = (file.name.split('.').pop() || '').toLowerCase();
        const maxSizeMb = Number(input.dataset.maxSizeMb || ATTACHMENT_RULES.maxSizeMb);
        const maxSize = maxSizeMb * 1024 * 1024;
        const allowedExt = ATTACHMENT_RULES.allowedExtensions;
        const allowedMime = ATTACHMENT_RULES.allowedMimeTypes;
        const labelText = input.closest('.upload-box')?.querySelector('.upload-placeholder .text')?.textContent || input.name;

        if (!allowedExt.includes(ext)) {
            return {
                valid: false,
                error: `${labelText}仅支持 JPG/PNG 格式`
            };
        }

        if (file.type && !allowedMime.includes(file.type)) {
            return {
                valid: false,
                error: `${labelText}格式无效，请上传 JPG/PNG 图片`
            };
        }

        if (file.size > maxSize) {
            return {
                valid: false,
                error: `${labelText}大小不能超过 ${maxSizeMb}MB`
            };
        }

        return { valid: true };
    }

    // ======================== 初始化 ========================
    // 页面加载时自动添加一个空白的学员表单
    addStudent();

    addBtn.addEventListener('click', addStudent);  // “添加学员”按钮点击事件

    // ======================== 提交逻辑 ========================
    /**
     * 点击“提交所有信息”按钮的处理流程：
     * 1. 校验所有学员表单
     * 2. 校验验证码（如已启用）
     * 3. 逐个提交学员数据（Multipart 表单）
     * 4. 显示提交结果模态框
     */
    submitBtn.addEventListener('click', async (e) => {
        e.preventDefault();

        const entries = document.querySelectorAll('.student-entry');
        let allValid = true;
        let oldStatus = document.getElementById('submit-status');
        if (oldStatus) oldStatus.remove();

        // 先校验所有表单
        entries.forEach(entry => {
            const res = validateEntry(entry);
            if (!res.valid) {
                allValid = false;
            }
        });

        if (!allValid) {
            const firstError = document.querySelector('.student-entry .error');
            if (firstError) {
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                firstError.focus();
            }
            return;
        }

        // 验证码校验
        if (typeof window.verifyCaptcha === 'function' && !window.verifyCaptcha()) {
            return;
        }

        // 逐个提交
        let successCount = 0;
        let failCount = 0;
        submitBtn.disabled = true;
        submitBtn.textContent = '正在提交...';

        for (const entry of entries) {
            try {
                const formData = new FormData();
                const inputs = entry.querySelectorAll('input, select');

                inputs.forEach(input => {
                    if (input.type === 'file') {
                        if (input.files[0]) {
                            formData.append(input.name, input.files[0]);
                        }
                    } else {
                        formData.append(input.name, input.value);
                    }
                });

                const trainingType = resolveTrainingType(entry);
                formData.set('training_type', trainingType);

                const response = await fetch('/api/students', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    successCount++;
                    entry.remove(); // 移除提交成功的条目
                } else {
                    failCount++;
                    const data = await response.json();
                    console.error('Submission failed:', data);
                    // 高亮条目或显示错误
                    entry.style.border = '2px solid red';
                }
            } catch (err) {
                console.error(err);
                failCount++;
            }
        }

        submitBtn.disabled = false;
        submitBtn.textContent = '提交所有信息';

        // 提交后重新生成验证码
        if (typeof window.refreshCaptcha === 'function') window.refreshCaptcha();

        if (container.children.length === 0) {
            showModal(`成功提交 ${successCount} 位学员信息！`, 'success');
            addStudent(); // 重置为一个空表单
        } else {
            showModal(`提交完成。成功: ${successCount}, 失败: ${failCount}。请检查失败条目。`, failCount > 0 ? 'error' : 'success');
        }
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        submitBtn.click();
    });

    /**
     * 添加一个新的学员表单条目。
     * 通过克隆 HTML template 元素创建，并绑定字段校验事件。
     */
    function addStudent() {
        const clone = template.content.cloneNode(true);
        container.appendChild(clone);
        const entry = container.lastElementChild;
        attachEntryValidation(entry);

        if (typeof window.initializeStudentEntry === 'function') {
            window.initializeStudentEntry(entry, false);
        }
    }

    /**
     * 删除一个学员条目（至少保留一个）。
     * 暴露为全局函数供 HTML onclick 调用。
     *
     * @param {HTMLElement} btn - 触发删除的按钮元素
     */
    window.removeStudent = function (btn) {
        if (container.children.length > 1) {
            btn.closest('.student-entry').remove();
        } else {
            showModal('至少保留一个学员信息框。', 'error');
        }
    };

    /**
     * 附件文件选择后的预览处理。
     * 暴露为全局函数供 HTML onchange 调用。
     *
     * 处理流程：
     * 1. 校验文件格式和大小
     * 2. 如果是个人照片，自动裁剪为一寸证件照比例 (2.5cm×3.5cm)
     * 3. 显示预览缩略图
     *
     * @param {HTMLInputElement} input - 文件输入框
     */
    window.previewFile = function (input) {
        const box = input.closest('.upload-box');
        const img = box.querySelector('.preview-img');
        const placeholder = box.querySelector('.upload-placeholder');

        if (input.files && input.files[0]) {
            const file = input.files[0];
            const validation = validateAttachmentFile(input, file);
            if (!validation.valid) {
                input.value = '';
                resetUploadPreview(box);
                showFieldError(input, validation.error);
                return;
            }

            // 如果是个人照片字段，在客户端裁剪为一寸证件照比例
            // 目标尺寸：2.5cm × 3.5cm，300 DPI
            if (input.name === 'photo') {
                const imgEl = new Image();
                const reader = new FileReader();
                reader.onload = function (ev) {
                    imgEl.onload = function () {
                        try {
                            // 目标物理尺寸: 2.5cm x 3.5cm -> 英寸
                            const tgtWIn = 2.5 / 2.54;
                            const tgtHIn = 3.5 / 2.54;
                            const dpi = 300;
                            const pxW = Math.max(120, Math.round(tgtWIn * dpi));
                            const pxH = Math.max(160, Math.round(tgtHIn * dpi));

                            const srcW = imgEl.naturalWidth;
                            const srcH = imgEl.naturalHeight;
                            const canvas = document.createElement('canvas');
                            canvas.width = pxW;
                            canvas.height = pxH;
                            const ctx = canvas.getContext('2d');
                            ctx.fillStyle = '#FFFFFF';
                            ctx.fillRect(0, 0, pxW, pxH);
                            // 等比缩放并居中（“包含”模式），避免裁剪人脸
                            const scale = Math.min(pxW / srcW, pxH / srcH);
                            const newW = Math.max(1, Math.round(srcW * scale));
                            const newH = Math.max(1, Math.round(srcH * scale));
                            const dx = Math.round((pxW - newW) / 2);
                            const dy = Math.round((pxH - newH) / 2);
                            ctx.drawImage(imgEl, 0, 0, srcW, srcH, dx, dy, newW, newH);

                            // 将 Canvas 转换为 Blob，替换原始文件
                            canvas.toBlob(function (blob) {
                                if (!blob) {
                                    img.src = ev.target.result;
                                    img.style.display = 'block';
                                    placeholder.style.display = 'none';
                                    return;
                                }
                                const newFile = new File([blob], file.name.replace(/\.[^/.]+$/, '') + '_1inch.jpg', { type: 'image/jpeg' });
                                try {
                                    const dt = new DataTransfer();
                                    dt.items.add(newFile);
                                    input.files = dt.files;
                                } catch (e) {
                                    console.warn('Could not replace FileList programmatically:', e);
                                }
                                try {
                                    img.src = URL.createObjectURL(newFile);
                                } catch (e) {
                                    const r2 = new FileReader();
                                    r2.onload = function (ev2) { img.src = ev2.target.result; };
                                    r2.readAsDataURL(newFile);
                                }
                                img.style.display = 'block';
                                placeholder.style.display = 'none';
                            }, 'image/jpeg', 0.95);
                        } catch (err) {
                            console.error('Photo processing failed:', err);
                            img.src = ev.target.result;
                            img.style.display = 'block';
                            placeholder.style.display = 'none';
                        }
                    };
                    imgEl.src = ev.target.result;
                };
                reader.readAsDataURL(file);
            } else {
                const reader = new FileReader();
                reader.onload = function (e) {
                    img.src = e.target.result;
                    img.style.display = 'block';
                    placeholder.style.display = 'none';
                }
                reader.readAsDataURL(file);
            }
        } else {
            resetUploadPreview(box);
        }
    };

    /**
     * 校验单个学员条目的所有字段。
     *
     * 使用 HTML5 原生的 checkValidity() API 进行校验，
     * 并根据字段名称显示自定义的中文错误提示。
     *
     * @param {HTMLElement} entry - 学员条目 DOM 元素
     * @returns {{valid: boolean, errors: Array}} 校验结果
     */
    function validateEntry(entry) {
        let isValid = true;
        const errors = [];
        const inputs = entry.querySelectorAll('input, select');

        // 字段名 -> 自定义错误消息映射
        // 支持字符串（统一提示）和对象（按错误类型区分提示）两种格式
        const errorMessages = {
            'name': '请输入姓名',
            'gender': '请选择性别',
            'education': '请选择文化程度',
            'id_card': {
                'valueMissing': '请输入身份证号',
                'patternMismatch': '身份证号应为18位，最后一位可以是X'
            },
            'phone': {
                'valueMissing': '请输入手机号',
                'patternMismatch': '手机号应为11位数字'
            },
            'company': '请输入单位名称',
            'company_address': '请输入单位地址',
            'job_category': '请选择作业类别',
            'exam_project': '请选择操作项目',
            'photo': '请上传个人照片（白底一寸照）',
            'diploma': '请上传学历证书',
            'id_card_front': '请上传身份证正面照片',
            'id_card_back': '请上传身份证反面照片',
            'hukou_residence': '请上传户口本户籍页照片',
            'hukou_personal': '请上传户口本个人页照片'
        };

        function getErrorMessage(input) {
            const name = input.name;
            const customMsg = errorMessages[name];

            if (typeof customMsg === 'object') {
                if (input.validity.valueMissing) {
                    return customMsg.valueMissing || '请填写此字段';
                }
                if (input.validity.patternMismatch) {
                    return customMsg.patternMismatch || '格式不正确';
                }
            }

            if (typeof customMsg === 'string') {
                return customMsg;
            }

            return input.title || input.validationMessage || '请填写此字段';
        }

        inputs.forEach(input => {
            clearFieldError(input);

            if (!input.checkValidity()) {
                showFieldError(input, getErrorMessage(input));
                isValid = false;

                const parent = input.closest('.form-group') || input.parentElement;
                const labelEl = parent.querySelector('label');
                const labelText = labelEl ? labelEl.textContent.trim() : input.name;
                errors.push({
                    input,
                    label: labelText,
                    message: getErrorMessage(input)
                });
            }
        });

        return { valid: isValid, errors };
    }

    /**
     * 显示字段级别的错误提示气泡。
     *
     * 在字段下方显示红色错误消息，2 秒后自动淡出。
     * 同时为字段和上传框添加错误样式类。
     *
     * @param {HTMLInputElement} input - 错误字段
     * @param {string} message - 错误消息
     */
    function showFieldError(input, message) {
        input.classList.add('error');
        const parent = input.closest('.form-group') || input.parentElement;
        parent.classList.add('has-error');

        if (input.type === 'file') {
            const box = input.closest('.upload-box');
            if (box) {
                box.classList.add('has-error');
            }
        }

        let pop = parent.querySelector('.error-pop');
        if (!pop) {
            pop = document.createElement('span');
            pop.className = 'error-pop';
            parent.appendChild(pop);
        }
        pop.textContent = message;
        pop.classList.remove('hiding');

        if (pop._autoHideTimer) {
            clearTimeout(pop._autoHideTimer);
        }
        pop._autoHideTimer = setTimeout(() => {
            if (pop.parentNode && !pop.classList.contains('hiding')) {
                pop.classList.add('hiding');
                setTimeout(() => {
                    if (pop.classList.contains('hiding') && pop.parentNode) {
                        pop.remove();
                    }
                }, 200);
            }
        }, 2000);
    }

    /**
     * 清除字段的错误状态和提示气泡。
     *
     * @param {HTMLInputElement} input - 目标字段
     */
    function clearFieldError(input) {
        input.classList.remove('error');
        const parent = input.closest('.form-group') || input.parentElement;
        parent.classList.remove('has-error');

        if (input.type === 'file') {
            const box = input.closest('.upload-box');
            if (box) {
                box.classList.remove('has-error');
            }
        }

        const pop = parent.querySelector('.error-pop');
        if (pop) {
            pop.classList.add('hiding');
            setTimeout(() => {
                if (pop.classList.contains('hiding')) {
                    pop.remove();
                }
            }, 200);
        }
    }

    /**
     * 为学员条目的所有字段绑定实时校验事件。
     *
     * 监听 input/blur/change 事件，使用 150ms 防抖动避免频繁触发。
     *
     * @param {HTMLElement} entry - 学员条目 DOM 元素
     */
    function attachEntryValidation(entry) {
        const inputs = entry.querySelectorAll('input, select');

        const errorMessages = {
            'name': '请输入姓名',
            'gender': '请选择性别',
            'education': '请选择文化程度',
            'id_card': {
                'valueMissing': '请输入身份证号',
                'patternMismatch': '身份证号应为18位，最后一位可以是X'
            },
            'phone': {
                'valueMissing': '请输入手机号',
                'patternMismatch': '手机号应为11位数字'
            },
            'company': '请输入单位名称',
            'company_address': '请输入单位地址',
            'job_category': '请选择作业类别',
            'exam_project': '请选择操作项目',
            'photo': '请上传个人照片（白底一寸照）',
            'diploma': '请上传学历证书',
            'id_card_front': '请上传身份证正面照片',
            'id_card_back': '请上传身份证反面照片',
            'hukou_residence': '请上传户口本户籍页照片',
            'hukou_personal': '请上传户口本个人页照片'
        };

        function getErrorMessage(input) {
            const name = input.name;
            const customMsg = errorMessages[name];

            if (typeof customMsg === 'object') {
                if (input.validity.valueMissing) {
                    return customMsg.valueMissing || '请填写此字段';
                }
                if (input.validity.patternMismatch) {
                    return customMsg.patternMismatch || '格式不正确';
                }
            }

            if (typeof customMsg === 'string') {
                return customMsg;
            }

            return input.title || input.validationMessage || '请填写此字段';
        }

        inputs.forEach(input => {
            let debounceTimer;

            const validateField = () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    if (!input.checkValidity()) {
                        showFieldError(input, getErrorMessage(input));
                    } else {
                        clearFieldError(input);
                    }
                }, 150);
            };

            input.addEventListener('input', validateField);
            input.addEventListener('blur', validateField);
            input.addEventListener('change', validateField);
        });
    }

    /**
     * 指定培训类型提交所有学员表单（可覆盖自动推断的类型）。
     * 暴露为全局函数，供外部按钮调用。
     *
     * @param {string} trainingType - 培训类型（'special_operation' 或 'special_equipment'）
     */
    window.submitFormWithTrainingType = async function (trainingType) {
        const entries = document.querySelectorAll('.student-entry');
        let allValid = true;
        let oldStatus = document.getElementById('submit-status');
        if (oldStatus) oldStatus.remove();

        // 先校验所有表单
        entries.forEach(entry => {
            const res = validateEntry(entry);
            if (!res.valid) {
                allValid = false;
            }
        });

        if (!allValid) {
            const firstError = document.querySelector('.student-entry .error');
            if (firstError) {
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                firstError.focus();
            }
            return;
        }

        // 验证码校验
        if (typeof window.verifyCaptcha === 'function' && !window.verifyCaptcha()) {
            return;
        }

        // 逐个提交
        let successCount = 0;
        let failCount = 0;
        submitBtn.disabled = true;
        submitBtn.textContent = '正在提交...';

        for (const entry of entries) {
            try {
                const formData = new FormData();
                const inputs = entry.querySelectorAll('input, select');

                inputs.forEach(input => {
                    if (input.type === 'file') {
                        if (input.files[0]) {
                            formData.append(input.name, input.files[0]);
                        }
                    } else {
                        formData.append(input.name, input.value);
                    }
                });

                const resolvedTrainingType = resolveTrainingType(entry);
                const targetTrainingType = trainingType || resolvedTrainingType;
                formData.set('training_type', targetTrainingType);

                const response = await fetch('/api/students', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    successCount++;
                    entry.remove(); // 移除提交成功的条目
                } else {
                    failCount++;
                    const data = await response.json();
                    console.error('Submission failed:', data);
                    // 高亮条目或显示错误
                    entry.style.border = '2px solid red';
                }
            } catch (err) {
                console.error(err);
                failCount++;
            }
        }

        submitBtn.disabled = false;
        submitBtn.textContent = '提交所有信息';

        // 提交后重新生成验证码
        if (typeof window.refreshCaptcha === 'function') window.refreshCaptcha();

        if (container.children.length === 0) {
            showModal(`成功提交 ${successCount} 位学员信息！`, 'success');
            addStudent(); // 重置为一个空表单
        } else {
            showModal(`提交完成。成功: ${successCount}, 失败: ${failCount}。请检查失败条目。`, failCount > 0 ? 'error' : 'success');
        }
    };
});
