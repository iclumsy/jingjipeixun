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


def _row_to_question_state(row, question_id_override=None):
    item = dict(row)
    answer = _json_loads(item.get('last_answer_json'), [])
    if not isinstance(answer, list):
        answer = [answer] if answer not in (None, '') else []
    return {
        'id': item.get('id'),
        'openid': item.get('openid') or '',
        'bankId': item.get('bank_id'),
        'questionId': question_id_override if question_id_override is not None else item.get('question_id'),
        'status': item.get('status') or 'seen',
        'answerCount': int(item.get('answer_count') or 0),
        'correctCount': int(item.get('correct_count') or 0),
        'wrongCount': int(item.get('wrong_count') or 0),
        'lastAnswer': answer,
        'lastMode': item.get('last_mode') or '',
        'seenAt': item.get('seen_at') or '',
        'lastAnsweredAt': item.get('last_answered_at') or '',
        'createdAt': item.get('created_at') or '',
        'updatedAt': item.get('updated_at') or '',
    }


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on', 'correct')


def _normalize_answer_payload(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if ',' in text:
        return [item.strip() for item in text.split(',') if item.strip()]
    return [text]


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
        conn.execute('DELETE FROM mini_question_states WHERE bank_id = ?', (bank_id,))
        conn.execute('DELETE FROM exam_questions WHERE bank_id = ?', (bank_id,))
        conn.execute('DELETE FROM exam_banks WHERE id = ?', (bank_id,))
    return {'success': True}


def get_questions(bank_id, mode='sequential', page=1, limit=20, wrong_question_ids=None, question_type='', openid=''):
    page_no = max(1, int(page or 1))
    page_size = min(max(1, int(limit or 20)), 100)
    offset = (page_no - 1) * page_size
    student_openid = str(openid or '').strip()
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

    order_params = []
    order = 'ORDER BY sort_order ASC, id ASC'
    if mode == 'memorize' and student_openid:
        order = '''
        ORDER BY CASE
            WHEN id IN (
                SELECT question_id
                FROM mini_question_states
                WHERE openid = ? AND bank_id = ? AND COALESCE(seen_at, '') != ''
            ) THEN 1 ELSE 0
        END, sort_order ASC, id ASC
        '''
        order_params = [student_openid, bank_id]
    if mode in ('random', 'exam'):
        order = 'ORDER BY RANDOM()'

    with get_db_connection() as conn:
        total = conn.execute(f'SELECT COUNT(*) FROM exam_questions {where}', params).fetchone()[0]
        rows = conn.execute(
            f'SELECT * FROM exam_questions {where} {order} LIMIT ? OFFSET ?',
            params + order_params + [page_size, offset],
        ).fetchall()
        question_rows = [_row_to_question(row) for row in rows]
        state_counts = {}
        states_by_question_id = {}
        if student_openid:
            state_where = 'WHERE qs.openid = ? AND qs.bank_id = ?'
            state_params = [student_openid, bank_id]
            if question_type in ('single', 'multi', 'judge'):
                state_where += ' AND eq.question_type = ?'
                state_params.append(question_type)
            state_row = conn.execute(
                f'''
                SELECT
                    SUM(CASE WHEN COALESCE(qs.seen_at, '') != '' THEN 1 ELSE 0 END) AS seen_count,
                    SUM(CASE WHEN qs.status = 'mastered' THEN 1 ELSE 0 END) AS mastered_count,
                    SUM(CASE WHEN qs.status = 'wrong' THEN 1 ELSE 0 END) AS wrong_count,
                    COUNT(*) AS touched_count
                FROM mini_question_states qs
                JOIN exam_questions eq ON eq.id = qs.question_id
                {state_where}
                ''',
                state_params,
            ).fetchone()
            state_counts = {
                'seen': int(state_row['seen_count'] or 0) if state_row else 0,
                'mastered': int(state_row['mastered_count'] or 0) if state_row else 0,
                'wrong': int(state_row['wrong_count'] or 0) if state_row else 0,
                'touched': int(state_row['touched_count'] or 0) if state_row else 0,
            }
            if not state_counts['touched']:
                legacy_progress = conn.execute(
                    '''
                    SELECT *
                    FROM mini_practice_progress
                    WHERE openid = ? AND bank_id = ? AND mode = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    ''',
                    (student_openid, bank_id, 'practice'),
                ).fetchone()
                if legacy_progress:
                    legacy_done = max(0, int(legacy_progress['done_count'] or 0))
                    legacy_correct = max(0, int(legacy_progress['correct_count'] or 0))
                    legacy_wrong_ids = _json_loads(legacy_progress['wrong_question_ids_json'], [])
                    legacy_wrong = len(legacy_wrong_ids) if isinstance(legacy_wrong_ids, list) else 0
                    if not legacy_wrong:
                        legacy_wrong = max(0, legacy_done - legacy_correct)
                    state_counts = {
                        'seen': 0,
                        'mastered': min(legacy_correct, legacy_done),
                        'wrong': max(0, legacy_wrong),
                        'touched': legacy_done,
                    }
            question_ids = [int(item['id']) for item in question_rows if str(item.get('id') or '').isdigit()]
            if question_ids:
                placeholders = ','.join(['?'] * len(question_ids))
                state_rows = conn.execute(
                    f'''
                    SELECT *
                    FROM mini_question_states
                    WHERE openid = ? AND bank_id = ? AND question_id IN ({placeholders})
                    ''',
                    [student_openid, bank_id] + question_ids,
                ).fetchall()
                states_by_question_id = {
                    int(row['question_id']): _row_to_question_state(row)
                    for row in state_rows
                }

    if states_by_question_id:
        for item in question_rows:
            item['state'] = states_by_question_id.get(int(item.get('id') or 0))

    return {
        'list': question_rows,
        'page': page_no,
        'limit': page_size,
        'total': total,
        'hasMore': offset + len(rows) < total,
        'questionState': _aggregate_question_state_summary(total, state_counts),
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


def _question_state_counts_for_banks(conn, openid, bank_ids):
    if not bank_ids or not openid:
        return {}
    placeholders = ','.join(['?'] * len(bank_ids))
    rows = conn.execute(
        f'''
        SELECT
            bank_id,
            SUM(CASE WHEN COALESCE(seen_at, '') != '' THEN 1 ELSE 0 END) AS seen_count,
            SUM(CASE WHEN status = 'mastered' THEN 1 ELSE 0 END) AS mastered_count,
            SUM(CASE WHEN status = 'wrong' THEN 1 ELSE 0 END) AS wrong_count,
            COUNT(*) AS touched_count
        FROM mini_question_states
        WHERE openid = ? AND bank_id IN ({placeholders})
        GROUP BY bank_id
        ''',
        [openid] + list(bank_ids),
    ).fetchall()
    result = {}
    for row in rows:
        result[row['bank_id']] = {
            'seen': int(row['seen_count'] or 0),
            'mastered': int(row['mastered_count'] or 0),
            'wrong': int(row['wrong_count'] or 0),
            'touched': int(row['touched_count'] or 0),
        }
    return result


def _wrong_question_ids_for_banks(conn, openid, bank_ids):
    if not bank_ids or not openid:
        return {}
    placeholders = ','.join(['?'] * len(bank_ids))
    rows = conn.execute(
        f'''
        SELECT bank_id, question_id
        FROM mini_question_states
        WHERE openid = ? AND bank_id IN ({placeholders}) AND status = ?
        ORDER BY updated_at DESC, id DESC
        ''',
        [openid] + list(bank_ids) + ['wrong'],
    ).fetchall()
    result = {}
    for row in rows:
        result.setdefault(row['bank_id'], []).append(row['question_id'])
    return result


def _aggregate_question_state_summary(question_count, counts=None):
    counts = counts or {}
    total = max(0, int(question_count or 0))
    seen_count = int(counts.get('seen') or 0)
    mastered_count = int(counts.get('mastered') or 0)
    wrong_count = int(counts.get('wrong') or 0)
    touched_count = int(counts.get('touched') or 0)
    if not touched_count:
        touched_count = seen_count + mastered_count + wrong_count
    answered_count = mastered_count + wrong_count
    untouched_count = max(0, total - touched_count)
    return {
        'seenCount': seen_count,
        'masteredCount': mastered_count,
        'wrongCount': wrong_count,
        'untouchedCount': untouched_count,
        'answeredCount': answered_count,
        'touchedCount': touched_count,
        'studyProgressPercent': round(touched_count * 100 / total) if total else 0,
        'answerProgressPercent': round(answered_count * 100 / total) if total else 0,
        'masteryPercent': round(mastered_count * 100 / total) if total else 0,
        'correctRate': round(mastered_count * 100 / answered_count) if answered_count else 0,
    }


def _format_summary_bank(bank, progress=None, type_counts=None, question_counts=None, wrong_question_ids=None):
    wrong_ids = _json_loads((progress or {}).get('wrong_question_ids_json'), [])
    done = int((progress or {}).get('done_count') or 0)
    correct = int((progress or {}).get('correct_count') or 0)
    state_summary = _aggregate_question_state_summary(
        int(bank.get('question_count') or 0),
        question_counts,
    )
    current_wrong_ids = wrong_question_ids if isinstance(wrong_question_ids, list) else None
    legacy_wrong_ids = wrong_ids if isinstance(wrong_ids, list) else []
    merged_wrong_ids = current_wrong_ids if current_wrong_ids is not None else legacy_wrong_ids
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
            'doneCount': state_summary['answeredCount'] or done,
            'correctCount': state_summary['masteredCount'] or correct,
            'wrongCount': state_summary['wrongCount'] if question_counts else len(legacy_wrong_ids),
            'wrongQuestionIds': merged_wrong_ids,
            'lastQuestionId': (progress or {}).get('last_question_id'),
        },
        'questionState': {
            **state_summary,
            'wrongQuestionIds': merged_wrong_ids,
        },
    }


