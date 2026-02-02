document.addEventListener('DOMContentLoaded', () => {
    let currentStatus = 'unreviewed';
    let currentStudentId = null;
    let students = [];

    const listContainer = document.getElementById('studentList');
    const mainContent = document.getElementById('mainContent');
    const searchInput = document.getElementById('searchInput');
    const tabs = document.querySelectorAll('.tab');
    const detailTemplate = document.getElementById('detail-template');

    // Init
    loadStudents();

    // Event Listeners
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentStatus = tab.dataset.status;
            loadStudents();
            mainContent.innerHTML = '<div class="empty-state">请选择左侧学员查看详情</div>';
            currentStudentId = null;
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

    async function loadStudents() {
        listContainer.innerHTML = '<div style="padding:20px;text-align:center;">加载中...</div>';
        try {
            const res = await fetch(`/api/students?status=${currentStatus}`);
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
                <h4>${student.name}</h4>
                <p>${student.job_category} - ${student.exam_category}</p>
            `;
            el.onclick = () => showDetail(student);
            listContainer.appendChild(el);
        });
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
        const editable = [
            { key: 'name', label: '姓名', required: true },
            { key: 'gender', label: '性别', required: true, pattern: '男|女', title: '请输入“男”或“女”' },
            { key: 'education', label: '文化程度', required: true },
            { key: 'id_card', label: '身份证号', required: true, pattern: '\\d{17}[\\dXx]', title: '请输入正确的18位身份证号' },
            { key: 'phone', label: '手机号', required: true, pattern: '\\d{11}', title: '请输入11位手机号' },
            { key: 'school', label: '毕业院校' },
            { key: 'major', label: '所学专业' },
            { key: 'company', label: '单位名称' },
            { key: 'company_address', label: '单位地址' },
            { key: 'job_category', label: '作业类别', required: true },
            { key: 'exam_project', label: '准操项目' },
            { key: 'exam_code', label: '项目代码' },
            { key: 'exam_category', label: '考试类别', required: true },
        ];
        editable.forEach(f => {
            const item = document.createElement('div');
            item.className = 'detail-item';
            const val = student[f.key] || '';
            const input = document.createElement('input');
            input.setAttribute('data-key', f.key);
            input.value = val;
            input.style.width = '100%';
            input.style.padding = '8px';
            input.style.border = '1px solid #ddd';
            input.style.borderRadius = '4px';
            if (f.required) input.required = true;
            if (f.pattern) input.pattern = f.pattern;
            if (f.title) input.title = f.title;
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

        // Files
        const filesContainer = clone.querySelector('.file-thumbs');
        const fileMap = {
            'photo_path': '个人照片',
            'diploma_path': '学历证书',
            'cert_path': '所持证件',
            'id_card_front_path': '身份证正面',
            'id_card_back_path': '身份证反面',
            'training_form_path': '培训信息登记表'
        };
        
        for (const [key, label] of Object.entries(fileMap)) {
            if (student[key]) {
                const wrapper = document.createElement('div');
                wrapper.className = 'file-item-wrapper';
                wrapper.style.display = 'flex';
                wrapper.style.flexDirection = 'column';
                wrapper.style.alignItems = 'center';
                wrapper.style.gap = '5px';

                const link = document.createElement('a');
                link.href = '/' + student[key];
                link.target = '_blank';
                
                const isImg = student[key].match(/\.(jpg|jpeg|png|gif)$/i);
                if (isImg) {
                    link.innerHTML = `<img src="/${student[key]}" class="file-thumb" title="${label}">`;
                } else {
                    link.innerHTML = `<div class="file-thumb" style="display:flex;align-items:center;justify-content:center;background:#eee">${label}</div>`;
                }
                
                const title = document.createElement('span');
                title.textContent = label;
                title.style.fontSize = '12px';
                title.style.color = '#666';

                wrapper.appendChild(link);
                wrapper.appendChild(title);

                // Inline replace control (skip training form; it's generated)
                if (key !== 'training_form_path') {
                    const replaceWrap = document.createElement('div');
                    replaceWrap.className = 'file-replace';
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.accept = 'image/*';
                    input.style.display = 'none';
                    // map db field to upload field name
                    const nameMap = {
                        photo_path: 'photo',
                        diploma_path: 'diploma',
                        cert_path: 'cert',
                        id_card_front_path: 'id_card_front',
                        id_card_back_path: 'id_card_back'
                    };
                    input.name = nameMap[key] || '';
                    const btn = document.createElement('button');
                    btn.className = 'btn secondary';
                    btn.style.padding = '6px 12px';
                    btn.style.fontSize = '0.85rem';
                    btn.textContent = '修改上传';
                    btn.onclick = (e) => {
                        e.preventDefault();
                        input.click();
                    };
                    input.addEventListener('change', () => {
                        const img = link.querySelector('img');
                        const placeholder = null; // not used in inline mode
                        if (img) {
                            // preview selected image into existing thumbnail
                            if (input.files && input.files[0]) {
                                const reader = new FileReader();
                                reader.onload = (ev) => {
                                    img.src = ev.target.result;
                                };
                                reader.readAsDataURL(input.files[0]);
                            }
                        }
                    });
                    replaceWrap.appendChild(btn);
                    replaceWrap.appendChild(input);
                    wrapper.appendChild(replaceWrap);
                }

                filesContainer.appendChild(wrapper);
            }
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
        } else {
            const genBtn = document.createElement('button');
            genBtn.className = 'btn primary';
            genBtn.textContent = '生成材料';
            genBtn.onclick = () => handleGenerate(student.id);
            actionBar.appendChild(genBtn);
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
        const inputs = mainContent.querySelectorAll('.detail-item input');
        inputs.forEach(inp => {
            const key = inp.getAttribute('data-key');
            formData.append(key, inp.value.trim());
        });
        const fileInputs = mainContent.querySelectorAll('.file-replace input[type="file"]');
        fileInputs.forEach(fi => {
            if (fi.files && fi.files[0]) {
                formData.append(fi.name, fi.files[0]);
            }
        });
        try {
            const res = await fetch(`/api/students/${id}`, { method: 'PUT', body: formData });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
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
            if (saveBtn) {
                const prev = saveBtn.textContent;
                saveBtn.disabled = false;
                saveBtn.textContent = '网络错误';
                setTimeout(() => { saveBtn.textContent = prev; }, 1500);
            }
        }
    }

    async function handleApprove(id) {
        if (!confirm('确认审核通过？')) return;
        
        try {
            const res = await fetch(`/api/students/${id}/approve`, { method: 'POST' });
            if (res.ok) {
                alert('审核通过');
                loadStudents();
                mainContent.innerHTML = '<div class="empty-state">操作成功，请选择下一位</div>';
            } else {
                alert('操作失败');
            }
        } catch (e) {
            alert('Error: ' + e);
        }
    }

    async function handleGenerate(id) {
        if (!confirm('确认生成材料？')) return;
        try {
            const res = await fetch(`/api/students/${id}/generate`, { method: 'POST' });
            if (res.ok) {
                alert('已生成材料');
            } else {
                alert('操作失败');
            }
        } catch (e) {
            alert('网络错误');
        }
    }

    async function handleReject(id) {
        if (!confirm('确认审核不通过？该学员将被删除。')) return;
        
        try {
            const res = await fetch(`/api/students/${id}/reject`, { method: 'POST' });
            if (res.ok) {
                alert('已删除该学员。');
                loadStudents();
                mainContent.innerHTML = '<div class="empty-state">已删除，请选择下一位</div>';
            } else {
                alert('操作失败');
            }
        } catch (e) {
            alert('Error: ' + e);
        }
    }
});
