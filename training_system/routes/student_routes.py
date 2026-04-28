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
from functools import wraps
from flask import Blueprint, request, jsonify, current_app, g, session
from models.student import (
    create_student, get_students, get_student_by_id, update_student,
    delete_student, get_companies
)
from services.wechat_service import send_review_result_message, broadcast_new_student_to_admins
from services.image_service import process_and_save_file, delete_student_files
from services.document_service import generate_health_check_form
from services import storage_service
from services.student_serializer import enrich_student, enrich_students
from utils.validators import validate_student_data, validate_file_upload
from utils.error_handlers import AppError, ValidationError, NotFoundError
from utils.auth import get_client_ip, resolve_openid_name
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
    'hukou_personal': 'hukou_personal_path',  # 户口本个人页
    'certificate_info_page': 'certificate_info_page_path',  # 原证件说明和个人信息页
    'certificate_records_page': 'certificate_records_page_path'  # 原证件作业项目和聘用记录页
}

# 各培训类型的默认必传附件清单
# 特种设备默认按新考证处理；复审通过 application_type 使用单独清单。
REQUIRED_ATTACHMENTS = {
    'special_operation': ['diploma', 'id_card_front', 'id_card_back'],
    'special_equipment': ['photo', 'diploma', 'id_card_front', 'id_card_back', 'hukou_residence', 'hukou_personal']
}

APPLICATION_TYPES = {'new_exam', 'renewal'}

