import json
import os
from datetime import datetime

from models.student import get_db_connection


ACTIVE_STUDENT_STATUSES = ('reviewed', 'registered')
EXAM_BANK_TRAINING_TYPE = 'special_equipment'


def _json_dumps(value):
    return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(',', ':'))


def _json_loads(value, fallback):
    try:
        return json.loads(value or '')
    except (TypeError, ValueError):
        return fallback


def _read_json_questions(file_stream):
    raw = file_stream.read()
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8-sig')
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as err:
        raise ValueError(f'题库 JSON 格式无效: {err}') from err
    if not isinstance(data, list):
        raise ValueError('题库 JSON 必须是题目数组')
    return data


def _bank_key_from_filename(filename):
    base = os.path.basename(filename or '').strip()
    if base.lower().endswith('.json'):
        base = base[:-5]
    return base or f'bank_{int(datetime.now().timestamp())}'


def _normalize_question_type(question):
    type_text = str(question.get('type') or '').strip()
    type_code = question.get('type_code')
    if type_text == '判断题' or type_code in (0, 3, '0', '3'):
        return 'judge'
    if type_text == '多选题' or type_code in (2, '2'):
        return 'multi'
    return 'single'


def _has_answer(question):
    answer = question.get('answer')
    if answer is True or answer is False:
        return True
    if isinstance(answer, str):
        return bool(answer.strip())
    if isinstance(answer, list):
        return len(answer) > 0
    return False


def _normalize_question(question, sort_order):
    if not isinstance(question, dict):
        raise ValueError(f'第 {sort_order + 1} 道题不是对象')
    if not str(question.get('question') or '').strip():
        raise ValueError(f'第 {sort_order + 1} 道题缺少题干')
    if not _has_answer(question):
        raise ValueError(f'第 {sort_order + 1} 道题缺少答案')

    return {
        'source_question_id': str(question.get('id') or ''),
        'question_type': _normalize_question_type(question),
        'type_code': question.get('type_code'),
        'question': str(question.get('question') or '').strip(),
        'question_html': str(question.get('question_html') or question.get('question') or '').strip(),
        'options_json': _json_dumps(question.get('options') or {}),
        'answer_json': _json_dumps(question.get('answer') if question.get('answer') is not None else []),
        'analysis': str(question.get('analysis') or ''),
        'question_images_json': _json_dumps(question.get('question_images') or []),
        'option_images_json': _json_dumps(question.get('option_images') or {}),
        'audio': str(question.get('audio') or ''),
        'sort_order': sort_order,
        'raw_json': _json_dumps(question),
    }


def _row_to_bank(row):
    if not row:
        return None
    return dict(row)


def _row_to_question(row):
    item = dict(row)
    item['options'] = _json_loads(item.pop('options_json', '{}'), {})
    item['answer'] = _json_loads(item.pop('answer_json', '[]'), [])
    item['question_images'] = _json_loads(item.pop('question_images_json', '[]'), [])
    item['option_images'] = _json_loads(item.pop('option_images_json', '{}'), {})
    item.pop('raw_json', None)
    return item


def _get_training_project(conn, training_project_id):
    row = conn.execute(
        'SELECT * FROM training_projects WHERE id = ?',
        (training_project_id,),
    ).fetchone()
    if not row:
        raise ValueError('培训项目不存在')
    project = dict(row)
    if project.get('training_type') != EXAM_BANK_TRAINING_TYPE:
        raise ValueError('题库和真题练习仅支持特种设备项目')
    return project


def list_training_projects(include_inactive=False):
    with get_db_connection() as conn:
        query = 'SELECT * FROM training_projects WHERE training_type = ?'
        params = [EXAM_BANK_TRAINING_TYPE]
        if not include_inactive:
            query += ' AND is_active = ?'
            params.append(1)
        query += ' ORDER BY training_type, job_category, project_code, exam_project'
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def list_exam_banks():
    with get_db_connection() as conn:
        rows = conn.execute(
            'SELECT * FROM exam_banks ORDER BY updated_at DESC, id DESC'
        ).fetchall()
    return [_row_to_bank(row) for row in rows]


def get_exam_bank(bank_id):
    with get_db_connection() as conn:
        row = conn.execute('SELECT * FROM exam_banks WHERE id = ?', (bank_id,)).fetchone()
    return _row_to_bank(row)


