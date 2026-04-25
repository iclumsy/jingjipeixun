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
        
        if result.get('success'):
            from models.student import update_student
            update_student(student_id, {'status': 'registered'})
            
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
    使用本地学员真实的身份证号向平台发起精准定位。
    """
    from models.student import get_student_by_id

    student = get_student_by_id(student_id)
    if not student:
        return jsonify({'success': False, 'message': '学员不存在'}), 404

    student_name = student.get('name', '')
    student_id_card = student.get('id_card', '')

    if not student_id_card:
        return jsonify({'success': False, 'message': f'学员「{student_name}」缺少身份证信息，无法查询流水号'}), 400

    try:
        client = _get_client()
        # 传入 sfzh 进行精准调用
        registrations = client.query_registrations(sfzh=student_id_card)

        # 拿到同身份证的所有记录后稍微过审一下姓名对不对（防平台重写或者错乱）
        matched = [r for r in registrations if r['id_card'] == student_id_card and r['name'] == student_name]
        
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
            return jsonify({'success': False, 'message': f'未找到「{student_name}」（{student_id_card}）的报名记录'})

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
        from models.student import get_student_by_id
        student = get_student_by_id(student_id) if student_id else None
        
        pdf_filename = f'申请表-{bmid}.pdf'
        form_path = None
        
        student_label = f"[{student['id_card']}] {student['name']}" if student else f"未知学员"
        current_app.logger.info(f'{student_label} 开始获取报名平台申请表(BMID: {bmid})')
        
        if student:
            id_card = student.get('id_card', '')
            name = student.get('name', '')
            if id_card and name:
                pdf_filename = f"{id_card}-{name}-报名申请表.pdf"

            base_dir = _get_base_dir()
            output_dir = os.path.join(_get_student_output_dir(student, base_dir), '报名材料')
            os.makedirs(output_dir, exist_ok=True)
            form_path = os.path.join(output_dir, pdf_filename)
            
            # 如果申请表已在本地缓存，直接返回下载
            if os.path.exists(form_path):
                current_app.logger.info(f'{student_label} 命中本地已生成的 PDF 申请表缓存: {pdf_filename}')
                return send_file(
                    form_path,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=pdf_filename,
                )

        # ----------------------------
        # 缓存未命中，前往网站获取 HTML 处理
        # ----------------------------
        current_app.logger.info(f'{student_label} 本地无缓存，前往平台抓取核心数据 (BMID: {bmid})...')
        client = _get_client()
        content, content_type, filename = client.download_application_form(bmid)
        current_app.logger.info(f'{student_label} 平台数据源获取成功，准备注入离线排版规则...')

        # 解码平台 HTML
        html = content.decode('utf-8', errors='replace')

        # 修正图片相对路径
        html = html.replace("src='image.do", "src='http://www.sxtsks.com/image.do")
        html = html.replace('src="image.do', 'src="http://www.sxtsks.com/image.do')

        # 清理 weasyprint 无法处理的外部引用和 JS
        import re as _re
        html = _re.sub(r'<link[^>]+href=["\']css/[^"\']+["\'][^>]*/?\s*>', '', html)
        html = _re.sub(r'<script[^>]+src=["\'][^"\']+["\'][^>]*>\s*</script>', '', html)
        html = _re.sub(r'<script[\s\S]*?</script>', '', html)
        html = html.replace('onLoad="loadpage()"', '')
        html = html.replace('class="noprint"', 'class="noprint" style="display:none"')

        # 删除原始 style 块，用精准复刻的样式替代
        html = _re.sub(r'<style type="text/css">\s*body\{.*?</style>', '', html, flags=_re.S)
        html = _re.sub(r'<style type="text/css" media="print">.*?</style>', '', html, flags=_re.S)

        # 去掉固定像素宽度，交给 CSS 自动布局（避免右边框被截断和身份证折行）
        html = html.replace('width="650"', '')
        html = html.replace('width="650px"', '')

        # 注入精确匹配原版 PDF 的 CSS
        inject_css = """<style>
