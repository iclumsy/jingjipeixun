document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('students-container');
    const template = document.getElementById('student-template');
    const addBtn = document.getElementById('addStudentBtn');
    const submitBtn = document.getElementById('submitBtn');
    const form = document.getElementById('collectionForm');
    const actions = document.querySelector('.actions');

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

    const ATTACHMENT_RULES = {
        maxSizeMb: 10,
        allowedExtensions: ['jpg', 'jpeg', 'png'],
        allowedMimeTypes: ['image/jpeg', 'image/png']
    };

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

    // Add initial student
    addStudent();

    addBtn.addEventListener('click', addStudent);

    submitBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        
        const entries = document.querySelectorAll('.student-entry');
        let allValid = true;
        let oldStatus = document.getElementById('submit-status');
        if (oldStatus) oldStatus.remove();
        
        // Validate all first
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

        // Submit one by one
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
                    entry.remove(); // Remove successful entries
                } else {
                    failCount++;
                    const data = await response.json();
                    console.error('Submission failed:', data);
                    // Highlight entry or show error
                    entry.style.border = '2px solid red';
                }
            } catch (err) {
                console.error(err);
                failCount++;
            }
        }

        submitBtn.disabled = false;
        submitBtn.textContent = '提交所有信息';

        if (container.children.length === 0) {
            showModal(`成功提交 ${successCount} 位学员信息！`, 'success');
            addStudent(); // Reset with one empty form
        } else {
            showModal(`提交完成。成功: ${successCount}, 失败: ${failCount}。请检查失败条目。`, failCount > 0 ? 'error' : 'success');
        }
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        submitBtn.click();
    });

    function addStudent() {
        const clone = template.content.cloneNode(true);
        container.appendChild(clone);
        const entry = container.lastElementChild;
        attachEntryValidation(entry);

        if (typeof window.initializeStudentEntry === 'function') {
            window.initializeStudentEntry(entry, false);
        }
    }

    window.removeStudent = function(btn) {
        if (container.children.length > 1) {
            btn.closest('.student-entry').remove();
        } else {
            showModal('至少保留一个学员信息框。', 'error');
        }
    };

    window.previewFile = function(input) {
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

            // If this is the personal photo field, crop to one-inch ratio client-side
            if (input.name === 'photo') {
                const imgEl = new Image();
                const reader = new FileReader();
                reader.onload = function(ev) {
                    imgEl.onload = function() {
                        try {
                            // Target physical size: 2.5cm x 3.5cm -> inches
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
                            // Scale to fit (contain) and center, avoid cropping face
                            const scale = Math.min(pxW / srcW, pxH / srcH);
                            const newW = Math.max(1, Math.round(srcW * scale));
                            const newH = Math.max(1, Math.round(srcH * scale));
                            const dx = Math.round((pxW - newW) / 2);
                            const dy = Math.round((pxH - newH) / 2);
                            ctx.drawImage(imgEl, 0, 0, srcW, srcH, dx, dy, newW, newH);

                            canvas.toBlob(function(blob) {
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
                                    r2.onload = function(ev2) { img.src = ev2.target.result; };
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
                reader.onload = function(e) {
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

    function validateEntry(entry) {
        let isValid = true;
        const errors = [];
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

    // Submit form with specific training type
    window.submitFormWithTrainingType = async function(trainingType) {
        const entries = document.querySelectorAll('.student-entry');
        let allValid = true;
        let oldStatus = document.getElementById('submit-status');
        if (oldStatus) oldStatus.remove();
        
        // Validate all first
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

        // Submit one by one
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
                    entry.remove(); // Remove successful entries
                } else {
                    failCount++;
                    const data = await response.json();
                    console.error('Submission failed:', data);
                    // Highlight entry or show error
                    entry.style.border = '2px solid red';
                }
            } catch (err) {
                console.error(err);
                failCount++;
            }
        }

        submitBtn.disabled = false;
        submitBtn.textContent = '提交所有信息';

        if (container.children.length === 0) {
            showModal(`成功提交 ${successCount} 位学员信息！`, 'success');
            addStudent(); // Reset with one empty form
        } else {
            showModal(`提交完成。成功: ${successCount}, 失败: ${failCount}。请检查失败条目。`, failCount > 0 ? 'error' : 'success');
        }
    };
});
