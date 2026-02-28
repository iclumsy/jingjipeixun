"""Student-related routes."""
from flask import Blueprint, request, jsonify, current_app, g
from models.student import (
    create_student, get_students, get_student_by_id, update_student,
    delete_student, delete_students_batch,
    get_companies
)
from services.image_service import process_and_save_file, delete_student_files
from services.document_service import generate_health_check_form
from utils.validators import validate_student_data, validate_file_upload
from utils.error_handlers import AppError, ValidationError, NotFoundError
import os
import io
import zipfile
import time


student_bp = Blueprint('student', __name__)

FILE_MAP = {
    'photo': 'photo_path',
    'diploma': 'diploma_path',
    'id_card_front': 'id_card_front_path',
    'id_card_back': 'id_card_back_path',
    'hukou_residence': 'hukou_residence_path',
    'hukou_personal': 'hukou_personal_path'
}

REQUIRED_ATTACHMENTS = {
    'special_operation': ['diploma', 'id_card_front', 'id_card_back'],
    'special_equipment': ['photo', 'diploma', 'id_card_front', 'id_card_back', 'hukou_residence', 'hukou_personal']
}

EDUCATION_NORMALIZATION_MAP = {
    '初中': '初中',
    '初中或同等学历': '初中',
    '高中': '高中或同等学历',
    '高中或同等学历': '高中或同等学历',
    '中专': '中专或同等学历',
    '中专或同等学历': '中专或同等学历',
    '专科': '专科或同等学历',
    '大专': '专科或同等学历',
    '专科或同等学历': '专科或同等学历',
    '大专或同等学历': '专科或同等学历',
    '本科': '本科或同等学历',
    '本科或同等学历': '本科或同等学历',
    '研究生': '研究生及以上',
    '研究生及以上': '研究生及以上',
    '研究生或同等学历': '研究生及以上'
}


def normalize_training_type(training_type):
    """Normalize and validate training type."""
    value = (training_type or '').strip()
    if value in REQUIRED_ATTACHMENTS:
        return value
    return 'special_operation'


def normalize_education(education):
    """Normalize education text from different clients to canonical values."""
    value = (education or '').strip()
    if not value:
        return value
    return EDUCATION_NORMALIZATION_MAP.get(value, value)


def parse_bool(value):
    """Parse truthy query value."""
    if isinstance(value, bool):
        return value
    normalized = str(value or '').strip().lower()
    return normalized in ('1', 'true', 'yes', 'on')


def get_mini_user():
    """Return mini-program auth payload from request context."""
    user = getattr(g, 'mini_user', None)
    return user if isinstance(user, dict) else None


def is_mini_admin():
    """Whether current mini-program caller is admin."""
    user = get_mini_user()
    return bool(user and user.get('is_admin'))


def get_mini_openid():
    """Return mini-program caller openid."""
    user = get_mini_user()
    if not user:
        return ''
    return str(user.get('openid', '') or '').strip()


def ensure_mini_admin():
    """Reject non-admin mini callers for admin operations."""
    user = get_mini_user()
    if user and not is_mini_admin():
        raise AppError('无权限执行该操作', status_code=403)


def ensure_mini_owner_or_admin(student):
    """Reject mini caller if not owner and not admin."""
    user = get_mini_user()
    if not user or is_mini_admin():
        return
    owner_openid = str(student.get('submitter_openid', '') or '').strip()
    if owner_openid != get_mini_openid():
        raise AppError('无权限访问该记录', status_code=403)


def ensure_safe_relative_student_path(path_value):
    """Validate relative file path for students folder."""
    raw = str(path_value or '').strip()
    if not raw:
        return ''
    normalized = raw.replace('\\', '/')
    if normalized.startswith('/'):
        raise ValidationError('附件路径无效')
    if '..' in normalized.split('/'):
        raise ValidationError('附件路径无效')
    if not normalized.startswith('students/'):
        raise ValidationError('附件路径无效')
    return normalized


