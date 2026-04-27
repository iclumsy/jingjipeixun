"""
文件服务路由。

本模块提供学员附件文件的静态文件访问服务，以及后台文件浏览功能。

API 端点:
    GET /students/<path:filename>          - 访问学员附件文件
    GET /api/files/browse                  - 列出 students/ 下所有文件夹
    GET /api/files/browse/<path:folder>    - 列出指定文件夹内的文件

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
    /api/files/browse 系列端点受 session 认证保护。
"""
from flask import Blueprint, current_app, jsonify, redirect, request, send_from_directory
from models.student import get_db_connection
from services import storage_service
import os
import sqlite3


# 创建文件服务蓝图
file_bp = Blueprint('file', __name__)


@file_bp.route('/students/<path:filename>')
def serve_students(filename):
    """
    提供学员文件夹中的文件访问。

    cos/dual 模式：302 重定向到 COS 公网 URL，由 COS 直接提供文件。
                  COS 对象须设置 Content-Disposition: inline（通过 fix_cos_headers 脚本）。
    local 模式：从本地磁盘服务，强制 Content-Disposition: inline。

    参数:
        filename (str): 相对于 students 目录的文件路径

    返回:
        302: 重定向到 COS URL（cos/dual 模式）
        200: 文件内容（local 模式，带 inline 头）
        404: 文件不存在
    """
    try:
        backend = storage_service._get_backend()

        if backend in ('cos', 'dual'):
            # COS/双写模式：重定向到 COS 公网 URL（COS 对象已设置 inline 元数据）
            url = storage_service.get_url(f'students/{filename}')
            if url.startswith('https://'):
                if request.query_string:
                    separator = '&' if '?' in url else '?'
                    url = f"{url}{separator}{request.query_string.decode('utf-8', errors='ignore')}"
                return redirect(url, code=302)

        # local 模式（或 COS 未配置降级）：本地服务 + 强制内联预览
        parts = filename.split('/', 1)
        if len(parts) == 2:
            student_folder, actual_filename = parts
            resp = send_from_directory(
                os.path.join(current_app.config['STUDENTS_FOLDER'], student_folder),
                actual_filename
            )
        else:
            resp = send_from_directory(current_app.config['STUDENTS_FOLDER'], filename)

        resp.headers['Content-Disposition'] = 'inline'
        return resp

    except Exception as e:
        current_app.logger.error(f'Error serving student file {filename}: {str(e)}')
        return "文件未找到", 404



# ======================== 图片扩展名集合 ========================
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}


def _get_dir_size(path):
    """递归计算目录总大小（字节）。"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total += entry.stat(follow_symlinks=False).st_size
            elif entry.is_dir(follow_symlinks=False):
                total += _get_dir_size(entry.path)
    except PermissionError:
        pass
    return total


def _count_files(path):
    """递归统计目录内文件数量。"""
    count = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                count += 1
            elif entry.is_dir(follow_symlinks=False):
                count += _count_files(entry.path)
    except PermissionError:
        pass
    return count


def _format_size(size_bytes):
    """将字节数转为可读字符串。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _build_student_lookup():
    """
    从数据库加载所有学员，构建 (姓名, 公司) -> student_id 的查找字典。
    同时构建 姓名 -> [student_id, ...] 的备用查找。
    """
    name_company_map = {}
    name_map = {}
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                'SELECT id, name, company, training_type FROM students'
            ).fetchall()
            for row in rows:
                r = dict(row)
                key = (r['name'], r.get('company', ''))
                name_company_map[key] = r['id']
                name_map.setdefault(r['name'], []).append(r['id'])
    except Exception:
        pass
    return name_company_map, name_map


def _match_folder_to_student(folder_name, name_company_map, name_map):
    """
    尝试将文件夹名匹配到数据库学员记录。
    文件夹名格式: 培训类型-公司名-姓名
    返回 (matched: bool, student_id: int|None)
    """
    parts = folder_name.split('-', 2)
    if len(parts) == 3:
        company = parts[1]
        name = parts[2]
        # 精确匹配：姓名 + 公司
        sid = name_company_map.get((name, company))
        if sid:
            return True, sid
        # 备用：仅姓名匹配
        ids = name_map.get(name, [])
        if ids:
            return True, ids[0]
    return False, None


