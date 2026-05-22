from flask import Blueprint, g, jsonify, render_template, request, current_app

from services import exam_bank_service
from services.operation_log_service import has_recent_duplicate_operation_log, log_student_operation


exam_bank_bp = Blueprint('exam_bank', __name__)
LEARNING_LOG_MIN_ANSWER_COUNT = 20


def _success(**payload):
    return jsonify({'success': True, **payload})


def _error(message, status=400):
    return jsonify({'success': False, 'message': str(message)}), status


def _parse_bool(value, default=False):
    if value is None or value == '':
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _require_mini_user():
    user = getattr(g, 'mini_user', None)
    if not isinstance(user, dict) or not user.get('openid'):
        return None
    return user


def _write_learning_operation_log(openid, bank_id, action, action_label, message, answered_count, metadata=None):
    if int(answered_count or 0) <= LEARNING_LOG_MIN_ANSWER_COUNT:
        return
    student = exam_bank_service.find_learning_log_student(openid, bank_id)
    if not student:
        return
    student_id = student.get('id')
    if has_recent_duplicate_operation_log(student_id, action, message):
        return
    log_student_operation(
        student_id,
        action,
        action_label,
        message=message,
        metadata={
            'bank_id': bank_id,
            'student_name': student.get('name', ''),
            **(metadata or {}),
        }
    )


@exam_bank_bp.route('/admin/exam-banks', methods=['GET'])
def exam_banks_admin_page():
    return render_template('exam_banks_admin.html')


@exam_bank_bp.route('/api/admin/exam_banks/projects', methods=['GET'])
def admin_exam_bank_projects():
    include_inactive = _parse_bool(request.args.get('include_inactive'), False)
    return _success(projects=exam_bank_service.list_training_projects(include_inactive=include_inactive))


@exam_bank_bp.route('/api/admin/exam_banks', methods=['GET'])
def admin_exam_banks():
    return _success(banks=exam_bank_service.list_exam_banks())


def _uploaded_file():
    file = request.files.get('file')
    if not file or not file.filename:
        raise ValueError('请选择题库 JSON 文件')
    return file


def _training_project_id():
    json_data = request.get_json(silent=True) or {} if request.is_json else {}
    raw = request.form.get('training_project_id') or json_data.get('training_project_id') or ''
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        raise ValueError('请选择培训项目')
    return value


@exam_bank_bp.route('/api/admin/exam_banks/import', methods=['POST'])
def admin_import_exam_bank():
    try:
        file = _uploaded_file()
        bank = exam_bank_service.import_exam_bank(
            file.stream,
            file.filename,
            _training_project_id(),
            display_name=request.form.get('display_name', ''),
            is_active=_parse_bool(request.form.get('is_active'), True),
        )
        return _success(bank=bank)
    except ValueError as err:
        return _error(err, 400)


@exam_bank_bp.route('/api/admin/exam_banks/<int:bank_id>/reimport', methods=['POST'])
def admin_reimport_exam_bank(bank_id):
    try:
        existing = exam_bank_service.get_exam_bank(bank_id)
        if not existing:
            return _error('题库不存在', 404)
        file = _uploaded_file()
        project_id = request.form.get('training_project_id') or existing.get('training_project_id')
        bank = exam_bank_service.import_exam_bank(
            file.stream,
            file.filename,
            int(project_id),
            display_name=request.form.get('display_name') or existing.get('display_name') or '',
            is_active=_parse_bool(request.form.get('is_active'), bool(existing.get('is_active'))),
            replace_bank_id=bank_id,
        )
        return _success(bank=bank)
    except ValueError as err:
        return _error(err, 400)


@exam_bank_bp.route('/api/admin/exam_banks/<int:bank_id>/toggle', methods=['POST'])
def admin_toggle_exam_bank(bank_id):
    try:
        data = request.get_json(silent=True) or {}
        bank = exam_bank_service.set_exam_bank_active(bank_id, _parse_bool(data.get('is_active'), False))
        return _success(bank=bank)
    except ValueError as err:
        return _error(err, 404)


@exam_bank_bp.route('/api/admin/exam_banks/<int:bank_id>/update', methods=['POST'])
def admin_update_exam_bank(bank_id):
    try:
        data = request.get_json(silent=True) or {}
        project_id = data.get('training_project_id') or data.get('trainingProjectId')
        bank = exam_bank_service.update_exam_bank(
            bank_id,
            display_name=data.get('display_name') or data.get('displayName') or '',
            training_project_id=int(project_id) if project_id else None,
        )
        return _success(bank=bank)
    except ValueError as err:
        return _error(err, 400)


@exam_bank_bp.route('/api/admin/exam_banks/<int:bank_id>', methods=['DELETE'])
def admin_delete_exam_bank(bank_id):
    try:
        return _success(**exam_bank_service.delete_exam_bank(bank_id))
    except ValueError as err:
        return _error(err, 404)


@exam_bank_bp.route('/api/miniprogram/practice/summary', methods=['GET'])
def mini_practice_summary():
    user = _require_mini_user()
    if not user:
        return _error('未授权访问，请先登录', 401)
    summary = exam_bank_service.get_practice_summary(
        user.get('openid', ''),
        is_admin=bool(user.get('is_admin')),
    )
    return jsonify(summary)