@student_bp.route('/api/students', methods=['POST'])
def create_student_route():
    """Create a new student."""
    try:
        use_multipart = bool(request.form or request.files)
        file_paths = {}

        if use_multipart:
            data = request.form
            files = request.files

            # Validate data
            validate_student_data(data)

            training_type = normalize_training_type(data.get('training_type', 'special_operation'))
            required_attachments = REQUIRED_ATTACHMENTS.get(training_type, REQUIRED_ATTACHMENTS['special_operation'])
            missing_files = [
                field for field in required_attachments
                if not files.get(field) or not files.get(field).filename
            ]
            if missing_files:
                fields = {field: '该培训项目下此附件为必传项' for field in missing_files}
                raise ValidationError('缺少必传附件', fields=fields)

            id_card_val = data.get('id_card', '').strip()
            company_val = data.get('company', '').strip()

            for input_name, db_key in FILE_MAP.items():
                file = files.get(input_name)
                if file and file.filename and id_card_val:
                    try:
                        validate_file_upload(file)
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
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                raise ValidationError('请求参数格式错误')

            validate_student_data(payload)
            training_type = normalize_training_type(payload.get('training_type', 'special_operation'))

            files_payload = payload.get('files', {}) if isinstance(payload.get('files', {}), dict) else {}
            for input_name, db_key in FILE_MAP.items():
                file_paths[db_key] = ensure_safe_relative_student_path(files_payload.get(input_name, ''))

            required_attachments = REQUIRED_ATTACHMENTS.get(training_type, REQUIRED_ATTACHMENTS['special_operation'])
            missing_files = [
                field for field in required_attachments
                if not file_paths.get(FILE_MAP[field], '')
            ]
            if missing_files:
                fields = {field: '该培训项目下此附件为必传项' for field in missing_files}
                raise ValidationError('缺少必传附件', fields=fields)

            student_payload = dict(payload)

        file_paths['training_form_path'] = ""

        # Create student
        student_payload['training_type'] = training_type
        student_payload['education'] = normalize_education(student_payload.get('education', ''))

        mini_user = get_mini_user()
        if mini_user and not is_mini_admin():
            student_payload['submitter_openid'] = get_mini_openid()
        else:
            student_payload['submitter_openid'] = (student_payload.get('submitter_openid', '') or '').strip()

        student_id = create_student(student_payload, file_paths)
        current_app.logger.info(f'Student created: ID={student_id}')

        return jsonify({'message': 'Student added successfully', 'id': student_id}), 201

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        current_app.logger.error(f'Error creating student (app error): {e.message}')
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.exception('Error creating student')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students', methods=['GET'])
def get_students_route():
    """Get students with optional filters."""
    try:
        status = request.args.get('status', 'unreviewed')
        search = request.args.get('search', '')
        company = request.args.get('company', '')
        training_type = request.args.get('training_type', '')
        mini_user = get_mini_user()

        if mini_user and not is_mini_admin():
            submitter_openid = get_mini_openid()
        else:
            my_only = parse_bool(request.args.get('my_only', False))
            submitter_openid = (request.args.get('submitter_openid', '') or '').strip()
            if my_only and not submitter_openid:
                # fallback: allow openid query alias
                submitter_openid = (request.args.get('openid', '') or '').strip()
            if not my_only:
                submitter_openid = ''

        students = get_students(status, search, company, training_type, submitter_openid)
        return jsonify(students)

    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error getting students: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>', methods=['GET'])
def get_student_route(id):
    """Get single student detail."""
    try:
        student = get_student_by_id(id)
        ensure_mini_owner_or_admin(student)
        return jsonify(student)
    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error getting student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>', methods=['PUT', 'PATCH'])
