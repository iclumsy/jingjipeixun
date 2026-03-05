"""文件服务路由。"""
from flask import Blueprint, current_app, send_from_directory
import os


file_bp = Blueprint('file', __name__)  # 文件蓝图


@file_bp.route('/students/<path:filename>')
def serve_students(filename):
    """提供学员文件夹中的文件访问。"""
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
        return "文件未找到", 404
