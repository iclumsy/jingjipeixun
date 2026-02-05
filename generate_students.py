#!/usr/bin/env python3
import sqlite3
import os
import random
from datetime import datetime, timedelta

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'training_system', 'database', 'students.db')

# Sample data
COMPANIES = [
    '阳泉市电力公司',
    '山西省建筑工程有限公司',
    '阳泉煤业集团',
    '山西省机械制造有限公司',
    '阳泉市热力公司',
    '山西省化工集团',
    '阳泉市自来水公司',
    '山西省交通运输有限公司',
    '阳泉市燃气公司',
    '山西省冶金工业有限公司'
]

JOB_CATEGORIES = [
    '电工作业',
    '熔化焊接与热切割作业',
    '高处作业',
    '制冷与空调作业',
    '冶金（有色）生产安全作业',
    '煤矿安全作业',
    '金属非金属矿山安全作业',
    '危险化学品安全作业'
]

EXAM_CATEGORIES = [
    '初次领证',
    '复审',
    '延期换证'
]

EDUCATION_LEVELS = [
    '初中',
    '高中',
    '中专',
    '大专',
    '本科',
    '研究生'
]

# Generate random Chinese name
def generate_name():
    surnames = ['张', '王', '李', '赵', '刘', '陈', '杨', '黄', '周', '吴', '徐', '孙', '马', '朱', '胡', '郭', '何', '高', '林', '罗']
    names = ['伟', '芳', '娜', '敏', '静', '丽', '强', '磊', '军', '洋', '勇', '艳', '杰', '娟', '涛', '明', '超', '秀英', '霞', '平']
    return random.choice(surnames) + random.choice(names)

# Generate random ID card number
def generate_id_card():
    # 18-digit ID card number
    area_code = random.choice(['140302', '140303', '140311', '140312', '140321', '140322'])
    birth_year = str(random.randint(1970, 2000))
    birth_month = str(random.randint(1, 12)).zfill(2)
    birth_day = str(random.randint(1, 28)).zfill(2)
    sequence = str(random.randint(100, 999))
    check_digit = str(random.randint(0, 9))
    return area_code + birth_year + birth_month + birth_day + sequence + check_digit

# Generate random phone number
def generate_phone():
    return '1' + str(random.randint(3, 9)) + ''.join([str(random.randint(0, 9)) for _ in range(9)])

# Generate random date
def generate_date():
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2026, 12, 31)
    delta = end_date - start_date
    random_days = random.randint(0, delta.days)
    return (start_date + timedelta(days=random_days)).strftime('%Y-%m-%d')

# Insert students into database
def insert_students():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for i in range(20):
        name = generate_name()
        gender = random.choice(['男', '女'])
        education = random.choice(EDUCATION_LEVELS)
        school = f"{random.choice(['山西', '阳泉', '太原'])}{random.choice(['大学', '学院', '职业技术学院'])}" if random.random() > 0.3 else ''
        major = random.choice(['电气工程', '机械工程', '土木工程', '化学工程', '计算机科学', '工商管理']) if school else ''
        id_card = generate_id_card()
        phone = generate_phone()
        company = random.choice(COMPANIES)
        company_address = f'{random.choice(["山西省", "阳泉市"])}{random.choice(["城区", "矿区", "郊区", "平定县", "盂县"])}{random.choice(["街道", "路", "巷"])}{random.randint(1, 100)}号'
        job_category = random.choice(JOB_CATEGORIES)
        exam_project = random.choice(['低压电工', '高压电工', '焊接与热切割', '高处安装、维护、拆除', '制冷与空调设备运行操作', '制冷与空调设备安装修理'])
        exam_code = f'{random.randint(1000, 9999)}'
        exam_category = random.choice(EXAM_CATEGORIES)
        status = random.choice(['unreviewed', 'reviewed'])
        
        # Exam-related fields
        theory_exam_time = generate_date() if status == 'reviewed' and random.random() > 0.3 else ''
        practical_exam_time = generate_date() if status == 'reviewed' and random.random() > 0.3 else ''
        passed = random.choice(['是', '否']) if status == 'reviewed' else ''
        theory_makeup_time = generate_date() if status == 'reviewed' and passed == '否' and random.random() > 0.5 else ''
        makeup_exam = '是' if theory_makeup_time else '否' if status == 'reviewed' else ''
        
        cursor.execute('''
            INSERT INTO students (
                name, gender, education, school, major, id_card, phone,
                company, company_address, job_category, exam_project, exam_code,
                exam_category, status, theory_exam_time, practical_exam_time, passed, theory_makeup_time, makeup_exam
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name, gender, education, school, major, id_card, phone,
            company, company_address, job_category, exam_project, exam_code,
            exam_category, status, theory_exam_time, practical_exam_time, passed, theory_makeup_time, makeup_exam
        ))
    
    conn.commit()
    conn.close()
    print(f'Successfully inserted 20 students into the database.')

if __name__ == '__main__':
    insert_students()
