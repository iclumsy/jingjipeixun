"""Student model and database operations."""
import sqlite3
import os
from contextlib import contextmanager
from flask import current_app
from utils.error_handlers import DatabaseError, NotFoundError


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
                exam_code TEXT,
                exam_category TEXT NOT NULL,
                status TEXT DEFAULT 'unreviewed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                photo_path TEXT,
                diploma_path TEXT,
                cert_front_path TEXT,
                cert_back_path TEXT,
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
    except sqlite3.Error as e:
        raise DatabaseError(f'Failed to initialize database: {str(e)}')
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
                company, company_address, job_category, exam_project, exam_code,
                exam_category, photo_path, diploma_path, cert_front_path, cert_back_path,
                id_card_front_path, id_card_back_path, training_form_path,
                theory_exam_time, practical_exam_time, passed, theory_makeup_time, makeup_exam
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['gender'], data['education'], data.get('school', ''),
            data.get('major', ''), data['id_card'], data['phone'], data.get('company', ''),
            data.get('company_address', ''), data['job_category'], data.get('exam_project', ''),
            data.get('exam_code', ''), data['exam_category'],
            file_paths.get('photo_path', ''), file_paths.get('diploma_path', ''),
            file_paths.get('cert_front_path', ''), file_paths.get('cert_back_path', ''),
            file_paths.get('id_card_front_path', ''), file_paths.get('id_card_back_path', ''),
            file_paths.get('training_form_path', ''),
            data.get('theory_exam_time', ''), data.get('practical_exam_time', ''),
            data.get('passed', ''), data.get('theory_makeup_time', ''), data.get('makeup_exam', '')
        ))
        return cursor.lastrowid


def get_students(status='unreviewed', search='', company='', passed='', examined=''):
    """
    Get students with optional filters.

    Args:
        status: Student status filter
        search: Search term for name, ID card, or phone
        company: Company name filter
        passed: Pass status filter
        examined: Examined status filter

    Returns:
        list: List of student records as dictionaries
    """
    with get_db_connection() as conn:
        # Base query
        if status == 'examined':
            query = """SELECT * FROM students
                      WHERE ((theory_exam_time IS NOT NULL AND theory_exam_time != '')
                      OR (practical_exam_time IS NOT NULL AND practical_exam_time != ''))"""
            params = []
        else:
            query = "SELECT * FROM students WHERE status = ?"
            params = [status]

            # For 'reviewed' status, exclude students who have already taken exams
            if status == 'reviewed':
                query += """ AND ((theory_exam_time IS NULL OR theory_exam_time = '')
                            AND (practical_exam_time IS NULL OR practical_exam_time = ''))"""

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
            query += """ AND ((theory_exam_time IS NOT NULL AND theory_exam_time != '')
                        OR (practical_exam_time IS NOT NULL AND practical_exam_time != ''))"""

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


def get_companies(status='', company_filter='', passed=''):
    """
    Get distinct company names with optional filters.

    Args:
        status: Student status filter
        company_filter: Company name filter
        passed: Pass status filter

    Returns:
        list: List of company names
    """
    with get_db_connection() as conn:
        query = """SELECT DISTINCT company FROM students
                  WHERE company IS NOT NULL AND company != ''"""
        params = []

        # Handle status filter
        if status == 'examined':
            query += """ AND ((theory_exam_time IS NOT NULL AND theory_exam_time != '')
                        OR (practical_exam_time IS NOT NULL AND practical_exam_time != ''))"""
        elif status:
            query += " AND status = ?"
            params.append(status)
            if status == 'reviewed':
                query += """ AND ((theory_exam_time IS NULL OR theory_exam_time = '')
                            AND (practical_exam_time IS NULL OR practical_exam_time = ''))"""

        if company_filter:
            query += " AND company LIKE ?"
            params.append(f"%{company_filter}%")

        if passed:
            query += " AND passed = ?"
            params.append(passed)

        query += " ORDER BY company"

        companies = conn.execute(query, params).fetchall()
        return [dict(c)['company'] for c in companies]

