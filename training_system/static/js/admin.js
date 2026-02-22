document.addEventListener('DOMContentLoaded', () => {
    let currentStatus = 'unreviewed';
    let currentStudentId = null;
    let currentTrainingType = 'special_equipment';
    let students = [];
    let jobCategoriesConfig = null;

    const listContainer = document.getElementById('studentList');
    const mainContent = document.getElementById('mainContent');
    const searchInput = document.getElementById('searchInput');
    const detailTemplate = document.getElementById('detail-template');
    
    let currentFilters = {
        company: ''
    };
    
    if (window.trainingType) {
        currentTrainingType = window.trainingType;
    } else {
        const urlParams = new URLSearchParams(window.location.search);
        const urlTrainingType = urlParams.get('training_type');
        if (urlTrainingType) {
            currentTrainingType = urlTrainingType;
        }
    }
    
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

    const ATTACHMENT_RULES = {
        maxSizeMb: 10,
        allowedExtensions: ['jpg', 'jpeg', 'png'],
        allowedMimeTypes: ['image/jpeg', 'image/png']
    };

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

    function getAttachmentConfig(trainingType) {
        return ATTACHMENT_CONFIG[trainingType] || ATTACHMENT_CONFIG.special_operation;
    }

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
    });
    
    async function loadCompanies(status = currentStatus) {
        const companyFilter = document.getElementById('companyFilter');
        if (!companyFilter) return;
        
        try {
            const queryParams = new URLSearchParams({
                status: status,
                training_type: currentTrainingType
            });
            
            const res = await fetch(`/api/students?${queryParams.toString()}`);
            if (!res.ok) {
                throw new Error(`网络错误: ${res.status}`);
            }
            const filteredStudents = await res.json();
            
            const companiesWithData = [...new Set(filteredStudents.map(student => student.company).filter(Boolean))];
            
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
        if (btnUnreviewed && btnReviewed) {
            if (currentStatus === 'unreviewed') {
                btnUnreviewed.style.background = '#4f46e5';
                btnUnreviewed.style.color = '#fff';
                btnUnreviewed.style.borderColor = '#4f46e5';
                btnReviewed.style.background = '#fff';
                btnReviewed.style.color = '#333';
                btnReviewed.style.borderColor = '#ddd';
            } else {
                btnReviewed.style.background = '#4f46e5';
                btnReviewed.style.color = '#fff';
                btnReviewed.style.borderColor = '#4f46e5';
                btnUnreviewed.style.background = '#fff';
                btnUnreviewed.style.color = '#333';
                btnUnreviewed.style.borderColor = '#ddd';
            }
        }
    }
    updateStatusButtons();
    
    const btnUnreviewed = document.getElementById('btnUnreviewed');
    const btnReviewed = document.getElementById('btnReviewed');
    
    if (btnUnreviewed) {
        btnUnreviewed.addEventListener('click', () => {
            currentStatus = 'unreviewed';
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
    
    if (btnReviewed) {
        btnReviewed.addEventListener('click', () => {
            currentStatus = 'reviewed';
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

    async function loadStudents() {
        listContainer.innerHTML = '<div style="padding:20px;text-align:center;">加载中...</div>';
        try {
            const queryParams = new URLSearchParams({
                status: currentStatus,
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
            listContainer.innerHTML = `<div style="padding:20px;text-align:center;color:red">加载失败: ${err.message}</div>`;
        }
    }

    function renderList(list) {
        listContainer.innerHTML = '';
        if (!list || list.length === 0) {
            listContainer.innerHTML = `<div style="padding:20px;text-align:center;color:#999">暂无数据 (${currentStatus === 'unreviewed' ? '未审核' : '已审核'})</div>`;
            return;
        }

        list.forEach(student => {
            const el = document.createElement('div');
            el.className = `list-item ${currentStudentId === student.id ? 'active' : ''}`;
            el.innerHTML = `
                <div style="flex: 1;">
                    <h4 style="font-size: 1rem; font-weight: 600; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: baseline;">
                        <span>${student.name}</span>
                        <span style="font-size: 0.8rem; color: #666; margin-left: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px;">${student.company || ''}</span>
                    </h4>
                    <div style="font-size: 0.75rem; color: #666; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                        <span style="flex: 1; min-width: 100px;">${student.job_category}</span>
                        <span>ID: ${student.id_card.slice(-4)}</span>
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

    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    const autoSave = debounce(async (studentId) => {
        if (!studentId) return;
        
        showSaveStatus('保存中...', 'info');
        
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
            
            const res = await fetch(`/api/students/${studentId}`, { method: 'PUT', body: formData });
            
            if (!res.ok) {
                throw new Error('保存失败');
            }
            
            const updated = await res.json();
            
            showSaveStatus('保存成功', 'success');
            
            const idx = students.findIndex(s => s.id === studentId);
            if (idx >= 0) {
                const previousTrainingType = students[idx].training_type;
                students[idx] = updated;
                if (currentStudentId === studentId && previousTrainingType !== updated.training_type) {
                    showDetail(updated);
                }
            }
            
        } catch (e) {
            console.error('Auto-save error:', e);
            showSaveStatus('保存失败', 'error');
        }
    }, 1000);
    
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

    function showMessage(message, type = 'info') {
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
        }, 4000);
    }

    function showDetail(student) {
        currentStudentId = student.id;
        document.querySelectorAll('.list-item').forEach(el => el.classList.remove('active'));
        renderList(students);

        const clone = detailTemplate.content.cloneNode(true);
        
        clone.querySelector('.student-name').textContent = student.name;
        clone.querySelector('.student-id').textContent = student.id_card;
        const statusBadge = clone.querySelector('.status-badge');
        if (statusBadge) {
            const reviewed = student.status === 'reviewed';
            statusBadge.innerHTML = `<span class="badge ${reviewed ? 'reviewed' : 'unreviewed'}">${reviewed ? '已审核' : '未审核'}</span>`;
        }
        
        const grid = clone.querySelector('.detail-grid');
        
        const editable = [
            { key: 'name', label: '姓名', required: true },
            { key: 'gender', label: '性别', required: true, pattern: '男|女', title: '请输入"男"或"女"' },
            { key: 'education', label: '文化程度', required: true, type: 'select', options: [
                { value: '', text: '请选择' },
                { value: '研究生及以上', text: '研究生及以上' },
                { value: '本科或同等学历', text: '本科或同等学历' },
                { value: '专科或同等学历', text: '专科或同等学历' },
                { value: '中专或同等学历', text: '中专或同等学历' },
                { value: '高中或同等学历', text: '高中或同等学历' },
                { value: '初中', text: '初中' }
            ]},
            { key: 'id_card', label: '身份证号', required: true, pattern: '\\d{17}[\\dXx]', title: '请输入正确的18位身份证号' },
            { key: 'phone', label: '手机号', required: true, pattern: '\\d{11}', title: '请输入11位手机号' },
            { key: 'school', label: '毕业院校' },
            { key: 'major', label: '所学专业' },
            { key: 'company', label: '单位名称' },
            { key: 'company_address', label: '单位地址' },
            { key: 'job_category', label: '作业类别', required: true, type: 'select', options: [] },
            { key: 'exam_project', label: '操作项目', required: true, type: 'select', options: [] },
            { key: 'project_code', label: '项目代号', readonly: true }
        ];
        
        const originalData = {...student};
        
        editable.forEach(f => {
            const item = document.createElement('div');
            item.className = 'detail-item';
            const val = student[f.key] || '';
            
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
                    
                    input.addEventListener('change', function() {
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
            input.style.padding = '8px';
            input.style.border = '1px solid #ddd';
            input.style.borderRadius = '4px';
            
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
                    input.addEventListener('change', () => {
                        showError();
                        if (input.checkValidity()) {
                            autoSave(student.id);
                        }
                    });
                } else {
                    input.addEventListener('blur', () => {
                        showError();
                        if (input.checkValidity()) {
                            autoSave(student.id);
                        }
                    });
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
                        if (originalValue && project.name === originalValue) {
                            option.selected = true;
                            if (projectCodeInput) projectCodeInput.value = project.code || '';
                        }
                        projectSelect.appendChild(option);
                    });
                }
            }
            
            projectSelect.onchange = function() {
                const selectedProjectOption = this.options[this.selectedIndex];
                if (projectCodeInput && selectedProjectOption && selectedProjectOption.dataset.code) {
                    projectCodeInput.value = selectedProjectOption.dataset.code;
                } else if (projectCodeInput) {
                    projectCodeInput.value = '';
                }
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
                    uploadBox.querySelector('input').click();
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
                img.src = '/' + existingPath;
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

                    const reader = new FileReader();
                    reader.onload = function(ev) {
                        img.src = ev.target.result;
                        img.style.display = 'block';
                        placeholder.style.display = 'none';
                        
                        uploadFile(student.id, attachment.fieldName, file, attachment.dbKey);
                    };
                    reader.readAsDataURL(file);
                }
            });

            const viewBtn = document.createElement('button');
            viewBtn.textContent = '查看';
            viewBtn.style.marginTop = '5px';
            viewBtn.style.fontSize = '12px';
            viewBtn.style.padding = '2px 8px';
            viewBtn.style.border = '1px solid #ddd';
            viewBtn.style.borderRadius = '4px';
            viewBtn.style.background = '#fff';
            viewBtn.style.cursor = 'pointer';
            viewBtn.style.display = existingPath ? 'block' : 'none';
            viewBtn.onclick = () => {
                const latest = students.find(s => s.id === student.id) || student;
                const latestPath = latest[attachment.dbKey];
                if (latestPath) {
                    window.open('/' + latestPath, '_blank');
                }
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
            uploadBox.appendChild(input);
            wrapper.appendChild(uploadBox);
            wrapper.appendChild(caption);
            wrapper.appendChild(viewBtn);
            filesContainer.appendChild(wrapper);
        });
        
        if (student.status === 'reviewed' && student.training_form_path) {
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
                window.open('/' + student.training_form_path, '_blank');
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
                link.href = '/' + student.training_form_path;
                link.download = `${student.id_card}-${student.name}-体检表.docx`;
                link.click();
            };
            
            healthCheckWrapper.appendChild(healthCheckBox);
            healthCheckWrapper.appendChild(downloadBtn);
            filesContainer.appendChild(healthCheckWrapper);
        }
        
        const actionBar = clone.querySelector('.action-bar');
        if (actionBar) {
            if (student.status === 'unreviewed') {
                const rejectBtn = document.createElement('button');
                rejectBtn.className = 'btn';
                rejectBtn.style.cssText = 'background: #FEE2E2; color: #EF4444;';
                rejectBtn.textContent = '审核不通过';
                rejectBtn.onclick = () => rejectStudent(true);
                actionBar.appendChild(rejectBtn);
                
                const approveBtn = document.createElement('button');
                approveBtn.className = 'btn primary';
                approveBtn.textContent = '审核通过';
                approveBtn.onclick = () => approveStudent();
                actionBar.appendChild(approveBtn);
            } else {
                const downloadZipBtn = document.createElement('button');
                downloadZipBtn.className = 'btn secondary';
                downloadZipBtn.textContent = '打包下载';
                downloadZipBtn.style.marginRight = '8px';
                downloadZipBtn.onclick = () => {
                    window.open(`/api/students/${student.id}/attachments.zip`, '_blank');
                };
                actionBar.appendChild(downloadZipBtn);
                
                const rejectBtn = document.createElement('button');
                rejectBtn.className = 'btn';
                rejectBtn.style.cssText = 'background: #FEE2E2; color: #EF4444;';
                rejectBtn.textContent = '审核不通过';
                rejectBtn.onclick = () => rejectStudent(false);
                actionBar.appendChild(rejectBtn);
            }
        }

        mainContent.innerHTML = '';
        mainContent.appendChild(clone);
    }

    async function uploadFile(studentId, fieldName, file, dbKey) {
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
            
            const idx = students.findIndex(s => s.id === studentId);
            if (idx >= 0) {
                students[idx][dbKey || result.field] = result.path;
                if (result.student) {
                    students[idx] = result.student;
                }
            }
            if (currentStudentId === studentId && idx >= 0) {
                showDetail(students[idx]);
            }
        } catch (e) {
            console.error('Upload error:', e);
            showSaveStatus('文件上传失败', 'error');
        }
    }

    window.approveStudent = async function() {
        if (!currentStudentId) return;
        try {
            const res = await fetch(`/api/students/${currentStudentId}/approve`, { method: 'POST' });
            if (!res.ok) throw new Error('操作失败');
            showMessage('审核通过', 'success');
            loadStudents();
            loadCompanies(currentStatus);
            mainContent.innerHTML = '<div class="empty-state">请选择左侧学员查看详情</div>';
            currentStudentId = null;
        } catch (e) {
            showMessage('操作失败: ' + e.message, 'error');
        }
    };

    window.rejectStudent = async function(shouldDelete) {
        if (!currentStudentId) return;
        try {
            const res = await fetch(`/api/students/${currentStudentId}/reject`, { 
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ delete: shouldDelete })
            });
            if (!res.ok) throw new Error('操作失败');
            showMessage(shouldDelete ? '已删除学员' : '已移至未审核', 'success');
            loadStudents();
            loadCompanies(currentStatus);
            mainContent.innerHTML = '<div class="empty-state">请选择左侧学员查看详情</div>';
            currentStudentId = null;
        } catch (e) {
            showMessage('操作失败: ' + e.message, 'error');
        }
    };
});
