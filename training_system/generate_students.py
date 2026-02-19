#!/usr/bin/env python3
"""
Script to generate random student data for testing purposes.
"""
import os
import random
import sqlite3
import string
import requests
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'students.db')

FIRST_NAMES = [
    '张', '王', '李', '赵', '刘', '陈', '杨', '黄', '周', '吴',
    '徐', '孙', '马', '朱', '胡', '郭', '何', '高', '林', '罗',
    '郑', '梁', '谢', '宋', '唐', '许', '韩', '冯', '邓', '曹'
]

LAST_NAMES = [
    '伟', '芳', '娜', '敏', '静', '丽', '强', '磊', '军', '洋',
    '勇', '艳', '杰', '娟', '涛', '明', '超', '秀英', '霞', '平',
    '刚', '桂英', '琴', '华', '梅', '荣', '健', '燕', '红', '芬'
]

GENDERS = ['男', '女']

EDUCATION_LEVELS = [
    '研究生及以上', '本科或同等学历', '专科或同等学历',
    '中专或同等学历', '高中或同等学历', '初中'
]

JOB_CATEGORIES = [
    '电工作业', '焊接与热切割作业', '高处作业',
    '制冷与空调作业', '金属非金属矿山安全作业',
    '危险化学品安全作业', '烟花爆竹安全作业', '建筑施工安全作业'
]

EXAM_PROJECTS = {
    '电工作业': ['低压电工', '高压电工', '防爆电气作业'],
    '焊接与热切割作业': ['熔化焊接与热切割作业', '压力焊作业', '钎焊作业'],
    '高处作业': ['登高架设作业', '高处安装、维护、拆除作业'],
    '制冷与空调作业': ['制冷与空调设备运行操作作业', '制冷与空调设备安装修理作业'],
    '金属非金属矿山安全作业': ['金属非金属矿井通风作业', '金属非金属矿山安全检查作业'],
    '危险化学品安全作业': ['光气及光气化工艺作业', '氯碱电解工艺作业'],
    '烟花爆竹安全作业': ['烟火药制造作业', '黑火药制造作业'],
    '建筑施工安全作业': ['建筑电工', '建筑架子工', '建筑起重信号司索工']
}

COMPANIES = [
    '阳泉市第一建筑工程有限公司', '阳泉市第二建筑工程有限公司',
    '阳泉市第三建筑工程有限公司', '阳泉市第四建筑工程有限公司',
    '阳泉市第五建筑工程有限公司', '阳泉市第六建筑工程有限公司',
    '阳泉市第七建筑工程有限公司', '阳泉市第八建筑工程有限公司',
    '阳泉市第九建筑工程有限公司', '阳泉市第十建筑工程有限公司',
    '阳泉市电力工程有限公司', '阳泉市热力工程有限公司',
    '阳泉市燃气工程有限公司', '阳泉市水务工程有限公司',
    '阳泉市通信工程有限公司', '阳泉市交通工程有限公司',
    '阳泉市环保工程有限公司', '阳泉市消防工程有限公司',
    '阳泉市安防工程有限公司', '阳泉市智能化工程有限公司'
]

ADDRESS_PREFIXES = [
    '山西省阳泉市城区', '山西省阳泉市矿区', '山西省阳泉市郊区',
    '山西省阳泉市平定县', '山西省阳泉市盂县'
]

def generate_id_card():
    area_code = ''.join(random.choices(string.digits, k=6))
    year = random.randint(1970, 2005)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    birth_date = f'{year:04d}{month:02d}{day:02d}'
    sequence = ''.join(random.choices(string.digits, k=3))
    check_digit = random.choice(list(string.digits) + ['X'])
    return f'{area_code}{birth_date}{sequence}{check_digit}'

def generate_phone():
    prefix = random.choice(['130', '131', '132', '133', '134', '135', '136', '137', '138', '139',
                           '150', '151', '152', '153', '155', '156', '157', '158', '159',
                           '170', '171', '172', '173', '175', '176', '177', '178',
                           '180', '181', '182', '183', '184', '185', '186', '187', '188', '189'])
    suffix = ''.join(random.choices(string.digits, k=8))
    return f'{prefix}{suffix}'

def generate_address():
    prefix = random.choice(ADDRESS_PREFIXES)
    street = random.choice(['胜利街', '解放路', '建设路', '青年路', '光明街', '前进街', '和平街', '友谊街'])
    number = random.randint(1, 100)
    unit = random.randint(1, 10) if random.random() > 0.5 else ''
    room = random.randint(101, 999) if unit else ''
    address = f'{prefix}{street}{number}号'
    if unit:
        address += f'{unit}单元'
    if room:
        address += f'{room}室'
    return address

def generate_exam_code(job_category, exam_project):
    job_abbr = ''.join([c for c in job_category if c.isalpha()])[:2].upper()
    project_abbr = ''.join([c for c in exam_project if c.isalpha()])[:2].upper()
    random_num = ''.join(random.choices(string.digits, k=4))
    return f'{job_abbr}{project_abbr}{random_num}'

def generate_file_path(training_type, company, name, id_card, file_type):
    training_type_map = {
        'special_operation': '特种作业',
        'special_equipment': '特种设备'
    }
    training_type_name = training_type_map.get(training_type, '特种作业')
    file_type_map = {
        'photo': '个人照片',
        'diploma': '学历证书',
        'id_front': '身份证正面',
        'id_back': '身份证反面'
    }
    file_type_name = file_type_map.get(file_type, file_type)
    folder_name = f"{training_type_name}-{company}-{name}"
    file_name = f"{id_card}-{name}-{file_type_name}.jpg"
    return f"students/{folder_name}/{file_name}"

