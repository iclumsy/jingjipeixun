document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('students-container');
    const template = document.getElementById('student-template');
    const addBtn = document.getElementById('addStudentBtn');
    const submitBtn = document.getElementById('submitBtn');
    const form = document.getElementById('collectionForm');
    const actions = document.querySelector('.actions');

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
            alert(`成功提交 ${successCount} 位学员信息！`);
            addStudent(); // Reset with one empty form
        } else {
            alert(`提交完成。成功: ${successCount}, 失败: ${failCount}。请检查失败条目。`);
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
    }

    window.removeStudent = function(btn) {
        if (container.children.length > 1) {
            btn.closest('.student-entry').remove();
        } else {
            alert('至少保留一个学员信息框。');
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
        inputs.forEach(input => {
            input.classList.remove('error');
            const parent = input.closest('.form-group') || input.parentElement;
            let pop = parent.querySelector('.error-pop');
            if (pop) pop.remove();
            if (!input.checkValidity()) {
                input.classList.add('error');
                isValid = false;
                const msgText = input.title || input.validationMessage || '请填写此字段';
                pop = document.createElement('span');
                pop.className = 'error-pop';
                pop.textContent = msgText;
                parent.appendChild(pop);
                const labelEl = parent.querySelector('label');
                const nameMap = {
                    'photo': '个人照片',
                    'diploma': '学历证书',
                    'cert': '所持证件',
                    'id_card_front': '身份证正面',
                    'id_card_back': '身份证反面'
                };
                const labelText = labelEl ? labelEl.textContent.trim() : (nameMap[input.name] || input.name);
                errors.push({ input, label: labelText, message: msgText });
                input.addEventListener('input', () => {
                    if (input.checkValidity()) {
                        input.classList.remove('error');
                        const p = parent.querySelector('.error-pop');
                        if (p) p.remove();
                    }
                });
                input.addEventListener('change', () => {
                    if (input.checkValidity()) {
                        input.classList.remove('error');
                        const p = parent.querySelector('.error-pop');
                        if (p) p.remove();
                    }
                });
            }
        });
        return { valid: isValid, errors };
    }

    function attachEntryValidation(entry) {
        const inputs = entry.querySelectorAll('input, select');
        inputs.forEach(input => {
            const parent = input.closest('.form-group') || input.parentElement;
            const showError = () => {
                input.classList.remove('error');
                const exist = parent.querySelector('.error-pop');
                if (exist) exist.remove();
                if (!input.checkValidity()) {
                    input.classList.add('error');
                    const msgText = input.title || input.validationMessage || '请填写此字段';
                    const pop = document.createElement('span');
                    pop.className = 'error-pop';
                    pop.textContent = msgText;
                    parent.appendChild(pop);
                }
            };
            input.addEventListener('input', showError);
            input.addEventListener('blur', showError);
            input.addEventListener('change', showError);
        });
    }
});