def import_exam_bank(file_stream, filename, training_project_id, display_name='', is_active=True, replace_bank_id=None):
    raw_questions = _read_json_questions(file_stream)
    normalized_questions = [
        _normalize_question(question, idx)
        for idx, question in enumerate(raw_questions)
    ]
    if not normalized_questions:
        raise ValueError('题库不能为空')

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    bank_key = _bank_key_from_filename(filename)
    with get_db_connection() as conn:
        project = _get_training_project(conn, training_project_id)
        if replace_bank_id:
            existing = conn.execute(
                'SELECT * FROM exam_banks WHERE id = ?',
                (replace_bank_id,),
            ).fetchone()
            if not existing:
                raise ValueError('题库不存在')
            bank_id = int(replace_bank_id)
            conn.execute(
                '''
                UPDATE exam_banks
                SET training_project_id = ?, bank_key = ?, training_type = ?,
                    job_category = ?, exam_project = ?, project_code = ?,
                    display_name = ?, source_filename = ?, question_count = ?,
                    is_active = ?, imported_at = ?, updated_at = ?
                WHERE id = ?
                ''',
                (
                    training_project_id, bank_key, project['training_type'],
                    project['job_category'], project['exam_project'],
                    project.get('project_code', ''), display_name or bank_key,
                    filename, len(normalized_questions), 1 if is_active else 0,
                    now, now, bank_id,
                ),
            )
            conn.execute('DELETE FROM exam_questions WHERE bank_id = ?', (bank_id,))
        else:
            cursor = conn.execute(
                '''
                INSERT INTO exam_banks (
                    training_project_id, bank_key, training_type, job_category,
                    exam_project, project_code, display_name, source_filename,
                    question_count, is_active, imported_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    training_project_id, bank_key, project['training_type'],
                    project['job_category'], project['exam_project'],
                    project.get('project_code', ''), display_name or bank_key,
                    filename, len(normalized_questions), 1 if is_active else 0,
                    now, now,
                ),
            )
            bank_id = cursor.lastrowid

        conn.executemany(
            '''
            INSERT INTO exam_questions (
                bank_id, source_question_id, question_type, type_code, question,
                question_html, options_json, answer_json, analysis,
                question_images_json, option_images_json, audio, sort_order,
                raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (
                    bank_id, item['source_question_id'], item['question_type'],
                    item['type_code'], item['question'], item['question_html'],
                    item['options_json'], item['answer_json'], item['analysis'],
                    item['question_images_json'], item['option_images_json'],
                    item['audio'], item['sort_order'], item['raw_json'],
                )
                for item in normalized_questions
            ],
        )
        row = conn.execute('SELECT * FROM exam_banks WHERE id = ?', (bank_id,)).fetchone()
        return _row_to_bank(row)


def set_exam_bank_active(bank_id, is_active):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_db_connection() as conn:
        conn.execute(
            'UPDATE exam_banks SET is_active = ?, updated_at = ? WHERE id = ?',
            (1 if is_active else 0, now, bank_id),
        )
        row = conn.execute('SELECT * FROM exam_banks WHERE id = ?', (bank_id,)).fetchone()
        if not row:
            raise ValueError('题库不存在')
        return _row_to_bank(row)


def update_exam_bank(bank_id, display_name='', training_project_id=None):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_db_connection() as conn:
        existing = conn.execute('SELECT * FROM exam_banks WHERE id = ?', (bank_id,)).fetchone()
        if not existing:
            raise ValueError('题库不存在')
        project_id = training_project_id or existing['training_project_id']
        project = _get_training_project(conn, project_id)
        name = str(display_name or '').strip() or existing['display_name'] or existing['bank_key']
        conn.execute(
            '''
            UPDATE exam_banks
            SET training_project_id = ?, training_type = ?, job_category = ?,
                exam_project = ?, project_code = ?, display_name = ?, updated_at = ?
            WHERE id = ?
            ''',
            (
                project_id, project['training_type'], project['job_category'],
                project['exam_project'], project.get('project_code', ''),
                name, now, bank_id,
            ),
        )
        row = conn.execute('SELECT * FROM exam_banks WHERE id = ?', (bank_id,)).fetchone()
        return _row_to_bank(row)


