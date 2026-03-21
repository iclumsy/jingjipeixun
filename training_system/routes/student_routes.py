"""
学员相关路由。

本模块是系统的核心业务路由，提供学员信息的完整生命周期管理：

API 端点列表:
    POST   /api/students                       - 创建新学员（支持表单和 JSON）
    GET    /api/students                        - 获取学员列表（支持多维度筛选）
    GET    /api/students/<id>                   - 获取单个学员详情
    PUT    /api/students/<id>                   - 更新学员信息（支持表单和 JSON）
    POST   /api/students/<id>/upload            - 为已有学员上传单个附件
    POST   /api/miniprogram/upload              - 小程序表单提交前预上传附件
    POST   /api/students/<id>/reject            - 驳回学员（更新状态或删除）
    POST   /api/students/<id>/approve           - 审核通过学员
    GET    /api/students/<id>/attachments.zip   - 打包下载学员所有附件
    GET    /api/companies                       - 获取公司名称列表

权限控制:
    - 创建学员：任何已认证用户（含小程序普通用户）
    - 查看列表：已认证用户，小程序普通用户仅能查看自己提交的记录
    - 查看详情：管理员或记录提交者本人
    - 更新学员：管理员或提交者本人（本人仅在被驳回状态可修改）
    - 审核/驳回：仅管理员
    - 打包下载：仅管理员
    - 公司列表：仅管理员

附件管理规则:
    - 特种作业 (special_operation)  : 必传学历证书、身份证正反面
    - 特种设备 (special_equipment)  : 必传个人照片、学历证书、身份证正反面、户口本户籍页和个人页
"""
from flask import Blueprint, request, jsonify, current_app, g
from models.student import (
    create_student, get_students, get_student_by_id, update_student,
    delete_student, get_companies
)
from services.wechat_service import send_review_result_message, broadcast_new_student_to_admins
from services.image_service import process_and_save_file, delete_student_files
from services.document_service import generate_health_check_form
from utils.validators import validate_student_data, validate_file_upload
from utils.error_handlers import AppError, ValidationError, NotFoundError
import os
import io
import zipfile
import time


# 创建学员蓝图
student_bp = Blueprint('student', __name__)

# ======================== 常量定义 ========================

# 前端字段名 -> 数据库字段名 映射
# 前端上传时使用简短的字段名（如 'photo'），数据库中存储带 _path 后缀的字段名
FILE_MAP = {
    'photo': 'photo_path',                   # 个人照片
    'diploma': 'diploma_path',               # 学历证书
    'id_card_front': 'id_card_front_path',   # 身份证正面
    'id_card_back': 'id_card_back_path',     # 身份证反面
    'hukou_residence': 'hukou_residence_path', # 户口本户籍页
    'hukou_personal': 'hukou_personal_path'  # 户口本个人页
}

# 各培训类型的必传附件清单
# 特种作业不要求照片和户口本；特种设备要求全部附件
REQUIRED_ATTACHMENTS = {
    'special_operation': ['diploma', 'id_card_front', 'id_card_back'],
    'special_equipment': ['photo', 'diploma', 'id_card_front', 'id_card_back', 'hukou_residence', 'hukou_personal']
}

# ======================== 辅助函数 ========================


def normalize_training_type(training_type):
    """
    标准化并校验培训类型。

    将传入的培训类型字符串标准化为合法的枚举值。
    如果传入值非法，默认回退到 'special_operation'。

    参数:
        training_type: 原始培训类型字符串

    返回:
        str: 标准化后的培训类型（'special_operation' 或 'special_equipment'）
    """
    value = (training_type or '').strip()
    if value in REQUIRED_ATTACHMENTS:
        return value
    return 'special_operation'


def parse_bool(value):
    """
    解析布尔型查询参数。

    支持多种真值表示：true、1、yes、on（不区分大小写）。
    其他值一律视为 False。

    参数:
        value: 查询参数值（字符串或布尔值）

    返回:
        bool: 解析后的布尔值
    """
    if isinstance(value, bool):
        return value
    normalized = str(value or '').strip().lower()
    return normalized in ('1', 'true', 'yes', 'on')


def build_internal_error_response(message='服务器内部错误，请稍后重试'):
    """
    构建统一的 500 错误 JSON 响应。

    用于 catch-all 异常处理中，避免向客户端泄露内部错误详情。

    参数:
        message: 用户可见的错误消息

    返回:
        tuple: (JSON 响应, 500 状态码)
    """
    return jsonify({
        'error': 'internal_error',
        'message': message
    }), 500


