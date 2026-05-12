"""
报名平台 (www.sxtsks.com) 自动化对接路由。

API 端点:
    POST /api/sxtsks/submit/<student_id>    - 仅提交报名（不下载申请表）
    GET  /api/sxtsks/registrations          - 查询已报名列表
    GET  /api/sxtsks/bmid/<student_id>      - 根据学员提交的身份证查询平台 BMID
    GET  /api/sxtsks/form/<bmid>            - 下载指定报名的申请表
"""
import os
import io
from flask import Blueprint, jsonify, request, current_app, send_file
from services.sxtsks_service import SxtsksClient
from services import storage_service
from services.operation_log_service import log_student_operation

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

    name_prefix = f"{id_card}-{name}"
    processed_photo = os.path.join(base_dir, student_folder, f"{name_prefix}-报名材料", f"{name_prefix}-个人照片.jpg")
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
        # 下载失败，清理空临时文件
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return None


def _get_student_output_dir(student, base_dir):
    """根据学员信息构建学员目录路径。"""
    student_folder_name = f"特种设备-{student.get('company', '')}-{student['name']}"
    return os.path.join(base_dir, 'students', student_folder_name)


def _send_pdf_no_store(file_obj, filename):
    """返回不允许缓存的 PDF 下载响应。"""
    response = send_file(
        file_obj,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@sxtsks_bp.route('/api/sxtsks/submit', methods=['POST'])
def submit_registration_compat():
    """兼容旧版小程序：POST body 传 student_ids 数组，转发到 submit_registration。"""
    data = request.get_json(silent=True) or {}
    student_ids = data.get('student_ids', [])
    if not student_ids:
        return jsonify({'success': False, 'message': '缺少 student_ids'}), 400
    # 取第一个 ID 转发
    try:
        sid = int(student_ids[0])
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'student_id 无效'}), 400
    return submit_registration(sid)


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
        
        # 附带步骤日志：steps 为格式化字符串（小程序用），step_details 为原始对象（网页端 buildStepsHtml 用）
        raw_steps = list(getattr(client, '_steps', []))
        result['step_details'] = raw_steps
        result['steps'] = [
            f"[{s.get('status','').upper()}] {s.get('step','')}: {s.get('detail','')}"
            for s in raw_steps
        ]
        
        if result.get('success'):
            from models.student import update_student
            update_student(student_id, {'status': 'registered'})
            log_student_operation(
                student_id,
                'platform_registration_submitted',
                '提交省网报名',
                message=result.get('message', '') or '省网报名提交成功',
                after={'status': 'registered'},
                metadata={
                    'name': student.get('name', ''),
                    'submitted_id_card': result.get('submitted_id_card', ''),
                    'step_count': len(raw_steps),
                }
            )
        else:
            log_student_operation(
                student_id,
                'platform_registration_submitted',
                '提交省网报名',
                status='fail',
                message=result.get('message', '') or '省网报名提交失败',
                metadata={
                    'name': student.get('name', ''),
                    'step_count': len(raw_steps),
                }
            )
            
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'报名平台提交异常: {e}', exc_info=True)
        log_student_operation(
            student_id,
            'platform_registration_submitted',
            '提交省网报名',
            status='fail',
            message=f'提交异常: {str(e)}',
            metadata={
                'name': student.get('name', '') if isinstance(student, dict) else '',
            }
        )
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
            log_student_operation(
                student_id,
                'platform_bmid_queried',
                '查询报名流水号',
                message='已查询到省网报名流水号',
                metadata={
                    'name': reg.get('name', ''),
                    'bmid': reg.get('bmid', ''),
                    'status': reg.get('status', ''),
                    'apply_date': reg.get('apply_date', ''),
                }
            )
            return jsonify({
                'success': True,
                'bmid': reg['bmid'],
                'name': reg['name'],
                'id_card': reg['id_card'],
                'status': reg['status'],
                'apply_date': reg['apply_date'],
            })
        else:
            log_student_operation(
                student_id,
                'platform_bmid_queried',
                '查询报名流水号',
                status='fail',
                message=f'未找到「{student_name}」的报名记录',
                metadata={
                    'name': student_name,
                }
            )
            return jsonify({'success': False, 'message': f'未找到「{student_name}」（{student_id_card}）的报名记录'})

    except Exception as e:
        current_app.logger.error(f'查询 BMID 异常: {e}', exc_info=True)
        log_student_operation(
            student_id,
            'platform_bmid_queried',
            '查询报名流水号',
            status='fail',
            message=str(e),
            metadata={
                'name': student_name,
            }
        )
        return jsonify({'success': False, 'message': str(e)}), 500


