document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('students-container');
    const template = document.getElementById('student-template');
    const addBtn = document.getElementById('addStudentBtn');
    const submitBtn = document.getElementById('submitBtn');

    // Add initial student
    addStudent();

    addBtn.addEventListener('click', addStudent);

    submitBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        
        const entries = document.querySelectorAll('.student-entry');
        let allValid = true;
        
        // Validate all first
        entries.forEach(entry => {
            if (!validateEntry(entry)) {
                allValid = false;
            }
        });

        if (!allValid) {
            // alert('请检查红色框标记的字段，填写正确后再提交。');
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
            const reader = new FileReader();
            
            reader.onload = function(e) {
                img.src = e.target.result;
                img.style.display = 'block';
                placeholder.style.display = 'none';
            }
            
            reader.readAsDataURL(input.files[0]);
        } else {
            img.style.display = 'none';
            img.src = '';
            placeholder.style.display = 'block';
        }
    };

    function validateEntry(entry) {
        let isValid = true;
        const inputs = entry.querySelectorAll('input, select');
        
        inputs.forEach(input => {
            // Reset
            input.classList.remove('error');
            const parent = input.parentElement;
            let pop = parent.querySelector('.error-pop');
            if (pop) pop.remove();
            
            // Check validity
            if (!input.checkValidity()) {
                input.classList.add('error');
                isValid = false;

                // Floating error tooltip
                const msgText = input.validity.patternMismatch && input.title
                    ? input.title
                    : (input.validationMessage || input.title || '请填写此字段');
                pop = document.createElement('span');
                pop.className = 'error-pop';
                pop.textContent = msgText;
                parent.appendChild(pop);
                
                // Add listener to remove error on input
                input.addEventListener('input', () => {
                    if (input.checkValidity()) {
                        input.classList.remove('error');
                        const p = parent.querySelector('.error-pop');
                        if (p) p.remove();
                    }
                });
            }
        });
        
        return isValid;
    }

    function attachEntryValidation(entry) {
        const inputs = entry.querySelectorAll('input, select');
        inputs.forEach(input => {
            const parent = input.parentElement;
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
            if (input.type === 'file') {
                input.addEventListener('change', showError);
            }
        });
    }
});