def get_mini_user():
    """
    从请求上下文获取小程序认证信息。

    在 app.py 的 before_request 中间件中，如果小程序令牌验证成功，
    会将用户信息存入 g.mini_user。此函数安全地读取该信息。

    返回:
        dict 或 None: 小程序用户信息字典 {'openid': '...', 'is_admin': bool}，
                      非小程序请求返回 None
    """
    user = getattr(g, 'mini_user', None)
    return user if isinstance(user, dict) else None


def is_mini_admin():
    """
    判断当前小程序调用者是否为管理员。

    管理员 openid 列表在环境变量 TRAINING_SYSTEM_ADMIN_OPENIDS 中配置。

    返回:
        bool: 是否为小程序管理员
    """
    user = get_mini_user()
    return bool(user and user.get('is_admin'))


def get_mini_openid():
    """
    获取小程序调用者的 openid。

    返回:
        str: openid 字符串，非小程序请求返回空字符串
    """
    user = get_mini_user()
    if not user:
        return ''
    return str(user.get('openid', '') or '').strip()


def ensure_mini_admin():
    """
    拒绝非管理员小程序用户的管理操作。

    用于审核、驳回、删除等管理员专属操作的权限检查。
    如果请求来自小程序但调用者不是管理员，抛出 403 错误。
    如果请求来自管理后台（非小程序），则不做限制（已通过 session 认证）。

    异常:
        AppError: 非管理员时抛出 403 错误
    """
    user = get_mini_user()
    if user and not is_mini_admin():
        raise AppError('无权限执行该操作', status_code=403)


def ensure_mini_owner_or_admin(student):
    """
    拒绝非本人且非管理员的小程序用户访问。

    用于学员详情查看和修改操作的权限检查。
    确保小程序普通用户只能访问自己提交的记录。

    参数:
        student: 学员记录字典（需要包含 submitter_openid 字段）

    异常:
        AppError: 无权限时抛出 403 错误
    """
    user = get_mini_user()
    # 非小程序请求（管理后台）或管理员直接放行
    if not user or is_mini_admin():
        return
    # 检查记录的提交人 openid 是否与当前用户匹配
    owner_openid = str(student.get('submitter_openid', '') or '').strip()
    if owner_openid != get_mini_openid():
        raise AppError('无权限访问该记录', status_code=403)


def ensure_safe_relative_student_path(path_value):
    """
    校验学员附件的相对路径安全性。

    JSON 模式提交时，客户端直接传递文件路径而非文件对象。
    此函数确保路径不会通过 ".." 等方式实现目录遍历攻击。

    安全校验规则:
    1. 路径不能为空
    2. 路径不能以 "/" 开头（必须是相对路径）
    3. 路径不能包含 ".." 组件（防止目录遍历）
    4. 路径必须以 "students/" 开头（限制在学员目录内）

    参数:
        path_value: 原始路径值

    返回:
        str: 校验通过的路径，空路径返回空字符串

    异常:
        ValidationError: 路径不安全时抛出
    """
    raw = str(path_value or '').strip()
    if not raw:
        return ''
    # 统一路径分隔符为正斜杠
    normalized = raw.replace('\\', '/')
    # 安全性校验
    if normalized.startswith('/'):
        raise ValidationError('附件路径无效')
    if '..' in normalized.split('/'):
        raise ValidationError('附件路径无效')
    if not normalized.startswith('students/'):
        raise ValidationError('附件路径无效')
    return normalized


# ======================== API 路由 ========================

