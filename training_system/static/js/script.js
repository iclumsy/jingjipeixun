document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('students-container');
    const template = document.getElementById('student-template');
    const addBtn = document.getElementById('addStudentBtn');
    const submitBtn = document.getElementById('submitBtn');
    const form = document.getElementById('collectionForm');
    const actions = document.querySelector('.actions');

    // Load job categories configuration from backend API
    let jobCategoriesConfig = null;
    try {
        const response = await fetch('/api/config/job_categories');
        if (response.ok) {
            const config = await response.json();
            jobCategoriesConfig = config.job_categories;
            // Store config globally for updateExamProjectOptions function
            window.jobCategoriesConfig = jobCategoriesConfig;
        } else {
            console.error('Failed to load job categories config');
        }
    } catch (error) {
        console.error('Error loading job categories config:', error);
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

                // Determine training type based on job category
                const jobCategorySelect = entry.querySelector('select[name="job_category"]');
                let trainingType = 'special_operation'; // Default
                if (jobCategorySelect && window.jobCategoriesConfig) {
                    const selectedOption = jobCategorySelect.options[jobCategorySelect.selectedIndex];
                    if (selectedOption && selectedOption.dataset.trainingType) {
                        trainingType = selectedOption.dataset.trainingType;
                    } else {
                        // Try to find from config
                        const category = window.jobCategoriesConfig.find(c => c.name === jobCategorySelect.value);
                        if (category) {
                            trainingType = category.training_type;
                        }
                    }
                }
                formData.append('training_type', trainingType);

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
            showMessage(`成功提交 ${successCount} 位学员信息！`, 'success');
            addStudent(); // Reset with one empty form
        } else {
            showMessage(`提交完成。成功: ${successCount}, 失败: ${failCount}。请检查失败条目。`, failCount > 0 ? 'error' : 'success');
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
        
        // Populate job category dropdown from config
        const jobCategorySelect = entry.querySelector('select[name="job_category"]');
        if (jobCategorySelect && window.jobCategoriesConfig) {
            jobCategorySelect.innerHTML = '<option value="">请选择</option>';
            window.jobCategoriesConfig.forEach(category => {
                const option = document.createElement('option');
                option.value = category.name;
                option.textContent = category.name;
                option.dataset.trainingType = category.training_type;
                jobCategorySelect.appendChild(option);
            });
        }
    }

    window.removeStudent = function(btn) {
        if (container.children.length > 1) {
            btn.closest('.student-entry').remove();
        } else {
            showMessage('至少保留一个学员信息框。', 'error');
        }
    };

    window.previewFile = function(input) {
        const box = input.closest('.upload-box');
        const img = box.querySelector('.preview-img');
        const placeholder = box.querySelector('.upload-placeholder');
        
        if (input.files && input.files[0]) {
            const file = input.files[0];
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
            img.style.display = 'none';
            img.src = '';
            placeholder.style.display = 'block';
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
            'job_category': '请选择作业类别',
            'exam_project': '请选择操作项目',
            'exam_category': '请选择考试类别',
            'photo': '请上传个人照片（白底一寸照）',
            'diploma': '请上传学历证书',
            'id_card_front': '请上传身份证正面照片',
            'id_card_back': '请上传身份证反面照片'
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
            'job_category': '请选择作业类别',
            'exam_project': '请选择操作项目',
            'exam_category': '请选择考试类别',
            'photo': '请上传个人照片（白底一寸照）',
            'diploma': '请上传学历证书',
            'id_card_front': '请上传身份证正面照片',
            'id_card_back': '请上传身份证反面照片'
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

                // Determine training type based on job category
                const jobCategorySelect = entry.querySelector('select[name="job_category"]');
                let trainingType = 'special_operation'; // Default
                if (jobCategorySelect && window.jobCategoriesConfig) {
                    const selectedOption = jobCategorySelect.options[jobCategorySelect.selectedIndex];
                    if (selectedOption && selectedOption.dataset.trainingType) {
                        trainingType = selectedOption.dataset.trainingType;
                    } else {
                        // Try to find from config
                        const category = window.jobCategoriesConfig.find(c => c.name === jobCategorySelect.value);
                        if (category) {
                            trainingType = category.training_type;
                        }
                    }
                }
                formData.append('training_type', trainingType);

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
            showMessage(`成功提交 ${successCount} 位学员信息！`, 'success');
            addStudent(); // Reset with one empty form
        } else {
            showMessage(`提交完成。成功: ${successCount}, 失败: ${failCount}。请检查失败条目。`, failCount > 0 ? 'error' : 'success');
        }
    };
});
