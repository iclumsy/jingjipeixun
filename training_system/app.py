import os
import sqlite3
import shutil
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from docx import Document
from werkzeug.utils import secure_filename
import re

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['REVIEWED_FOLDER'] = os.path.join(BASE_DIR, 'reviewed_students')
app.config['DATABASE'] = os.path.join(BASE_DIR, 'database/students.db')
app.config['TEMPLATE_PATH'] = os.path.join(BASE_DIR, 'template.docx')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REVIEWED_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'database'), exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
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
            status TEXT DEFAULT 'unreviewed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            photo_path TEXT,
            diploma_path TEXT,
            cert_path TEXT,
            id_card_front_path TEXT,
            id_card_back_path TEXT,
            training_form_path TEXT,
            theory_exam_time TEXT,
            practical_exam_time TEXT,
            passed TEXT,
            theory_makeup_time TEXT,
            makeup_exam TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/students', methods=['POST'])
def create_student():
    try:
        data = request.form
        files = request.files
        
        # Server-side validation (required fields and patterns)
        required_fields = ['name', 'gender', 'education', 'id_card', 'phone', 'job_category', 'exam_category']
        errors = {}
        for f in required_fields:
            if not data.get(f):
                errors[f] = '必填项'
        if 'gender' in data and data.get('gender') not in ['男', '女']:
            errors['gender'] = '性别须为“男”或“女”'
        if 'id_card' in data and not re.fullmatch(r'\d{17}[\dXx]', data.get('id_card', '')):
            errors['id_card'] = '身份证号格式不正确'
        if 'phone' in data and not re.fullmatch(r'\d{11}', data.get('phone', '')):
            errors['phone'] = '手机号格式不正确'
        if errors:
            return jsonify({'error': 'validation_failed', 'fields': errors}), 400
        
        # Save files
        file_paths = {}
        # Map input names to DB column keys
        file_map = {
            'photo': 'photo_path',
            'diploma': 'diploma_path',
            'cert': 'cert_path',
            'id_card_front': 'id_card_front_path',
            'id_card_back': 'id_card_back_path'
        }
        
        for input_name, db_key in file_map.items():
            file = files.get(input_name)
            if file and file.filename:
                filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                # Save to absolute path
                abs_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(abs_path)
                # Save relative path to database
                file_paths[db_key] = f"uploads/{filename}"
            else:
                file_paths[db_key] = ""
        
        # training_form is generated, not collected
        file_paths['training_form_path'] = ""

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO students (
                name, gender, education, school, major, id_card, phone,
                company, company_address, job_category, exam_project, exam_code,
                exam_category, photo_path, diploma_path, cert_path, id_card_front_path, id_card_back_path, training_form_path,
                theory_exam_time, practical_exam_time, passed, theory_makeup_time, makeup_exam
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['gender'], data['education'], data.get('school', ''), data.get('major', ''),
            data['id_card'], data['phone'], data.get('company', ''), data.get('company_address', ''),
            data['job_category'], data.get('exam_project', ''), data.get('exam_code', ''), data['exam_category'],
            file_paths['photo_path'], file_paths['diploma_path'], file_paths['cert_path'],
            file_paths['id_card_front_path'], file_paths['id_card_back_path'], file_paths['training_form_path'],
            data.get('theory_exam_time', ''), data.get('practical_exam_time', ''), data.get('passed', ''),
            data.get('theory_makeup_time', ''), data.get('makeup_exam', '')
        ))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Student added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students', methods=['GET'])
def get_students():
    status = request.args.get('status', 'unreviewed')
    search = request.args.get('search', '')
    company = request.args.get('company', '')
    passed = request.args.get('passed', '')
    examined = request.args.get('examined', '')
    
    conn = get_db_connection()
    
    # Base query
    if status == 'examined':
        # Special case for examined status
        query = "SELECT * FROM students WHERE ((theory_exam_time IS NOT NULL AND theory_exam_time != '') OR (practical_exam_time IS NOT NULL AND practical_exam_time != ''))"
        params = []
    else:
        query = "SELECT * FROM students WHERE status = ?"
        params = [status]
    
    if search:
        query += " AND (name LIKE ? OR id_card LIKE ? OR phone LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    
    if company:
        query += " AND company LIKE ?"
        params.append(f"%{company}%")
    
    if passed:
        query += " AND passed = ?"
        params.append(passed)
    
    if examined and status != 'examined':
        query += " AND ((theory_exam_time IS NOT NULL AND theory_exam_time != '') OR (practical_exam_time IS NOT NULL AND practical_exam_time != ''))"
        
    students = conn.execute(query, params).fetchall()
    conn.close()
    
    return jsonify([dict(s) for s in students])