def update_student_route(id):
    """Update a student."""
    try:
        allowed_text = [
            'name', 'gender', 'education', 'school', 'major', 'id_card', 'phone',
            'company', 'company_address', 'job_category', 'exam_project', 'project_code', 'training_type', 'status'
        ]

        current_student = get_student_by_id(id)
        ensure_mini_owner_or_admin(current_student)
        if get_mini_user() and not is_mini_admin() and current_student.get('status') != 'rejected':
            raise AppError('当前状态不允许修改', status_code=403)

        updates = {}

        # Handle form data (multipart) or JSON
        if request.form:
            data = request.form
            for k in allowed_text:
                if k in data:
                    updates[k] = data[k]
            if 'project_code' not in updates and 'exam_code' in data:
                updates['project_code'] = data.get('exam_code', '')
            if 'training_type' in updates:
                updates['training_type'] = normalize_training_type(updates['training_type'])
            if 'education' in updates:
                updates['education'] = normalize_education(updates['education'])

            # Validate partial update
            if updates:
                validate_student_data(updates, required_fields=[])

            # Handle file uploads
            effective_training_type = normalize_training_type(
                data.get('training_type', updates.get('training_type', current_student.get('training_type', 'special_operation')))
            )
            allowed_attachments = set(REQUIRED_ATTACHMENTS.get(effective_training_type, REQUIRED_ATTACHMENTS['special_operation']))

            for input_name, db_key in FILE_MAP.items():
                f = request.files.get(input_name)
                if f and f.filename:
                    if input_name not in allowed_attachments:
                        raise ValidationError(f'{effective_training_type} 不允许上传 {input_name}')

                    validate_file_upload(f)
                    id_card_for_name = data.get('id_card', current_student['id_card'])
                    name_for_save = data.get('name', current_student['name'])
                    company_for_name = data.get('company', current_student.get('company', ''))

                    # Delete old file
                    old_rel = current_student.get(db_key)
                    if old_rel:
                        delete_student_files({db_key: old_rel}, current_app.config['BASE_DIR'])

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
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                raise ValidationError('请求参数格式错误')

            for k in allowed_text:
                if k in payload:
                    updates[k] = payload[k]
            if 'project_code' not in updates and 'exam_code' in payload:
                updates['project_code'] = payload.get('exam_code', '')
            if 'training_type' in updates:
                updates['training_type'] = normalize_training_type(updates['training_type'])
            if 'education' in updates:
                updates['education'] = normalize_education(updates['education'])

            # Validate partial update
            if updates:
                validate_student_data(updates, required_fields=[])

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
                    raise ValidationError(f'{effective_training_type} 不允许上传 {input_name}')

                old_rel = current_student.get(db_key, '')
                if old_rel and rel != old_rel:
                    delete_student_files({db_key: old_rel}, current_app.config['BASE_DIR'])
                updates[db_key] = rel

        effective_training_type = normalize_training_type(
            updates.get('training_type', current_student.get('training_type', 'special_operation'))
        )
        required_attachments = REQUIRED_ATTACHMENTS.get(effective_training_type, REQUIRED_ATTACHMENTS['special_operation'])
        for attachment_field in required_attachments:
            db_key = FILE_MAP[attachment_field]
            final_value = updates.get(db_key, current_student.get(db_key, ''))
            if not final_value:
                raise ValidationError(
                    '缺少必传附件',
                    fields={attachment_field: '该培训项目下此附件为必传项'}
                )

        # Update student
        updated_student = update_student(id, updates)
        current_app.logger.info(f'Student updated: ID={id}')

        return jsonify(updated_student)

    except (ValidationError, NotFoundError, AppError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error updating student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>/upload', methods=['POST'])
def upload_student_attachment_route(id):
    """Upload a single attachment for an existing student."""
    try:
        student = get_student_by_id(id)
        ensure_mini_owner_or_admin(student)
        if get_mini_user() and not is_mini_admin() and student.get('status') != 'rejected':
            raise AppError('当前状态不允许修改', status_code=403)

        training_type = normalize_training_type(student.get('training_type', 'special_operation'))
        allowed_attachments = set(REQUIRED_ATTACHMENTS.get(training_type, REQUIRED_ATTACHMENTS['special_operation']))

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

        if upload_field not in allowed_attachments:
            raise ValidationError('当前培训项目不需要该附件')

        validate_file_upload(upload_file)

        id_card_for_name = student.get('id_card', '')
        name_for_save = student.get('name', '')
        company_for_name = student.get('company', '')

        db_key = FILE_MAP[upload_field]
        old_rel = student.get(db_key)
        if old_rel:
            delete_student_files({db_key: old_rel}, current_app.config['BASE_DIR'])

        rel = process_and_save_file(
            upload_file,
            id_card_for_name,
            name_for_save,
            upload_field,
            company_for_name,
            training_type
        )
        updated = update_student(id, {db_key: rel})

        return jsonify({
            'message': '上传成功',
            'field': db_key,
            'path': rel,
            'student': updated
        })

    except (ValidationError, NotFoundError, AppError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error uploading attachment for student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/miniprogram/upload', methods=['POST'])
def miniprogram_upload_attachment_route():
    """Upload a single attachment before form submit (mini-program direct mode)."""
    try:
        upload_file = request.files.get('file')
        if not upload_file or not upload_file.filename:
            raise ValidationError('未检测到有效上传文件')

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
        allowed_attachments = set(REQUIRED_ATTACHMENTS.get(training_type, REQUIRED_ATTACHMENTS['special_operation']))
        if file_type not in allowed_attachments:
            raise ValidationError('当前培训项目不需要该附件')

        validate_file_upload(upload_file)

        id_card_for_name = str(request.form.get('id_card', '') or '').strip() or f"temp{int(time.time())}"
        name_for_save = str(request.form.get('name', '') or '').strip() or '未命名'
        company_for_name = str(request.form.get('company', '') or '').strip()

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
        current_app.logger.error(f'Error uploading mini attachment: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>/reject', methods=['POST'])
def reject_student_route(id):
    """Reject a student: update status by default, delete only when explicitly requested."""
    try:
        ensure_mini_admin()
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}

        should_delete_raw = data.get('delete', False)
        if isinstance(should_delete_raw, str):
            should_delete = should_delete_raw.strip().lower() in ('1', 'true', 'yes', 'y')
        else:
            should_delete = bool(should_delete_raw)

        target_status = str(data.get('status', 'rejected')).strip() or 'rejected'
        if target_status not in ('unreviewed', 'rejected'):
            target_status = 'rejected'
        
        if should_delete:
            student = delete_student(id)
            delete_student_files(student, current_app.config['BASE_DIR'])
            current_app.logger.info(f'Student rejected and deleted: ID={id}')
            return jsonify({'message': 'Student rejected and deleted'})
        else:
            student = update_student(id, {'status': target_status})
            current_app.logger.info(f'Student moved to {target_status}: ID={id}')
            return jsonify({'message': f'Student moved to {target_status}', 'student': student})

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error rejecting student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>/approve', methods=['POST'])
def approve_student_route(id):
    """Approve a student."""
    try:
        ensure_mini_admin()
        current_student = get_student_by_id(id)
        
        health_check_path = generate_health_check_form(
            current_student,
            current_app.config['BASE_DIR'],
            current_app.config['STUDENTS_FOLDER']
        )

        updates = {'status': 'reviewed'}
        if health_check_path:
            updates['training_form_path'] = health_check_path
        student = update_student(id, updates)

        if health_check_path:
            current_app.logger.info(f'Health check form generated for student ID={id}')
        
        current_app.logger.info(f'Student approved: ID={id}')
        return jsonify(student)

    except NotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error approving student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/<int:id>/generate', methods=['POST'])
def generate_materials_route(id):
    """Deprecated endpoint kept for backward compatibility."""
    current_app.logger.warning('Deprecated generate endpoint called for student ID=%s', id)
    return jsonify({
        'error': '该接口已下线，请使用审核通过自动生成体检表流程'
    }), 410


@student_bp.route('/api/students/<int:id>/attachments.zip', methods=['GET'])
def download_attachments_zip_route(id):
    """Download all attachments for a student as ZIP."""
    try:
        ensure_mini_admin()
        student = get_student_by_id(id)

        if student.get('status') != 'reviewed':
            return jsonify({'error': '仅支持已审核学员打包下载'}), 400

        attachment_keys = [
            'photo_path', 'diploma_path',
            'id_card_front_path', 'id_card_back_path',
            'hukou_residence_path', 'hukou_personal_path', 'training_form_path'
        ]

        files_to_zip = []
        for key in attachment_keys:
            rel = student.get(key, '')
            if not rel:
                continue
            abs_path = os.path.join(current_app.config['BASE_DIR'], rel)
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                arcname = os.path.basename(abs_path)
                files_to_zip.append((abs_path, arcname))

        if not files_to_zip:
            return jsonify({'error': '该学员暂无可打包的附件'}), 400

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            for abs_path, arcname in files_to_zip:
                try:
                    zf.write(abs_path, arcname)
                except Exception as e:
                    current_app.logger.error(f'Failed to add file to ZIP: {str(e)}')

        buffer.seek(0)

        from flask import send_file
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
        current_app.logger.error(f'Error generating ZIP for student {id}: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/batch/approve', methods=['POST'])
def batch_approve_students_route():
    """Batch approve students."""
    try:
        ensure_mini_admin()
        data = request.get_json()
        if not data or 'ids' not in data:
            raise ValidationError('Missing student IDs')

        ids = data['ids']
        if not isinstance(ids, list):
            raise ValidationError('IDs must be a list')

        approved_count = 0
        for student_id in ids:
            try:
                student = get_student_by_id(student_id)
                health_check_path = generate_health_check_form(
                    student,
                    current_app.config['BASE_DIR'],
                    current_app.config['STUDENTS_FOLDER']
                )
                updates = {'status': 'reviewed'}
                if health_check_path:
                    updates['training_form_path'] = health_check_path
                update_student(student_id, updates)
                approved_count += 1
            except Exception as e:
                current_app.logger.error(f'Failed to generate health check for student {student_id}: {str(e)}')
        
        current_app.logger.info(f'Batch approved {approved_count}/{len(ids)} students')

        return jsonify({'message': f'Successfully approved {approved_count} of {len(ids)} students'}), 200

    except (ValidationError, AppError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error batch approving students: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/batch/reject', methods=['POST'])
def batch_reject_students_route():
    """Batch reject and delete students."""
    try:
        ensure_mini_admin()
        data = request.get_json()
        if not data or 'ids' not in data:
            raise ValidationError('Missing student IDs')

        ids = data['ids']
        if not isinstance(ids, list):
            raise ValidationError('IDs must be a list')

        students = delete_students_batch(ids)

        # Delete files for each student
        for student in students:
            delete_student_files(student, current_app.config['BASE_DIR'])

        current_app.logger.info(f'Batch rejected {len(ids)} students')
        return jsonify({'message': f'Successfully rejected and deleted {len(ids)} students'}), 200

    except (ValidationError, AppError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error batch rejecting students: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/students/batch/delete', methods=['POST'])
def batch_delete_students_route():
    """Batch delete students."""
    try:
        ensure_mini_admin()
        data = request.get_json()
        if not data or 'ids' not in data:
            raise ValidationError('Missing student IDs')

        ids = data['ids']
        if not isinstance(ids, list):
            raise ValidationError('IDs must be a list')

        students = delete_students_batch(ids)

        # Delete files for each student
        for student in students:
            delete_student_files(student, current_app.config['BASE_DIR'])

        current_app.logger.info(f'Batch deleted {len(ids)} students')
        return jsonify({'message': f'Successfully deleted {len(ids)} students'}), 200

    except (ValidationError, AppError) as e:
        return jsonify(e.to_dict()), e.status_code
    except Exception as e:
        current_app.logger.error(f'Error batch deleting students: {str(e)}')
        return jsonify({'error': str(e)}), 500


@student_bp.route('/api/companies', methods=['GET'])
def get_companies_route():
    """Get distinct company names."""
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
        current_app.logger.error(f'Error getting companies: {str(e)}')
        return jsonify({'error': str(e)}), 500