REQUIRED_ATTACHMENTS_BY_APPLICATION = {
    ('special_equipment', 'new_exam'): REQUIRED_ATTACHMENTS['special_equipment'],
    ('special_equipment', 'renewal'): ['photo', 'certificate_info_page', 'certificate_records_page'],
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


def normalize_application_type(training_type, application_type):
    """
    标准化报名类型。

    仅特种设备区分新考证和复审，其他培训类型统一按新考证处理。
    """
    if normalize_training_type(training_type) != 'special_equipment':
        return 'new_exam'
    value = (application_type or '').strip()
    if value in APPLICATION_TYPES:
        return value
    return 'new_exam'


def get_required_attachments(training_type, application_type='new_exam'):
    """
    获取当前培训类型和报名类型下的必传附件。
    """
    normalized_training_type = normalize_training_type(training_type)
    normalized_application_type = normalize_application_type(
        normalized_training_type,
        application_type
    )
    by_application = REQUIRED_ATTACHMENTS_BY_APPLICATION.get(
        (normalized_training_type, normalized_application_type)
    )
    if by_application is not None:
        return list(by_application)
    return list(REQUIRED_ATTACHMENTS.get(
        normalized_training_type,
        REQUIRED_ATTACHMENTS['special_operation']
    ))


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


def mini_admin_required(f):
    """
    装饰器：限制小程序普通用户访问管理员接口。

    判断逻辑：
    - Web 管理后台请求（g.mini_user 为 None）：已通过 session 认证，直接放行
    - 小程序管理员（is_admin=True）：放行
    - 小程序普通用户（is_admin=False）：返回 403
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = getattr(g, 'mini_user', None)
        if user and not user.get('is_admin'):
            return jsonify({
                'error': 'forbidden',
                'message': '无权限执行此操作'
            }), 403
        return f(*args, **kwargs)
    return decorated




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

            data_dict = data.to_dict(flat=True)
            # 校验学员基本信息（替换掉 job_category，改为校验 training_project_id）
            req_fields = ['name', 'gender', 'education', 'id_card', 'phone', 'company', 'company_address', 'training_project_id']
            validate_student_data(data_dict, required_fields=req_fields)

            project_id = data_dict.get('training_project_id')
            from models.student import get_db_connection
            with get_db_connection() as conn:
                proj = conn.execute("SELECT * FROM training_projects WHERE id = ? AND is_active = 1", (project_id,)).fetchone()
                if not proj:
                    raise ValidationError('所选培训项目不存在或已停用')
            
            data_dict['job_category'] = proj['job_category']
            data_dict['exam_project'] = proj['exam_project']
            data_dict['project_code'] = proj['project_code']
            data_dict['training_type'] = proj['training_type']
            training_type = proj['training_type']
            application_type = normalize_application_type(
                training_type,
                data_dict.get('application_type')
            )
            data_dict['application_type'] = application_type
            
            required_attachments = get_required_attachments(training_type, application_type)

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

            student_payload = data_dict
        else:
            # ---- JSON 路径引用模式 ----
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                raise ValidationError('请求参数格式错误')

            # 校验学员基本信息
            req_fields = ['name', 'gender', 'education', 'id_card', 'phone', 'company', 'company_address', 'training_project_id']
            validate_student_data(payload, required_fields=req_fields)

            project_id = payload.get('training_project_id')
            from models.student import get_db_connection
            with get_db_connection() as conn:
                proj = conn.execute("SELECT * FROM training_projects WHERE id = ? AND is_active = 1", (project_id,)).fetchone()
                if not proj:
                    raise ValidationError('所选培训项目不存在或已停用')
            
            payload['job_category'] = proj['job_category']
            payload['exam_project'] = proj['exam_project']
            payload['project_code'] = proj['project_code']
            payload['training_type'] = proj['training_type']
            training_type = proj['training_type']
            application_type = normalize_application_type(
                training_type,
                payload.get('application_type')
            )
            payload['application_type'] = application_type

            # 从 JSON 的 files 字段中提取并校验文件路径
            files_payload = payload.get('files', {}) if isinstance(payload.get('files', {}), dict) else {}

            # 检查必传附件路径是否齐全（提交时校验）
            required_attachments = get_required_attachments(training_type, application_type)
            missing_files = [
                field for field in required_attachments
                if not files_payload.get(field, '')
            ]
            if missing_files:
                fields = {field: '该培训项目下此附件为必传项' for field in missing_files}
                raise ValidationError('缺少必传附件', fields=fields)

            # 把临时文件 move 到学员正式目录，获取正式路径
            from services.image_service import commit_temp_files
            id_card_val = payload.get('id_card', '').strip()
            name_val = payload.get('name', '').strip()
            company_val = payload.get('company', '').strip()
            file_paths = commit_temp_files(
                files_payload, id_card_val, name_val, company_val, training_type
            )

            # 再次确认必传路径有效（commit 后再校验一次，防止文件缺失）
            still_missing = [
                field for field in required_attachments
                if not file_paths.get(FILE_MAP[field], '')
            ]
            if still_missing:
                fields = {field: '附件文件不存在或已过期，请重新上传' for field in still_missing}
                raise ValidationError('必传附件处理失败', fields=fields)

            student_payload = dict(payload)
            # 剔除前端 JSON 中非数据库列的字段（files 是附件路径字典，不是数据库列）
            student_payload.pop('files', None)

        # 体检表/培训表路径初始为空（审核通过时自动生成）
        file_paths['training_form_path'] = ""

        # 设置培训类型
        student_payload['training_type'] = training_type

        # 防重拦截：检查是否有正在处理的同项目报名
        from models.student import get_db_connection
        rejected_id = None
        with get_db_connection() as conn:
            existing = conn.execute(
                "SELECT id, status FROM students "
                "WHERE id_card = ? AND training_project_id = ? AND application_type = ?",
                (
                    student_payload.get('id_card', ''),
                    student_payload.get('training_project_id'),
                    student_payload.get('application_type', 'new_exam')
                )
            ).fetchone()
            if existing:
                if existing['status'] in ('unreviewed', 'reviewed', 'registered'):
                    raise AppError('该项目您已有正在处理或已通过的报名，请勿重复提交', status_code=400)
                elif existing['status'] == 'rejected':
                    rejected_id = existing['id']

        # 绑定提交人 openid
        mini_user = get_mini_user()
        if mini_user:
            # 小程序直接提交时，始终将记录归属绑定到令牌中的 openid
            student_payload['submitter_openid'] = get_mini_openid()
        else:
            # 管理后台提交时，保留前端传入的 openid（如有）
            student_payload['submitter_openid'] = (student_payload.get('submitter_openid', '') or '').strip()

        from models.student import create_student, update_student
        if rejected_id:
            # 覆盖修改已被驳回的老记录
            updates = dict(student_payload)
            updates.update(file_paths)
            updates['status'] = 'unreviewed'
            updates['reject_reason'] = '' # 清空驳回理由
            
            update_student(rejected_id, updates)
            student_id = rejected_id
            current_app.logger.info(f'重新提交学员(覆盖被驳回记录): ID={student_id}, 姓名={student_payload.get("name")}')
        else:
            # 创建数据库记录
            student_id = create_student(student_payload, file_paths)
            current_app.logger.info(f'新增学员: ID={student_id}, 姓名={student_payload.get("name")}')
        
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
        return jsonify(enrich_students(students))

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
        return jsonify(enrich_student(student))
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
        # 注意：status 不在此白名单中，状态变更必须通过 /approve 或 /reject 专用端点，
        # 以确保体检表生成、通知推送、报名材料自动生成等审核附加流程不被绕过。
        allowed_text = [
            'name', 'gender', 'education', 'school', 'major', 'id_card', 'phone',
            'company', 'company_address', 'training_project_id', 'application_type'
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

            # 校验部分更新字段（不要求必填字段齐全）
            if updates:
                validate_student_data(updates, required_fields=[])
                
            # 如果更新了项目
            if 'training_project_id' in updates:
                from models.student import get_db_connection
                with get_db_connection() as conn:
                    proj = conn.execute("SELECT * FROM training_projects WHERE id = ?", (updates['training_project_id'],)).fetchone()
                    if proj:
                        updates['job_category'] = proj['job_category']
                        updates['exam_project'] = proj['exam_project']
                        updates['project_code'] = proj['project_code']
                        updates['training_type'] = proj['training_type']
            effective_training_type = normalize_training_type(
                updates.get('training_type', current_student.get('training_type', 'special_operation'))
            )
            updates['application_type'] = normalize_application_type(
                effective_training_type,
                updates.get('application_type', current_student.get('application_type', 'new_exam'))
            )

            # 处理附件上传
            # 仅允许上传当前培训类型需要的附件
            allowed_attachments = set(get_required_attachments(
                effective_training_type,
                updates.get('application_type')
            ))

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
                        rel = process_and_save_file(
                                f, id_card_for_name, name_for_save, input_name, company_for_name, effective_training_type
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

            # 校验部分更新字段
            if updates:
                validate_student_data(updates, required_fields=[])
                
            # 如果更新了项目
            if 'training_project_id' in updates:
                from models.student import get_db_connection
                with get_db_connection() as conn:
                    proj = conn.execute("SELECT * FROM training_projects WHERE id = ?", (updates['training_project_id'],)).fetchone()
                    if proj:
                        updates['job_category'] = proj['job_category']
                        updates['exam_project'] = proj['exam_project']
                        updates['project_code'] = proj['project_code']
                        updates['training_type'] = proj['training_type']
            effective_training_type = normalize_training_type(
                updates.get('training_type', current_student.get('training_type', 'special_operation'))
            )
            updates['application_type'] = normalize_application_type(
                effective_training_type,
                updates.get('application_type', current_student.get('application_type', 'new_exam'))
            )

            # 处理 JSON 中的文件路径更新
            files_payload = payload.get('files', {}) if isinstance(payload.get('files', {}), dict) else {}
            allowed_attachments = set(get_required_attachments(
                effective_training_type,
                updates.get('application_type')
            ))

            from services.image_service import commit_temp_files
            id_card_val = updates.get('id_card', current_student.get('id_card', ''))
            name_val = updates.get('name', current_student.get('name', ''))
            company_val = updates.get('company', current_student.get('company', ''))
            # 提交临时目录的文件到正式目录，并获取其重命名后的路径
            committed_files = commit_temp_files(files_payload, id_card_val, name_val, company_val, effective_training_type)

            for input_name, db_key in FILE_MAP.items():
                if input_name not in files_payload:
                    continue
                rel = files_payload.get(input_name, '')
                if rel and input_name not in allowed_attachments:
                    # 忽略目标培训类型不需要的附件，避免历史遗留字段导致保存失败
                    continue

                # 如果文件是新上传的临时文件，已经经过 commit_temp_files 处理重命名并在 committed_files 产生结果
                if committed_files.get(db_key):
                    updates[db_key] = committed_files[db_key]
                else:
                    # 添加原有的更新路径（即未修改过的已经命名好的旧文件路径），安全检验后保留
                    updates[db_key] = ensure_safe_relative_student_path(rel)

        # 最终校验：确保更新后所有必传附件仍然齐全
        effective_training_type = normalize_training_type(
            updates.get('training_type', current_student.get('training_type', 'special_operation'))
        )
        effective_application_type = normalize_application_type(
            effective_training_type,
            updates.get('application_type', current_student.get('application_type', 'new_exam'))
        )
        required_attachments = get_required_attachments(
            effective_training_type,
            effective_application_type
        )
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
                
            # 2. 防止 ABA 并发流转：如果此时数据库已经是通过/已报名状态（管理员已处理），报错拦截
            if current_student.get('status') in ('reviewed', 'registered'):
                raise AppError('管理员已审核通过或已完成报名，无法再提交修改', status_code=403)
                
            # 3. 强制降维：既然他确实重新编辑并提交了图片或文字，强制恢复为待审核状态
            updates['status'] = 'unreviewed'
            updates['reject_reason'] = ''  # 清空旧的驳回原因
        # =========================================================

        # 通用逻辑：任何人（包括管理员）修改了已驳回学员的信息，自动重置为未审核
        if current_student.get('status') == 'rejected' and 'status' not in updates:
            updates['status'] = 'unreviewed'
            updates['reject_reason'] = ''

        # 执行数据库更新
        updated_student = update_student(id, updates)
        current_app.logger.info(f'修改学员资料: ID={id}, 姓名={updates.get("name", current_student.get("name"))}')

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

        return jsonify(enrich_student(updated_student))

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
        application_type = normalize_application_type(
            training_type,
            student.get('application_type', 'new_exam')
        )
        allowed_attachments = set(get_required_attachments(training_type, application_type))

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

        validate_file_upload(upload_file)

        # 保存到临时目录（提交时再 move 到正式目录）
        from services.image_service import save_temp_file
        tmp_rel = save_temp_file(upload_file, file_type)
        if not tmp_rel:
            raise AppError('临时文件保存失败', status_code=500)

        return jsonify({
            'success': True,
            'path': tmp_rel,
            'file_type': file_type
        })

    except (ValidationError, AppError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error uploading mini attachment')
        return build_internal_error_response()

@student_bp.route('/api/miniprogram/students/sync_cos', methods=['POST'])
def miniprogram_sync_cos_route():
    """
    接收小程序直接上传到 COS 后的回调同步请求。
    
    请求体 (JSON):
        cos_key   : COS 中的文件路径（如 students/tmp/.../xxx.jpg）
        file_type : 附件类型
    
    返回:
        200: {"success": true, "path": "students/...", "file_type": "photo"}
    """
    try:
        data = request.json or {}
        cos_key = data.get('cos_key')
        file_type = str(data.get('file_type') or data.get('fileType') or '').strip()

        if not cos_key or not cos_key.startswith('students/tmp/'):
            raise ValidationError('无效的 COS 同步路径')
            
        if file_type not in FILE_MAP:
            raise ValidationError('附件类型无效')

        from services.storage_service import pull_from_cos
        
        # 将 COS 文件下载回本地（因为后续生成体检表需要本地文件参与处理）
        success = pull_from_cos(cos_key)
        if not success:
            raise AppError('COS 文件同步到本地失败', status_code=500)

        # 这里直接返回与原接口一致的结构，无需额外再走 local tmp generator，
        # 因为 cos_key 本身已经包含了类似 tmp/... 的 uuid 格式，
        # 且已被 pull_from_cos 放置在了本地严格对应的文件位置上，
        # 在最终提交表单时，commit_temp_files 会顺畅地处理这些文件。
        
        return jsonify({
            'success': True,
            'path': cos_key,
            'file_type': file_type
        })
    except (ValidationError, AppError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error syncing cos attachment')
        return build_internal_error_response()


@student_bp.route('/api/students/<int:id>/reject', methods=['POST'])
@mini_admin_required
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
            operator = session.get('auth_user', 'unknown')
            client_ip = get_client_ip(request)
            submitter = resolve_openid_name(student.get('submitter_openid', ''))
            current_app.logger.info(
                f'[驱回并删除] 操作人={operator} IP={client_ip} '
                f'学员ID={id} 姓名={student.get("name","")} 提交人={submitter}'
            )
            return jsonify({'message': 'Student rejected and deleted'})
        else:
            # 保存状态和驳回原因
            reject_reason = str(data.get('reject_reason', '') or '').strip()
            updates = {'status': target_status}
            if target_status == 'rejected':
                updates['reject_reason'] = reject_reason
            else:
                updates['reject_reason'] = ''  # 恢复待审核时清空旧原因
            student = update_student(id, updates)

            # 发送微信推送消息
            submitter_openid = student.get('submitter_openid')
            student_name = student.get('name')
            if submitter_openid and target_status == 'rejected':
                # 微信模板 thing11 通常有字数限制（一般 20 个字符）
                remark = reject_reason[:20] if reject_reason else "请点击前往小程序进行修改"
                send_review_result_message(submitter_openid, student_name, '已驳回', remark=remark)
                
            operator = session.get('auth_user', 'unknown')
            client_ip = get_client_ip(request)
            submitter = resolve_openid_name(student.get('submitter_openid', ''))
            current_app.logger.info(
                f'[驱回] 操作人={operator} IP={client_ip} 目标状态={target_status} '
                f'学员ID={id} 姓名={student_name} 提交人={submitter}'
            )
            return jsonify({'message': f'Student moved to {target_status}', 'student': enrich_student(student)})

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error rejecting student %s', id)
        return build_internal_error_response('驳回学员失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/approve', methods=['POST'])
@mini_admin_required
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

        current_student = get_student_by_id(id)
        student_name = current_student.get('name', '未命名')
        
        # ---- 1. 先自动生成报名材料（人脸会被裁剪/白底处理，并在本地生成结果） ----
        materials_ok = False
        try:
            from services.material_service import generate_student_materials
            import io as _io
            import contextlib

            base_dir = current_app.config['BASE_DIR']
            output_root = current_app.config['STUDENTS_FOLDER']
            training_type = current_student.get('training_type', 'special_operation')
            company = current_student.get('company', '')
            training_type_map = {
                'special_operation': '特种作业',
                'special_equipment': '特种设备'
            }
            training_type_name = training_type_map.get(training_type, '特种作业')
            student_folder_name = f"{training_type_name}-{company}-{student_name}"
            actual_output_root = os.path.join(output_root, student_folder_name)

            log_buffer = _io.StringIO()
            with contextlib.redirect_stdout(log_buffer):
                report = generate_student_materials(current_student, base_dir, actual_output_root)

            for line in log_buffer.getvalue().splitlines():
                if line.strip():
                    current_app.logger.info(line)

            materials_ok = bool(report.get('success'))
            if materials_ok:
                current_app.logger.info(f'[自动生成材料] 学员ID={id} 姓名={student_name} 成功')
            else:
                current_app.logger.warning(f'[自动生成材料] 学员ID={id} 姓名={student_name} 未完全成功')
        except Exception as mat_err:
            current_app.logger.warning(f'[自动生成材料] 学员ID={id} 异常(不影响审核): {mat_err}')

        # ---- 2. 再尝试为特定项目的学员生成体检表（可使用刚生成的个人照片） ----
        health_check_path = generate_health_check_form(
            current_student,
            current_app.config['BASE_DIR'],
            current_app.config['STUDENTS_FOLDER']
        )

        # 构建更新字段：状态 + 可选的体检表路径 + 清空驳回原因
        updates = {'status': 'reviewed', 'reject_reason': ''}
        if health_check_path:
            updates['training_form_path'] = health_check_path
        student = update_student(id, updates)

        # 发送微信推送消息
        submitter_openid = student.get('submitter_openid')
        if submitter_openid:
            send_review_result_message(submitter_openid, student_name, '已通过', remark="请点击前往小程序查看详情")

        if health_check_path:
            current_app.logger.info(f'Health check form generated for student ID={id}')
            
        # 记录操作者信息：管理员账号 + 客户端 IP + 提交人 openid 映射
        operator = session.get('auth_user', 'unknown')
        client_ip = get_client_ip(request)
        submitter = resolve_openid_name(submitter_openid or '')
        current_app.logger.info(
            f'[审核通过] 操作人={operator} IP={client_ip} '
            f'学员ID={id} 姓名={student_name} 提交人={submitter}'
        )

        result = dict(student)
        result['materials_auto_generated'] = materials_ok
        return jsonify(enrich_student(result))

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error approving student %s', id)
        return build_internal_error_response('审核学员失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/swap_materials', methods=['POST'])
@mini_admin_required
def swap_materials_route(id):
    """
    互换两张图片的路径，例如身份证正反面、户口本首页和本人页等。
    参数: {"pair": "id_card" | "hukou"}
    """
    try:
        data = request.get_json(silent=True) or {}
        pair = data.get('pair')
        if pair not in ('id_card', 'hukou'):
            return jsonify({'error': '无效的互换类型'}), 400

        student = get_student_by_id(id)
        
        if pair == 'id_card':
            val1 = student.get('id_card_front_path')
            val2 = student.get('id_card_back_path')
            if not val1 or not val2:
                return jsonify({'error': '缺少照片，无法互换'}), 400
            update_student(id, {'id_card_front_path': val2, 'id_card_back_path': val1})
            
        elif pair == 'hukou':
            val1 = student.get('hukou_residence_path')
            val2 = student.get('hukou_personal_path')
            if not val1 or not val2:
                return jsonify({'error': '缺少照片，无法互换'}), 400
            update_student(id, {'hukou_residence_path': val2, 'hukou_personal_path': val1})

        updated = get_student_by_id(id)
        
        # 记录操作者信息：管理员账号 + 客户端 IP + 提交人 openid 映射
        operator = session.get('auth_user', 'unknown')
        client_ip = get_client_ip(request)
        submitter = resolve_openid_name(student.get('submitter_openid', ''))
        student_name = student.get('name', '未知')
        pair_name = '身份证正反面' if pair == 'id_card' else '户口本首页/本人页'
        
        current_app.logger.info(
            f'[图片互换] 操作人={operator} IP={client_ip} 互换目标={pair_name} '
            f'学员ID={id} 姓名={student_name} 提交人={submitter}'
        )
        
        return jsonify({'message': '互换成功', 'student': enrich_student(updated)})

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error swapping materials for student %s', id)
        return build_internal_error_response('互换失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/activate_card', methods=['POST'])
@mini_admin_required
def activate_card_route(id):
    """
    为特种设备审核通过学员开学习卡。

    仅限特种设备（special_equipment）且状态为已审核（reviewed）的学员。
    管理员需在前端核对学员信息后确认提交，本接口当前直接返回成功占位，
    后续将对接外部培训考试系统的开卡接口。

    参数:
        id: 学员 ID

    返回:
        200: {\"message\": \"开卡成功\", \"student\": {...}}
        400: 不符合开卡条件
        404: 学员不存在
    """
    try:
        student = get_student_by_id(id)

        # 仅特种设备且已审核的学员可以开卡
        if student.get('training_type') != 'special_equipment':
            return jsonify({'error': '仅特种设备学员可以开卡'}), 400
        if student.get('status') != 'reviewed':
            return jsonify({'error': '仅审核通过的学员可以开卡'}), 400

        # 防止重复开卡
        if student.get('card_activated'):
            return jsonify({'error': '该学员已开卡，请勿重复操作'}), 400

        # 调用外部系统接口实际办理开卡
        from services.junrui_service import activate_card_for_student
        from datetime import datetime
        
        operator_openid = get_mini_openid()
        if operator_openid:
            # 常见管理员映射提取
            mini_admin_names = {
                'oQRQz3VglMF63fWRtTCX8gbl21jo': '程超',
                'oQRQz3amHUiSlU5RYNqu-r4GBJlk': '单利亚',
                'oQRQz3SPn9tEiMy74NxfrzV1ZzJE': '霍玉萍'
            }
            operator = f"小程序-{mini_admin_names.get(operator_openid, operator_openid)}"
        else:
            operator = session.get('auth_user', 'unknown')
        client_ip = get_client_ip(request)
        current_app.logger.info(
            f'[开卡请求] 操作人={operator} IP={client_ip} '
            f'学员ID={id} 姓名={student.get("name","")} '
            f'身份证={student.get("id_card","")} 手机={student.get("phone","")} '
            f'项目={student.get("exam_project","")}'
        )

        result = activate_card_for_student(student)
        if not result.get("success"):
            return jsonify({'error': result.get("message", "办理失败，请重试")}), 400

        # 开卡成功，记录状态到数据库
        updated_student = update_student(id, {
            'card_activated': 1,
            'card_activated_at': datetime.now().isoformat()
        })

        current_app.logger.info(f'[开卡完成] 学员ID={id} 成功')
        return jsonify({'message': result.get("message", "开卡成功"), 'student': enrich_student(updated_student)})

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error activating card for student %s', id)
        return build_internal_error_response('开卡失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/query_card', methods=['POST'])
@mini_admin_required
def query_card_route(id):
    """
    查询学员的君瑞学习卡信息（纯查询，不写库）。

    通过身份证号到君瑞系统查询卡号和密码，直接返回给前端展示。
    """
    try:
        student = get_student_by_id(id)

        from services.junrui_service import query_card_for_student
        result = query_card_for_student(student)

        if result.get("success"):
            current_app.logger.info(
                f'[查询学习卡] 学员ID={id} 卡号={result.get("card_id", "")} 成功'
            )
            return jsonify(result)
        else:
            return jsonify(result), 400

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error querying card for student %s', id)
        return build_internal_error_response('查询学习卡失败')


@student_bp.route('/api/students/<int:id>/attachments.zip', methods=['GET'])
@mini_admin_required
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

        student = get_student_by_id(id)

        # 仅允许下载已审核学员的附件
        if student.get('status') != 'reviewed':
            return jsonify({'error': '仅支持已审核学员打包下载'}), 400

        # 需要打包的附件字段列表
        attachment_keys = [
            'photo_path', 'diploma_path',
            'id_card_front_path', 'id_card_back_path',
            'hukou_residence_path', 'hukou_personal_path',
            'certificate_info_page_path', 'certificate_records_page_path',
            'training_form_path'
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


@student_bp.route('/api/students/<int:id>/training_form', methods=['GET'])
@mini_admin_required
def download_training_form_route(id):
    """
    下载学员体检表文件。

    供小程序管理员和 Web 管理员直接下载体检表（.docx），
    不依赖静态文件服务，通过 Flask send_file 返回文件流，
    小程序端可通过 wx.downloadFile 接收。

    权限:
        - Web 管理员（session 认证）：允许
        - 小程序管理员（JWT is_admin）：允许
        - 小程序普通用户：403

    参数:
        id: 学员 ID

    返回:
        200: 体检表文件流（application/octet-stream）
        400: 学员未审核或无体检表
        403: 无权限（小程序普通用户）
        404: 学员不存在
    """
    from flask import send_file
    try:
        student = get_student_by_id(id)


        if student.get('status') != 'reviewed':
            return jsonify({'error': '仅支持已审核学员下载体检表'}), 400

        rel = student.get('training_form_path', '')
        if not rel:
            return jsonify({'error': '该学员暂无体检表'}), 400

        abs_path = os.path.join(current_app.config['BASE_DIR'], rel)
        if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
            return jsonify({'error': '体检表文件不存在，请重新审核生成'}), 400

        filename = os.path.basename(abs_path)
        current_app.logger.info(f'[体检表下载] 学员ID={id} 姓名={student.get("name","")} 文件={filename}')
        return send_file(
            abs_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=filename
        )

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error downloading training form for student %s', id)
        return build_internal_error_response('下载体检表失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/regenerate_training_form', methods=['POST'])
@mini_admin_required
def regenerate_training_form_route(id):
    """
    重新生成体检表，使用最新的报名材料个人照片。
    仅对已审核/已报名学员可用。
    """
    try:
        student = get_student_by_id(id)
        if student.get('status') not in ('reviewed', 'registered'):
            return jsonify({'error': '仅支持已审核学员重新生成体检表'}), 400

        health_check_path = generate_health_check_form(
            student,
            current_app.config['BASE_DIR'],
            current_app.config['STUDENTS_FOLDER']
        )

        if not health_check_path:
            return jsonify({'error': '该学员不支持生成体检表（仅支持叉车司机N1/锅炉水处理G3）'}), 400

        updated = update_student(id, {'training_form_path': health_check_path})
        current_app.logger.info(f'[体检表重新生成] 学员ID={id} 姓名={student.get("name","")} 路径={health_check_path}')

        # 同步到 COS
        try:
            base_dir = current_app.config['BASE_DIR']
            abs_path = os.path.join(base_dir, health_check_path)
            if os.path.exists(abs_path):
                from services.cos_service import upload_to_cos
                upload_to_cos(abs_path, health_check_path)
        except Exception as cos_err:
            current_app.logger.warning(f'[体检表重新生成] COS同步失败: {cos_err}')

        return jsonify({'message': '体检表已重新生成', 'training_form_path': health_check_path})

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error regenerating training form for student %s', id)
        return build_internal_error_response('重新生成体检表失败')


@student_bp.route('/api/students/<int:id>/generate_materials', methods=['POST'])
@mini_admin_required
def generate_materials_route(id):
    """
    生成报名材料。
    """
    try:

        student = get_student_by_id(id)
        if student.get('status') != 'reviewed':
            return jsonify({'error': '仅支持已审核学员生成报名材料'}), 400
            
        from services.material_service import generate_student_materials, generate_health_check_form
        import io as _io
        import contextlib
        base_dir = current_app.config['BASE_DIR']
        output_root = current_app.config['STUDENTS_FOLDER']
        
        data = request.get_json(silent=True) or {}
        material_type = data.get('material_type')

        if material_type == 'training_form':
            health_check_path = generate_health_check_form(student, base_dir, output_root)
            if not health_check_path:
                return jsonify({'error': '该学员不支持生成体检表'}), 400
            update_student(id, {'training_form_path': health_check_path})
            return jsonify({'message': '体检表已重新生成', 'training_form_path': health_check_path})

        training_type = student.get('training_type', 'special_operation')
        company = student.get('company', '')
        name = student.get('name', '')
        training_type_map = {
            'special_operation': '特种作业',
            'special_equipment': '特种设备'
        }
        training_type_name = training_type_map.get(training_type, '特种作业')
        student_folder_name = f"{training_type_name}-{company}-{name}"
        actual_output_root = os.path.join(output_root, student_folder_name)
        
        # 捕获 print 输出
        log_buffer = _io.StringIO()
        with contextlib.redirect_stdout(log_buffer):
            report = generate_student_materials(student, base_dir, actual_output_root)
        logs = log_buffer.getvalue()
        
        # 同时输出到服务器日志
        for line in logs.splitlines():
            if line.strip():
                current_app.logger.info(line)
        
        payload = {
            'message': '生成成功' if report.get('success') else '生成未完全成功',
            'logs': logs,
            'log_summary': report.get('log_summary', {}),
            'log_events': report.get('log_events', []),
        }
        if not report.get('success'):
            payload['error'] = 'material_generation_failed'
            return jsonify(payload), 500
        return jsonify(payload)
    except Exception as e:
        current_app.logger.exception('Error generating materials for student %s', id)
        return build_internal_error_response('生成报名材料失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/analyze_material_points', methods=['POST'])
@mini_admin_required
def analyze_material_points_route(id):
    """
    预分析材料裁剪点坐标。用于前端裁图调整时默认展示 AI 自动裁剪的识别区域。
    """
    try:

        student = get_student_by_id(id)
        if not student:
            return jsonify({'error': '未找到学员'}), 404

        data = request.get_json(silent=True) or {}
        material_type = data.get('material_type', '')
        adjustments = dict(data.get('adjustments', {}))
        
        base_dir = current_app.config['BASE_DIR']
        
        def _get_points(path_key, profile_func):
            rel = student.get(path_key)
            if not rel:
                return None
            abs_p = os.path.join(base_dir, rel)
            if not os.path.exists(abs_p):
                return None
            from services.material_service import read_cv_image
            img = read_cv_image(abs_p)
            if img is None:
                return None
                
            crop_kwargs = {
                'return_meta': True,
                'expand_level': adjustments.get('expand_level'),
                'skip_ratio_trim': adjustments.get('skip_ratio_trim', False)
            }
            crop_mode = adjustments.get('crop_mode', 'auto')
            if crop_mode == 'none':
                return None
            if crop_mode == 'rect_only':
                crop_kwargs['allow_perspective'] = False
            # auto_crop_diploma 不接受 canny_scale
            if 'canny_scale' in adjustments and profile_func != auto_crop_diploma:
                crop_kwargs['canny_scale'] = float(adjustments['canny_scale'])
                
            _, meta = profile_func(img, **crop_kwargs)
            sel = meta.get('selected_candidate')
            if sel and sel.get('points_orig'):
                return sel['points_orig']
            return None

        result = {}
        from services.material_service import auto_crop_id_card, auto_crop_diploma, auto_crop_hukou_page

        if material_type == 'id_card':
            result['front_points'] = _get_points('id_card_front_path', auto_crop_id_card)
            result['back_points'] = _get_points('id_card_back_path', auto_crop_id_card)
        elif material_type == 'diploma':
            result['points'] = _get_points('diploma_path', auto_crop_diploma)
        elif material_type == 'hukou':
            result['home_points'] = _get_points('hukou_residence_path', auto_crop_hukou_page)
            result['personal_points'] = _get_points('hukou_personal_path', auto_crop_hukou_page)
            
        return jsonify(result)

    except Exception as e:
        current_app.logger.exception('Error analyzing points for student %s', id)
        return build_internal_error_response('预分析裁剪区域失败')


@student_bp.route('/api/students/<int:id>/manual_crop_material', methods=['POST'])
@mini_admin_required
def manual_crop_material_route(id):
    """
    手动画框裁剪：接收用户在原图上标记的 4 个角点，对原始附件图像做透视变换，
    然后以 crop_mode=none 调用 regenerate_single_material 完成 A4 排版和方向校正。
    """
    import tempfile
    try:

        student = get_student_by_id(id)
        if not student:
            return jsonify({'error': '未找到学员'}), 404

        data = request.get_json(silent=True) or {}
        material_type = data.get('material_type', '')
        if material_type not in ('diploma', 'id_card', 'hukou', 'photo'):
            return jsonify({'error': '无效的 material_type'}), 400

        base_dir = current_app.config['BASE_DIR']
        output_root = current_app.config['STUDENTS_FOLDER']

        def crop_points_to_temp(abs_path, points, crop_mode):
            """对原图按给定模式裁剪，写入临时文件并返回路径。"""
            if not abs_path or not os.path.exists(abs_path):
                return None
            import numpy as np
            from services.material_service import read_cv_image, write_cv_image, crop_image_with_points
            img = read_cv_image(abs_path)
            if img is None:
                return None
            current_app.logger.info(f"[manual_crop] Loaded image {abs_path} with shape {img.shape}")
            current_app.logger.info(f"[manual_crop] Received manual points: {points}")
            pts = np.array(points, dtype='float32')
            if crop_mode == 'none':
                return None
            actual_mode = 'rect_only' if crop_mode == 'rect_only' else 'perspective'
            cropped = crop_image_with_points(img, pts, mode=actual_mode)
            suffix = os.path.splitext(abs_path)[1] or '.jpg'
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False,
                                              dir=os.path.dirname(abs_path))
            tmp.close()
            write_cv_image(tmp.name, cropped)
            return tmp.name

        def resolve(key, pts_key, crop_mode):
            """返回 (abs_path, is_temp)：有 4 点则透视裁剪成临时文件，否则用原始路径。"""
            rel = student.get(key)
            abs_p = os.path.join(base_dir, rel) if rel else None
            pts = data.get(pts_key)
            if pts and len(pts) == 4:
                tmp_path = crop_points_to_temp(abs_p, pts, crop_mode)
                if tmp_path is None:
                    return abs_p, False
                return tmp_path, True
            return abs_p, False

        tmp_files = []
        adjustments = dict(data.get('adjustments', {}))
        crop_mode = adjustments.get('crop_mode', 'auto')

        student_copy = dict(student)

        if material_type == 'photo':
            # photo 固定比例矩形裁剪（前端已转为4点格式）使用 rect_only 模式
            p, is_tmp = resolve('photo_path', 'points', 'rect_only')
            if is_tmp and p:
                tmp_files.append(p)
                student_copy['photo_path'] = os.path.relpath(p, base_dir)
                adjustments['manual_crop_applied'] = True

        elif material_type == 'id_card':
            front_path, front_tmp = resolve('id_card_front_path', 'front_points', crop_mode)
            back_path,  back_tmp  = resolve('id_card_back_path',  'back_points', crop_mode)
            if front_tmp and front_path:
                tmp_files.append(front_path)
                student_copy['id_card_front_path'] = os.path.relpath(front_path, base_dir)
                adjustments['front_manual_crop_applied'] = True
            if back_tmp and back_path:
                tmp_files.append(back_path)
                student_copy['id_card_back_path'] = os.path.relpath(back_path, base_dir)
                adjustments['back_manual_crop_applied'] = True

        elif material_type == 'diploma':
            p, is_tmp = resolve('diploma_path', 'points', crop_mode)
            if is_tmp and p:
                tmp_files.append(p)
                student_copy['diploma_path'] = os.path.relpath(p, base_dir)
                adjustments['manual_crop_applied'] = True

        elif material_type == 'hukou':
            hp, h_tmp = resolve('hukou_residence_path', 'home_points', crop_mode)
            pp, p_tmp = resolve('hukou_personal_path',  'personal_points', crop_mode)
            if h_tmp and hp:
                tmp_files.append(hp)
                student_copy['hukou_residence_path'] = os.path.relpath(hp, base_dir)
                adjustments['home_manual_crop_applied'] = True
            if p_tmp and pp:
                tmp_files.append(pp)
                student_copy['hukou_personal_path'] = os.path.relpath(pp, base_dir)
                adjustments['personal_manual_crop_applied'] = True

        import io as _io, contextlib
        from services.material_service import regenerate_single_material

        log_buffer = _io.StringIO()
        try:
            with contextlib.redirect_stdout(log_buffer):
                report = regenerate_single_material(student_copy, base_dir, output_root, material_type, adjustments)
        finally:
            for f in tmp_files:
                try:
                    os.remove(f)
                except Exception:
                    pass

        logs = log_buffer.getvalue()
        for line in logs.splitlines():
            if line.strip():
                current_app.logger.info(line)

        payload = {
            'message': '手动裁剪并重新生成成功' if report.get('success') else '手动裁剪后的重新生成失败',
            'logs': logs,
            'log_summary': report.get('log_summary', {}),
            'log_events': report.get('log_events', []),
        }
        if not report.get('success'):
            payload['error'] = 'material_generation_failed'
            return jsonify(payload), 500
        return jsonify(payload)
    except Exception as e:
        current_app.logger.exception('Error in manual_crop_material for student %s', id)
        return build_internal_error_response('手动裁剪失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/regenerate_material', methods=['POST'])
@mini_admin_required
def regenerate_material_route(id):
    """
    重新生成单个报名材料（带调整参数）。
    """
    try:

        student = get_student_by_id(id)
        if student.get('status') != 'reviewed':
            return jsonify({'error': '仅支持已审核学员'}), 400

        data = request.get_json(silent=True) or {}
        material_type = data.get('material_type', '')
        if material_type not in ('diploma', 'id_card', 'hukou', 'photo', 'training_form'):
            return jsonify({'error': '无效的 material_type'}), 400
            
        base_dir = current_app.config['BASE_DIR']
        output_root = current_app.config['STUDENTS_FOLDER']
        
        # ==== 特殊处理：如果是重新生成体检表 ====
        if material_type == 'training_form':
            from services.document_service import generate_health_check_form
            health_check_path = generate_health_check_form(student, base_dir, output_root)
            if health_check_path:
                updates = {'training_form_path': health_check_path}
                update_student(id, updates)
                try:
                    from services.cos_service import upload_file
                    abs_path = os.path.join(base_dir, health_check_path)
                    if os.path.exists(abs_path):
                        with open(abs_path, 'rb') as f:
                            upload_file(health_check_path, f.read())
                except Exception as e:
                    current_app.logger.warning(f"重新生成体检表同步COS失败: {e}")
                return jsonify({'message': '体检表重新生成成功'})
            else:
                return jsonify({'error': '体检表重新生成失败'}), 500

        adjustments = data.get('adjustments', {})

        from services.material_service import regenerate_single_material
        import io as _io
        import contextlib
        base_dir = current_app.config['BASE_DIR']
        output_root = current_app.config['STUDENTS_FOLDER']

        log_buffer = _io.StringIO()
        with contextlib.redirect_stdout(log_buffer):
            report = regenerate_single_material(student, base_dir, output_root, material_type, adjustments)
        logs = log_buffer.getvalue()

        for line in logs.splitlines():
            if line.strip():
                current_app.logger.info(line)

        payload = {
            'message': '重新生成成功' if report.get('success') else '重新生成失败',
            'logs': logs,
            'log_summary': report.get('log_summary', {}),
            'log_events': report.get('log_events', []),
        }
        if not report.get('success'):
            payload['error'] = 'material_generation_failed'
            return jsonify(payload), 500
        return jsonify(payload)
    except Exception as e:
        current_app.logger.exception('Error regenerating material for student %s', id)
        return build_internal_error_response('重新生成失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/generated_materials', methods=['GET'])
@mini_admin_required
def get_generated_materials_route(id):
    """
    获取已生成的报名材料预览列表。
    """
    try:

        student = get_student_by_id(id)
        
        id_card = student.get('id_card', '')
        name = student.get('name', '')
        name_prefix = f"{id_card}-{name}"
        
        training_type = student.get('training_type', 'special_operation')
        company = student.get('company', '')
        training_type_map = {
            'special_operation': '特种作业',
            'special_equipment': '特种设备'
        }
        training_type_name = training_type_map.get(training_type, '特种作业')
        student_folder_name = f"{training_type_name}-{company}-{name}"
        material_folder_name = f"{name_prefix}-报名材料"
        
        output_dir = os.path.join(current_app.config['STUDENTS_FOLDER'], student_folder_name, material_folder_name)
        
        if not os.path.exists(output_dir) or not os.path.isdir(output_dir):
            materials = []
        else:
            materials = []
            for filename in sorted(os.listdir(output_dir)):
                if filename.startswith('.'):
                    continue
                abs_path = os.path.join(output_dir, filename)
                if os.path.isfile(abs_path):
                    mtime = int(os.path.getmtime(abs_path))
                    url = f"students/{student_folder_name}/{material_folder_name}/{filename}"
                    materials.append({
                        "name": filename,
                        "url": url,
                        "mtime": mtime
                    })

        # 追加位于父目录的体检表（不在报名材料文件夹中）
        training_form_rel = student.get('training_form_path')
        if training_form_rel:
            abs_form_path = os.path.join(current_app.config['BASE_DIR'], training_form_rel)
            if os.path.exists(abs_form_path):
                materials.append({
                    "name": os.path.basename(abs_form_path),
                    "url": training_form_rel,
                    "mtime": int(os.path.getmtime(abs_form_path))
                })

        return jsonify({'exists': len(materials) > 0, 'materials': materials}), 200

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error fetching generated materials for student %s', id)
        return build_internal_error_response('获取报名材料失败，请稍后重试')


@student_bp.route('/api/students/<int:id>/download_materials.zip', methods=['GET'])
@mini_admin_required
def download_materials_zip_route(id):
    """
    下载生成的报名材料（ZIP）。
    """
    try:

        student = get_student_by_id(id)
        if student.get('status') != 'reviewed':
            return jsonify({'error': '仅支持已审核学员打包下载'}), 400
            
        id_card = student.get('id_card', '')
        name = student.get('name', '')
        name_prefix = f"{id_card}-{name}"
        
        training_type = student.get('training_type', 'special_operation')
        company = student.get('company', '')
        training_type_map = {
            'special_operation': '特种作业',
            'special_equipment': '特种设备'
        }
        training_type_name = training_type_map.get(training_type, '特种作业')
        student_folder_name = f"{training_type_name}-{company}-{name}"
        
        output_dir = os.path.join(current_app.config['STUDENTS_FOLDER'], student_folder_name, f"{name_prefix}-报名材料")
        
        if not os.path.exists(output_dir) or not os.path.isdir(output_dir):
            return jsonify({'error': '该学员暂未生成报名材料子文件夹'}), 400
            
        files_to_zip = []
        for filename in os.listdir(output_dir):
            abs_path = os.path.join(output_dir, filename)
            if os.path.isfile(abs_path):
                # 为了保留子文件夹结构
                arcname = os.path.join(f"{name_prefix}-报名材料", filename)
                files_to_zip.append((abs_path, arcname))

        if not files_to_zip:
            return jsonify({'error': '报名材料文件夹为空'}), 400

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            for abs_path, arcname in files_to_zip:
                try:
                    zf.write(abs_path, arcname)
                except Exception as e:
                    current_app.logger.error(f'Failed to add file to ZIP: {str(e)}')

        buffer.seek(0)

        from flask import send_file
        safe_name = f"{name_prefix}-报名材料".replace('/', '-').replace('\\', '-')

        return send_file(
            buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{safe_name}.zip"
        )

    except Exception as e:
        current_app.logger.exception('Error generating materials ZIP for student %s', id)
        return build_internal_error_response('打包报名材料失败，请稍后重试')


@student_bp.route('/api/companies', methods=['GET'])
@mini_admin_required
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


@student_bp.route('/api/stats/dashboard', methods=['GET'])
@mini_admin_required
def dashboard_stats_route():
    """
    数据看板统计 API。

    返回:
        - total: 学员总数
        - by_status: 各状态数量
        - this_month: 本月新增数量
        - by_training_type: 按培训类型分布
        - monthly_trend: 近 6 个月新增趋势
        - recent_students: 最近 5 名学员摘要
    """
    try:
        from models.student import get_db_connection
        from datetime import datetime, timedelta

        with get_db_connection() as conn:
            # 总数
            total = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]

            # 各状态数量
            rows = conn.execute(
                'SELECT status, COUNT(*) as cnt FROM students GROUP BY status'
            ).fetchall()
            by_status = {r['status']: r['cnt'] for r in rows}

            # 本月新增
            now = datetime.now()
            month_start = now.strftime('%Y-%m-01')
            this_month = conn.execute(
                'SELECT COUNT(*) FROM students WHERE created_at >= ?',
                (month_start,)
            ).fetchone()[0]

            # 按培训类型分布
            rows = conn.execute(
                'SELECT training_type, COUNT(*) as cnt FROM students GROUP BY training_type'
            ).fetchall()
            type_map = {'special_operation': '特种作业', 'special_equipment': '特种设备'}
            by_training_type = {type_map.get(r['training_type'], r['training_type']): r['cnt'] for r in rows}

            # 近 6 个月趋势
            monthly_trend = []
            for i in range(5, -1, -1):
                d = now - timedelta(days=i * 30)
                m_start = d.strftime('%Y-%m-01')
                # 计算下个月第一天
                if d.month == 12:
                    m_end = f'{d.year + 1}-01-01'
                else:
                    m_end = f'{d.year}-{d.month + 1:02d}-01'
                cnt = conn.execute(
                    'SELECT COUNT(*) FROM students WHERE created_at >= ? AND created_at < ?',
                    (m_start, m_end)
                ).fetchone()[0]
                monthly_trend.append({
                    'month': d.strftime('%Y-%m'),
                    'count': cnt
                })

            # 最近 5 名学员
            recent = conn.execute(
                'SELECT id, name, company, status, training_type, created_at '
                'FROM students ORDER BY id DESC LIMIT 5'
            ).fetchall()
            recent_students = [dict(r) for r in recent]

        return jsonify({
            'total': total,
            'by_status': by_status,
            'this_month': this_month,
            'by_training_type': by_training_type,
            'monthly_trend': monthly_trend,
            'recent_students': recent_students,
        })

    except Exception as e:
        current_app.logger.exception('Error getting dashboard stats')
        return build_internal_error_response('获取统计数据失败')
