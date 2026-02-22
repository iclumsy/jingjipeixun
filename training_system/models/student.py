"""Student model and database operations."""
import sqlite3
import os
import json
import shutil
from datetime import datetime
from contextlib import contextmanager
from flask import current_app
from utils.error_handlers import DatabaseError, NotFoundError

STUDENTS_TABLE_COLUMNS = [
    'id', 'name', 'gender', 'education', 'school', 'major', 'id_card', 'phone',
    'company', 'company_address', 'job_category', 'exam_project', 'project_code',
    'training_type', 'status', 'created_at', 'photo_path', 'diploma_path',
    'id_card_front_path', 'id_card_back_path', 'hukou_residence_path',
    'hukou_personal_path', 'training_form_path'
]

OBSOLETE_COLUMNS = [
    'exam_code', 'exam_category', 'cert_path', 'theory_exam_time',
    'practical_exam_time', 'passed', 'theory_makeup_time', 'makeup_exam',
    'cert_front_path', 'cert_back_path'
]

SPECIAL_EQUIPMENT_CATEGORIES = [
    '特种设备安全管理',
    '锅炉作业',
    '压力容器作业',
    '起重机作业',
    '场(厂)内专用机动车辆作业'
]

SPECIAL_OPERATION_CATEGORIES = [
    '电工作业',
    '焊接与热切割作业',
    '高处作业'
]


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Ensures connections are properly closed.
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


