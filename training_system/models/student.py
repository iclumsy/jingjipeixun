"""学员模型与数据库操作。"""
import sqlite3
from contextlib import contextmanager
from flask import current_app
from utils.error_handlers import DatabaseError, NotFoundError


@contextmanager
def get_db_connection():
    """
    数据库连接上下文管理器。
    确保连接被正确关闭。
    """
    conn = None
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'])
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        current_app.logger.error(f'Database error: {str(e)}')
        raise DatabaseError(f'Database operation failed: {str(e)}')
    finally:
        if conn:
            conn.close()


def _ensure_column_exists(conn, table_name, column_name, column_definition):
    """在列缺失时自动添加，用于轻量级模式迁移。"""
    columns = conn.execute(f'PRAGMA table_info({table_name})').fetchall()
    existed = any(str(col[1]) == column_name for col in columns)
    if not existed:
        conn.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_definition}')


def init_db(database_path):
    """
    初始化数据库，创建必要的表。

    参数:
        database_path: 数据库文件路径
    """
    conn = sqlite3.connect(database_path)
    try:
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
                project_code TEXT,
                training_type TEXT DEFAULT 'special_operation',
                status TEXT DEFAULT 'unreviewed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                photo_path TEXT,
                diploma_path TEXT,
                id_card_front_path TEXT,
                id_card_back_path TEXT,
                hukou_residence_path TEXT,
                hukou_personal_path TEXT,
                training_form_path TEXT,
                submitter_openid TEXT
            )
        ''')
        _ensure_column_exists(conn, 'students', 'submitter_openid', 'submitter_openid TEXT')
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_students_status_training_company "
            "ON students(status, training_type, company)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_students_submitter_openid "
            "ON students(submitter_openid)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_students_created_at_desc "
            "ON students(created_at DESC)"
        )
        conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(f'Failed to initialize database: {str(e)}')
    finally:
        conn.close()


def create_student(data, file_paths):
    """
    创建新的学员记录。

    参数:
        data: 包含学员数据的字典
        file_paths: 包含文件路径的字典

    返回:
        int: 创建的学员 ID
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO students (
                name, gender, education, school, major, id_card, phone,
                company, company_address, job_category, exam_project, project_code,
                training_type, photo_path, diploma_path,
                id_card_front_path, id_card_back_path,
                hukou_residence_path, hukou_personal_path, training_form_path, submitter_openid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['gender'], data['education'], data.get('school', ''),
            data.get('major', ''), data['id_card'], data['phone'], data.get('company', ''),
            data.get('company_address', ''), data['job_category'], data.get('exam_project', ''),
            data.get('project_code', ''),
            data.get('training_type', 'special_operation'),
            file_paths.get('photo_path', ''), file_paths.get('diploma_path', ''),
            file_paths.get('id_card_front_path', ''), file_paths.get('id_card_back_path', ''),
            file_paths.get('hukou_residence_path', ''), file_paths.get('hukou_personal_path', ''),
            file_paths.get('training_form_path', ''), data.get('submitter_openid', '')
        ))
        return cursor.lastrowid


def get_students(status='unreviewed', search='', company='', training_type='', submitter_openid=''):
    """
    获取学员列表，支持可选筛选条件。

    参数:
        status: 学员状态筛选
        search: 按姓名、身份证号、手机号搜索
        company: 公司名称筛选
        training_type: 培训类型筛选

    返回:
        list: 学员记录字典列表
    """
    with get_db_connection() as conn:
        query = "SELECT * FROM students WHERE 1=1"
        params = []

        if status:
            if status == 'pending':
                query += " AND status IN (?, ?)"
                params.extend(['unreviewed', 'rejected'])
            else:
                query += " AND status = ?"
                params.append(status)

        if training_type:
            query += " AND training_type = ?"
            params.append(training_type)

        if search:
            query += " AND (name LIKE ? OR id_card LIKE ? OR phone LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        if company:
            query += " AND company LIKE ?"
            params.append(f"%{company}%")

        if submitter_openid:
            query += " AND submitter_openid = ?"
            params.append(submitter_openid)

        query += " ORDER BY id DESC"

        students = conn.execute(query, params).fetchall()
        return [dict(s) for s in students]


def get_student_by_id(student_id):
    """
    根据 ID 获取学员。

    参数:
        student_id: 学员 ID

    返回:
        dict: 学员记录

    异常:
        NotFoundError: 学员不存在时抛出
    """
    with get_db_connection() as conn:
        student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        if not student:
            raise NotFoundError('学员不存在')
        return dict(student)



def update_student(student_id, updates):
    """
    更新学员记录。

    参数:
        student_id: 学员 ID
        updates: 要更新的字段字典

    返回:
        dict: 更新后的学员记录
    """
    if not updates:
        raise DatabaseError('没有要更新的字段')

    with get_db_connection() as conn:
        # 检查学员是否存在
        student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        if not student:
            raise NotFoundError('学员不存在')

        # 构建更新 SQL
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [student_id]
        conn.execute(f"UPDATE students SET {set_clause} WHERE id = ?", values)

        # 返回更新后的学员记录
        updated = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        return dict(updated)


def delete_student(student_id):
    """
    删除学员记录。

    参数:
        student_id: 学员 ID

    返回:
        dict: 被删除的学员记录（用于清理文件）
    """
    with get_db_connection() as conn:
        student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        if not student:
            raise NotFoundError('学员不存在')

        conn.execute('DELETE FROM students WHERE id = ?', (student_id,))
        return dict(student)


def approve_student(student_id):
    """
    审核通过学员（将状态改为 'reviewed'）。

    参数:
        student_id: 学员 ID

    返回:
        dict: 更新后的学员记录
    """
    return update_student(student_id, {'status': 'reviewed'})


def get_companies(status='', company_filter='', training_type=''):
    """
    获取去重后的公司名称列表，支持可选筛选条件。

    参数:
        status: 学员状态筛选
        company_filter: 公司名称筛选
        training_type: 培训类型筛选

    返回:
        list: 公司名称列表
    """
    with get_db_connection() as conn:
        query = """SELECT DISTINCT company FROM students
                  WHERE company IS NOT NULL AND company != ''"""
        params = []

        # 处理状态筛选
        if status:
            if status == 'pending':
                query += " AND status IN (?, ?)"
                params.extend(['unreviewed', 'rejected'])
            else:
                query += " AND status = ?"
                params.append(status)

        if training_type:
            query += " AND training_type = ?"
            params.append(training_type)

        if company_filter:
            query += " AND company LIKE ?"
            params.append(f"%{company_filter}%")

        query += " ORDER BY company"

        companies = conn.execute(query, params).fetchall()
        return [dict(c)['company'] for c in companies]