@exam_bank_bp.route('/api/miniprogram/practice/banks/<int:bank_id>/questions', methods=['GET'])
def mini_practice_questions(bank_id):
    user = _require_mini_user()
    if not user:
        return _error('未授权访问，请先登录', 401)
    if not exam_bank_service.can_access_bank(user.get('openid', ''), bank_id, bool(user.get('is_admin'))):
        return _error('无权限访问该题库', 403)
    wrong_ids = []
    if request.args.get('wrong_ids'):
        wrong_ids = [item for item in request.args.get('wrong_ids', '').split(',') if item.strip()]
    
    # 记录日志
    bank = exam_bank_service.get_exam_bank(bank_id)
    bank_name = bank.get('display_name') if bank else f"ID {bank_id}"
    mode = request.args.get('mode', 'sequential')
    mode_labels = {
        'sequential': '顺序练习',
        'random': '随机练习',
        'exam': '模拟考试',
        'wrong': '错题练习',
        'memorize': '背题模式',
        'type': '题型练习'
    }
    mode_label = mode_labels.get(mode, mode)
    current_app.logger.info(f"拉取了题库「{bank_name}」的题目，练习模式：{mode_label}")

    result = exam_bank_service.get_questions(
        bank_id,
        mode=request.args.get('mode', 'sequential'),
        page=request.args.get('page', 1),
        limit=request.args.get('limit', 20),
        wrong_question_ids=wrong_ids,
        question_type=request.args.get('question_type', ''),
    )
    return jsonify(result)


@exam_bank_bp.route('/api/miniprogram/practice/progress', methods=['POST'])
def mini_practice_progress():
    user = _require_mini_user()
    if not user:
        return _error('未授权访问，请先登录', 401)
    data = request.get_json(silent=True) or {}
    bank_id = int(data.get('bankId') or data.get('bank_id') or 0)
    if not exam_bank_service.can_access_bank(user.get('openid', ''), bank_id, bool(user.get('is_admin'))):
        return _error('无权限访问该题库', 403)

    # 记录日志
    bank = exam_bank_service.get_exam_bank(bank_id)
    bank_name = bank.get('display_name') if bank else f"ID {bank_id}"
    done = int(data.get('doneCount') or data.get('done_count') or 0)
    correct = int(data.get('correctCount') or data.get('correct_count') or 0)
    wrong_ids = data.get('wrongQuestionIds') or data.get('wrong_question_ids') or []
    message = f"更新了题库「{bank_name}」的练习进度，已做 {done} 题，答对 {correct} 题，错题数 {len(wrong_ids)}"
    current_app.logger.info(message)
    result = exam_bank_service.save_progress(user.get('openid', ''), bank_id, data)
    mode = str(data.get('mode') or 'practice')
    if mode == 'practice':
        _write_learning_operation_log(
            user.get('openid', ''),
            bank_id,
            'practice_progress_updated',
            '题库练习',
            message,
            done,
            metadata={
                'bank_name': bank_name,
                'done_count': done,
                'correct_count': correct,
                'wrong_count': len(wrong_ids),
            }
        )

    return jsonify(result)


@exam_bank_bp.route('/api/miniprogram/practice/exams', methods=['POST'])
def mini_practice_exam_record():
    user = _require_mini_user()
    if not user:
        return _error('未授权访问，请先登录', 401)
    data = request.get_json(silent=True) or {}
    bank_id = int(data.get('bankId') or data.get('bank_id') or 0)
    if not exam_bank_service.can_access_bank(user.get('openid', ''), bank_id, bool(user.get('is_admin'))):
        return _error('无权限访问该题库', 403)

    # 记录日志
    bank = exam_bank_service.get_exam_bank(bank_id)
    bank_name = bank.get('display_name') if bank else f"ID {bank_id}"
    score = int(data.get('score') or 0)
    total = int(data.get('total') or 0)
    correct = int(data.get('correctCount') or data.get('correct_count') or 0)
    duration = int(data.get('durationSeconds') or data.get('duration_seconds') or 0)
    passed = bool(data.get('passed'))
    
    passed_text = "通过" if passed else "未通过"
    minutes = duration // 60
    seconds = duration % 60
    duration_text = f"{minutes}分{seconds}秒" if minutes > 0 else f"{seconds}秒"
    
    message = f"提交了题库「{bank_name}」的模拟考试，得分：{score}分，总题数：{total}，答对：{correct}，用时：{duration_text}，结果：{passed_text}"
    current_app.logger.info(message)
    result = exam_bank_service.save_exam_record(user.get('openid', ''), bank_id, data)
    _write_learning_operation_log(
        user.get('openid', ''),
        bank_id,
        'practice_exam_submitted',
        '模拟考试',
        message,
        total,
        metadata={
            'bank_name': bank_name,
            'score': score,
            'total': total,
            'correct_count': correct,
            'duration_seconds': duration,
            'passed': passed,
        }
    )

    return jsonify(result)
