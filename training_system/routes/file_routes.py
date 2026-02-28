"""File serving routes."""
from flask import Blueprint, current_app, g, send_from_directory
import os
from models.student import get_student_by_file_path


file_bp = Blueprint('file', __name__)


@file_bp.route('/students/<path:filename>')
def serve_students(filename):
    """Serve files from students folder."""
    try:
        mini_user = getattr(g, 'mini_user', None)
        if mini_user and not bool(mini_user.get('is_admin')):
            normalized_filename = str(filename or '').replace('\\', '/')
            rel_path = f"students/{normalized_filename}"
            owner = get_student_by_file_path(rel_path)
            if not owner:
                return "Forbidden", 403
            owner_openid = str(owner.get('submitter_openid', '') or '').strip()
            current_openid = str(mini_user.get('openid', '') or '').strip()
            if not owner_openid or owner_openid != current_openid:
                return "Forbidden", 403

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