@student_bp.route('/api/students', methods=['POST'])
def create_student_route():
    """
    创建新学员。

    支持两种提交模式:
    1. Multipart 表单 (有文件上传): 前端表单直接提交，文件在服务端保存
    2. JSON (路径引用模式): 小程序预上传文件后，提交文件路径引用

    流程:
    1. 根据 Content-Type 判断提交模式
    2. 校验学员基本信息
    3. 检查必传附件是否齐全
    4. 保存附件文件（Multipart 模式）或校验路径（JSON 模式）
    5. 绑定提交人 openid（小程序提交时自动绑定）
    6. 创建数据库记录

    返回:
        201: {"message": "Student added successfully", "id": <新学员ID>}
        400: 校验错误详情
        500: 内部错误
    """
    try:
        # 判断提交模式：有表单字段或文件时为 Multipart 模式
        use_multipart = bool(request.form or request.files)
        file_paths = {}

        if use_multipart:
            # ---- Multipart 表单模式 ----
            data = request.form
            files = request.files

            # 校验学员基本信息字段
            validate_student_data(data)

            # 确定培训类型，据此判断必传附件
            training_type = normalize_training_type(data.get('training_type', 'special_operation'))
            required_attachments = REQUIRED_ATTACHMENTS.get(training_type, REQUIRED_ATTACHMENTS['special_operation'])

            # 检查必传附件是否齐全
            missing_files = [
                field for field in required_attachments
                if not files.get(field) or not files.get(field).filename
            ]
            if missing_files:
                fields = {field: '该培训项目下此附件为必传项' for field in missing_files}
                raise ValidationError('缺少必传附件', fields=fields)

            # 用于文件命名的关键信息
            id_card_val = data.get('id_card', '').strip()
            company_val = data.get('company', '').strip()

            # 逐个保存上传的附件文件
            for input_name, db_key in FILE_MAP.items():
                file = files.get(input_name)
                if file and file.filename and id_card_val:
                    try:
                        # 校验文件格式和大小
                        validate_file_upload(file)
                        # 保存文件到学员目录并获取相对路径
                        rel = process_and_save_file(
                            file, id_card_val, data.get('name', ''),
                            input_name, company_val, training_type
                        )
                        file_paths[db_key] = rel
                    except Exception as err:
                        current_app.logger.error(f'Failed to save file {input_name}: {str(err)}')
                        file_paths[db_key] = ""
                else:
                    file_paths[db_key] = ""

            student_payload = data.to_dict(flat=True)
        else:
            # ---- JSON 路径引用模式 ----
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                raise ValidationError('请求参数格式错误')

            # 校验学员基本信息
            validate_student_data(payload)
            training_type = normalize_training_type(payload.get('training_type', 'special_operation'))

            # 从 JSON 的 files 字段中提取并校验文件路径
            files_payload = payload.get('files', {}) if isinstance(payload.get('files', {}), dict) else {}
            for input_name, db_key in FILE_MAP.items():
                file_paths[db_key] = ensure_safe_relative_student_path(files_payload.get(input_name, ''))

            # 检查必传附件路径是否齐全
            required_attachments = REQUIRED_ATTACHMENTS.get(training_type, REQUIRED_ATTACHMENTS['special_operation'])
            missing_files = [
                field for field in required_attachments
                if not file_paths.get(FILE_MAP[field], '')
            ]
            if missing_files:
                fields = {field: '该培训项目下此附件为必传项' for field in missing_files}
                raise ValidationError('缺少必传附件', fields=fields)

            student_payload = dict(payload)

        # 体检表/培训表路径初始为空（审核通过时自动生成）
        file_paths['training_form_path'] = ""

        # 设置培训类型
        student_payload['training_type'] = training_type

        # 防重拦截：检查是否有正在处理的同项目报名
        from models.student import get_db_connection
        with get_db_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM students WHERE id_card = ? AND training_type = ? AND status IN ('unreviewed', 'reviewed')",
                (student_payload.get('id_card', ''), training_type)
            ).fetchone()
            if existing:
                raise AppError('该项目您已有正在处理的报名，请勿重复提交', status_code=400)

        # 绑定提交人 openid
        mini_user = get_mini_user()
        if mini_user:
            # 小程序直接提交时，始终将记录归属绑定到令牌中的 openid
            student_payload['submitter_openid'] = get_mini_openid()
        else:
            # 管理后台提交时，保留前端传入的 openid（如有）
            student_payload['submitter_openid'] = (student_payload.get('submitter_openid', '') or '').strip()

        # 创建数据库记录
        student_id = create_student(student_payload, file_paths)
        current_app.logger.info(f'Student created: ID={student_id}')
        
        # 异步/非阻塞方式发送给所有管理员（基于小程序订阅消息）
        broadcast_new_student_to_admins(student_name=student_payload.get('name', ''))

        return jsonify({'message': 'Student added successfully', 'id': student_id}), 201

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        current_app.logger.error(f'Error creating student (app error): {e.message}')
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error creating student')
        return build_internal_error_response('创建学员失败，请稍后重试')