def init_db(database_path):
    """
    Initialize the database with required tables.

    Args:
        database_path: Path to the database file
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
                training_form_path TEXT
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(f'Failed to initialize database: {str(e)}')
    finally:
        conn.close()


def _get_student_columns(conn):
    cursor = conn.execute("PRAGMA table_info(students)")
    return [row[1] for row in cursor.fetchall()]


def _snapshot_migration_state(conn):
    columns = _get_student_columns(conn)
    has_training_type = 'training_type' in columns

    def missing_expr(col_name, alias):
        if col_name in columns:
            return f"SUM(CASE WHEN {col_name} IS NULL OR {col_name}='' THEN 1 ELSE 0 END) AS {alias}"
        return f"0 AS {alias}"

    def equipment_missing_expr(col_name, alias):
        if has_training_type and col_name in columns:
            return f"SUM(CASE WHEN training_type='special_equipment' AND ({col_name} IS NULL OR {col_name}='') THEN 1 ELSE 0 END) AS {alias}"
        return f"0 AS {alias}"

    special_equipment_expr = "SUM(CASE WHEN training_type='special_equipment' THEN 1 ELSE 0 END)" if has_training_type else "0"
    special_operation_expr = "SUM(CASE WHEN training_type='special_operation' THEN 1 ELSE 0 END)" if has_training_type else "0"

    stats_query = f"""
        SELECT
            COUNT(*) AS total,
            {special_equipment_expr} AS special_equipment_count,
            {special_operation_expr} AS special_operation_count,
            {missing_expr('training_type', 'missing_training_type_count')},
            {missing_expr('project_code', 'missing_project_code_count')},
            {missing_expr('diploma_path', 'missing_diploma_count')},
            {missing_expr('id_card_front_path', 'missing_id_card_front_count')},
            {missing_expr('id_card_back_path', 'missing_id_card_back_count')},
            {equipment_missing_expr('photo_path', 'equipment_missing_photo_count')},
            {equipment_missing_expr('hukou_residence_path', 'equipment_missing_hukou_residence_count')},
            {equipment_missing_expr('hukou_personal_path', 'equipment_missing_hukou_personal_count')}
        FROM students
    """
    stats = conn.execute(stats_query).fetchone()
    result = dict(stats) if stats else {}
    result['columns'] = columns
    return result


def _build_new_table(conn):
    conn.execute("DROP TABLE IF EXISTS students_new")
    conn.execute(
        '''
        CREATE TABLE students_new (
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
            training_form_path TEXT
        )
        '''
    )


def _rebuild_students_table(conn, current_columns):
    _build_new_table(conn)

    select_cols = []
    for col in STUDENTS_TABLE_COLUMNS:
        if col in current_columns:
            select_cols.append(col)
        elif col == 'project_code' and 'exam_code' in current_columns:
            select_cols.append('exam_code AS project_code')
        elif col == 'id_card_front_path' and 'cert_front_path' in current_columns:
            select_cols.append('cert_front_path AS id_card_front_path')
        elif col == 'id_card_back_path' and 'cert_back_path' in current_columns:
            select_cols.append('cert_back_path AS id_card_back_path')
        elif col == 'training_type':
            select_cols.append("'special_operation' AS training_type")
        elif col == 'status':
            select_cols.append("'unreviewed' AS status")
        elif col == 'created_at':
            select_cols.append("CURRENT_TIMESTAMP AS created_at")
        else:
            select_cols.append(f"'' AS {col}")

    conn.execute(
        f"""
        INSERT INTO students_new ({', '.join(STUDENTS_TABLE_COLUMNS)})
        SELECT {', '.join(select_cols)} FROM students
        """
    )
    conn.execute("DROP TABLE students")
    conn.execute("ALTER TABLE students_new RENAME TO students")


def _normalize_students_data(conn):
    equipment_placeholders = ','.join(['?'] * len(SPECIAL_EQUIPMENT_CATEGORIES))
    operation_placeholders = ','.join(['?'] * len(SPECIAL_OPERATION_CATEGORIES))
    conn.execute(
        f"""
        UPDATE students
        SET training_type = CASE
            WHEN job_category IN ({equipment_placeholders}) THEN 'special_equipment'
            WHEN job_category IN ({operation_placeholders}) THEN 'special_operation'
            ELSE 'special_operation'
        END
        WHERE training_type IS NULL
           OR training_type = ''
           OR training_type NOT IN ('special_operation', 'special_equipment')
        """,
        SPECIAL_EQUIPMENT_CATEGORIES + SPECIAL_OPERATION_CATEGORIES
    )
    conn.execute("UPDATE students SET project_code = '' WHERE project_code IS NULL")
    conn.execute("UPDATE students SET status = 'unreviewed' WHERE status IS NULL OR status = ''")


def migrate_db(database_path, create_backup=False, report_path=None):
    """
    Migrate students table structure and normalize legacy data.

    Args:
        database_path: Path to the database file
        create_backup: Whether to create backup before migration
        report_path: Optional report output path (JSON)

    Returns:
        dict: Migration report
    """
    if not os.path.exists(database_path):
        raise DatabaseError(f'Database file not found: {database_path}')

    backup_path = ''
    if create_backup:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{database_path}.bak.{timestamp}"
        shutil.copy2(database_path, backup_path)

    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    try:
        before = _snapshot_migration_state(conn)
        columns = before.get('columns', [])

        has_obsolete_columns = any(col in columns for col in OBSOLETE_COLUMNS)
        has_missing_columns = any(col not in columns for col in STUDENTS_TABLE_COLUMNS)
        rebuilt = False

        if has_obsolete_columns or has_missing_columns:
            _rebuild_students_table(conn, columns)
            rebuilt = True

        _normalize_students_data(conn)
        conn.commit()

        after = _snapshot_migration_state(conn)
        report = {
            'database_path': database_path,
            'backup_path': backup_path,
            'rebuilt_table': rebuilt,
            'before': before,
            'after': after,
            'removed_columns': [col for col in columns if col not in after.get('columns', [])],
            'added_columns': [col for col in after.get('columns', []) if col not in columns]
        }

        if report_path:
            report_dir = os.path.dirname(report_path)
            if report_dir:
                os.makedirs(report_dir, exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f'Failed to migrate database: {str(e)}')
    finally:
        conn.close()


def create_student(data, file_paths):
    """
    Create a new student record.

    Args:
        data: Dictionary containing student data
        file_paths: Dictionary containing file paths

    Returns:
        int: ID of the created student
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO students (
                name, gender, education, school, major, id_card, phone,
                company, company_address, job_category, exam_project, project_code,
                training_type, photo_path, diploma_path,
                id_card_front_path, id_card_back_path,
                hukou_residence_path, hukou_personal_path, training_form_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['gender'], data['education'], data.get('school', ''),
            data.get('major', ''), data['id_card'], data['phone'], data.get('company', ''),
            data.get('company_address', ''), data['job_category'], data.get('exam_project', ''),
            data.get('project_code', ''),
            data.get('training_type', 'special_operation'),
            file_paths.get('photo_path', ''), file_paths.get('diploma_path', ''),
            file_paths.get('id_card_front_path', ''), file_paths.get('id_card_back_path', ''),
            file_paths.get('hukou_residence_path', ''), file_paths.get('hukou_personal_path', ''),
            file_paths.get('training_form_path', '')
        ))
        return cursor.lastrowid