@app.route('/api/students/<int:id>', methods=['PUT', 'PATCH'])
def update_student(id):
    allowed_text = [
        'name', 'gender', 'education', 'school', 'major', 'id_card', 'phone',
        'company', 'company_address', 'job_category', 'exam_project', 'exam_code',
        'exam_category', 'theory_exam_time', 'practical_exam_time', 'passed',
        'theory_makeup_time', 'makeup_exam'
    ]
    file_map = {
        'photo': 'photo_path',
        'diploma': 'diploma_path',
        'cert': 'cert_path',
        'id_card_front': 'id_card_front_path',
        'id_card_back': 'id_card_back_path'
    }
    conn = get_db_connection()
    current = conn.execute('SELECT * FROM students WHERE id = ?', (id,)).fetchone()
    if not current:
        conn.close()
        return jsonify({'error': 'Student not found'}), 404
    updates = {}
    # Prefer form data when present (multipart), else JSON
    if request.form:
        data = request.form
        for k in allowed_text:
            if k in data:
                updates[k] = data[k]
        # Validate present text fields (partial update)
        errors = {}
        if 'gender' in data and data.get('gender') not in ['男', '女']:
            errors['gender'] = '性别须为“男”或“女”'
        if 'id_card' in data and not re.fullmatch(r'\d{17}[\dXx]', data.get('id_card', '')):
            errors['id_card'] = '身份证号格式不正确'
        if 'phone' in data and not re.fullmatch(r'\d{11}', data.get('phone', '')):
            errors['phone'] = '手机号格式不正确'
        if errors:
            conn.close()
            return jsonify({'error': 'validation_failed', 'fields': errors}), 400
        for input_name, db_key in file_map.items():
            f = request.files.get(input_name)
            if f and f.filename:
                filename = secure_filename(f"{datetime.now().timestamp()}_{f.filename}")
                abs_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                f.save(abs_path)
                # delete old file if exists
                old_rel = current[db_key]
                if old_rel:
                    old_fn = os.path.basename(old_rel)
                    old_abs = os.path.join(app.config['UPLOAD_FOLDER'], old_fn)
                    if os.path.exists(old_abs):
                        try:
                            os.remove(old_abs)
                        except Exception:
                            pass
                updates[db_key] = f"uploads/{filename}"
    else:
        payload = request.get_json(silent=True) or {}
        for k in allowed_text:
            if k in payload:
                updates[k] = payload[k]
        # Validate present text fields (partial update)
        errors = {}
        if 'gender' in payload and payload.get('gender') not in ['男', '女']:
            errors['gender'] = '性别须为“男”或“女”'
        if 'id_card' in payload and not re.fullmatch(r'\d{17}[\dXx]', payload.get('id_card', '')):
            errors['id_card'] = '身份证号格式不正确'
        if 'phone' in payload and not re.fullmatch(r'\d{11}', payload.get('phone', '')):
            errors['phone'] = '手机号格式不正确'
        if errors:
            conn.close()
            return jsonify({'error': 'validation_failed', 'fields': errors}), 400
    if not updates:
        conn.close()
        return jsonify({'error': 'no fields to update'}), 400
    sets = ', '.join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values()) + [id]
    conn.execute(f"UPDATE students SET {sets} WHERE id = ?", values)
    conn.commit()
    student = conn.execute('SELECT * FROM students WHERE id = ?', (id,)).fetchone()
    conn.close()
    return jsonify(dict(student))