def download_image(url, save_path):
    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded image to {save_path}")
        return True
    except Exception as e:
        print(f"Error downloading image: {e}")
        return False

def get_real_person_photo(gender='male'):
    try:
        api_url = f"https://randomuser.me/api/?inc=picture&gender={gender}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('results') and len(data['results']) > 0:
            picture_url = data['results'][0]['picture']['large']
            return picture_url
    except Exception as e:
        print(f"Error getting real person photo: {e}")
    return None

def generate_student(training_type, gender_cn=None):
    try:
        if gender_cn is None:
            gender_cn = random.choice(GENDERS)
        gender_en = 'male' if gender_cn == '男' else 'female'
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        name = first_name + last_name
        education = random.choice(EDUCATION_LEVELS)
        id_card = generate_id_card()
        phone = generate_phone()
        company = random.choice(COMPANIES)
        company_address = generate_address()
        job_category = random.choice(list(EXAM_PROJECTS.keys()))
        exam_project = random.choice(EXAM_PROJECTS[job_category])
        exam_code = generate_exam_code(job_category, exam_project)
        
        photo_path = generate_file_path(training_type, company, name, id_card, 'photo')
        diploma_path = generate_file_path(training_type, company, name, id_card, 'diploma')
        id_card_front_path = generate_file_path(training_type, company, name, id_card, 'id_front')
        id_card_back_path = generate_file_path(training_type, company, name, id_card, 'id_back')
        
        full_photo_path = os.path.join(os.path.dirname(__file__), photo_path)
        full_diploma_path = os.path.join(os.path.dirname(__file__), diploma_path)
        full_id_card_front_path = os.path.join(os.path.dirname(__file__), id_card_front_path)
        full_id_card_back_path = os.path.join(os.path.dirname(__file__), id_card_back_path)
        
        real_photo_url = get_real_person_photo(gender_en)
        if real_photo_url:
            download_image(real_photo_url, full_photo_path)
        else:
            fallback_url = f"https://ui-avatars.com/api/?name={name}&size=200&background=random"
            download_image(fallback_url, full_photo_path)
        
        diploma_url = f"https://picsum.photos/400/300?random={random.randint(1, 1000)}"
        id_front_url = f"https://picsum.photos/400/250?random={random.randint(1, 1000)}"
        id_back_url = f"https://picsum.photos/400/250?random={random.randint(1, 1000)}"
        
        download_image(diploma_url, full_diploma_path)
        download_image(id_front_url, full_id_card_front_path)
        download_image(id_back_url, full_id_card_back_path)
        
        schools = ['阳泉职业技术学院', '阳泉市第一中学', '阳泉市第二中学', '阳泉市第三中学', '阳泉市第四中学']
        majors = ['电气工程', '机械工程', '土木工程', '计算机科学', '会计学']
        school = random.choice(schools) if random.random() > 0.5 else ''
        major = random.choice(majors) if school else ''
        
        return {
            'name': name,
            'gender': gender_cn,
            'education': education,
            'school': school,
            'major': major,
            'id_card': id_card,
            'phone': phone,
            'company': company,
            'company_address': company_address,
            'job_category': job_category,
            'exam_project': exam_project,
            'exam_code': exam_code,
            'training_type': training_type,
            'photo_path': photo_path,
            'diploma_path': diploma_path,
            'id_card_front_path': id_card_front_path,
            'id_card_back_path': id_card_back_path
        }
    except Exception as e:
        print(f'Error in generate_student: {e}')
        import traceback
        traceback.print_exc()
        raise

def insert_student(conn, student_data):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO students (
            name, gender, education, school, major, id_card, phone, company, company_address,
            job_category, exam_project, exam_code, training_type, status,
            photo_path, diploma_path, id_card_front_path, id_card_back_path,
            training_form_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        student_data['name'], student_data['gender'], student_data['education'],
        student_data['school'], student_data['major'], student_data['id_card'],
        student_data['phone'], student_data['company'], student_data['company_address'],
        student_data['job_category'], student_data['exam_project'], student_data['exam_code'],
        student_data['training_type'], 'unreviewed',
        student_data['photo_path'], student_data['diploma_path'],
        student_data['id_card_front_path'], student_data['id_card_back_path'],
        ''
    ))
    conn.commit()
    return cursor.lastrowid

def main():
    conn = sqlite3.connect(DB_PATH)
    
    try:
        print('Clearing existing data...')
        conn.execute('DELETE FROM students')
        conn.commit()
        print('Existing data cleared successfully!')
        
        print('\nGenerating 20 special operation students...')
        for i in range(20):
            try:
                gender = random.choice(GENDERS)
                student_data = generate_student('special_operation', gender)
                student_id = insert_student(conn, student_data)
                print(f'Generated special operation student {i+1}: ID={student_id}, Name={student_data["name"]}, Gender={student_data["gender"]}')
            except Exception as e:
                print(f'Error generating special operation student {i+1}: {e}')
                conn.rollback()
        
        print('\nGenerating 20 special equipment students...')
        for i in range(20):
            try:
                gender = random.choice(GENDERS)
                student_data = generate_student('special_equipment', gender)
                student_id = insert_student(conn, student_data)
                print(f'Generated special equipment student {i+1}: ID={student_id}, Name={student_data["name"]}, Gender={student_data["gender"]}')
            except Exception as e:
                print(f'Error generating special equipment student {i+1}: {e}')
                conn.rollback()
        
        print('\nAll students generated successfully!')
        
    except Exception as e:
        print(f'Error generating students: {e}')
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    main()