def _duration_text(seconds):
    seconds = max(0, int(seconds or 0))
    minutes = seconds // 60
    remain = seconds % 60
    if minutes > 0:
        return f'{minutes}分{remain}秒'
    return f'{remain}秒'


def _format_learning_time(value):
    value = str(value or '').strip()
    if not value:
        return ''
    if len(value) >= 16:
        return value[:16].replace('T', ' ')
    return value.replace('T', ' ')


def _empty_learning_summary(state='not_started'):
    text_map = {
        'no_bank': ('未匹配题库', '该学员当前项目还没有可用题库'),
        'not_started': ('未开始', '还没有练习或模拟考试记录'),
        'practicing': ('练习中', '已开始题库练习'),
        'exam_attempted': ('已模拟考试', '已有模拟考试记录'),
        'passed': ('已通过模拟考试', '最近可关注后续报名进度'),
    }
    state_text, advice_text = text_map.get(state, text_map['not_started'])
    return {
        'state': state,
        'stateText': state_text,
        'adviceText': advice_text,
        'doneCount': 0,
        'questionCount': 0,
        'progressPercent': 0,
        'seenCount': 0,
        'masteredCount': 0,
        'untouchedCount': 0,
        'answeredCount': 0,
        'studyProgressPercent': 0,
        'answerProgressPercent': 0,
        'masteryPercent': 0,
        'correctCount': 0,
        'correctRate': 0,
        'wrongCount': 0,
        'lastStudyAt': '',
        'lastStudyTimeText': '',
        'examCount': 0,
        'latestScore': None,
        'bestScore': None,
        'passCount': 0,
        'latestPassed': False,
        'latestDurationText': '',
    }