def delete_exam_bank(bank_id):
    with get_db_connection() as conn:
        existing = conn.execute('SELECT id FROM exam_banks WHERE id = ?', (bank_id,)).fetchone()
        if not existing:
            raise ValueError('题库不存在')
        conn.execute('DELETE FROM mini_exam_records WHERE bank_id = ?', (bank_id,))
        conn.execute('DELETE FROM mini_practice_progress WHERE bank_id = ?', (bank_id,))
        conn.execute('DELETE FROM exam_questions WHERE bank_id = ?', (bank_id,))
        conn.execute('DELETE FROM exam_banks WHERE id = ?', (bank_id,))
    return {'success': True}


def get_questions(bank_id, mode='sequential', page=1, limit=20, wrong_question_ids=None, question_type=''):
    page_no = max(1, int(page or 1))
    page_size = min(max(1, int(limit or 20)), 100)
    offset = (page_no - 1) * page_size
    params = [bank_id]
    where = 'WHERE bank_id = ?'

    if wrong_question_ids:
        ids = [int(qid) for qid in wrong_question_ids if str(qid).isdigit()]
        if ids:
            placeholders = ','.join(['?'] * len(ids))
            where += f' AND id IN ({placeholders})'
            params.extend(ids)

    if question_type in ('single', 'multi', 'judge'):
        where += ' AND question_type = ?'
        params.append(question_type)

    order = 'ORDER BY sort_order ASC, id ASC'
    if mode in ('random', 'exam'):
        order = 'ORDER BY RANDOM()'

    with get_db_connection() as conn:
        total = conn.execute(f'SELECT COUNT(*) FROM exam_questions {where}', params).fetchone()[0]
        rows = conn.execute(
            f'SELECT * FROM exam_questions {where} {order} LIMIT ? OFFSET ?',
            params + [page_size, offset],
        ).fetchall()

    return {
        'list': [_row_to_question(row) for row in rows],
        'page': page_no,
        'limit': page_size,
        'total': total,
        'hasMore': offset + len(rows) < total,
    }


def _progress_for_banks(conn, openid, bank_ids):
    if not bank_ids:
        return {}
    placeholders = ','.join(['?'] * len(bank_ids))
    rows = conn.execute(
        f'''
        SELECT * FROM mini_practice_progress
        WHERE openid = ? AND bank_id IN ({placeholders}) AND mode = ?
        ''',
        [openid] + list(bank_ids) + ['practice'],
    ).fetchall()
    return {row['bank_id']: dict(row) for row in rows}


def _type_counts_for_banks(conn, bank_ids):
    if not bank_ids:
        return {}
    placeholders = ','.join(['?'] * len(bank_ids))
    rows = conn.execute(
        f'''
        SELECT bank_id, question_type, COUNT(*) AS count
        FROM exam_questions
        WHERE bank_id IN ({placeholders})
        GROUP BY bank_id, question_type
        ''',
        list(bank_ids),
    ).fetchall()
    result = {}
    for row in rows:
        bank_counts = result.setdefault(row['bank_id'], {
            'all': 0,
            'single': 0,
            'multi': 0,
            'judge': 0,
        })
        qtype = row['question_type'] if row['question_type'] in bank_counts else 'single'
        bank_counts[qtype] += int(row['count'] or 0)
        bank_counts['all'] += int(row['count'] or 0)
    return result


def _format_summary_bank(bank, progress=None, type_counts=None):
    wrong_ids = _json_loads((progress or {}).get('wrong_question_ids_json'), [])
    done = int((progress or {}).get('done_count') or 0)
    correct = int((progress or {}).get('correct_count') or 0)
    counts = type_counts or {
        'all': int(bank.get('question_count') or 0),
        'single': 0,
        'multi': 0,
        'judge': 0,
    }
    return {
        'id': bank['id'],
        'bankKey': bank['bank_key'],
        'displayName': bank['display_name'],
        'projectCode': bank.get('project_code') or '',
        'examProject': bank.get('exam_project') or '',
        'questionCount': int(bank.get('question_count') or 0),
        'typeCounts': counts,
        'progress': {
            'doneCount': done,
            'correctCount': correct,
            'wrongCount': len(wrong_ids) if isinstance(wrong_ids, list) else 0,
            'wrongQuestionIds': wrong_ids if isinstance(wrong_ids, list) else [],
        },
    }


