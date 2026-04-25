"""
报名平台 (www.sxtsks.com) 自动化对接路由。

API 端点:
    POST /api/sxtsks/submit/<student_id>    - 仅提交报名（不下载申请表）
    GET  /api/sxtsks/registrations          - 查询已报名列表
    GET  /api/sxtsks/bmid/<student_id>      - 根据学员提交的身份证查询平台 BMID
    GET  /api/sxtsks/form/<bmid>            - 下载指定报名的申请表并保存到学员目录
"""
import os
import io
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


def _get_base_dir():
    """获取系统根目录。"""
    base_dir = current_app.config.get('BASE_DIR', os.path.dirname(os.path.abspath(__file__)))
    if not base_dir.endswith('training_system'):
        base_dir = os.path.join(base_dir, 'training_system') if os.path.isdir(os.path.join(base_dir, 'training_system')) else base_dir
    return base_dir


def _get_student_photo_path(student, base_dir):
    """
    获取学员证件照的本地路径。
    优先使用已处理的材料输出照片，其次使用原始上传照片。
    """
    training_type = student.get('training_type', 'special_equipment')
    training_type_name = '特种设备' if training_type == 'special_equipment' else '特种作业'
    student_folder = f"students/{training_type_name}-{student.get('company', '')}-{student['name']}"
    id_card = student.get('id_card', '')
    name = student.get('name', '')

    processed_photo = os.path.join(base_dir, student_folder, f"{id_card}-{name}-个人照片.jpg")
    if os.path.exists(processed_photo):
        return processed_photo

    photo_path = student.get('photo_path', '')
    if photo_path:
        abs_path = os.path.join(base_dir, photo_path)
        if os.path.exists(abs_path):
            return abs_path
        import tempfile
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.jpg')
        os.close(tmp_fd)
        if storage_service.download_to_file(photo_path, tmp_path):
            return tmp_path

    return None


def _get_student_output_dir(student, base_dir):
    """根据学员信息构建学员目录路径。"""
    student_folder_name = f"特种设备-{student.get('company', '')}-{student['name']}"
    return os.path.join(base_dir, 'students', student_folder_name)


@sxtsks_bp.route('/api/sxtsks/submit/<int:student_id>', methods=['POST'])
def submit_registration(student_id):
    """
    仅提交学员报名到平台（不下载申请表）。

    流程: 登录 → 上传照片 → 提交报名
    返回 submitted_id_card 供后续查询 BMID 使用。
    """
    from models.student import get_student_by_id

    student = get_student_by_id(student_id)
    if not student:
        return jsonify({'success': False, 'message': '学员不存在'}), 404

    if student.get('training_type') != 'special_equipment':
        return jsonify({'success': False, 'message': '仅支持特种设备学员'}), 400

    if student.get('status') != 'reviewed':
        return jsonify({'success': False, 'message': '学员状态不是已审核'}), 400

    base_dir = _get_base_dir()
    photo_path = _get_student_photo_path(student, base_dir)
    if not photo_path:
        return jsonify({'success': False, 'message': '未找到学员证件照'}), 400

    try:
        client = _get_client()
        # 只提交报名，不下载申请表
        result = client.submit_registration(student, photo_path)
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


@sxtsks_bp.route('/api/sxtsks/bmid/<int:student_id>', methods=['GET'])
def query_bmid(student_id):
    """
    查询学员在平台上的报名 BMID。
    由于提交时使用的是随机测试身份证，这里查询全部报名列表后按姓名匹配。
    """
    from models.student import get_student_by_id

    student = get_student_by_id(student_id)
    if not student:
        return jsonify({'success': False, 'message': '学员不存在'}), 404

    student_name = student.get('name', '')

    try:
        client = _get_client()
        # 不传 sfzh，查询该账号下的全部报名记录
        registrations = client.query_registrations()

        # 按姓名匹配（可能有多条，取最新的一条）
        matched = [r for r in registrations if r['name'] == student_name]
        if matched:
            reg = matched[0]  # 第一条即最新
            return jsonify({
                'success': True,
                'bmid': reg['bmid'],
                'name': reg['name'],
                'id_card': reg['id_card'],
                'status': reg['status'],
                'apply_date': reg['apply_date'],
            })
        else:
            return jsonify({'success': False, 'message': f'未找到「{student_name}」的报名记录'})

    except Exception as e:
        current_app.logger.error(f'查询 BMID 异常: {e}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@sxtsks_bp.route('/api/sxtsks/form/<int:bmid>', methods=['GET'])
def download_form(bmid):
    """
    下载指定报名 ID 的申请表 PDF。
    服务端从平台获取 HTML → weasyprint 转 PDF → 直接下载。
    """
    student_id = request.args.get('student_id', type=int)

    try:
        client = _get_client()
        content, content_type, filename = client.download_application_form(bmid)

        # 解码平台 HTML
        html_body = content.decode('utf-8', errors='replace')

        # 修正图片相对路径
        html_body = html_body.replace('src="image.do', 'src="http://www.sxtsks.com/image.do')
        html_body = html_body.replace("src='image.do", "src='http://www.sxtsks.com/image.do")

        # 隐藏平台自带的「下载」「关闭」按钮，并确保表格样式对 PDF 友好
        pdf_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
    body {{ font-family: "SimSun", "STSong", "Noto Serif CJK SC", serif; font-size: 14px; }}
    #bt {{ display: none !important; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td, th {{ border: 1px solid #000; padding: 6px 8px; }}
    @page {{ size: A4; margin: 15mm; }}
</style>
</head><body>{html_body}</body></html>"""

        # weasyprint 转 PDF
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=pdf_html).write_pdf()

        pdf_filename = f'申请表-{bmid}.pdf'

        # 保存到学员目录
        if student_id:
            try:
                from models.student import get_student_by_id
                student = get_student_by_id(student_id)
                if student:
                    base_dir = _get_base_dir()
                    output_dir = _get_student_output_dir(student, base_dir)
                    os.makedirs(output_dir, exist_ok=True)
                    form_path = os.path.join(output_dir, pdf_filename)
                    with open(form_path, 'wb') as f:
                        f.write(pdf_bytes)
                    current_app.logger.info(f'申请表 PDF 已保存: {form_path}')
            except Exception as save_err:
                current_app.logger.warning(f'保存申请表失败: {save_err}')

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=pdf_filename,
        )
    except Exception as e:
        current_app.logger.error(f'下载申请表异常: {e}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
