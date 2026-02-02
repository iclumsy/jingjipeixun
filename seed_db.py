import sqlite3
import os
import shutil

def seed_data():
    # 1. Create dummy images in uploads folder
    upload_dir = 'training_system/uploads'
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    # Create simple colored squares as dummy images
    dummy_files = {
        'photo.jpg': b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00d\x00d\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfd\xfc\xa2\x8a(\xa0\x0f', # Minimal valid JPG header
        'id_front.jpg': b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00d\x00d\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfd\xfc\xa2\x8a(\xa0\x0f',
        'id_back.jpg': b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00d\x00d\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfd\xfc\xa2\x8a(\xa0\x0f'
    }

    for name, content in dummy_files.items():
        with open(os.path.join(upload_dir, f"test_{name}"), 'wb') as f:
            f.write(content)

    # 2. Insert test data
    students = [
        ('张三', '男', '本科', '山西大学', '电气工程', '140302199001011234', '13800138000', '阳泉煤业', '阳泉市矿区', '电工作业', '高压电工作业', '101', '初次领证', 'uploads/test_photo.jpg', '', '', 'uploads/test_id_front.jpg', 'uploads/test_id_back.jpg', 'unreviewed'),
        ('李四', '女', '大专', '太原电力专科', '机电一体化', '140302199505055678', '13900139000', '阳泉供电公司', '阳泉市城区', '电工作业', '低压电工作业', '102', '复审', 'uploads/test_photo.jpg', 'uploads/test_photo.jpg', '', 'uploads/test_id_front.jpg', 'uploads/test_id_back.jpg', 'unreviewed'),
        ('王五', '男', '高中', '', '', '140302198508089012', '13700137000', '个体户', '阳泉市郊区', '高处作业', '高处安装、维护、拆除作业', '201', '延期换证', 'uploads/test_photo.jpg', '', 'uploads/test_photo.jpg', 'uploads/test_id_front.jpg', 'uploads/test_id_back.jpg', 'unreviewed')
    ]

    # Ensure database directory exists
    db_path = 'training_system/database/students.db'
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Ensure table exists (in case app hasn't run yet)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT NOT NULL,
            education TEXT NOT NULL,
            school TEXT,
            major TEXT,
            id_card TEXT NOT NULL,
            phone TEXT NOT NULL,
            company TEXT,
            company_address TEXT,
            job_category TEXT NOT NULL,
            exam_project TEXT,
            exam_code TEXT,
            exam_category TEXT NOT NULL,
            photo_path TEXT,
            diploma_path TEXT,
            cert_path TEXT,
            id_card_front_path TEXT,
            id_card_back_path TEXT,
            training_form_path TEXT,
            status TEXT DEFAULT 'unreviewed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.executemany('''
        INSERT INTO students (
            name, gender, education, school, major, id_card, phone,
            company, company_address, job_category, exam_project, exam_code,
            exam_category, photo_path, diploma_path, cert_path, id_card_front_path, id_card_back_path, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', students)

    conn.commit()
    conn.close()
    print("Database seeded with 3 test students.")

if __name__ == '__main__':
    seed_data()