def get_practice_summary(openid, is_admin=False):
    openid = str(openid or '').strip()
    with get_db_connection() as conn:
        if is_admin:
            rows = conn.execute(
                '''
                SELECT * FROM exam_banks
                WHERE is_active = 1 AND training_type = ?
                ORDER BY project_code, exam_project, id
                ''',
                (EXAM_BANK_TRAINING_TYPE,),
            ).fetchall()
        else:
            rows = conn.execute(
                f'''
                SELECT DISTINCT eb.*
                FROM exam_banks eb
                JOIN students s
                  ON (
                    (s.training_project_id IS NOT NULL AND s.training_project_id = eb.training_project_id)
                    OR (
                      COALESCE(s.project_code, '') = COALESCE(eb.project_code, '')
                      AND COALESCE(s.exam_project, '') = COALESCE(eb.exam_project, '')
                    )
                  )
                WHERE eb.is_active = 1
                  AND eb.training_type = ?
                  AND s.submitter_openid = ?
                  AND s.status IN ({','.join(['?'] * len(ACTIVE_STUDENT_STATUSES))})
                ORDER BY eb.project_code, eb.exam_project, eb.id
                ''',
                [EXAM_BANK_TRAINING_TYPE, openid] + list(ACTIVE_STUDENT_STATUSES),
            ).fetchall()
        banks = [_row_to_bank(row) for row in rows]
        progress = _progress_for_banks(conn, openid, [bank['id'] for bank in banks])
        type_counts = _type_counts_for_banks(conn, [bank['id'] for bank in banks])

    summary_banks = [
        _format_summary_bank(bank, progress.get(bank['id']), type_counts.get(bank['id']))
        for bank in banks
    ]
    return {
        'practiceEnabled': bool(summary_banks),
        'banks': summary_banks,
    }


def can_access_bank(openid, bank_id, is_admin=False):
    bank = get_exam_bank(bank_id)
    if not bank or int(bank.get('is_active') or 0) != 1:
        return False
    if bank.get('training_type') != EXAM_BANK_TRAINING_TYPE:
        return False
    if is_admin:
        return True
    summary = get_practice_summary(openid, is_admin=False)
    return any(item['id'] == int(bank_id) for item in summary['banks'])


def save_progress(openid, bank_id, payload):
    mode = str((payload or {}).get('mode') or 'practice')
    done = int((payload or {}).get('doneCount') or (payload or {}).get('done_count') or 0)
    correct = int((payload or {}).get('correctCount') or (payload or {}).get('correct_count') or 0)
    wrong_ids = (payload or {}).get('wrongQuestionIds')
    if wrong_ids is None:
        wrong_ids = (payload or {}).get('wrong_question_ids') or []
    last_question_id = (payload or {}).get('lastQuestionId') or (payload or {}).get('last_question_id')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_db_connection() as conn:
        conn.execute(
            '''
            INSERT INTO mini_practice_progress (
                openid, bank_id, mode, done_count, correct_count,
                wrong_question_ids_json, last_question_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(openid, bank_id, mode) DO UPDATE SET
                done_count = excluded.done_count,
                correct_count = excluded.correct_count,
                wrong_question_ids_json = excluded.wrong_question_ids_json,
                last_question_id = excluded.last_question_id,
                updated_at = excluded.updated_at
            ''',
            (
                openid, bank_id, mode, done, correct, _json_dumps(wrong_ids),
                last_question_id, now,
            ),
        )
    return {'success': True}


def save_exam_record(openid, bank_id, payload):
    payload = payload or {}
    score = int(payload.get('score') or 0)
    total = int(payload.get('total') or 0)
    correct = int(payload.get('correctCount') or payload.get('correct_count') or 0)
    duration = int(payload.get('durationSeconds') or payload.get('duration_seconds') or 0)
    passed = bool(payload.get('passed'))
    answers = payload.get('answers') or {}
    with get_db_connection() as conn:
        cursor = conn.execute(
            '''
            INSERT INTO mini_exam_records (
                openid, bank_id, score, total, correct_count,
                duration_seconds, passed, answers_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                openid, bank_id, score, total, correct,
                duration, 1 if passed else 0, _json_dumps(answers),
            ),
        )
        return {'success': True, 'id': cursor.lastrowid}