def get_students(status='unreviewed', search='', company='', training_type=''):
    """
    Get students with optional filters.

    Args:
        status: Student status filter
        search: Search term for name, ID card, or phone
        company: Company name filter
        training_type: Training type filter

    Returns:
        list: List of student records as dictionaries
    """
    with get_db_connection() as conn:
        # Base query
        query = "SELECT * FROM students WHERE status = ?"
        params = [status]
        query = "SELECT * FROM students WHERE status = ?"
        params = [status]

        if training_type:
            query += " AND training_type = ?"
            params.append(training_type)

        if search:
            query += " AND (name LIKE ? OR id_card LIKE ? OR phone LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        if company:
            query += " AND company LIKE ?"
            params.append(f"%{company}%")

        students = conn.execute(query, params).fetchall()
        return [dict(s) for s in students]


def get_student_by_id(student_id):
    """
    Get a student by ID.

    Args:
        student_id: Student ID

    Returns:
        dict: Student record

    Raises:
        NotFoundError: If student not found
    """
    with get_db_connection() as conn:
        student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        if not student:
            raise NotFoundError('Student not found')
        return dict(student)


def update_student(student_id, updates):
    """
    Update a student record.

    Args:
        student_id: Student ID
        updates: Dictionary of fields to update

    Returns:
        dict: Updated student record
    """
    if not updates:
        raise DatabaseError('No fields to update')

    with get_db_connection() as conn:
        # Check if student exists
        student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        if not student:
            raise NotFoundError('Student not found')

        # Build update query
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [student_id]
        conn.execute(f"UPDATE students SET {set_clause} WHERE id = ?", values)

        # Return updated student
        updated = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        return dict(updated)


def delete_student(student_id):
    """
    Delete a student record.

    Args:
        student_id: Student ID

    Returns:
        dict: Deleted student record (for cleanup purposes)
    """
    with get_db_connection() as conn:
        student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
        if not student:
            raise NotFoundError('Student not found')

        conn.execute('DELETE FROM students WHERE id = ?', (student_id,))
        return dict(student)


def delete_students_batch(student_ids):
    """
    Delete multiple students.

    Args:
        student_ids: List of student IDs

    Returns:
        list: List of deleted student records
    """
    with get_db_connection() as conn:
        placeholders = ','.join(['?'] * len(student_ids))
        students = conn.execute(
            f"SELECT * FROM students WHERE id IN ({placeholders})",
            student_ids
        ).fetchall()

        conn.execute(f"DELETE FROM students WHERE id IN ({placeholders})", student_ids)
        return [dict(s) for s in students]


def approve_student(student_id):
    """
    Approve a student (change status to 'reviewed').

    Args:
        student_id: Student ID

    Returns:
        dict: Updated student record
    """
    return update_student(student_id, {'status': 'reviewed'})


def approve_students_batch(student_ids):
    """
    Approve multiple students.

    Args:
        student_ids: List of student IDs
    """
    with get_db_connection() as conn:
        placeholders = ','.join(['?'] * len(student_ids))
        conn.execute(
            f"UPDATE students SET status = 'reviewed' WHERE id IN ({placeholders})",
            student_ids
        )


def get_companies(status='', company_filter='', training_type=''):
    """
    Get distinct company names with optional filters.

    Args:
        status: Student status filter
        company_filter: Company name filter
        training_type: Training type filter

    Returns:
        list: List of company names
    """
    with get_db_connection() as conn:
        query = """SELECT DISTINCT company FROM students
                  WHERE company IS NOT NULL AND company != ''"""
        params = []

        # Handle status filter
        if status:
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