def _find_student_bank(conn, student):
    training_project_id = student.get('training_project_id')
    project_code = str(student.get('project_code') or '').strip()
    exam_project = str(student.get('exam_project') or '').strip()
    row = conn.execute(
        '''
        SELECT *
        FROM exam_banks
        WHERE is_active = 1
          AND training_type = ?
          AND (
            (? IS NOT NULL AND training_project_id = ?)
            OR (
              COALESCE(project_code, '') = ?
              AND COALESCE(exam_project, '') = ?
            )
          )
        ORDER BY
          CASE WHEN (? IS NOT NULL AND training_project_id = ?) THEN 0 ELSE 1 END,
          updated_at DESC,
          id DESC
        LIMIT 1
        ''',
        (
            EXAM_BANK_TRAINING_TYPE,
            training_project_id, training_project_id,
            project_code, exam_project,
            training_project_id, training_project_id,
        ),
    ).fetchone()
    return _row_to_bank(row)


def _format_exam_record(row):
    return {
        'id': row.get('id'),
        'score': int(row.get('score') or 0),
        'total': int(row.get('total') or 0),
        'correctCount': int(row.get('correct_count') or 0),
        'durationSeconds': int(row.get('duration_seconds') or 0),
        'durationText': _duration_text(row.get('duration_seconds')),
        'passed': bool(int(row.get('passed') or 0)),
        'createdAt': row.get('created_at') or '',
        'timeText': _format_learning_time(row.get('created_at')),
    }