@student_bp.route('/api/students', methods=['GET'])
def get_students_route():
    """
    获取学员列表，支持筛选条件。

    查询参数:
        status (str)         : 审核状态筛选，默认 'unreviewed'
        search (str)         : 按姓名、身份证号、手机号模糊搜索
        company (str)        : 按公司名称筛选
        training_type (str)  : 按培训类型筛选
        my_only (bool)       : 是否仅查看自己提交的记录（管理后台使用）
        submitter_openid (str): 指定提交人 openid 筛选

    权限说明:
        - 小程序普通用户：自动限制为仅查看自己提交的记录
        - 管理员和管理后台：可查看所有记录，支持 my_only 筛选

    返回:
        200: 学员记录数组 [{"id": 1, "name": "...", ...}, ...]
    """
    try:
        # 获取筛选参数
        status = request.args.get('status', 'unreviewed')
        search = request.args.get('search', '')
        company = request.args.get('company', '')
        training_type = request.args.get('training_type', '')
        mini_user = get_mini_user()

        if mini_user and not is_mini_admin():
            # 小程序普通用户：强制限制为仅查看自己提交的记录
            submitter_openid = get_mini_openid()
        else:
            # 管理员或管理后台：支持可选的 my_only 筛选
            my_only = parse_bool(request.args.get('my_only', False))
            submitter_openid = (request.args.get('submitter_openid', '') or '').strip()
            if my_only and not submitter_openid:
                # 兼容：允许使用 openid 作为查询别名
                submitter_openid = (request.args.get('openid', '') or '').strip()
            if not my_only:
                submitter_openid = ''

        students = get_students(status, search, company, training_type, submitter_openid)
        return jsonify(students)

    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error getting students')
        return build_internal_error_response('加载学员列表失败，请稍后重试')


@student_bp.route('/api/students/<int:id>', methods=['GET'])
def get_student_route(id):
    """
    获取单个学员详情。

    包含学员所有字段和附件路径信息。

    参数:
        id: 学员 ID（URL 路径参数）

    权限:
        小程序普通用户仅能查看自己提交的记录

    返回:
        200: 学员记录对象
        404: 学员不存在
    """
    try:
        student = get_student_by_id(id)
        # 检查小程序用户是否有权查看此记录
        ensure_mini_owner_or_admin(student)
        return jsonify(student)
    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error getting student %s', id)
        return build_internal_error_response('加载学员详情失败，请稍后重试')