@app.route('/api/students/<int:id>/reject', methods=['POST'])
def reject_student(id):
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE id = ?', (id,)).fetchone()
    
    if not student:
        conn.close()
        return jsonify({'error': 'Student not found'}), 404
        
    # Delete files
    for key in ['photo_path', 'diploma_path', 'cert_path', 'id_card_front_path', 'id_card_back_path', 'training_form_path']:
        if student[key]:
            # Construct absolute path from relative DB path
            # DB stores "uploads/filename", we need "/abs/path/to/uploads/filename"
            # But UPLOAD_FOLDER is "/abs/path/to/uploads"
            # So we strip "uploads/" from student[key] or use basename
            filename = os.path.basename(student[key])
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            
    conn.execute('DELETE FROM students WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Student rejected and deleted'})

@app.route('/api/students/<int:id>/approve', methods=['POST'])
def approve_student(id):
    conn = get_db_connection()
    exists = conn.execute('SELECT id FROM students WHERE id = ?', (id,)).fetchone()
    if not exists:
        conn.close()
        return jsonify({'error': 'Student not found'}), 404
    conn.execute("UPDATE students SET status = 'reviewed' WHERE id = ?", (id,))
    conn.commit()
    student = conn.execute('SELECT * FROM students WHERE id = ?', (id,)).fetchone()
    conn.close()
    return jsonify(dict(student))

@app.route('/api/students/<int:id>/generate', methods=['POST'])
def generate_materials(id):
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE id = ?', (id,)).fetchone()
    if not student:
        conn.close()
        return jsonify({'error': 'Student not found'}), 404
    folder_name = f"{student['id_card']}{student['name']}"
    student_dir = os.path.join(app.config['REVIEWED_FOLDER'], folder_name)
    os.makedirs(student_dir, exist_ok=True)
    file_mapping = {
        'training_form_path': f"{student['id_card']}-培训信息登记表.jpg",
        'diploma_path': f"{student['id_card']}-学历证书复印件.jpg",
        'cert_path': f"{student['id_card']}-所持证件复印件.jpg",
        'id_card_front_path': f"{student['id_card']}-身份证正面.jpg",
        'id_card_back_path': f"{student['id_card']}-身份证反面.jpg",
        'photo_path': f"{student['name']}.jpg"
    }
    for db_field, target_name in file_mapping.items():
        db_path = student[db_field]
        if db_path:
            filename = os.path.basename(db_path)
            src_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(src_path):
                _, ext = os.path.splitext(src_path)
                base_target_name = os.path.splitext(target_name)[0]
                final_target_name = base_target_name + ext
                shutil.copy2(src_path, os.path.join(student_dir, final_target_name))
    doc_path = os.path.join(student_dir, "复审纸质资料.docx")
    photo_abs_path = None
    if student['photo_path']:
        filename = os.path.basename(student['photo_path'])
        photo_abs_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    generate_word_doc(app.config['TEMPLATE_PATH'], doc_path, student, photo_abs_path)
    conn.close()
    return jsonify({'message': 'materials generated'})

def generate_word_doc(template_path, output_path, data, photo_path=None):
    doc = Document(template_path)
    
    # 1. Text Replacement (Preserving Style)
    replacements = {
        '姓　名': data['name'],
        '姓名': data['name'],
        '性别': data['gender'],
        '文化程度': data['education'],
        '身份证号': data['id_card'],
        '移动电话': data['phone'],
        '手机号': data['phone'],
        '工作单位': data['company'],
        '作业类别': data['job_category'],
        '操作项目': data['exam_project']
    }
    
    for table in doc.tables:
        for row in table.rows:
            for i, cell in enumerate(row.cells):
                text = cell.text.strip()
                if text in replacements:
                    # Look for the next cell
                    if i + 1 < len(row.cells):
                        target_cell = row.cells[i+1]
                        
                        # Safety check: Don't overwrite if the target cell is also a known label
                        # This prevents issues with merged cells or repeated labels like "移动电话 | 移动电话"
                        if target_cell.text.strip() in replacements:
                            continue
                            
                        new_val = replacements[text]
                        
                        # Replace text in the first run of the first paragraph to preserve formatting
                        if target_cell.paragraphs:
                            p = target_cell.paragraphs[0]
                            if p.runs:
                                p.runs[0].text = new_val
                                # Clear other runs in this paragraph
                                for r in p.runs[1:]:
                                    r.text = ''
                            else:
                                # No runs, add one (formatting might be default, but better than nothing)
                                p.add_run(new_val)
                                
                            # Clear other paragraphs in the cell
                            for p in target_cell.paragraphs[1:]:
                                p.clear()
                        else:
                            target_cell.text = new_val
    
    # 2. Image Replacement (Replace rId4 which is likely the photo)
    if photo_path and os.path.exists(photo_path):
        try:
            # We assume the photo is rId4 based on inspection
            # A more robust way would be to search for the blip again, but let's try the direct approach first
            # compatible with the template structure
            
            # Find the blip rel ID from paragraphs (since we saw it in Paragraph 8)
            blip_rid = None
            for p in doc.paragraphs:
                xml = p._element.xml
                if 'r:embed="' in xml:
                    import re
                    match = re.search(r'r:embed="([^"]+)"', xml)
                    if match:
                        blip_rid = match.group(1)
                        break
            
            if blip_rid:
                with open(photo_path, 'rb') as f:
                    img_data = f.read()
                
                # Access the relationship and replace the target part's blob
                if blip_rid in doc.part.rels:
                    doc.part.rels[blip_rid].target_part._blob = img_data
        except Exception as e:
            print(f"Error replacing image: {e}")
            
    doc.save(output_path)

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/reviewed_students/<path:filename>')
def serve_reviewed(filename):
    return send_from_directory(app.config['REVIEWED_FOLDER'], filename)