def get_student_learning_status(student):
    """汇总管理员查看某个学员学习情况所需的数据。"""
    student = dict(student or {})
    openid = str(student.get('submitter_openid') or '').strip()
    base = {
        'success': True,
        'student': {
            'id': student.get('id'),
            'name': student.get('name') or '',
            'status': student.get('status') or '',
            'examProject': student.get('exam_project') or '',
            'projectCode': student.get('project_code') or '',
            'trainingProjectId': student.get('training_project_id'),
        },
        'bank': None,
        'summary': _empty_learning_summary('no_bank'),
        'examStats': {
            'count': 0,
            'bestScore': None,
            'passCount': 0,
            'latest': None,
        },
        'activities': [],
    }
    if not openid:
        base['summary']['stateText'] = '未绑定用户'
        base['summary']['adviceText'] = '该学员没有小程序提交人信息'
        base['examStats']['records'] = []
        return base

    with get_db_connection() as conn:
        bank = _find_student_bank(conn, student)
        if not bank:
            return base

        progress = conn.execute(
            '''
            SELECT *
            FROM mini_practice_progress
            WHERE openid = ? AND bank_id = ? AND mode = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            ''',
            (openid, bank['id'], 'practice'),
        ).fetchone()
        state_rows = conn.execute(
            '''
            SELECT
                SUM(CASE WHEN COALESCE(seen_at, '') != '' THEN 1 ELSE 0 END) AS seen_count,
                SUM(CASE WHEN status = 'mastered' THEN 1 ELSE 0 END) AS mastered_count,
                SUM(CASE WHEN status = 'wrong' THEN 1 ELSE 0 END) AS wrong_count,
                COUNT(*) AS touched_count
            FROM mini_question_states
            WHERE openid = ? AND bank_id = ?
            ''',
            (openid, bank['id']),
        ).fetchone()
        latest_state = conn.execute(
            '''
            SELECT updated_at
            FROM mini_question_states
            WHERE openid = ? AND bank_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            ''',
            (openid, bank['id']),
        ).fetchone()
        exam_rows = conn.execute(
            '''
            SELECT *
            FROM mini_exam_records
            WHERE openid = ? AND bank_id = ?
            ORDER BY created_at DESC, id DESC
            ''',
            (openid, bank['id']),
        ).fetchall()

    progress = dict(progress) if progress else None
    latest_state = dict(latest_state) if latest_state else None
    exams = [dict(row) for row in exam_rows]
    question_count = int(bank.get('question_count') or 0)
    state_row = dict(state_rows) if state_rows else {}
    state_counts = {
        'seen': int(state_row.get('seen_count') or 0),
        'mastered': int(state_row.get('mastered_count') or 0),
        'wrong': int(state_row.get('wrong_count') or 0),
        'touched': int(state_row.get('touched_count') or 0),
    }
    state_summary = _aggregate_question_state_summary(question_count, state_counts)
    done = state_summary['answeredCount']
    correct = state_summary['masteredCount']
    wrong_count = state_summary['wrongCount']
    touched_count = state_summary['touchedCount']
    exam_count = len(exams)
    pass_count = sum(1 for row in exams if int(row.get('passed') or 0) == 1)
    best_score = max([int(row.get('score') or 0) for row in exams], default=None)
    latest = exams[0] if exams else None

    if pass_count > 0:
        state = 'passed'
    elif exam_count > 0:
        state = 'exam_attempted'
    elif touched_count > 0:
        state = 'practicing'
    else:
        state = 'not_started'

    summary = _empty_learning_summary(state)
    last_candidates = []
    if latest_state and latest_state.get('updated_at'):
        last_candidates.append(str(latest_state.get('updated_at')))
    if latest and latest.get('created_at'):
        last_candidates.append(str(latest.get('created_at')))
    last_study_at = max(last_candidates) if last_candidates else ''

    summary.update({
        'doneCount': done,
        'questionCount': question_count,
        'progressPercent': state_summary['studyProgressPercent'],
        'seenCount': state_summary['seenCount'],
        'masteredCount': state_summary['masteredCount'],
        'untouchedCount': state_summary['untouchedCount'],
        'answeredCount': state_summary['answeredCount'],
        'studyProgressPercent': state_summary['studyProgressPercent'],
        'answerProgressPercent': state_summary['answerProgressPercent'],
        'masteryPercent': state_summary['masteryPercent'],
        'correctCount': correct,
        'correctRate': state_summary['correctRate'],
        'wrongCount': wrong_count,
        'lastStudyAt': last_study_at,
        'lastStudyTimeText': _format_learning_time(last_study_at),
        'examCount': exam_count,
        'latestScore': int(latest.get('score') or 0) if latest else None,
        'bestScore': best_score,
        'passCount': pass_count,
        'latestPassed': bool(int(latest.get('passed') or 0)) if latest else False,
        'latestDurationText': _duration_text(latest.get('duration_seconds')) if latest else '',
    })

    activities = []
    if touched_count > 0:
        activities.append({
            'type': 'practice',
            'title': '题库练习',
            'happenedAt': (latest_state or {}).get('updated_at') or '',
            'timeText': _format_learning_time((latest_state or {}).get('updated_at')),
            'detail': f'已浏览 {state_summary["seenCount"]} 题，已掌握 {correct} 题，错题 {wrong_count} 题',
            'doneCount': done,
            'correctCount': correct,
            'wrongCount': wrong_count,
            '_sortId': 0,
        })

    for row in exams:
        passed = bool(int(row.get('passed') or 0))
        score = int(row.get('score') or 0)
        total = int(row.get('total') or 0)
        exam_correct = int(row.get('correct_count') or 0)
        duration_text = _duration_text(row.get('duration_seconds'))
        activities.append({
            'type': 'exam',
            'title': '模拟考试',
            'happenedAt': row.get('created_at') or '',
            'timeText': _format_learning_time(row.get('created_at')),
            'detail': f'{score} 分，{"通过" if passed else "未通过"}，总题数 {total}，答对 {exam_correct}，用时{duration_text}',
            'score': score,
            'total': total,
            'correctCount': exam_correct,
            'durationText': duration_text,
            'passed': passed,
            '_sortId': int(row.get('id') or 0),
        })

    activities.sort(key=lambda item: (str(item.get('happenedAt') or ''), int(item.get('_sortId') or 0)), reverse=True)
    for item in activities:
        item.pop('_sortId', None)

    latest_payload = None
    if latest:
        latest_payload = _format_exam_record(latest)

    base.update({
        'bank': {
            'id': bank['id'],
            'displayName': bank.get('display_name') or bank.get('bank_key') or '',
            'questionCount': question_count,
            'examProject': bank.get('exam_project') or '',
            'projectCode': bank.get('project_code') or '',
        },
        'summary': summary,
        'examStats': {
            'count': exam_count,
            'bestScore': best_score,
            'passCount': pass_count,
            'latest': latest_payload,
            'records': [_format_exam_record(row) for row in exams],
        },
        'activities': activities,
    })
    return base


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
        question_state_counts = _question_state_counts_for_banks(conn, openid, [bank['id'] for bank in banks])
        wrong_question_ids = _wrong_question_ids_for_banks(conn, openid, [bank['id'] for bank in banks])

    summary_banks = [
        _format_summary_bank(
            bank,
            progress.get(bank['id']),
            type_counts.get(bank['id']),
            question_state_counts.get(bank['id']),
            wrong_question_ids.get(bank['id']),
        )
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


def save_question_state(openid, bank_id, question_id, payload):
    openid = str(openid or '').strip()
    bank_id = int(bank_id or 0)
    raw_question_id = str(question_id or '').strip()
    if not openid:
        raise ValueError('用户不存在')
    if bank_id <= 0:
        raise ValueError('题库不存在')
    if not raw_question_id:
        raise ValueError('题目不存在')

    payload = payload or {}
    action = str(payload.get('action') or 'answer').strip().lower()
    if action not in ('seen', 'answer'):
        raise ValueError('题目状态动作无效')
    mode = str(payload.get('mode') or '').strip()
    answer = _normalize_answer_payload(payload.get('answer'))
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with get_db_connection() as conn:
        bank = conn.execute(
            'SELECT id FROM exam_banks WHERE id = ?',
            (bank_id,),
        ).fetchone()
        if not bank:
            raise ValueError('题库不存在')

        question = conn.execute(
            '''
            SELECT id, source_question_id
            FROM exam_questions
            WHERE bank_id = ? AND (
                CAST(id AS TEXT) = ?
                OR CAST(source_question_id AS TEXT) = ?
            )
            ORDER BY CASE WHEN CAST(source_question_id AS TEXT) = ? THEN 0 ELSE 1 END, id
            LIMIT 1
            ''',
            (bank_id, raw_question_id, raw_question_id, raw_question_id),
        ).fetchone()
        if not question:
            raise ValueError('题目不存在')
        state_question_id = int(question['id'])

        existing = conn.execute(
            '''
            SELECT *
            FROM mini_question_states
            WHERE openid = ? AND bank_id = ? AND question_id = ?
            ''',
            (openid, bank_id, state_question_id),
        ).fetchone()
        existing_dict = dict(existing) if existing else None

        if action == 'seen':
            next_status = (existing_dict or {}).get('status') or 'seen'
            answer_count = int((existing_dict or {}).get('answer_count') or 0)
            correct_count = int((existing_dict or {}).get('correct_count') or 0)
            wrong_count = int((existing_dict or {}).get('wrong_count') or 0)
            last_answer_json = (existing_dict or {}).get('last_answer_json') or _json_dumps([])
            seen_at = (existing_dict or {}).get('seen_at') or now
            last_answered_at = (existing_dict or {}).get('last_answered_at')
        else:
            is_correct = _as_bool(payload.get('isCorrect') if 'isCorrect' in payload else payload.get('is_correct'))
            next_status = 'mastered' if is_correct else 'wrong'
            answer_count = int((existing_dict or {}).get('answer_count') or 0) + 1
            correct_count = int((existing_dict or {}).get('correct_count') or 0) + (1 if is_correct else 0)
            wrong_count = int((existing_dict or {}).get('wrong_count') or 0) + (0 if is_correct else 1)
            last_answer_json = _json_dumps(answer)
            seen_at = (existing_dict or {}).get('seen_at')
            last_answered_at = now

        conn.execute(
            '''
            INSERT INTO mini_question_states (
                openid, bank_id, question_id, status, answer_count,
                correct_count, wrong_count, last_answer_json, last_mode,
                seen_at, last_answered_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(openid, bank_id, question_id) DO UPDATE SET
                status = excluded.status,
                answer_count = excluded.answer_count,
                correct_count = excluded.correct_count,
                wrong_count = excluded.wrong_count,
                last_answer_json = excluded.last_answer_json,
                last_mode = excluded.last_mode,
                seen_at = excluded.seen_at,
                last_answered_at = excluded.last_answered_at,
                updated_at = excluded.updated_at
            ''',
            (
                openid, bank_id, state_question_id, next_status, answer_count,
                correct_count, wrong_count, last_answer_json, mode,
                seen_at, last_answered_at, now, now,
            ),
        )
        if action == 'answer' and mode in ('practice', 'sequential'):
            conn.execute(
                '''
                INSERT INTO mini_practice_progress (
                    openid, bank_id, mode, last_question_id, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(openid, bank_id, mode) DO UPDATE SET
                    last_question_id = excluded.last_question_id,
                    updated_at = excluded.updated_at
                ''',
                (openid, bank_id, 'practice', state_question_id, now),
            )
        row = conn.execute(
            '''
            SELECT *
            FROM mini_question_states
            WHERE openid = ? AND bank_id = ? AND question_id = ?
            ''',
            (openid, bank_id, state_question_id),
        ).fetchone()
    return {'success': True, 'state': _row_to_question_state(row, question_id_override=int(raw_question_id) if raw_question_id.isdigit() else raw_question_id)}


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
