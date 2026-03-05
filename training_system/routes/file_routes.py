"""
文件服务路由。

本模块提供学员附件文件的静态文件访问服务。

API 端点:
    GET /students/<path:filename> - 访问学员附件文件

文件存储结构:
    students/
    ├── 特种作业-公司名-姓名/
    │   ├── 身份证号-姓名-个人照片.jpg
    │   ├── 身份证号-姓名-学历证书.jpg
    │   ├── 身份证号-姓名-身份证正面.jpg
    │   └── ...
    └── 特种设备-公司名-姓名/
        └── ...

安全说明:
    此路由在 app.py 的 before_request 中间件中被列为白名单，
    无需认证即可访问。这是因为文件路径包含身份证号和姓名，
    不易被猜测，且文件内容为学员自行上传的资料。
"""
from flask import Blueprint, current_app, send_from_directory
import os


# 创建文件服务蓝图
file_bp = Blueprint('file', __name__)


@file_bp.route('/students/<path:filename>')
def serve_students(filename):
    """
    提供学员文件夹中的文件访问。

    URL 路径格式: /students/<学员文件夹>/<文件名>
    例如: /students/特种设备-阳泉市公司-张三/123456789012345678-张三-个人照片.jpg

    参数:
        filename (str): 相对于 students 目录的文件路径

    返回:
        200: 文件内容
        404: 文件不存在
    """
    try:
        # 解析路径：分为学员文件夹名和实际文件名两部分
        parts = filename.split('/', 1)
        if len(parts) == 2:
            # 标准路径：students/<文件夹>/<文件名>
            student_folder, actual_filename = parts
            return send_from_directory(
                os.path.join(current_app.config['STUDENTS_FOLDER'], student_folder),
                actual_filename
            )
        else:
            # 简单路径：直接在 students 目录下查找
            return send_from_directory(current_app.config['STUDENTS_FOLDER'], filename)

    except Exception as e:
        current_app.logger.error(f'Error serving student file {filename}: {str(e)}')
        return "文件未找到", 404