@student_bp.route('/api/students/<int:id>', methods=['PUT', 'PATCH'])
def update_student_route(id):
    """
    更新学员信息。

    支持部分更新（PATCH 语义），只更新传入的字段。
    同时支持 Multipart 表单（可上传新附件）和 JSON 两种模式。

    更新流程:
    1. 获取当前学员记录
    2. 权限检查（管理员或提交者本人，本人仅在被驳回状态可修改）
    3. 提取可更新的文本字段
    4. 处理附件上传/替换（删除旧文件，保存新文件）
    5. 检查更新后必传附件是否齐全
    6. 写入数据库

    参数:
        id: 学员 ID（URL 路径参数）

    返回:
        200: 更新后的学员记录
        400: 校验错误
        403: 权限不足
        404: 学员不存在
    """
    try:
        # 可更新的文本字段白名单（防止恶意修改其他字段）
        allowed_text = [
            'name', 'gender', 'education', 'school', 'major', 'id_card', 'phone',
            'company', 'company_address', 'job_category', 'exam_project', 'project_code', 'training_type', 'status'
        ]

        # 获取当前学员记录并检查权限
        current_student = get_student_by_id(id)
        ensure_mini_owner_or_admin(current_student)
        # 小程序普通用户在未审核和被驳回状态均可修改自己的记录
        if get_mini_user() and not is_mini_admin() and current_student.get('status') not in ('unreviewed', 'rejected'):
            raise AppError('当前状态不允许修改', status_code=403)

        updates = {}

        # ---- 处理表单数据（Multipart 模式） ----
        if request.form:
            data = request.form
            # 提取白名单内的文本字段
            for k in allowed_text:
                if k in data:
                    updates[k] = data[k]
            # 兼容旧字段名 exam_code -> project_code
            if 'project_code' not in updates and 'exam_code' in data:
                updates['project_code'] = data.get('exam_code', '')
            # 标准化培训类型
            if 'training_type' in updates:
                updates['training_type'] = normalize_training_type(updates['training_type'])

            # 校验部分更新字段（不要求必填字段齐全）
            if updates:
                validate_student_data(updates, required_fields=[])

            # 处理附件上传
            effective_training_type = normalize_training_type(
                data.get('training_type', updates.get('training_type', current_student.get('training_type', 'special_operation')))
            )
            # 仅允许上传当前培训类型需要的附件
            allowed_attachments = set(REQUIRED_ATTACHMENTS.get(effective_training_type, REQUIRED_ATTACHMENTS['special_operation']))

            for input_name, db_key in FILE_MAP.items():
                f = request.files.get(input_name)
                if f and f.filename:
                    # 拒绝上传非必需附件
                    if input_name not in allowed_attachments:
                        raise ValidationError(f'{effective_training_type} 不允许上传 {input_name}')

                    validate_file_upload(f)
                    id_card_for_name = data.get('id_card', current_student['id_card'])
                    name_for_save = data.get('name', current_student['name'])
                    company_for_name = data.get('company', current_student.get('company', ''))

                    # 保存新文件（底层会自动安全原子覆盖同名文件）
                    try:
                        training_type = normalize_training_type(
                            data.get('training_type', current_student.get('training_type', 'special_operation'))
                        )
                        rel = process_and_save_file(
                                f, id_card_for_name, name_for_save, input_name, company_for_name, training_type
                            )
                        updates[db_key] = rel
                    except Exception as e:
                        current_app.logger.error(f'Failed to save file {input_name}: {str(e)}')
                        updates[db_key] = ''
        else:
            # ---- JSON 模式 ----
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                raise ValidationError('请求参数格式错误')

            # 提取白名单内的文本字段
            for k in allowed_text:
                if k in payload:
                    updates[k] = payload[k]
            if 'project_code' not in updates and 'exam_code' in payload:
                updates['project_code'] = payload.get('exam_code', '')
            if 'training_type' in updates:
                updates['training_type'] = normalize_training_type(updates['training_type'])

            # 校验部分更新字段
            if updates:
                validate_student_data(updates, required_fields=[])

            # 处理 JSON 中的文件路径更新
            files_payload = payload.get('files', {}) if isinstance(payload.get('files', {}), dict) else {}
            effective_training_type = normalize_training_type(
                updates.get('training_type', current_student.get('training_type', 'special_operation'))
            )
            allowed_attachments = set(REQUIRED_ATTACHMENTS.get(effective_training_type, REQUIRED_ATTACHMENTS['special_operation']))

            for input_name, db_key in FILE_MAP.items():
                if input_name not in files_payload:
                    continue
                rel = ensure_safe_relative_student_path(files_payload.get(input_name, ''))
                if rel and input_name not in allowed_attachments:
                    # 忽略目标培训类型不需要的附件，避免历史遗留字段导致保存失败
                    continue

                # 添加更新路径，文件替换处理在最后统一处理清理
                updates[db_key] = rel

        # 最终校验：确保更新后所有必传附件仍然齐全
        effective_training_type = normalize_training_type(
            updates.get('training_type', current_student.get('training_type', 'special_operation'))
        )
        required_attachments = REQUIRED_ATTACHMENTS.get(effective_training_type, REQUIRED_ATTACHMENTS['special_operation'])
        for attachment_field in required_attachments:
            db_key = FILE_MAP[attachment_field]
            # 优先取更新值，否则取当前数据库中的值
            final_value = updates.get(db_key, current_student.get(db_key, ''))
            if not final_value:
                raise ValidationError(
                    '缺少必传附件',
                    fields={attachment_field: '该培训项目下此附件为必传项'}
                )

        # ======= 【新增防线：处理学员修改的越权与并发冲突】 =======
        if get_mini_user() and not is_mini_admin():
            # 1. 防止越权：无情剔除前端自己伪造的 status 字段，杜绝自己给自己“盖章通过审核”
            if 'status' in updates:
                del updates['status']
                
            # 2. 防止 ABA 并发流转：如果此时数据库已经是通过状态（管理员刚批完），报错拦截他提交，保留你的审核成果
            if current_student.get('status') == 'reviewed':
                raise AppError('管理员刚刚已审核通过，无法再提交修改', status_code=403)
                
            # 3. 强制降维：既然他确实重新编辑并提交了图片或文字，强制恢复为待审核状态
            updates['status'] = 'unreviewed'
        # =========================================================

        # 执行数据库更新
        updated_student = update_student(id, updates)
        current_app.logger.info(f'Student updated: ID={id}')

        # 成功更新数据库后，清理因改名导致路径变更产生的孤儿旧文件
        for db_key in FILE_MAP.values():
            old_rel = current_student.get(db_key, '')
            new_rel = updated_student.get(db_key, '')
            if old_rel and old_rel != new_rel:
                delete_student_files({db_key: old_rel}, current_app.config['BASE_DIR'])

        # 检查是否是从被驳回修改为重新提交（待审核）状态
        is_resubmitted = (
            current_student.get('status') == 'rejected' and
            updates.get('status') == 'unreviewed'
        )
        if is_resubmitted:
            # 获取更新后的全名或备用名称发送提醒
            student_name_for_notice = updates.get('name', current_student.get('name', ''))
            broadcast_new_student_to_admins(student_name_for_notice)

        return jsonify(updated_student)

    except (ValidationError, NotFoundError, AppError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error updating student %s', id)
        return build_internal_error_response('更新学员失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/upload', methods=['POST'])
def upload_student_attachment_route(id):
    """
    为已有学员上传单个附件。

    管理后台中点击附件缩略图时触发。自动识别上传的是哪种附件，
    替换旧文件并更新数据库记录。

    参数:
        id: 学员 ID（URL 路径参数）

    请求体:
        Multipart 表单，包含一个文件字段（字段名为 FILE_MAP 中的键）

    返回:
        200: {"message": "上传成功", "field": "photo_path", "path": "students/...", "student": {...}}
    """
    try:
        student = get_student_by_id(id)
        ensure_mini_owner_or_admin(student)
        # 小程序普通用户在未审核和被驳回状态均可上传附件
        if get_mini_user() and not is_mini_admin() and student.get('status') not in ('unreviewed', 'rejected'):
            raise AppError('当前状态不允许修改', status_code=403)

        training_type = normalize_training_type(student.get('training_type', 'special_operation'))
        allowed_attachments = set(REQUIRED_ATTACHMENTS.get(training_type, REQUIRED_ATTACHMENTS['special_operation']))

        # 从请求的文件列表中找到第一个有效的上传文件
        upload_field = ''
        upload_file = None
        for field_name in FILE_MAP:
            candidate = request.files.get(field_name)
            if candidate and candidate.filename:
                upload_field = field_name
                upload_file = candidate
                break

        if not upload_field or upload_file is None:
            raise ValidationError('未检测到有效上传文件')

        # 确保上传的附件类型是当前培训类型所需的
        if upload_field not in allowed_attachments:
            raise ValidationError('当前培训项目不需要该附件')

        validate_file_upload(upload_file)

        # 获取用于文件命名的学员信息
        id_card_for_name = student.get('id_card', '')
        name_for_save = student.get('name', '')
        company_for_name = student.get('company', '')

        db_key = FILE_MAP[upload_field]
        old_rel = student.get(db_key)

        # 保存新文件（底层会自动安全原子覆盖同名文件）并更新数据库
        rel = process_and_save_file(
            upload_file,
            id_card_for_name,
            name_for_save,
            upload_field,
            company_for_name,
            training_type
        )
        updated = update_student(id, {db_key: rel})

        # 成功更新数据库后，清理因改名导致路径变更产生的孤儿旧文件
        if old_rel and old_rel != rel:
            delete_student_files({db_key: old_rel}, current_app.config['BASE_DIR'])

        return jsonify({
            'message': '上传成功',
            'field': db_key,
            'path': rel,
            'student': updated
        })

    except (ValidationError, NotFoundError, AppError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error uploading attachment for student %s', id)
        return build_internal_error_response('上传附件失败，请稍后重试')


@student_bp.route('/api/miniprogram/upload', methods=['POST'])
def miniprogram_upload_attachment_route():
    """
    小程序表单提交前上传单个附件（直传模式）。

    小程序端的文件上传分为两个步骤:
    1. 先通过此接口逐个上传附件，获取服务端存储路径
    2. 然后将所有路径作为 JSON 数据提交到 /api/students（创建学员）

    这种"预上传"模式避免了小程序端需要同时上传大量文件的问题。

    请求体 (Multipart):
        file          : 文件本体
        file_type     : 附件类型（photo, diploma, id_card_front 等）
        training_type : 培训类型
        id_card       : 身份证号（用于文件命名，可选）
        name          : 姓名（用于文件命名，可选）
        company       : 公司名称（用于文件命名，可选）

    返回:
        200: {"success": true, "path": "students/...", "file_type": "photo"}
    """
    try:
        upload_file = request.files.get('file')
        if not upload_file or not upload_file.filename:
            raise ValidationError('未检测到有效上传文件')

        # 获取附件类型（兼容驼峰和下划线两种命名）
        file_type = str(
            request.form.get('file_type')
            or request.form.get('fileType')
            or ''
        ).strip()
        if file_type not in FILE_MAP:
            raise ValidationError('附件类型无效')

        training_type = normalize_training_type(
            request.form.get('training_type') or request.form.get('trainingType') or 'special_operation'
        )
        # 上传阶段宽松处理：允许替换任何已知附件类型
        # 必传附件约束在最终提交/更新校验时强制执行

        validate_file_upload(upload_file)

        # 文件命名信息：如果未提供身份证号，使用时间戳作为临时标识
        id_card_for_name = str(request.form.get('id_card', '') or '').strip() or f"temp{int(time.time())}"
        name_for_save = str(request.form.get('name', '') or '').strip() or '未命名'
        company_for_name = str(request.form.get('company', '') or '').strip()

        # 保存文件并返回相对路径
        rel = process_and_save_file(
            upload_file,
            id_card_for_name,
            name_for_save,
            file_type,
            company_for_name,
            training_type
        )

        return jsonify({
            'success': True,
            'path': rel,
            'file_type': file_type
        })

    except (ValidationError, AppError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error uploading mini attachment')
        return build_internal_error_response('上传附件失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/reject', methods=['POST'])
def reject_student_route(id):
    """
    驳回学员：默认更新状态，仅在明确请求时删除记录。

    此接口支持两种操作:
    1. 驳回（默认）: 将学员状态改为 'rejected'，学员可修改后重新提交
    2. 删除: 彻底删除学员记录和关联的所有附件文件

    请求体 (JSON):
        delete (bool): 是否彻底删除记录，默认 false
        status (str) : 目标状态，默认 'rejected'，也可设为 'unreviewed'

    参数:
        id: 学员 ID

    返回:
        200: {"message": "Student rejected and deleted"} 或 {"message": "...", "student": {...}}
    """
    try:
        ensure_mini_admin()
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}

        # 解析 delete 参数（支持字符串和布尔值两种格式）
        should_delete_raw = data.get('delete', False)
        if isinstance(should_delete_raw, str):
            should_delete = should_delete_raw.strip().lower() in ('1', 'true', 'yes', 'y')
        else:
            should_delete = bool(should_delete_raw)

        # 安全限制目标状态：仅允许 unreviewed 和 rejected
        target_status = str(data.get('status', 'rejected')).strip() or 'rejected'
        if target_status not in ('unreviewed', 'rejected'):
            target_status = 'rejected'
        
        if should_delete:
            # 彻底删除：先删除数据库记录，再清理附件文件
            student = delete_student(id)
            delete_student_files(student, current_app.config['BASE_DIR'])
            current_app.logger.info(f'Student rejected and deleted: ID={id}')
            return jsonify({'message': 'Student rejected and deleted'})
        else:
            # 仅更新状态
            student = update_student(id, {'status': target_status})
            
            # 发送微信推送消息
            submitter_openid = student.get('submitter_openid')
            student_name = student.get('name')
            if submitter_openid and target_status == 'rejected':
                # 后台非阻塞发送防止拖慢响应，这里简单同步调用（已在服务内吃掉异常）
                send_review_result_message(submitter_openid, student_name, '已驳回', remark="请点击前往小程序进行修改")
                
            current_app.logger.info(f'Student moved to {target_status}: ID={id}')
            return jsonify({'message': f'Student moved to {target_status}', 'student': student})

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error rejecting student %s', id)
        return build_internal_error_response('驳回学员失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/approve', methods=['POST'])
def approve_student_route(id):
    """
    审核通过学员。

    审核通过时会执行以下操作:
    1. 为符合条件的学员自动生成体检表 Word 文档
       （目前支持叉车司机 N1 和锅炉水处理 G3 项目）
    2. 将学员状态更新为 'reviewed'
    3. 如果生成了体检表，将文件路径保存到 training_form_path 字段

    参数:
        id: 学员 ID

    返回:
        200: 更新后的学员记录
    """
    try:
        ensure_mini_admin()
        current_student = get_student_by_id(id)
        
        # 尝试为特定项目的学员生成体检表
        health_check_path = generate_health_check_form(
            current_student,
            current_app.config['BASE_DIR'],
            current_app.config['STUDENTS_FOLDER']
        )

        # 构建更新字段：状态 + 可选的体检表路径
        updates = {'status': 'reviewed'}
        if health_check_path:
            updates['training_form_path'] = health_check_path
        student = update_student(id, updates)

        # 发送微信推送消息
        submitter_openid = student.get('submitter_openid')
        student_name = student.get('name')
        if submitter_openid:
            send_review_result_message(submitter_openid, student_name, '已通过', remark="请点击前往小程序查看详情")

        if health_check_path:
            current_app.logger.info(f'Health check form generated for student ID={id}')
        
        current_app.logger.info(f'Student approved: ID={id}')
        return jsonify(student)

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error approving student %s', id)
        return build_internal_error_response('审核学员失败，请稍后重试')



@student_bp.route('/api/students/<int:id>/attachments.zip', methods=['GET'])
def download_attachments_zip_route(id):
    """
    将学员所有附件打包为 ZIP 下载。

    仅对已审核学员可用。将学员的所有附件文件（照片、证书、体检表等）
    打包为 ZIP 文件，通过内存缓冲区直接返回给客户端。

    ZIP 文件命名格式: <身份证号>-<姓名>.zip

    参数:
        id: 学员 ID

    返回:
        200: ZIP 文件流（Content-Type: application/zip）
        400: 学员未审核或无可打包文件
    """
    try:
        ensure_mini_admin()
        student = get_student_by_id(id)

        # 仅允许下载已审核学员的附件
        if student.get('status') != 'reviewed':
            return jsonify({'error': '仅支持已审核学员打包下载'}), 400

        # 需要打包的附件字段列表
        attachment_keys = [
            'photo_path', 'diploma_path',
            'id_card_front_path', 'id_card_back_path',
            'hukou_residence_path', 'hukou_personal_path', 'training_form_path'
        ]

        # 收集实际存在的附件文件
        files_to_zip = []
        for key in attachment_keys:
            rel = student.get(key, '')
            if not rel:
                continue
            abs_path = os.path.join(current_app.config['BASE_DIR'], rel)
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                # 使用文件名作为 ZIP 内的存档名
                arcname = os.path.basename(abs_path)
                files_to_zip.append((abs_path, arcname))

        if not files_to_zip:
            return jsonify({'error': '该学员暂无可打包的附件'}), 400

        # 在内存中创建 ZIP 文件（避免写入临时文件）
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            for abs_path, arcname in files_to_zip:
                try:
                    zf.write(abs_path, arcname)
                except Exception as e:
                    current_app.logger.error(f'Failed to add file to ZIP: {str(e)}')

        # 将读取位置重置到开头
        buffer.seek(0)

        from flask import send_file
        # 生成安全的文件名（移除路径分隔符）
        safe_name = f"{student.get('id_card','')}-{student.get('name','')}".replace('/', '-').replace('\\', '-')
        current_app.logger.info(f'Attachments ZIP generated for student ID={id}')

        return send_file(
            buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{safe_name}.zip"
        )

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error generating ZIP for student %s', id)
        return build_internal_error_response('打包附件失败，请稍后重试')



@student_bp.route('/api/companies', methods=['GET'])
def get_companies_route():
    """
    获取去重后的公司名称列表。

    用于管理后台的公司筛选下拉框，返回当前条件下有学员数据的公司列表。

    查询参数:
        status (str)        : 按学员状态筛选
        company (str)       : 按公司名称模糊筛选
        training_type (str) : 按培训类型筛选

    返回:
        200: 公司名称数组 ["公司A", "公司B", ...]
    """
    try:
        ensure_mini_admin()
        status = request.args.get('status', '')
        company_filter = request.args.get('company', '')
        training_type = request.args.get('training_type', '')

        companies = get_companies(status, company_filter, training_type)
        return jsonify(companies)

    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error getting companies')
        return build_internal_error_response('加载公司列表失败，请稍后重试')
