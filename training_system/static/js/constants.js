const ExamProjectOptions = {
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

const EducationOptions = [
    { value: '', text: '请选择' },
    { value: '研究生及以上', text: '研究生及以上' },
    { value: '本科或同等学历', text: '本科或同等学历' },
    { value: '专科或同等学历', text: '专科或同等学历' },
    { value: '中专或同等学历', text: '中专或同等学历' },
    { value: '高中或同等学历', text: '高中或同等学历' },
    { value: '初中', text: '初中' }
];

const JobCategoryOptions = [
    { value: '', text: '请选择' },
    { value: '电工作业', text: '电工作业' },
    { value: '焊接与热切割作业', text: '焊接与热切割作业' },
    { value: '高处作业', text: '高处作业' }
];

const ExamCategoryOptions = [
    { value: '初次领证', text: '初次领证' },
    { value: '复审', text: '复审' },
    { value: '延期换证', text: '延期换证' }
];

const FileLabelNameMap = {
    'photo': '个人照片',
    'diploma': '学历证书',
    'cert_front': '所持证件正面',
    'cert_back': '所持证件反面',
    'id_card_front': '身份证正面',
    'id_card_back': '身份证反面'
};

function updateExamProjectOptions(categorySelect, projectSelectId) {
    const projectSelect = document.getElementById(projectSelectId);
    const selectedCategory = categorySelect.value;
    
    projectSelect.innerHTML = '<option value="">请选择操作项目</option>';
    
    // Use config from backend API if available
    if (window.jobCategoriesConfig && selectedCategory) {
        const category = window.jobCategoriesConfig.find(c => c.name === selectedCategory);
        if (category && category.exam_projects) {
            category.exam_projects.forEach(project => {
                const optionElement = document.createElement('option');
                optionElement.value = project;
                optionElement.textContent = project;
                projectSelect.appendChild(optionElement);
            });
        }
    } else if (selectedCategory && ExamProjectOptions[selectedCategory]) {
        // Fallback to static config
        ExamProjectOptions[selectedCategory].forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option.value;
            optionElement.textContent = option.text;
            projectSelect.appendChild(optionElement);
        });
    }
}