@app.route('/api/companies', methods=['GET'])
def get_companies():
    conn = get_db_connection()
    companies = conn.execute('SELECT DISTINCT company FROM students WHERE company IS NOT NULL AND company != "" ORDER BY company').fetchall()
    conn.close()
    return jsonify([dict(c)['company'] for c in companies])

@app.route('/api/students/batch/approve', methods=['POST'])
def batch_approve_students():
    try:
        data = request.get_json()
        if not data or 'ids' not in data:
            return jsonify({'error': 'Missing student IDs'}), 400
        
        ids = data['ids']
        if not isinstance(ids, list):
            return jsonify({'error': 'IDs must be a list'}), 400
        
        conn = get_db_connection()
        
        # Update status for all selected students
        placeholders = ','.join(['?'] * len(ids))
        query = f"UPDATE students SET status = 'reviewed' WHERE id IN ({placeholders})"
        conn.execute(query, ids)
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'Successfully approved {len(ids)} students'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/batch/reject', methods=['POST'])
def batch_reject_students():
    try:
        data = request.get_json()
        if not data or 'ids' not in data:
            return jsonify({'error': 'Missing student IDs'}), 400
        
        ids = data['ids']
        if not isinstance(ids, list):
            return jsonify({'error': 'IDs must be a list'}), 400
        
        conn = get_db_connection()
        
        # Get all students to delete
        placeholders = ','.join(['?'] * len(ids))
        students = conn.execute(f"SELECT * FROM students WHERE id IN ({placeholders})", ids).fetchall()
        
        # Delete files for each student
        for student in students:
            for key in ['photo_path', 'diploma_path', 'cert_path', 'id_card_front_path', 'id_card_back_path', 'training_form_path']:
                if student[key]:
                    filename = os.path.basename(student[key])
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
        
        # Delete students from database
        conn.execute(f"DELETE FROM students WHERE id IN ({placeholders})", ids)
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'Successfully rejected and deleted {len(ids)} students'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/batch/delete', methods=['POST'])
def batch_delete_students():
    try:
        data = request.get_json()
        if not data or 'ids' not in data:
            return jsonify({'error': 'Missing student IDs'}), 400
        
        ids = data['ids']
        if not isinstance(ids, list):
            return jsonify({'error': 'IDs must be a list'}), 400
        
        conn = get_db_connection()
        
        # Get all students to delete
        placeholders = ','.join(['?'] * len(ids))
        students = conn.execute(f"SELECT * FROM students WHERE id IN ({placeholders})", ids).fetchall()
        
        # Delete files for each student
        for student in students:
            for key in ['photo_path', 'diploma_path', 'cert_path', 'id_card_front_path', 'id_card_back_path', 'training_form_path']:
                if student[key]:
                    filename = os.path.basename(student[key])
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
        
        # Delete students from database
        conn.execute(f"DELETE FROM students WHERE id IN ({placeholders})", ids)
        conn.commit()
        conn.close()
        
        return jsonify({'message': f'Successfully deleted {len(ids)} students'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
