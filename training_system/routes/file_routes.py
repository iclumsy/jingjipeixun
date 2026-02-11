"""File serving routes."""
from flask import Blueprint, send_from_directory, current_app
import os


file_bp = Blueprint('file', __name__)


@file_bp.route('/uploads/<path:filename>')
def serve_uploads(filename):
    """Serve files from uploads folder."""
    try:
        # Check if file exists in old uploads folder
        if os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], filename)):
            return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

        # Try students folder structure
        parts = filename.split('/', 1)
        if len(parts) == 2:
            student_folder, actual_filename = parts
            student_path = os.path.join(
                current_app.config['STUDENTS_FOLDER'],
                student_folder,
                actual_filename
            )
            if os.path.exists(student_path):
                return send_from_directory(
                    os.path.join(current_app.config['STUDENTS_FOLDER'], student_folder),
                    actual_filename
                )

        return "File not found", 404

    except Exception as e:
        current_app.logger.error(f'Error serving upload file {filename}: {str(e)}')
        return "File not found", 404


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
