document.addEventListener('DOMContentLoaded', () => {
    let currentStatus = 'unreviewed';
    let currentStudentId = null;
    let students = [];

    const listContainer = document.getElementById('studentList');
    const mainContent = document.getElementById('mainContent');
    const searchInput = document.getElementById('searchInput');
    const tabs = document.querySelectorAll('.tab');
    const detailTemplate = document.getElementById('detail-template');
    
    // Filter controls
    let currentFilters = {
        company: '',
        passed: ''
    };

    // Init
    loadStudents();
    loadCompanies();
    
    // Load companies for dropdown
    async function loadCompanies(status = currentStatus) {
        const companyFilter = document.getElementById('companyFilter');
        if (!companyFilter) return;
        
        try {
            // Build query string with current filters and status
            const queryParams = new URLSearchParams({
                status: status
            });
            
            // Add passed filter if it's set
            if (currentFilters.passed) {
                queryParams.append('passed', currentFilters.passed);
            }
            
            // Load students with current filters to get companies with data
            const res = await fetch(`/api/students?${queryParams.toString()}`);
            if (!res.ok) {
                throw new Error(`网络错误: ${res.status}`);
            }
            const filteredStudents = await res.json();
            
            // Get unique companies that have students matching the filters
            const companiesWithData = [...new Set(filteredStudents.map(student => student.company).filter(Boolean))];
            
            // Clear existing options except the first one
            while (companyFilter.options.length > 1) {
                companyFilter.remove(1);
            }
            
            // Add companies to dropdown
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

    // Mobile menu toggle
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const sidebar = document.getElementById('sidebar');
    
    if (mobileMenuToggle && sidebar) {
        mobileMenuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('mobile-open');
        });
        
        // Close sidebar when clicking on a student
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 && 
                !sidebar.contains(e.target) && 
                !mobileMenuToggle.contains(e.target) && 
                sidebar.classList.contains('mobile-open')) {
                sidebar.classList.remove('mobile-open');
            }
        });
    }
    
    // Event Listeners
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentStatus = tab.dataset.status;
            loadStudents();
            loadCompanies(currentStatus);
            // Reset company filter when changing tab
            if (companyFilter) {
                companyFilter.value = '';
                currentFilters.company = '';
            }
            // Toggle passed filter visibility based on status
            togglePassedFilterVisibility(currentStatus);
            mainContent.innerHTML = '<div class="empty-state">请选择左侧学员查看详情</div>';
            currentStudentId = null;
            
            // Don't close sidebar on mobile after selecting a tab
            // Let user select a student first
        });
    });

    searchInput.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        const filtered = students.filter(s => 
            s.name.toLowerCase().includes(term) || 
            s.id_card.includes(term) || 
            s.phone.includes(term)
        );
        renderList(filtered);
    });
    
    // Filter event listeners
    const companyFilter = document.getElementById('companyFilter');
    const passedFilter = document.getElementById('passedFilter');
    const passedFilterContainer = document.getElementById('passedFilterContainer');
    const resetFilters = document.getElementById('resetFilters');
    
    // Function to toggle passed filter visibility based on status
    function togglePassedFilterVisibility(status) {
        if (passedFilterContainer) {
            if (status === 'examined') {
                passedFilterContainer.style.display = 'block';
            } else {
                passedFilterContainer.style.display = 'none';
                // Reset passed filter when hiding
                if (passedFilter) {
                    passedFilter.value = '';
                    currentFilters.passed = '';
                }
            }
        }
    }
    
    // Initial toggle based on current status
    togglePassedFilterVisibility(currentStatus);
    
    if (companyFilter) {
        companyFilter.addEventListener('change', (e) => {
            currentFilters.company = e.target.value;
            loadStudents();
        });
    }
    
    if (passedFilter) {
        passedFilter.addEventListener('change', (e) => {
            currentFilters.passed = e.target.value;
            loadStudents();
            loadCompanies(currentStatus);
            // Reset company filter when changing passed filter
            if (companyFilter) {
                companyFilter.value = '';
                currentFilters.company = '';
            }
        });
    }
    
    if (resetFilters) {
        resetFilters.addEventListener('click', () => {
            if (companyFilter) companyFilter.value = '';
            if (passedFilter) passedFilter.value = '';
            currentFilters = {
                company: '',
                passed: ''
            };
            loadStudents();
            loadCompanies(currentStatus);
        });
    }
    


    async function loadStudents() {
        listContainer.innerHTML = '<div style="padding:20px;text-align:center;">加载中...</div>';
        try {
            // Build query string with filters
            const queryParams = new URLSearchParams({
                status: currentStatus,
                company: currentFilters.company,
                passed: currentFilters.passed
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

                // Close sidebar on mobile after selecting a student
                if (window.innerWidth <= 768 && sidebar) {
                    sidebar.classList.remove('mobile-open');
                }
            };
            listContainer.appendChild(el);
        });
    }

    // Debounce function for auto-save
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
    
    // Auto-save function with status feedback
    const autoSave = debounce(async (studentId) => {
        if (!studentId) return;
        
        // Show saving status
        showSaveStatus('保存中...', 'info');
        
        try {
            const formData = new FormData();
            
            // Get all input elements including those in exam fields
            const allInputs = mainContent.querySelectorAll('input[data-key], select[data-key]');
            allInputs.forEach(input => {
                const key = input.getAttribute('data-key');
                if (key) {
                    formData.append(key, input.value.trim());
                }
            });
            
            const res = await fetch(`/api/students/${studentId}`, { method: 'PUT', body: formData });
            
            if (!res.ok) {
                throw new Error('保存失败');
            }
            
            const updated = await res.json();
            
            // Show success status
            showSaveStatus('保存成功', 'success');
            
            // Update local student data
            const idx = students.findIndex(s => s.id === studentId);
            if (idx >= 0) students[idx] = updated;
            
        } catch (e) {
            console.error('Auto-save error:', e);
            showSaveStatus('保存失败', 'error');
        }
    }, 1000); // 1 second debounce
    
    // Show save status feedback
    function showSaveStatus(message, type = 'info') {
        // Remove existing status if any
        const existingStatus = mainContent.querySelector('.save-status');
        if (existingStatus) {
            existingStatus.remove();
        }

        // Create status element
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

        // Set styles based on type
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

        // Remove after 3 seconds
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

    // Show message function
    function showMessage(message, type = 'info') {
        // Remove existing message if any
        const existingMessage = document.querySelector('.custom-message');
        if (existingMessage) {
            existingMessage.remove();
        }

        // Create message element
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

        // Set styles based on type
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

        // Remove after 4 seconds
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
        // Highlight in list
        document.querySelectorAll('.list-item').forEach(el => el.classList.remove('active'));
        // Find the clicked one and add active (simple re-render or find index)
        renderList(students); // Re-render to update active state simply

        const clone = detailTemplate.content.cloneNode(true);
        
        // Populate
        clone.querySelector('.student-name').textContent = student.name;
        clone.querySelector('.student-id').textContent = student.id_card;
        const statusBadge = clone.querySelector('.status-badge');
        if (statusBadge) {
            const reviewed = student.status === 'reviewed';
            statusBadge.innerHTML = `<span class="badge ${reviewed ? 'reviewed' : 'unreviewed'}">${reviewed ? '已审核' : '未审核'}</span>`;
        }
        
        const grid = clone.querySelector('.detail-grid');
        
        // 二级联动下拉选项数据
        const examProjectOptions = {
            '电工作业': [
                { value: '低压电工作业', text: '低压电工作业' },
                { value: '高压电工作业', text: '高压电工作业' },
                { value: '电力电缆作业', text: '电力电缆作业' },
                { value: '电气试验作业', text: '电气试验作业' },
                { value: '继电保护作业', text: '继电保护作业' },
                { value: '防爆电气作业', text: '防爆电气作业' }
            ],
            '焊接与热切割作业': [
                { value: '熔化焊接与热切割作业', text: '熔化焊接与热切割作业' }
            ],
            '高处作业': [
                { value: '高处安装、维护、拆除作业', text: '高处安装、维护、拆除作业' },
                { value: '登高架设作业', text: '登高架设作业' }
            ]
        };

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
            { key: 'job_category', label: '作业类别', required: true, type: 'select', options: [
                { value: '', text: '请选择' },
                { value: '电工作业', text: '电工作业' },
                { value: '焊接与热切割作业', text: '焊接与热切割作业' },
                { value: '高处作业', text: '高处作业' }
            ]},
            { key: 'exam_project', label: '操作项目', required: true, type: 'select', options: [] },
            { key: 'exam_code', label: '项目代码' },
            { key: 'exam_category', label: '考试类别', required: true, type: 'select', options: [
                { value: '初次领证', text: '初次领证' },
                { value: '复审', text: '复审' },
                { value: '延期换证', text: '延期换证' }
            ]}
        ];
        
        // Store the original student data for comparison
        const originalData = {...student};
        
        editable.forEach(f => {
            const item = document.createElement('div');
            item.className = 'detail-item';
            const val = student[f.key] || '';
            
            let input;
            if (f.type === 'select') {
                input = document.createElement('select');
                input.setAttribute('data-key', f.key);
                
                f.options.forEach(option => {
                    const optionElement = document.createElement('option');
                    optionElement.value = option.value;
                    optionElement.textContent = option.text;
                    if (option.value === val) {
                        optionElement.selected = true;
                    }
                    input.appendChild(optionElement);
                });
                
                // If this is the job_category field, add event listener for secondary联动
                if (f.key === 'job_category') {
                    input.addEventListener('change', function() {
                        updateExamProjectOptions(this, originalData.exam_project);
                    });
                    
                    // Initialize the exam_project options based on current job_category
                    setTimeout(() => {
                        updateExamProjectOptions(input, originalData.exam_project);
                    }, 0);
                }
            } else {
                input = document.createElement('input');
                input.setAttribute('data-key', f.key);
                input.value = val;
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
            
            // realtime validation
            const parent = item;
            const showError = () => {
                input.classList.remove('error');
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
        });

        // Function to update exam project options based on job category selection
        function updateExamProjectOptions(categorySelect, originalValue) {
            const projectSelect = Array.from(grid.querySelectorAll('select')).find(select => select.getAttribute('data-key') === 'exam_project');
            if (!projectSelect) return;
            
            const selectedCategory = categorySelect.value;
            
            // Clear exam project options
            projectSelect.innerHTML = '<option value="">请选择操作项目</option>';
            
            if (selectedCategory && examProjectOptions[selectedCategory]) {
                // Add corresponding exam project options
                examProjectOptions[selectedCategory].forEach(option => {
                    const optionElement = document.createElement('option');
                    optionElement.value = option.value;
                    optionElement.textContent = option.text;
                    if (originalValue && option.value === originalValue) {
                        optionElement.selected = true;
                    }
                    projectSelect.appendChild(optionElement);
                });
            }
        }

        // Add exam-related fields for reviewed students
        if (student.status === 'reviewed') {
            const examFields = [
            { key: 'theory_exam_time', label: '理论考试时间' },
            { key: 'practical_exam_time', label: '实操考试时间' },
            { key: 'passed', label: '是否通过', type: 'toggle' },
            { key: 'theory_makeup_time', label: '理论补考时间' },
            { key: 'makeup_exam', label: '是否补考', type: 'toggle' }
        ];
            
            examFields.forEach(f => {
                const item = document.createElement('div');
                item.className = 'detail-item';
                item.innerHTML = `<label>${f.label}</label>`;
                item.style.position = 'relative';
                
                const val = student[f.key] || '';
                
                if (f.type === 'toggle') {
                    // Create toggle switch for pass/fail and makeup exam
                    const toggleContainer = document.createElement('div');
                    toggleContainer.style.display = 'flex';
                    toggleContainer.style.alignItems = 'center';
                    toggleContainer.style.gap = '10px';
                    
                    // Hidden input to store the value
                    const hiddenInput = document.createElement('input');
                    hiddenInput.setAttribute('data-key', f.key);
                    hiddenInput.type = 'hidden';
                    hiddenInput.value = val || '否';
                    toggleContainer.appendChild(hiddenInput);
                    
                    // Create a simple toggle button
                    const toggleButton = document.createElement('button');
                    toggleButton.style.width = '60px';
                    toggleButton.style.height = '24px';
                    toggleButton.style.border = 'none';
                    toggleButton.style.borderRadius = '12px';
                    toggleButton.style.backgroundColor = val === '是' ? '#4f46e5' : '#ccc';
                    toggleButton.style.color = 'white';
                    toggleButton.style.fontSize = '12px';
                    toggleButton.style.fontWeight = 'bold';
                    toggleButton.style.cursor = 'pointer';
                    toggleButton.style.transition = 'all 0.3s ease';
                    toggleButton.style.display = 'flex';
                    toggleButton.style.alignItems = 'center';
                    toggleButton.style.justifyContent = val === '是' ? 'flex-end' : 'flex-start';
                    toggleButton.style.padding = '0 4px';
                    toggleButton.style.position = 'relative';
                    toggleButton.style.boxSizing = 'border-box';
                    
                    // Create slider
                    const slider = document.createElement('span');
                    slider.style.width = '20px';
                    slider.style.height = '20px';
                    slider.style.borderRadius = '50%';
                    slider.style.backgroundColor = 'white';
                    slider.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';
                    slider.style.transition = 'all 0.3s ease';
                    slider.style.boxSizing = 'border-box';
                    
                    toggleButton.appendChild(slider);
                    toggleContainer.appendChild(toggleButton);
                    
                    // Status text
                    const statusText = document.createElement('span');
                    statusText.textContent = val === '是' ? '是' : '否';
                    statusText.style.fontSize = '0.9rem';
                    statusText.style.color = val === '是' ? '#10b981' : '#666';
                    toggleContainer.appendChild(statusText);
                    
                    // Toggle functionality
                    toggleButton.addEventListener('click', function() {
                        const currentValue = hiddenInput.value;
                        const newValue = currentValue === '是' ? '否' : '是';
                        
                        hiddenInput.value = newValue;
                        statusText.textContent = newValue;
                        statusText.style.color = newValue === '是' ? '#10b981' : '#666';
                        
                        // Update button style
                        toggleButton.style.backgroundColor = newValue === '是' ? '#4f46e5' : '#ccc';
                        toggleButton.style.justifyContent = newValue === '是' ? 'flex-end' : 'flex-start';
                        
                        // Trigger auto-save
                        autoSave(student.id);
                    });
                    
                    item.appendChild(toggleContainer);
                } else {
                        const input = document.createElement('input');
                        input.setAttribute('data-key', f.key);
                        input.value = val;
                        input.style.width = '100%';
                        input.style.padding = '8px';
                        input.style.border = '1px solid #ddd';
                        input.style.borderRadius = '4px';
                        input.type = 'date';
                        item.appendChild(input);
                        
                        // Add input event listener for auto-save
                        input.addEventListener('input', () => {
                            autoSave(student.id);
                        });
                        
                        input.addEventListener('change', () => {
                            autoSave(student.id);
                        });
                    }
                
                grid.appendChild(item);
            });
        }

        // Files
        const filesContainer = clone.querySelector('.file-thumbs');
        filesContainer.style.display = 'flex';
        filesContainer.style.flexWrap = 'nowrap';
        filesContainer.style.gap = '15px';
        filesContainer.style.overflowX = 'auto';
        filesContainer.style.padding = '10px 0';
        
        const fileMap = {
            'photo_path': '个人照片',
            'diploma_path': '学历证书',
            'cert_front_path': '所持证件正面',
            'cert_back_path': '所持证件反面',
            'id_card_front_path': '身份证正面',
            'id_card_back_path': '身份证反面'
        };
        
        for (const [key, label] of Object.entries(fileMap)) {
            const wrapper = document.createElement('div');
            wrapper.className = 'file-item-wrapper';
            wrapper.style.display = 'flex';
            wrapper.style.flexDirection = 'column';
            wrapper.style.alignItems = 'center';
            wrapper.style.gap = '5px';
            wrapper.style.minWidth = '100px';

            // Upload box similar to frontend
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
            placeholder.style.display = student[key] ? 'none' : 'flex';
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
            text.textContent = label;
            text.style.fontSize = '12px';
            text.style.color = '#666';
            text.style.textAlign = 'center';
            text.style.maxWidth = '80px';
            text.style.wordBreak = 'break-all';
            
            placeholder.appendChild(icon);
            placeholder.appendChild(text);

            const img = document.createElement('img');
            img.className = 'preview-img';
            img.style.display = student[key] ? 'block' : 'none';
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'cover';
            if (student[key]) {
                img.src = '/' + student[key];
            }

            // map db field to upload field name
            const nameMap = {
                photo_path: 'photo',
                diploma_path: 'diploma',
                cert_front_path: 'cert_front',
                cert_back_path: 'cert_back',
                id_card_front_path: 'id_card_front',
                id_card_back_path: 'id_card_back'
            };
            
            const input = document.createElement('input');
            input.type = 'file';
            input.name = nameMap[key] || '';
            input.accept = 'image/*';
            input.style.display = 'none';
            
            input.addEventListener('change', () => {
                if (input.files && input.files[0]) {
                    const file = input.files[0];
                    // If this is the personal photo field, crop to one-inch ratio client-side
                    if (input.name === 'photo') {
                        const imgEl = new Image();
                        const reader = new FileReader();
                        reader.onload = function(ev) {
                            imgEl.onload = function() {
                                try {
                                    // Target physical size: 2.5cm x 3.5cm -> in inches
                                    const tgtWIn = 2.5 / 2.54;
                                    const tgtHIn = 3.5 / 2.54;
                                    const dpi = 300;
                                    const pxW = Math.max(120, Math.round(tgtWIn * dpi));
                                    const pxH = Math.max(160, Math.round(tgtHIn * dpi));

                                    // Scale to fit target box (contain) and center, padding with white
                                    const srcW = imgEl.naturalWidth;
                                    const srcH = imgEl.naturalHeight;
                                    const canvas = document.createElement('canvas');
                                    canvas.width = pxW;
                                    canvas.height = pxH;
                                    const ctx = canvas.getContext('2d');
                                    // Fill white background
                                    ctx.fillStyle = '#FFFFFF';
                                    ctx.fillRect(0, 0, pxW, pxH);
                                    // Compute scale to fit entire source image into target (no cropping)
                                    const scale = Math.min(pxW / srcW, pxH / srcH);
                                    const newW = Math.max(1, Math.round(srcW * scale));
                                    const newH = Math.max(1, Math.round(srcH * scale));
                                    const dx = Math.round((pxW - newW) / 2);
                                    const dy = Math.round((pxH - newH) / 2);
                                    ctx.drawImage(imgEl, 0, 0, srcW, srcH, dx, dy, newW, newH);

                                    // Convert to blob and replace input.files with the cropped file
                                    canvas.toBlob(function(blob) {
                                        if (!blob) {
                                            // fallback to original preview
                                            img.src = ev.target.result;
                                            img.style.display = 'block';
                                            placeholder.style.display = 'none';
                                            return;
                                        }
                                        const newFile = new File([blob], file.name.replace(/\.[^/.]+$/, '') + '_1inch.jpg', { type: 'image/jpeg' });
                                        // Update the input's FileList
                                        try {
                                            const dt = new DataTransfer();
                                            dt.items.add(newFile);
                                            input.files = dt.files;
                                        } catch (e) {
                                            // Some browsers may not support DataTransfer constructor
                                            console.warn('Could not replace FileList programmatically:', e);
                                        }
                                        // Update preview
                                        try {
                                            const objUrl = URL.createObjectURL(newFile);
                                            img.src = objUrl;
                                        } catch (e) {
                                            // fallback to dataURL
                                            const reader2 = new FileReader();
                                            reader2.onload = function(ev2) { img.src = ev2.target.result; };
                                            reader2.readAsDataURL(newFile);
                                        }
                                        img.style.display = 'block';
                                        placeholder.style.display = 'none';
                                    }, 'image/jpeg', 0.95);
                                } catch (err) {
                                    console.error('Photo processing failed:', err);
                                    // fallback to original preview
                                    img.src = ev.target.result;
                                    img.style.display = 'block';
                                    placeholder.style.display = 'none';
                                }
                            };
                            imgEl.src = ev.target.result;
                        };
                        reader.readAsDataURL(file);
                    } else {
                        // Non-photo files: simple preview
                        const reader = new FileReader();
                        reader.onload = function(e) {
                            img.src = e.target.result;
                            img.style.display = 'block';
                            placeholder.style.display = 'none';
                        };
                        reader.readAsDataURL(file);
                    }
                } else {
                    img.style.display = 'none';
                    img.src = '';
                    placeholder.style.display = 'flex';
                }
            });

            uploadBox.appendChild(placeholder);
            uploadBox.appendChild(img);
            uploadBox.appendChild(input);

            wrapper.appendChild(uploadBox);

            const title = document.createElement('span');
            title.textContent = label;
            title.style.fontSize = '11px';
            title.style.color = '#666';
            title.style.textAlign = 'center';
            title.style.maxWidth = '100px';
            title.style.wordBreak = 'break-all';

            wrapper.appendChild(title);
            filesContainer.appendChild(wrapper);
        }

        // Buttons
        const actionBar = clone.querySelector('.action-bar');
        actionBar.innerHTML = '';
        const saveBtn = document.createElement('button');
        saveBtn.className = 'btn';
        saveBtn.textContent = '保存修改';
        saveBtn.setAttribute('data-role', 'save');
        saveBtn.onclick = () => handleSave(student.id);
        actionBar.appendChild(saveBtn);
        
        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn';
        deleteBtn.style.background = '#FEE2E2';
        deleteBtn.style.color = '#EF4444';
        deleteBtn.textContent = '删除学员';
        deleteBtn.onclick = () => handleDelete(student.id);
        actionBar.appendChild(deleteBtn);
        
        if (currentStatus === 'unreviewed') {
            const rejectBtn = document.createElement('button');
            rejectBtn.className = 'btn';
            rejectBtn.style.background = '#FEE2E2';
            rejectBtn.style.color = '#EF4444';
            rejectBtn.textContent = '审核不通过';
            rejectBtn.onclick = () => handleReject(student.id);
            const approveBtn = document.createElement('button');
            approveBtn.className = 'btn primary';
            approveBtn.textContent = '审核通过';
            approveBtn.onclick = () => handleApprove(student.id);
            actionBar.appendChild(rejectBtn);
            actionBar.appendChild(approveBtn);
        } else if (currentStatus === 'reviewed') {
            const genBtn = document.createElement('button');
            genBtn.className = 'btn primary';
            genBtn.textContent = '生成体检表';
            genBtn.onclick = () => handleGenerate(student.id, genBtn);
            actionBar.appendChild(genBtn);
            
            const zipBtn = document.createElement('button');
            zipBtn.className = 'btn';
            zipBtn.textContent = '附件打包下载';
            zipBtn.onclick = () => {
                window.location.href = `/api/students/${student.id}/attachments.zip`;
            };
            actionBar.appendChild(zipBtn);
        }

        mainContent.innerHTML = '';
        mainContent.appendChild(clone);
    }

    function previewSelected(input, img, placeholder) {
        if (input.files && input.files[0]) {
            const reader = new FileReader();
            reader.onload = e => {
                img.src = e.target.result;
                img.style.display = 'block';
                placeholder.style.display = 'none';
            };
            reader.readAsDataURL(input.files[0]);
        } else {
            img.style.display = 'none';
            img.src = '';
            placeholder.style.display = 'block';
        }
    }

    function validateDetail() {
        let ok = true;
        const inputs = mainContent.querySelectorAll('.detail-item input');
        inputs.forEach(input => {
            input.classList.remove('error');
            const parent = input.parentElement;
            const existing = parent.querySelector('.error-message');
            if (existing) existing.remove();
            if (!input.checkValidity()) {
                input.classList.add('error');
                ok = false;
                const msg = document.createElement('span');
                msg.className = 'error-message';
                msg.textContent = input.validationMessage || input.title || '请填写此字段';
                if (input.validity.patternMismatch && input.title) {
                    msg.textContent = input.title;
                }
                parent.appendChild(msg);
                input.addEventListener('input', () => {
                    if (input.checkValidity()) {
                        input.classList.remove('error');
                        const m = parent.querySelector('.error-message');
                        if (m) m.remove();
                    }
                });
            }
        });
        return ok;
    }

    async function handleSave(id) {
        const saveBtn = mainContent.querySelector('.action-bar .btn[data-role="save"]');
        if (!validateDetail()) {
            if (saveBtn) {
                const prev = saveBtn.textContent;
                saveBtn.textContent = '请修正后再保存';
                setTimeout(() => { saveBtn.textContent = prev; }, 1500);
            }
            return;
        }
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = '正在保存...';
        }
        const formData = new FormData();
        
        // Get all input elements including those in exam fields
        const allInputs = mainContent.querySelectorAll('input[data-key], select[data-key]');
        allInputs.forEach(input => {
            const key = input.getAttribute('data-key');
            if (key) {
                formData.append(key, input.value.trim());
            }
        });
        
        // Handle file uploads
        const fileInputs = mainContent.querySelectorAll('input[type="file"]');
        fileInputs.forEach(fi => {
            if (fi.files && fi.files[0]) {
                formData.append(fi.name, fi.files[0]);
            }
        });
        
        try {
            const res = await fetch(`/api/students/${id}`, { method: 'PUT', body: formData });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                console.error('Save failed:', err);
                if (saveBtn) {
                    const prev = saveBtn.textContent;
                    saveBtn.disabled = false;
                    saveBtn.textContent = '保存失败';
                    setTimeout(() => { saveBtn.textContent = prev; }, 1500);
                }
                return;
            }
            const updated = await res.json();
            if (saveBtn) {
                saveBtn.textContent = '已保存';
                setTimeout(() => {
                    saveBtn.disabled = false;
                    saveBtn.textContent = '保存修改';
                }, 1200);
            }
            const idx = students.findIndex(s => s.id === id);
            if (idx >= 0) students[idx] = updated;
            showDetail(updated);
            renderList(students);
        } catch (e) {
            console.error('Save error:', e);
            if (saveBtn) {
                const prev = saveBtn.textContent;
                saveBtn.disabled = false;
                saveBtn.textContent = '网络错误';
                setTimeout(() => { saveBtn.textContent = prev; }, 1500);
            }
        }
    }

    async function handleApprove(id) {
        // Create custom modalal for confirmation
        const modalal = document.createElement('div');
        modalal.style.position = 'fixed';
        modalal.style.top = '0';
        modalal.style.left = '0';
        modalal.style.width = '100%';
        modalal.style.height = '100%';
        modalal.style.backgroundColor = 'rgba(0,0,0,0.5)';
        modalal.style.display = 'flex';
        modalal.style.justifyContent = 'center';
        modalal.style.alignItems = 'center';
        modalal.style.zIndex = '10000';
        modalal.innerHTML = `
            <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); max-width: 400px; width: 90%;">
                <h3 style="margin-top: 0; color: #10b981;">确认操作</h3>
                <p>确认审核通过？该学员将被标记为已审核。</p>
                <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
                    <button id="cancel-approve" style="padding: 8px 16px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer;">取消</button>
                    <button id="confirm-approve" style="padding: 8px 16px; background: #10b981; color: white; border: none; border-radius: 4px; cursor: pointer;">确认通过</button>
                </div>
            </div>
        `;
        document.body.appendChild(modalal);

        document.getElementById('cancel-approve').onclick = () => {
            document.body.removeChild(modalal);
        };

        document.getElementById('confirm-approve').onclick = async () => {
            try {
                const res = await fetch(`/api/students/${id}/approve`, { method: 'POST' });
                document.body.removeChild(modalal);
                
                if (res.ok) {
                    // Show success message
                    showMessage('审核通过', 'success');
                    loadStudents();
                    mainContent.innerHTML = '<div class="empty-state">操作成功，请选择下一位</div>';
                } else {
                    // Show error message
                    const errorData = await res.json().catch(() => ({}));
                    showMessage(`操作失败: ${errorData.error || '未知错误'}`, 'error');
                }
            } catch (e) {
                document.body.removeChild(modalal);
                showMessage(`Error: ${e.message}`, 'error');
            }
        };
    }

    async function handleGenerate(id, btn) {
        // direct generate without confirmation; show inline status above button
        const actionBar = btn ? btn.parentElement : null;
        let statusEl = mainContent.querySelector('.generate-result');
        if (!statusEl && actionBar) {
            statusEl = document.createElement('div');
            statusEl.className = 'generate-result';
            statusEl.style.marginBottom = '8px';
            statusEl.style.fontSize = '0.95rem';
            statusEl.style.color = '#0f172a';
            statusEl.style.padding = '6px 10px';
            statusEl.style.borderRadius = '6px';
            statusEl.style.background = 'rgba(241,245,249,0.8)';
            actionBar.insertAdjacentElement('beforebegin', statusEl);
        }
        if (statusEl) {
            statusEl.textContent = '正在生成体检表...';
            statusEl.style.background = 'rgba(219,234,254,0.9)';
        }
        if (btn) {
            btn.disabled = true;
            btn.textContent = '生成中...';
        }
        try {
            const res = await fetch(`/api/students/${id}/generate`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json().catch(() => ({}));
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '下载体检表';
                    btn.onclick = () => {
                        if (data.download_url) {
                            window.location.href = data.download_url;
                        } else {
                            // fallback: refresh to show link in UI
                            window.location.reload();
                        }
                    };
                }
                if (statusEl) {
                    statusEl.textContent = '生成成功：体检表已生成，点击“下载体检表”下载';
                    statusEl.style.background = 'rgba(220,253,233,0.9)';
                }
            } else {
                const err = await res.json().catch(() => ({}));
                console.error('生成失败', err);
                if (btn) { btn.disabled = false; btn.textContent = '生成体检表'; }
                if (statusEl) {
                    statusEl.textContent = '生成失败，请重试';
                    statusEl.style.background = 'rgba(254,226,226,0.9)';
                }
            }
        } catch (e) {
            if (btn) { btn.disabled = false; btn.textContent = '生成体检表'; }
            if (statusEl) {
                statusEl.textContent = '网络错误，生成失败';
                statusEl.style.background = 'rgba(254,226,226,0.9)';
            }
        }
    }

    async function handleReject(id) {
        // Create custom modalalal for confirmation
        const modalalal = document.createElement('div');
        modalalal.style.position = 'fixed';
        modalalal.style.top = '0';
        modalalal.style.left = '0';
        modalalal.style.width = '100%';
        modalalal.style.height = '100%';
        modalalal.style.backgroundColor = 'rgba(0,0,0,0.5)';
        modalalal.style.display = 'flex';
        modalalal.style.justifyContent = 'center';
        modalalal.style.alignItems = 'center';
        modalalal.style.zIndex = '10000';
        modalalal.innerHTML = `
            <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); max-width: 400px; width: 90%;">
                <h3 style="margin-top: 0; color: #ef4444;">确认操作</h3>
                <p>确认审核不通过？该学员将被删除。</p>
                <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
                    <button id="cancel-reject" style="padding: 8px 16px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer;">取消</button>
                    <button id="confirm-reject" style="padding: 8px 16px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor: pointer;">确认删除</button>
                </div>
            </div>
        `;
        document.body.appendChild(modalalal);

        document.getElementById('cancel-reject').onclick = () => {
            document.body.removeChild(modalalal);
        };

        document.getElementById('confirm-reject').onclick = async () => {
            try {
                const res = await fetch(`/api/students/${id}/reject`, { method: 'POST' });
                document.body.removeChild(modalalal);
                
                if (res.ok) {
                    // Show success message
                    showMessage('已删除该学员。', 'success');
                    loadStudents();
                    mainContent.innerHTML = '<div class="empty-state">已删除，请选择下一位</div>';
                } else {
                    // Show error message
                    const errorData = await res.json().catch(() => ({}));
                    showMessage(`操作失败: ${errorData.error || '未知错误'}`, 'error');
                }
            } catch (e) {
                document.body.removeChild(modalalal);
                showMessage(`Error: ${e.message}`, 'error');
            }
        };
    }

    async function handleDelete(id) {
        // Create custom modalalal for confirmation
        const modalalal = document.createElement('div');
        modalalal.style.position = 'fixed';
        modalalal.style.top = '0';
        modalalal.style.left = '0';
        modalalal.style.width = '100%';
        modalalal.style.height = '100%';
        modalalal.style.backgroundColor = 'rgba(0,0,0,0.5)';
        modalalal.style.display = 'flex';
        modalalal.style.justifyContent = 'center';
        modalalal.style.alignItems = 'center';
        modalalal.style.zIndex = '10000';
        modalalal.innerHTML = `
            <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); max-width: 400px; width: 90%;">
                <h3 style="margin-top: 0; color: #ef4444;">确认操作</h3>
                <p>确认删除该学员？此操作不可恢复。</p>
                <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
                    <button id="cancel-delete" style="padding: 8px 16px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer;">取消</button>
                    <button id="confirm-delete" style="padding: 8px 16px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor: pointer;">确认删除</button>
                </div>
            </div>
        `;
        document.body.appendChild(modalalal);

        document.getElementById('cancel-delete').onclick = () => {
            document.body.removeChild(modalalal);
        };

        document.getElementById('confirm-delete').onclick = async () => {
            try {
                const res = await fetch(`/api/students/${id}/reject`, { method: 'POST' });
                document.body.removeChild(modalalal);
                
                if (res.ok) {
                    // Show success message
                    showMessage('已删除该学员。', 'success');
                    loadStudents();
                    mainContent.innerHTML = '<div class="empty-state">已删除，请选择下一位</div>';
                } else {
                    // Show error message
                    const errorData = await res.json().catch(() => ({}));
                    showMessage(`操作失败: ${errorData.error || '未知错误'}`, 'error');
                }
            } catch (e) {
                document.body.removeChild(modalalal);
                showMessage(`Error: ${e.message}`, 'error');
            }
        };
    }
});