@file_bp.route('/api/files/browse')
def browse_folders():
    """
    列出 students/ 下所有子项（文件夹和文件）。
    返回每个文件夹的名称、大小、文件数、是否匹配数据库学员。
    """
    students_dir = current_app.config['STUDENTS_FOLDER']
    if not os.path.isdir(students_dir):
        return jsonify([])

    name_company_map, name_map = _build_student_lookup()
    items = []

    try:
        for entry in sorted(os.scandir(students_dir), key=lambda e: e.name):
            if entry.is_dir(follow_symlinks=False):
                full_path = entry.path
                size = _get_dir_size(full_path)
                file_count = _count_files(full_path)
                matched, student_id = _match_folder_to_student(
                    entry.name, name_company_map, name_map
                )
                stat = entry.stat(follow_symlinks=False)
                items.append({
                    'name': entry.name,
                    'type': 'directory',
                    'size': size,
                    'size_display': _format_size(size),
                    'file_count': file_count,
                    'matched': matched,
                    'student_id': student_id,
                    'modified': stat.st_mtime,
                })
            elif entry.is_file(follow_symlinks=False):
                stat = entry.stat(follow_symlinks=False)
                items.append({
                    'name': entry.name,
                    'type': 'file',
                    'size': stat.st_size,
                    'size_display': _format_size(stat.st_size),
                    'modified': stat.st_mtime,
                })
    except Exception as e:
        current_app.logger.error(f'Error browsing students folder: {e}')
        return jsonify({'error': str(e)}), 500

    return jsonify(items)


@file_bp.route('/api/files/browse/<path:folder_name>')
def browse_folder_contents(folder_name):
    """
    列出指定文件夹内的文件和子文件夹。
    支持多级路径，如 "学员文件夹/子文件夹"。
    """
    students_dir = current_app.config['STUDENTS_FOLDER']
    target_dir = os.path.normpath(os.path.join(students_dir, folder_name))

    # 防止路径穿越
    if not target_dir.startswith(os.path.normpath(students_dir)):
        return jsonify({'error': '非法路径'}), 403

    if not os.path.isdir(target_dir):
        return jsonify({'error': '文件夹不存在'}), 404

    items = []
    try:
        for entry in sorted(os.scandir(target_dir), key=lambda e: (not e.is_dir(), e.name)):
            if entry.is_dir(follow_symlinks=False):
                stat = entry.stat(follow_symlinks=False)
                size = _get_dir_size(entry.path)
                items.append({
                    'name': entry.name,
                    'type': 'directory',
                    'size': size,
                    'size_display': _format_size(size),
                    'file_count': _count_files(entry.path),
                    'modified': stat.st_mtime,
                })
            elif entry.is_file(follow_symlinks=False):
                stat = entry.stat(follow_symlinks=False)
                ext = os.path.splitext(entry.name)[1].lower()
                is_image = ext in IMAGE_EXTENSIONS
                # 返回相对路径，前端请求 /students/... 时 serve_students 会透明重定向到 COS
                preview_url = f'/students/{folder_name}/{entry.name}' if is_image else None
                items.append({
                    'name': entry.name,
                    'type': 'file',
                    'size': stat.st_size,
                    'size_display': _format_size(stat.st_size),
                    'modified': stat.st_mtime,
                    'is_image': is_image,
                    'preview_url': preview_url,
                })
    except Exception as e:
        current_app.logger.error(f'Error browsing folder {folder_name}: {e}')
        return jsonify({'error': str(e)}), 500

    return jsonify(items)


@file_bp.route('/api/files/delete', methods=['POST'])
def delete_local_file():
    """
    删除指定的本地文件或文件夹（仅限 students/ 目录内）。
    受 admin session 认证保护。

    请求体 (JSON):
        path: 相对于 students/ 的路径，如 "tmp/xxx/photo.jpg" 或 "tmp/xxx"
        type: "file" 或 "directory"
    """
    from flask import request, session
    if not session.get('auth_verified'):
        return jsonify({'error': '未登录'}), 401

    data = request.json or {}
    rel_path = str(data.get('path') or '').strip().replace('\\', '/')

    if not rel_path:
        return jsonify({'error': '路径不能为空'}), 400

    # 安全：不允许路径穿越
    if '..' in rel_path.split('/'):
        return jsonify({'error': '非法路径'}), 403

    students_dir = current_app.config['STUDENTS_FOLDER']
    target = os.path.normpath(os.path.join(students_dir, rel_path))

    # 再次确认还在 students 目录范围内
    if not target.startswith(os.path.normpath(students_dir)):
        return jsonify({'error': '路径越界'}), 403

    try:
        if os.path.isfile(target):
            os.remove(target)
            # 如果父目录变成空了，顺手删掉空目录
            parent = os.path.dirname(target)
            if os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
            current_app.logger.warning(f'管理员通过文件管理面板删除本地文件: {rel_path}')
            return jsonify({'success': True, 'message': '文件已删除'})
        elif os.path.isdir(target):
            import shutil
            shutil.rmtree(target)
            current_app.logger.warning(f'管理员通过文件管理面板删除本地文件夹: {rel_path}')
            return jsonify({'success': True, 'message': '文件夹已删除'})
        else:
            return jsonify({'error': '文件或文件夹不存在'}), 404
    except Exception as e:
        current_app.logger.error(f'Error deleting {rel_path}: {e}')
        return jsonify({'error': str(e)}), 500