@sxtsks_bp.route('/api/sxtsks/form/<int:bmid>', methods=['GET'])
def download_form(bmid):
    """
    下载指定报名 ID 的申请表 PDF。
    服务端从平台获取 HTML → weasyprint 转 PDF → 直接下载。

    查询参数:
        student_id: 学员 ID
        mode: 'generate' 时只生成PDF并返回JSON日志，不返回文件流
    """
    student_id = request.args.get('student_id', type=int)
    mode = request.args.get('mode', '')  # 'generate' = 只生成并返回日志
    step_logs = []  # 收集进度日志

    try:
        from models.student import get_student_by_id
        student = get_student_by_id(student_id) if student_id else None
        
        pdf_filename = f'申请表-{bmid}.pdf'
        
        student_label = f"[{student['id_card']}] {student['name']}" if student else f"未知学员"
        step_logs.append(f'开始获取 {student_label} 的报名申请表')
        current_app.logger.info(f'{student_label} 开始获取报名平台申请表(BMID: {bmid})')
        
        if student:
            id_card = student.get('id_card', '')
            name = student.get('name', '')
            if id_card and name:
                pdf_filename = f"{id_card}-{name}-报名申请表.pdf"

        # ----------------------------
        # 离线渲染策略：
        # - 学员已有水印号 → 完全离线（DB 字段 + 本地模板 + 本地照片）
        # - 没有水印号 → 访问省网一次，提取水印号入库，之后永久离线
        # ----------------------------
        from services.sxtsks_form_renderer import (
            render_application_form_pdf,
            extract_watermark_text,
        )
        from models.student import update_student

        watermark_text = (student or {}).get('sxtsks_watermark', '') or ''

        if not watermark_text:
            step_logs.append('首次生成，连接省网获取水印号...')
            current_app.logger.info(f'{student_label} 首次生成，前往省网抓取水印号 (BMID: {bmid})...')
            client = _get_client()
            content, _content_type, _filename = client.download_application_form(
                bmid, sfzh=student.get('id_card', '') if student else ''
            )

            # 检测平台是否返回了错误页面（session 失效或权限问题）
            _error_keywords = ['错误，请联系网络管理员', '很抱歉', '请重新登录', '会话已过期', '登录超时', '如有疑问请联系管理员']
            _content_text = content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else str(content)
            if any(kw in _content_text for kw in _error_keywords):
                step_logs.append('平台返回错误页面，尝试重新登录后重试...')
                current_app.logger.warning(f'{student_label} 平台返回错误页面，内容前500字: {_content_text[:500]}')
                client.logged_in = False
                login_result = client.login()
                current_app.logger.info(f'{student_label} 重新登录结果: {login_result}')
                if not login_result.get('success'):
                    error_msg = f'省平台重新登录失败: {login_result.get("message", "未知原因")}'
                    step_logs.append(error_msg)
                    current_app.logger.error(f'{student_label} {error_msg}')
                    if student_id:
                        log_student_operation(
                            student_id,
                            'registration_form_downloaded',
                            '下载报名申请表',
                            status='fail',
                            message=error_msg,
                            metadata={'bmid': bmid}
                        )
                    return jsonify({'success': False, 'message': error_msg}), 502
                content, _content_type, _filename = client.download_application_form(
                    bmid, sfzh=student.get('id_card', '') if student else ''
                )
                _content_text = content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else str(content)
                if any(kw in _content_text for kw in _error_keywords):
                    error_msg = '省平台返回错误页面，重新登录后仍然失败，请稍后重试或联系管理员'
                    step_logs.append(error_msg)
                    current_app.logger.error(f'{student_label} {error_msg}，重试后内容前500字: {_content_text[:500]}')
                    if student_id:
                        log_student_operation(
                            student_id,
                            'registration_form_downloaded',
                            '下载报名申请表',
                            status='fail',
                            message=error_msg,
                            metadata={'bmid': bmid}
                        )
                    return jsonify({'success': False, 'message': error_msg}), 502

            html_text = content.decode('utf-8', errors='replace')
            watermark_text = extract_watermark_text(html_text)
            if not watermark_text:
                error_msg = '未能从省网申请表中解析到水印号'
                step_logs.append(error_msg)
                current_app.logger.error(f'{student_label} {error_msg}')
                return jsonify({'success': False, 'message': error_msg}), 502

            step_logs.append(f'水印号已获取并入库: {watermark_text}')
            current_app.logger.info(f'{student_label} 水印号解析成功: {watermark_text}')
            if student_id and student is not None:
                try:
                    update_student(student_id, {
                        'sxtsks_bmid': str(bmid),
                        'sxtsks_watermark': watermark_text,
                    })
                    student['sxtsks_watermark'] = watermark_text
                    student['sxtsks_bmid'] = str(bmid)
                except Exception as ue:
                    current_app.logger.warning(f'{student_label} 水印号写入数据库失败: {ue}')
        else:
            step_logs.append('使用本地缓存水印号，跳过省网访问')
            current_app.logger.info(f'{student_label} 使用缓存水印号 {watermark_text}，本地渲染申请表')

        # 本地模板渲染 PDF（DB 字段 + 本地照片 + 已记录的水印号）
        step_logs.append('本地模板正在渲染 PDF...')
        base_dir = _get_base_dir()
        photo_abs_path = _get_student_photo_path(student, base_dir) if student else None

        try:
            pdf_bytes = render_application_form_pdf(
                student or {}, watermark_text, photo_abs_path=photo_abs_path
            )
        except Exception as re_e:
            current_app.logger.error(f'{student_label} 本地渲染 PDF 失败: {re_e}', exc_info=True)
            return jsonify({'success': False, 'message': f'渲染 PDF 失败: {re_e}'}), 500

        pdf_size_kb = len(pdf_bytes) // 1024
        step_logs.append(f'PDF 渲染完成，文件大小 {pdf_size_kb} KB')
        current_app.logger.info(f'{student_label} PDF 渲染完毕，大小约 {pdf_size_kb} KB')

        if mode == 'generate':
            step_logs.append('PDF 生成完毕（未缓存）')
            if student_id:
                log_student_operation(
                    student_id,
                    'registration_form_generated',
                    '生成报名申请表',
                    message='报名申请表 PDF 已生成',
                    metadata={
                        'bmid': bmid,
                        'filename': pdf_filename,
                        'name': student.get('name', '') if student else '',
                    }
                )
            return jsonify({'success': True, 'logs': step_logs, 'cached': False, 'filename': pdf_filename})
        if student_id:
            log_student_operation(
                student_id,
                'registration_form_downloaded',
                '下载报名申请表',
                message='报名申请表已下载',
                metadata={
                    'bmid': bmid,
                    'filename': pdf_filename,
                    'name': student.get('name', '') if student else '',
                }
            )
        return _send_pdf_no_store(io.BytesIO(pdf_bytes), pdf_filename)
    except Exception as e:
        current_app.logger.error(f'下载申请表异常: {e}', exc_info=True)
        if student_id:
            log_student_operation(
                student_id,
                'registration_form_downloaded',
                '下载报名申请表',
                status='fail',
                message=str(e),
                metadata={
                    'bmid': bmid,
                }
            )
        return jsonify({'success': False, 'message': str(e)}), 500