@page { size: A4; margin: 15mm; }
body { font-size:12pt; font-family:"PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif; margin:0; padding:0; }
.tit1 { padding:0 0 10px 0; line-height:36pt; text-align:center; font-size:18pt; font-weight:normal;
        font-family:"PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif; }
.tbsd { border:1px solid #000; width:100%; border-collapse:collapse; margin:0 auto; table-layout:fixed; box-sizing:border-box; }
.tbsd tr:first-child td:nth-child(1) { width: 20%; }
.tbsd tr:first-child td:nth-child(2) { width: 32%; }
.tbsd tr:first-child td:nth-child(3) { width: 15%; }
.tbsd tr:first-child td:nth-child(4) { width: 15%; }
.tbsd tr:first-child td:nth-child(5) { width: 18%; }
.tbsd td { font-size:12pt; padding:6px 4px; line-height:16pt; border:1px solid #000;
           font-family:"PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif; word-break:break-all; vertical-align:middle; box-sizing:border-box; }
.tbsd td p { font-size:12pt; font-family:"PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif; margin:0; }
td[height="84"] { height:64pt; }
td[height="115"] { height:85pt; }
table { width:100%; border-collapse:collapse; }
img { max-width:86px; max-height:125px; display:block; margin:0 auto; }
.noprint,.Noprint { display:none !important; }
input[type="hidden"] { display:none; }
strong { font-weight:bold; font-family:"PingFang SC","Microsoft YaHei",sans-serif; font-size:9pt; }
div[align="right"] { font-size:9pt; text-align:right; margin-right:20px; }
div[align="left"] { font-size:9pt; text-align:left; margin-left:10px; }
</style>"""
        html = html.replace('</head>', inject_css + '</head>')

        # 从原始 HTML 中提取身份证计算性别，如果原有性别为空则填上
        id_card_match = _re.search(r'身份证件号\s*</td>\s*<td[^>]*>\s*([0-9X]{18})', html, _re.I)
        if id_card_match:
            try:
                card = id_card_match.group(1)
                gender_char = card[16:17]
                gender_str = '女' if int(gender_char) % 2 == 0 else '男'
                html = _re.sub(r'(>性别\s*</td>\s*<td[^>]*>)\s*&nbsp;\s*</td>', f'\\g<1>{gender_str}</td>', html)
            except Exception:
                pass

        # 从原始 HTML 中提取水印文字
        watermark_match = _re.search(r"watermark\.innerText\s*=\s*'([^']+)'", content.decode('utf-8', errors='replace'))
        watermark_text = watermark_match.group(1) if watermark_match else '山西省特种设备作业人员考核管理平台'

        # 原版水印：调整为底层显示 (z-index:-10)，从 body 顶部注入使其渲染在文字下方
        watermark_html = f'<div style="position:fixed; top:105mm; left:15mm; font-size:20pt; font-family:PingFang SC,Microsoft YaHei,sans-serif; color:#a1a1ab; white-space:nowrap; z-index:-10;">{watermark_text}</div>'
        html = _re.sub(r'(<body[^>]*>)', r'\1' + watermark_html, html, count=1)

        # weasyprint 转 PDF
        current_app.logger.info(f'{student_label} 准备调用 WeasyPrint 将 HTML 排版为保真 PDF 文件...')
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        current_app.logger.info(f'{student_label} PDF 转换生成完毕，最终大小缩略约为 {len(pdf_bytes) // 1024} KB')

        # 保存并返回
        if form_path:
            try:
                with open(form_path, 'wb') as f:
                    f.write(pdf_bytes)
                current_app.logger.info(f'{student_label} PDF 文件已成功冷备份到设备持久化层: {form_path}')
                return send_file(
                    form_path,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=pdf_filename,
                )
            except Exception as save_err:
                current_app.logger.warning(f'保存申请表失败: {save_err}')

        # 降级: 放内存处理
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=pdf_filename,
        )
    except Exception as e:
        current_app.logger.error(f'下载申请表异常: {e}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
