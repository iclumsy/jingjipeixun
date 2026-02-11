"""Main application entry point."""
import os
import shutil
from flask import Flask, render_template
from models.student import init_db
from routes.student_routes import student_bp
from routes.file_routes import file_bp
from routes.export_routes import export_bp
from utils.logger import setup_logger
from utils.error_handlers import register_error_handlers


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Configuration
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    app.config['BASE_DIR'] = BASE_DIR
    app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
    app.config['STUDENTS_FOLDER'] = os.path.join(BASE_DIR, 'students')
    app.config['DATABASE'] = os.path.join(BASE_DIR, 'database/students.db')
    app.config['TEMPLATE_PATH'] = os.path.join(
        BASE_DIR,
        '特种设备作业人员考试体检表（锅炉水处理、客运索道司机）-杜臻.docx'
    )
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['STUDENTS_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'database'), exist_ok=True)

    # Initialize database
    init_db(app.config['DATABASE'])

    # Setup logging
    setup_logger(app)

    # Register error handlers
    register_error_handlers(app)

    # Register blueprints
    app.register_blueprint(student_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(export_bp)

    # Main routes
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/admin')
    def admin():
        return render_template('admin.html')

    # Run migration if needed
    _run_migration_if_needed(app)

    app.logger.info('Application initialized successfully')

    return app


def _run_migration_if_needed(app):
    """Run data migration if not already completed."""
    migration_marker = os.path.join(app.config['BASE_DIR'], '.migration_complete')

    if not os.path.exists(migration_marker):
        app.logger.info('Running data migration...')
        try:
            _migrate_existing_files(app)
            with open(migration_marker, 'w') as f:
                f.write('Migration completed on startup')
            app.logger.info('Migration completed successfully')
        except Exception as e:
            app.logger.error(f'Migration failed: {str(e)}')


def _migrate_existing_files(app):
    """
    Migrate existing file paths in the database to the new structure.
    Move files from uploads/ and old students/<id_card><name>/ to students/<company>-<name>/.
    """
    import sqlite3

    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    students = conn.execute("SELECT * FROM students").fetchall()

    for student in students:
        id_card = student['id_card']
        name = student['name']
        company = student['company'] or '未知公司'
        student_folder_name = f"{company}-{name}"
        student_folder_path = os.path.join(app.config['STUDENTS_FOLDER'], student_folder_name)
        os.makedirs(student_folder_path, exist_ok=True)

        file_fields = [
            'photo_path', 'diploma_path', 'cert_front_path', 'cert_back_path',
            'id_card_front_path', 'id_card_back_path', 'training_form_path'
        ]

        updates = {}
        for field in file_fields:
            old_path = student[field]
            if old_path and old_path.startswith('uploads/') and not old_path.startswith('students/'):
                filename = os.path.basename(old_path)
                old_abs_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

                if os.path.exists(old_abs_path):
                    new_file_path = os.path.join(student_folder_path, filename)
                    shutil.move(old_abs_path, new_file_path)
                    new_rel_path = f"students/{student_folder_name}/{filename}"
                    updates[field] = new_rel_path

            elif old_path and old_path.startswith('students/'):
                parts = old_path.split('/', 2)
                if len(parts) >= 2:
                    old_folder_name = parts[1]

                    if old_folder_name.startswith(id_card):
                        old_file_path = os.path.join(app.config['BASE_DIR'], old_path)

                        if os.path.exists(old_file_path):
                            new_file_path = os.path.join(student_folder_path, os.path.basename(old_file_path))
                            os.makedirs(student_folder_path, exist_ok=True)
                            shutil.move(old_file_path, new_file_path)
                            new_rel_path = f"students/{student_folder_name}/{os.path.basename(old_file_path)}"
                            updates[field] = new_rel_path

        # Apply updates
        if updates:
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values()) + [student['id']]
            conn.execute(f"UPDATE students SET {set_clause} WHERE id = ?", values)

    # Clean up old folders
    for student in students:
        id_card = student['id_card']
        name = student['name']
        company = student['company'] or '未知公司'
        new_folder_name = f"{company}-{name}"
        old_folder_name = f"{id_card}{name}"
        old_folder_path = os.path.join(app.config['STUDENTS_FOLDER'], old_folder_name)

        if os.path.exists(old_folder_path) and os.path.isdir(old_folder_path):
            new_folder_path = os.path.join(app.config['STUDENTS_FOLDER'], new_folder_name)
            for item in os.listdir(old_folder_path):
                src_path = os.path.join(old_folder_path, item)
                dst_path = os.path.join(new_folder_path, item)

                if os.path.isfile(src_path) and not os.path.exists(dst_path):
                    shutil.move(src_path, dst_path)

            if os.path.isdir(old_folder_path) and not os.listdir(old_folder_path):
                os.rmdir(old_folder_path)

    conn.commit()
    conn.close()


# Create application instance
app = create_app()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'migrate':
        print("开始运行迁移函数...")
        _migrate_existing_files(app)
        print("迁移完成！")
    else:
        # Use environment variable for debug mode
        debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        app.run(debug=debug_mode, host='0.0.0.0', port=5001)
