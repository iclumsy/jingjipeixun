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
                training_type TEXT DEFAULT 'special_operation',
                status TEXT DEFAULT 'unreviewed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                photo_path TEXT,
                diploma_path TEXT,
                cert_front_path TEXT,
                cert_back_path TEXT,
                id_card_front_path TEXT,
                id_card_back_path TEXT,
                training_form_path TEXT
                training_form_path TEXT
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(f'Failed to initialize database: {str(e)}')
    finally:
        conn.close()


def migrate_db(database_path):
    """
    Migrate the database to add missing fields.

    Args:
        database_path: Path to the database file
    """
    conn = sqlite3.connect(database_path)
    try:
        # Check if training_type column exists
        cursor = conn.execute("PRAGMA table_info(students)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'training_type' not in columns:
            # Add training_type column with default value
            conn.execute("ALTER TABLE students ADD COLUMN training_type TEXT DEFAULT 'special_operation'")
            conn.commit()
        
        # Modify exam_category column to allow NULL values
        # First, check if exam_category column exists and is NOT NULL
        cursor = conn.execute("PRAGMA table_info(students)")
        for row in cursor.fetchall():
            if row[1] == 'exam_category' and row[3] == 1:  # 1 means NOT NULL
                # Create a new table without NOT NULL constraint
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS students_new (
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
                        exam_category TEXT,
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
                        makeup_exam TEXT,
                        cert_front_path TEXT,
                        cert_back_path TEXT,
                        training_type TEXT DEFAULT 'special_operation'
                    )
                ''')
                # Copy data from old table to new table
                conn.execute('''
                    INSERT INTO students_new (
                        id, name, gender, education, school, major, id_card, phone,
                        company, company_address, job_category, exam_project, exam_code, exam_category,
                        status, created_at, photo_path, diploma_path, cert_path,
                        id_card_front_path, id_card_back_path, training_form_path, theory_exam_time,
                        practical_exam_time, passed, theory_makeup_time, makeup_exam,
                        cert_front_path, cert_back_path, training_type
                    ) SELECT 
                        id, name, gender, education, school, major, id_card, phone,
                        company, company_address, job_category, exam_project, exam_code, exam_category,
                        status, created_at, photo_path, diploma_path, cert_path,
                        id_card_front_path, id_card_back_path, training_form_path, theory_exam_time,
                        practical_exam_time, passed, theory_makeup_time, makeup_exam,
                        cert_front_path, cert_back_path, training_type
                    FROM students
                ''')
                # Drop old table
                conn.execute("DROP TABLE students")
                # Rename new table to old table
                conn.execute("ALTER TABLE students_new RENAME TO students")
                conn.commit()
                break
    except sqlite3.Error as e:
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
                company, company_address, job_category, exam_project, exam_code, exam_category,
                training_type, photo_path, diploma_path, cert_front_path, cert_back_path,
                id_card_front_path, id_card_back_path, training_form_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['gender'], data['education'], data.get('school', ''),
            data.get('major', ''), data['id_card'], data['phone'], data.get('company', ''),
            data.get('company_address', ''), data['job_category'], data.get('exam_project', ''),
            data.get('exam_code', ''), data.get('exam_category', ''),
            data.get('training_type', 'special_operation'),
            file_paths.get('photo_path', ''), file_paths.get('diploma_path', ''),
            file_paths.get('cert_front_path', ''), file_paths.get('cert_back_path', ''),
            file_paths.get('id_card_front_path', ''), file_paths.get('id_card_back_path', ''),
            file_paths.get('training_form_path', '')
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

