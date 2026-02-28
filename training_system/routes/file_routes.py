"""File serving routes."""
from flask import Blueprint, current_app, send_from_directory
import os


file_bp = Blueprint('file', __name__)


@file_bp.route('/students/<path:filename>')
def serve_students(filename):
    """Serve files from students folder."""
    try:
        parts = filename.split('/', 1)
        if len(parts) == 2:
            student_folder, actual_filename = parts
            return send_from_directory(
                os.path.join(current_app.config['STUDENTS_FOLDER'], student_folder),
                actual_filename
            )
        else:
            return send_from_directory(current_app.config['STUDENTS_FOLDER'], filename)

    except Exception as e:
        current_app.logger.error(f'Error serving student file {filename}: {str(e)}')
        return "File not found", 404
