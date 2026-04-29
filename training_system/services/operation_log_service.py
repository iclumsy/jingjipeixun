"""
学员业务操作日志服务。

本模块负责把报名、审核、材料处理、下载、省网提交等关键动作写入
operation_logs 表，并提供按学员查询时间线的接口数据。
"""
import json

from flask import g, has_request_context, request

from models.student import get_db_connection
from utils.auth import get_client_ip, get_current_actor_name, get_current_actor_source


def _dump_json(value):
    try:
        return json.dumps(value or {}, ensure_ascii=False, separators=(',', ':'))
    except (TypeError, ValueError):
        return '{}'


def _load_json(value):
    try:
        decoded = json.loads(value or '{}')
        return decoded if isinstance(decoded, dict) else {}
    except (TypeError, ValueError):
        return {}


def _current_actor_openid():
    if not has_request_context():
        return ''
    mini_user = getattr(g, 'mini_user', None)
    if isinstance(mini_user, dict):
        return str(mini_user.get('openid') or '').strip()
    return ''


def _current_ip():
    if not has_request_context():
        return ''
    return get_client_ip(request)


def _current_user_agent():
    if not has_request_context():
        return ''
    return str(request.headers.get('User-Agent', '') or '')[:500]


def create_operation_log(
    student_id,
    action,
    action_label,
    actor_name=None,
    actor_source=None,
    actor_openid=None,
    status='success',
    message='',
    metadata=None,
    before=None,
    after=None,
):
    """写入一条学员操作日志，返回日志 ID。"""
    action = str(action or '').strip()
    action_label = str(action_label or '').strip()
    if not action or not action_label:
        return None

    with get_db_connection() as conn:
        cursor = conn.execute(
            '''
            INSERT INTO operation_logs (
                student_id, action, action_label, actor_name, actor_source,
                actor_openid, ip, user_agent, status, message,
                before_json, after_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                student_id,
                action,
                action_label,
                actor_name if actor_name is not None else get_current_actor_name(),
                actor_source if actor_source is not None else get_current_actor_source(),
                actor_openid if actor_openid is not None else _current_actor_openid(),
                _current_ip(),
                _current_user_agent(),
                str(status or 'success'),
                str(message or ''),
                _dump_json(before),
                _dump_json(after),
                _dump_json(metadata),
            )
        )
        return cursor.lastrowid


def get_student_operation_logs(student_id, limit=100):
    """按学员 ID 获取操作时间线，最新记录在前。"""
    try:
        normalized_limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        normalized_limit = 100

    with get_db_connection() as conn:
        rows = conn.execute(
            '''
            SELECT *
            FROM operation_logs
            WHERE student_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            ''',
            (student_id, normalized_limit)
        ).fetchall()

    logs = []
    for row in rows:
        item = dict(row)
        item['metadata'] = _load_json(item.pop('metadata_json', '{}'))
        item['before'] = _load_json(item.pop('before_json', '{}'))
        item['after'] = _load_json(item.pop('after_json', '{}'))
        logs.append(item)
    return logs


def log_student_operation(*args, **kwargs):
    """路由埋点用的容错包装：日志失败不影响主业务。"""
    try:
        return create_operation_log(*args, **kwargs)
    except Exception:
        return None
