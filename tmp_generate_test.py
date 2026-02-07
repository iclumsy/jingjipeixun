import os
from training_system.app import get_db_connection, generate_word_doc, app

conn = get_db_connection()
student = conn.execute('SELECT * FROM students WHERE id = ?', (1,)).fetchone()
conn.close()
if not student:
    print('student id=1 not found')
    raise SystemExit(1)
folder_name = f"{student['id_card']}{student['name']}"
base_dir = os.path.dirname(os.path.abspath(__file__))
student_dir = os.path.join(base_dir, 'training_system', 'reviewed_students', folder_name)
os.makedirs(student_dir, exist_ok=True)
doc_path = os.path.join(student_dir, f"{student['id_card']}-体检表.docx")
photo_abs_path = None
if student['photo_path']:
    filename = os.path.basename(student['photo_path'])
    photo_abs_path = os.path.join(base_dir, 'training_system', 'uploads', filename)
print('template:', app.config['TEMPLATE_PATH'])
print('output:', doc_path)
print('photo:', photo_abs_path)
generate_word_doc(app.config['TEMPLATE_PATH'], doc_path, student, photo_abs_path)
print('done')
