"""
报名平台 (www.sxtsks.com) 自动化对接路由。

API 端点:
    POST /api/sxtsks/submit/<student_id>    - 提交报名并自动下载申请表
    GET  /api/sxtsks/registrations          - 查询已报名列表
    GET  /api/sxtsks/form/<bmid>            - 下载指定报名的申请表
"""
import os
import base64
from flask import Blueprint, jsonify, request, current_app, send_file
from services.sxtsks_service import SxtsksClient
from services import storage_service

sxtsks_bp = Blueprint('sxtsks', __name__)

# 单例客户端（跨请求复用登录会话）
_client = None


def _get_client():
    """获取或创建单例客户端。"""
    global _client
    if _client is None:
        _client = SxtsksClient()
    return _client


def _get_student_photo_path(student, base_dir):
    """
    获取学员证件照的本地路径。
    优先使用已处理的材料输出照片，其次使用原始上传照片。
    """
    # 优先查找已生成的白底证件照
    training_type = student.get('training_type', 'special_equipment')
    training_type_name = '特种设备' if training_type == 'special_equipment' else '特种作业'
    student_folder = f"students/{training_type_name}-{student.get('company', '')}-{student['name']}"
    id_card = student.get('id_card', '')
    name = student.get('name', '')

    # 检查 material_service 生成的照片
    processed_photo = os.path.join(base_dir, student_folder, f"{id_card}-{name}-个人照片.jpg")
    if os.path.exists(processed_photo):
        return processed_photo

    # 降级：使用原始上传的照片
    photo_path = student.get('photo_path', '')
    if photo_path:
        abs_path = os.path.join(base_dir, photo_path)
        if os.path.exists(abs_path):
            return abs_path
        # 尝试从 COS 下载
        import tempfile
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.jpg')
        os.close(tmp_fd)
        if storage_service.download_to_file(photo_path, tmp_path):
            return tmp_path

    return None


@sxtsks_bp.route('/api/sxtsks/submit/<int:student_id>', methods=['POST'])
def submit_registration(student_id):
    """
    提交学员报名到平台并自动下载申请表。

    完整流程: 登录 → 上传照片 → 提交报名 → 查询 → 下载申请表 → 保存到学员目录
    """
    from models.student import get_student_by_id

    student = get_student_by_id(student_id)
    if not student:
        return jsonify({'success': False, 'message': '学员不存在'}), 404

    # 仅允许已审核的特种设备学员
    if student.get('training_type') != 'special_equipment':
        return jsonify({'success': False, 'message': '仅支持特种设备学员'}), 400

    if student.get('status') != 'reviewed':
        return jsonify({'success': False, 'message': '学员状态不是已审核'}), 400

    base_dir = current_app.config.get('BASE_DIR', os.path.dirname(os.path.abspath(__file__)))
    if not base_dir.endswith('training_system'):
        base_dir = os.path.join(base_dir, 'training_system') if os.path.isdir(os.path.join(base_dir, 'training_system')) else base_dir

    # 获取证件照路径
    photo_path = _get_student_photo_path(student, base_dir)
    if not photo_path:
        return jsonify({'success': False, 'message': '未找到学员证件照'}), 400

    try:
        client = _get_client()

        # 构建学员目录用于保存申请表
        training_type_name = '特种设备'
        student_folder_name = f"{training_type_name}-{student.get('company', '')}-{student['name']}"
        output_dir = os.path.join(base_dir, 'students', student_folder_name)

        # 一键提交并下载
        result = client.submit_and_download(student, photo_path, output_dir=output_dir)

        # 不返回 form_content 二进制字段
        result.pop('form_content', None)

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'报名平台提交异常: {e}', exc_info=True)
        return jsonify({'success': False, 'message': f'提交异常: {str(e)}'}), 500


@sxtsks_bp.route('/api/sxtsks/registrations', methods=['GET'])
def query_registrations():
    """查询平台上的报名记录列表。"""
    sfzh = request.args.get('sfzh', '')
    try:
        client = _get_client()
        registrations = client.query_registrations(sfzh=sfzh or None)
        return jsonify({'success': True, 'registrations': registrations})
    except Exception as e:
        current_app.logger.error(f'查询报名列表异常: {e}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@sxtsks_bp.route('/api/sxtsks/form/<int:bmid>', methods=['GET'])
def download_form(bmid):
    """下载指定报名 ID 的申请表。"""
    try:
        client = _get_client()
        content, content_type, filename = client.download_application_form(bmid)

        import io
        return send_file(
            io.BytesIO(content),
            mimetype=content_type,
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        current_app.logger.error(f'下载申请表异常: {e}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
