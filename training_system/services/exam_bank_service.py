import json
import os
import sqlite3
from datetime import datetime, timedelta

from models.student import get_db_connection


ACTIVE_STUDENT_STATUSES = ('reviewed', 'registered')
EXAM_BANK_TRAINING_TYPE = 'special_equipment'
EXAM_QUESTION_DISTRIBUTION = (
    ('single', 50),
    ('multi', 30),
    ('judge', 20),
)


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
    if type_text == '案例题' or type_code in (4, '4'):
        return 'case'
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

    # 校验 source_question_id
    source_id = str(question.get('id') or '').strip()
    if not source_id:
        raise ValueError(f'第 {sort_order + 1} 道题缺少 id 字段（source_question_id）')

    return {
        'source_question_id': source_id,
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


def _load_fixed_exam_questions(conn, where, params, page_size):
    if page_size != sum(count for _, count in EXAM_QUESTION_DISTRIBUTION):
        rows = conn.execute(
            f'SELECT * FROM exam_questions {where} ORDER BY RANDOM() LIMIT ?',
            params + [page_size],
        ).fetchall()
        return rows

    rows = []
    for qtype, count in EXAM_QUESTION_DISTRIBUTION:
        rows.extend(conn.execute(
            f'SELECT * FROM exam_questions {where} AND question_type = ? ORDER BY RANDOM() LIMIT ?',
            params + [qtype, count],
        ).fetchall())
    return rows


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

    # 检查 source_question_id 是否有重复
    source_ids = [q['source_question_id'] for q in normalized_questions]
    duplicates = [sid for sid in set(source_ids) if source_ids.count(sid) > 1]
    if duplicates:
        raise ValueError(f'题库中存在重复的题目 ID: {", ".join(duplicates[:5])}{"..." if len(duplicates) > 5 else ""}')

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

            # 获取旧题库中的题目映射 (source_question_id -> id)
            old_questions = conn.execute(
                'SELECT id, source_question_id FROM exam_questions WHERE bank_id = ?',
                (bank_id,)
            ).fetchall()
            old_question_map = {q['source_question_id']: q['id'] for q in old_questions}

            # 更新题库信息
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

            # 智能更新：根据 source_question_id 匹配
            new_source_ids = set()
            for item in normalized_questions:
                source_id = item['source_question_id']
                new_source_ids.add(source_id)

                if source_id in old_question_map:
                    # 已存在，更新题目内容（保留原 id），并标记为活跃
                    old_id = old_question_map[source_id]
                    conn.execute(
                        '''
                        UPDATE exam_questions
                        SET question_type = ?, type_code = ?, question = ?,
                            question_html = ?, options_json = ?, answer_json = ?,
                            analysis = ?, question_images_json = ?, option_images_json = ?,
                            audio = ?, sort_order = ?, raw_json = ?, is_active = 1
                        WHERE id = ?
                        ''',
                        (
                            item['question_type'], item['type_code'], item['question'],
                            item['question_html'], item['options_json'], item['answer_json'],
                            item['analysis'], item['question_images_json'], item['option_images_json'],
                            item['audio'], item['sort_order'], item['raw_json'],
                            old_id,
                        )
                    )
                else:
                    # 新题目，插入（默认 is_active = 1）
                    conn.execute(
                        '''
                        INSERT INTO exam_questions (
                            bank_id, source_question_id, question_type, type_code, question,
                            question_html, options_json, answer_json, analysis,
                            question_images_json, option_images_json, audio, sort_order,
                            raw_json, is_active
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                        ''',
                        (
                            bank_id, item['source_question_id'], item['question_type'],
                            item['type_code'], item['question'], item['question_html'],
                            item['options_json'], item['answer_json'], item['analysis'],
                            item['question_images_json'], item['option_images_json'],
                            item['audio'], item['sort_order'], item['raw_json'],
                        )
                    )

            # 处理新题库中不存在的旧题目
            old_source_ids = set(old_question_map.keys())
            removed_source_ids = old_source_ids - new_source_ids

            for source_id in removed_source_ids:
                old_id = old_question_map[source_id]

                # 检查是否有学员数据（包括练习记录和考试记录）
                has_practice_data = conn.execute(
                    'SELECT COUNT(*) as cnt FROM mini_question_states WHERE question_id = ?',
                    (old_id,)
                ).fetchone()['cnt']

                has_exam_data = conn.execute(
                    '''
                    SELECT COUNT(*) as cnt FROM mini_exam_records
                    WHERE bank_id = ? AND (
                        (json_valid(answers_json) AND json_type(answers_json, '$.' || ?) IS NOT NULL)
                        OR
                        (json_valid(question_order) AND EXISTS (
                            SELECT 1 FROM json_each(question_order) WHERE value = ?
                        ))
                    )
                    ''',
                    (bank_id, str(old_id), int(old_id))
                ).fetchone()['cnt']

                if has_practice_data == 0 and has_exam_data == 0:
                    # 无学员数据，可以删除
                    conn.execute('DELETE FROM exam_questions WHERE id = ?', (old_id,))
                else:
                    # 有学员数据，保留题目但标记为非活跃
                    conn.execute(
                        'UPDATE exam_questions SET is_active = 0 WHERE id = ?',
                        (old_id,)
                    )
            row = conn.execute('SELECT * FROM exam_banks WHERE id = ?', (bank_id,)).fetchone()
            return _row_to_bank(row)
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
                raw_json, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
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
    max_limit = 500 if mode in ('sequential', 'wrong', 'memorize') else 100
    page_size = min(max(1, int(limit or 20)), max_limit)
    offset = (page_no - 1) * page_size
    student_openid = str(openid or '').strip()
    params = [bank_id]
    where = 'WHERE bank_id = ? AND is_active = 1'  # 只查询活跃的题目

    if mode == 'wrong' and student_openid:
        where += '''
            AND id IN (
                SELECT question_id
                FROM mini_question_states
                WHERE openid = ? AND bank_id = ? AND status = 'wrong'
            )
        '''
        params.extend([student_openid, bank_id])
    elif wrong_question_ids:
        ids = [int(qid) for qid in wrong_question_ids if str(qid).isdigit()]
        if ids:
            placeholders = ','.join(['?'] * len(ids))
            where += f' AND id IN ({placeholders})'
            params.extend(ids)

    if question_type in ('single', 'multi', 'judge', 'case'):
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
    elif mode in ('random', 'exam'):
        order = 'ORDER BY RANDOM()'

    with get_db_connection() as conn:
        total = conn.execute(f'SELECT COUNT(*) FROM exam_questions {where}', params).fetchone()[0]
        if mode == 'exam' and not question_type and offset == 0:
            rows = _load_fixed_exam_questions(conn, where, params, page_size)
        else:
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
            if question_type in ('single', 'multi', 'judge', 'case'):
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
                {state_where} AND eq.is_active = 1
                ''',
                state_params,
            ).fetchone()
            state_counts = {
                'seen': int(state_row['seen_count'] or 0) if state_row else 0,
                'mastered': int(state_row['mastered_count'] or 0) if state_row else 0,
                'wrong': int(state_row['wrong_count'] or 0) if state_row else 0,
                'touched': int(state_row['touched_count'] or 0) if state_row else 0,
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


def get_next_question(bank_id, mode='sequential', current_question_id=None, question_type='', openid=''):
    student_openid = str(openid or '').strip()

    # 验证 current_question_id
    current_id = None
    if current_question_id:
        if str(current_question_id).isdigit():
            current_id = int(current_question_id)
        else:
            current_id = None

    params = [bank_id]
    where = 'WHERE bank_id = ? AND is_active = 1'
    count_where = 'WHERE bank_id = ? AND is_active = 1'
    count_params = [bank_id]

    if question_type in ('single', 'multi', 'judge', 'case'):
        where += ' AND question_type = ?'
        count_where += ' AND question_type = ?'
        params.append(question_type)
        count_params.append(question_type)

    order = 'ORDER BY sort_order ASC, id ASC'
    order_params = []

    if mode == 'wrong' and student_openid:
        wrong_subquery = '''
            AND id IN (
                SELECT question_id
                FROM mini_question_states
                WHERE openid = ? AND bank_id = ? AND status = 'wrong'
            )
        '''
        where += wrong_subquery
        count_where += wrong_subquery
        params.extend([student_openid, bank_id])
        count_params.extend([student_openid, bank_id])
    elif mode == 'memorize' and student_openid:
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

    with get_db_connection() as conn:
        # 游标：基于 (sort_order, id) 而不是只用 id
        if current_id:
            if mode == 'memorize' and student_openid:
                # 题目浏览：需要考虑"未浏览优先"排序
                # 获取当前题的 sort_order 和是否已浏览
                current_row = conn.execute(
                    'SELECT sort_order FROM exam_questions WHERE id = ?',
                    [current_id]
                ).fetchone()
                if current_row:
                    current_sort_order = current_row['sort_order']
                    current_seen = conn.execute(
                        '''
                        SELECT COUNT(*) FROM mini_question_states
                        WHERE openid = ? AND bank_id = ? AND question_id = ? AND COALESCE(seen_at, '') != ''
                        ''',
                        [student_openid, bank_id, current_id]
                    ).fetchone()[0] > 0

                    if current_seen:
                        # 当前题已浏览：下一题可以是未浏览的任意题，或已浏览且排序更后的题
                        where += '''
                            AND (
                                id NOT IN (
                                    SELECT question_id
                                    FROM mini_question_states
                                    WHERE openid = ? AND bank_id = ? AND COALESCE(seen_at, '') != ''
                                )
                                OR (
                                    id IN (
                                        SELECT question_id
                                        FROM mini_question_states
                                        WHERE openid = ? AND bank_id = ? AND COALESCE(seen_at, '') != ''
                                    )
                                    AND (sort_order > ? OR (sort_order = ? AND id > ?))
                                )
                            )
                        '''
                        params.extend([student_openid, bank_id, student_openid, bank_id, current_sort_order, current_sort_order, current_id])
                    else:
                        # 当前题未浏览：下一题是未浏览且排序更后的题
                        where += '''
                            AND id NOT IN (
                                SELECT question_id
                                FROM mini_question_states
                                WHERE openid = ? AND bank_id = ? AND COALESCE(seen_at, '') != ''
                            )
                            AND (sort_order > ? OR (sort_order = ? AND id > ?))
                        '''
                        params.extend([student_openid, bank_id, current_sort_order, current_sort_order, current_id])
            else:
                # 其他模式：基于 (sort_order, id) 游标
                current_row = conn.execute(
                    'SELECT sort_order FROM exam_questions WHERE id = ?',
                    [current_id]
                ).fetchone()
                if current_row:
                    current_sort_order = current_row['sort_order']
                    where += ' AND (sort_order > ? OR (sort_order = ? AND id > ?))'
                    params.extend([current_sort_order, current_sort_order, current_id])
        # 计算当前模式下的总题数
        total = conn.execute(f'SELECT COUNT(*) FROM exam_questions {count_where}', count_params).fetchone()[0]

        # 查询下一题
        row = conn.execute(
            f'SELECT * FROM exam_questions {where} {order} LIMIT 1',
            params + order_params,
        ).fetchone()

        if not row:
            return {'question': None, 'total': total, 'hasMore': False, 'currentPosition': total}

        question = _row_to_question(row)

        # 计算当前位置：按照实际排序规则计算
        if mode == 'memorize' and student_openid:
            # 题目浏览：位置基于 sort_order, id 的绝对位置
            # 不使用"未浏览优先"排序，否则浏览后位置会跳变
            position_query = f'''
                SELECT COUNT(*) FROM exam_questions
                {count_where}
                AND (sort_order < ? OR (sort_order = ? AND id <= ?))
            '''
            position_params = count_params + [
                question['sort_order'], question['sort_order'], question['id']
            ]
        else:
            # 其他模式：按 sort_order, id 排序
            position_query = f'''
                SELECT COUNT(*) FROM exam_questions
                {count_where}
                AND (sort_order < ? OR (sort_order = ? AND id <= ?))
            '''
            position_params = count_params + [
                question['sort_order'], question['sort_order'], question['id']
            ]

        current_position = conn.execute(position_query, position_params).fetchone()[0] - 1

        state_counts = {}
        if student_openid:
            state_where = 'WHERE qs.openid = ? AND qs.bank_id = ?'
            state_params = [student_openid, bank_id]
            if question_type in ('single', 'multi', 'judge', 'case'):
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
                {state_where} AND eq.is_active = 1
                ''',
                state_params,
            ).fetchone()
            state_counts = {
                'seen': int(state_row['seen_count'] or 0) if state_row else 0,
                'mastered': int(state_row['mastered_count'] or 0) if state_row else 0,
                'wrong': int(state_row['wrong_count'] or 0) if state_row else 0,
                'touched': int(state_row['touched_count'] or 0) if state_row else 0,
            }

            question_state = conn.execute(
                'SELECT * FROM mini_question_states WHERE openid = ? AND bank_id = ? AND question_id = ?',
                [student_openid, bank_id, question['id']],
            ).fetchone()
            if question_state:
                question['state'] = _row_to_question_state(question_state)

        # 检查是否还有更多题：使用与游标一致的逻辑
        if mode == 'memorize' and student_openid:
            # 题目浏览：检查是否还有未浏览题或已浏览且排序更后的题
            current_seen = conn.execute(
                '''
                SELECT COUNT(*) FROM mini_question_states
                WHERE openid = ? AND bank_id = ? AND question_id = ? AND COALESCE(seen_at, '') != ''
                ''',
                [student_openid, bank_id, question['id']]
            ).fetchone()[0] > 0

            if current_seen:
                has_more_query = f'''
                    SELECT COUNT(*) FROM exam_questions
                    {count_where}
                    AND (
                        id NOT IN (
                            SELECT question_id
                            FROM mini_question_states
                            WHERE openid = ? AND bank_id = ? AND COALESCE(seen_at, '') != ''
                        )
                        OR (
                            id IN (
                                SELECT question_id
                                FROM mini_question_states
                                WHERE openid = ? AND bank_id = ? AND COALESCE(seen_at, '') != ''
                            )
                            AND (sort_order > ? OR (sort_order = ? AND id > ?))
                        )
                    )
                '''
                has_more_params = count_params + [student_openid, bank_id, student_openid, bank_id, question['sort_order'], question['sort_order'], question['id']]
            else:
                has_more_query = f'''
                    SELECT COUNT(*) FROM exam_questions
                    {count_where}
                    AND id NOT IN (
                        SELECT question_id
                        FROM mini_question_states
                        WHERE openid = ? AND bank_id = ? AND COALESCE(seen_at, '') != ''
                    )
                    AND (sort_order > ? OR (sort_order = ? AND id > ?))
                '''
                has_more_params = count_params + [student_openid, bank_id, question['sort_order'], question['sort_order'], question['id']]
        else:
            # 其他模式：基于 (sort_order, id) 判断
            has_more_query = f'''
                SELECT COUNT(*) FROM exam_questions
                {count_where}
                AND (sort_order > ? OR (sort_order = ? AND id > ?))
            '''
            has_more_params = count_params + [question['sort_order'], question['sort_order'], question['id']]

        has_more = conn.execute(has_more_query, has_more_params).fetchone()[0] > 0

        return {
            'question': question,
            'total': total,
            'currentPosition': current_position,
            'hasMore': has_more,
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
    result = {}
    for row in rows:
        d = dict(row)
        # 若 last_question_id 指向已下架（is_active=0）的题目，清空以免前端跳转到旧题
        last_qid = d.get('last_question_id')
        if last_qid:
            active = conn.execute(
                'SELECT 1 FROM exam_questions WHERE id = ? AND is_active = 1',
                (last_qid,)
            ).fetchone()
            if not active:
                d['last_question_id'] = None
        result[d['bank_id']] = d
    return result


def _type_counts_for_banks(conn, bank_ids):
    if not bank_ids:
        return {}
    placeholders = ','.join(['?'] * len(bank_ids))
    rows = conn.execute(
        f'''
        SELECT bank_id, question_type, COUNT(*) AS count
        FROM exam_questions
        WHERE bank_id IN ({placeholders}) AND is_active = 1
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
            'case': 0,
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
            qs.bank_id,
            SUM(CASE WHEN COALESCE(qs.seen_at, '') != '' THEN 1 ELSE 0 END) AS seen_count,
            SUM(CASE WHEN qs.status = 'mastered' THEN 1 ELSE 0 END) AS mastered_count,
            SUM(CASE WHEN qs.status = 'wrong' THEN 1 ELSE 0 END) AS wrong_count,
            COUNT(*) AS touched_count
        FROM mini_question_states qs
        JOIN exam_questions eq ON eq.id = qs.question_id
        WHERE qs.openid = ? AND qs.bank_id IN ({placeholders}) AND eq.is_active = 1
        GROUP BY qs.bank_id
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
        SELECT qs.bank_id, qs.question_id
        FROM mini_question_states qs
        JOIN exam_questions eq ON eq.id = qs.question_id
        WHERE qs.openid = ? AND qs.bank_id IN ({placeholders}) AND qs.status = ? AND eq.is_active = 1
        ORDER BY qs.updated_at DESC, qs.id DESC
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


def _format_summary_bank(bank, progress=None, type_counts=None, question_counts=None, wrong_question_ids=None, exam_stats=None):
    state_summary = _aggregate_question_state_summary(
        int(bank.get('question_count') or 0),
        question_counts,
    )
    merged_wrong_ids = wrong_question_ids if isinstance(wrong_question_ids, list) else []
    counts = type_counts or {
        'all': int(bank.get('question_count') or 0),
        'single': 0,
        'multi': 0,
        'judge': 0,
    }
    exam_stats = exam_stats or {}
    return {
        'id': bank['id'],
        'bankKey': bank['bank_key'],
        'displayName': bank['display_name'],
        'projectCode': bank.get('project_code') or '',
        'examProject': bank.get('exam_project') or '',
        'questionCount': int(bank.get('question_count') or 0),
        'typeCounts': counts,
        'progress': {
            'doneCount': state_summary['answeredCount'],
            'correctCount': state_summary['masteredCount'],
            'wrongCount': state_summary['wrongCount'],
            'wrongQuestionIds': merged_wrong_ids,
            'lastQuestionId': (progress or {}).get('last_question_id'),
        },
        'questionState': {
            **state_summary,
            'wrongQuestionIds': merged_wrong_ids,
            'examCount': int(exam_stats.get('exam_count') or 0),
            'bestScore': int(exam_stats.get('best_score') or 0),
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

        # 估算学习时长
        exam_seconds_row = conn.execute(
            "SELECT SUM(COALESCE(duration_seconds, 0)) FROM mini_exam_records WHERE openid = ? AND bank_id = ?",
            (openid, bank['id'])
        ).fetchone()
        exam_seconds = exam_seconds_row[0] if exam_seconds_row and exam_seconds_row[0] is not None else 0

        states_for_time = conn.execute(
            """
            SELECT last_answered_at
            FROM mini_question_states
            WHERE openid = ? AND bank_id = ? AND last_answered_at IS NOT NULL AND last_answered_at != ''
            ORDER BY last_answered_at ASC
            """,
            (openid, bank['id'])
        ).fetchall()
        
        practice_seconds = 0
        from datetime import datetime
        if states_for_time:
            parsed_times = []
            for s in states_for_time:
                ts = s[0]
                try:
                    ts_clean = ts.split(".")[0]
                    parsed_times.append(datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S"))
                except Exception:
                    continue
            if parsed_times:
                parsed_times.sort()
                practice_seconds += 15
                for i in range(1, len(parsed_times)):
                    diff = (parsed_times[i] - parsed_times[i - 1]).total_seconds()
                    if 0 < diff <= 300:
                        practice_seconds += diff
                    else:
                        practice_seconds += 15

        total_seconds = int(exam_seconds + practice_seconds)
        if total_seconds <= 0:
            study_duration_text = "-"
        elif total_seconds < 60:
            study_duration_text = f"{total_seconds}秒"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            study_duration_text = f"{minutes}分钟"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if minutes > 0:
                study_duration_text = f"{hours}小时{minutes}分"
            else:
                study_duration_text = f"{hours}小时"

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
                SUM(CASE WHEN COALESCE(qs.seen_at, '') != '' THEN 1 ELSE 0 END) AS seen_count,
                SUM(CASE WHEN qs.status = 'mastered' THEN 1 ELSE 0 END) AS mastered_count,
                SUM(CASE WHEN qs.status = 'wrong' THEN 1 ELSE 0 END) AS wrong_count,
                COUNT(*) AS touched_count
            FROM mini_question_states qs
            JOIN exam_questions eq ON eq.id = qs.question_id
            WHERE qs.openid = ? AND qs.bank_id = ? AND eq.is_active = 1
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
        'studyDurationText': study_duration_text,
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
        bank_ids = [bank['id'] for bank in banks]
        progress = _progress_for_banks(conn, openid, bank_ids)
        type_counts = _type_counts_for_banks(conn, bank_ids)
        question_state_counts = _question_state_counts_for_banks(conn, openid, bank_ids)
        wrong_question_ids = _wrong_question_ids_for_banks(conn, openid, bank_ids)

        # 聚合每个题库的模考统计（次数、最高分）
        exam_stats_map = {}
        if openid and bank_ids:
            es_placeholders = ','.join(['?'] * len(bank_ids))
            es_rows = conn.execute(
                f'''
                SELECT bank_id, COUNT(*) as exam_count, MAX(score) as best_score
                FROM mini_exam_records
                WHERE openid = ? AND bank_id IN ({es_placeholders})
                GROUP BY bank_id
                ''',
                [openid] + bank_ids
            ).fetchall()
            for r in es_rows:
                exam_stats_map[r['bank_id']] = dict(r)

    summary_banks = [
        _format_summary_bank(
            bank,
            progress.get(bank['id']),
            type_counts.get(bank['id']),
            question_state_counts.get(bank['id']),
            wrong_question_ids.get(bank['id']),
            exam_stats_map.get(bank['id']),
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
            WHERE bank_id = ? AND is_active = 1 AND (
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

        consecutive_correct = int((existing_dict or {}).get('consecutive_correct') or 0)

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
            answer_count = int((existing_dict or {}).get('answer_count') or 0) + 1
            correct_count = int((existing_dict or {}).get('correct_count') or 0) + (1 if is_correct else 0)
            wrong_count = int((existing_dict or {}).get('wrong_count') or 0) + (0 if is_correct else 1)
            last_answer_json = _json_dumps(answer)
            seen_at = (existing_dict or {}).get('seen_at') or now
            last_answered_at = now
            # 错题练习模式下需要连续答对 2 次才标记为已掌握
            if is_correct:
                consecutive_correct += 1
            else:
                consecutive_correct = 0
            if mode == 'wrong':
                next_status = 'mastered' if consecutive_correct >= 2 else 'wrong'
            else:
                next_status = 'mastered' if is_correct else 'wrong'

        conn.execute(
            '''
            INSERT INTO mini_question_states (
                openid, bank_id, question_id, status, answer_count,
                correct_count, wrong_count, last_answer_json, last_mode,
                seen_at, last_answered_at, consecutive_correct, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(openid, bank_id, question_id) DO UPDATE SET
                status = excluded.status,
                answer_count = excluded.answer_count,
                correct_count = excluded.correct_count,
                wrong_count = excluded.wrong_count,
                last_answer_json = excluded.last_answer_json,
                last_mode = excluded.last_mode,
                seen_at = excluded.seen_at,
                last_answered_at = excluded.last_answered_at,
                consecutive_correct = excluded.consecutive_correct,
                updated_at = excluded.updated_at
            ''',
            (
                openid, bank_id, state_question_id, next_status, answer_count,
                correct_count, wrong_count, last_answer_json, mode,
                seen_at, last_answered_at, consecutive_correct, now, now,
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


def save_exam_record(openid, bank_id, payload):
    payload = payload or {}
    score = int(payload.get('score') or 0)
    total = int(payload.get('total') or 0)
    correct = int(payload.get('correctCount') or payload.get('correct_count') or 0)
    duration = int(payload.get('durationSeconds') or payload.get('duration_seconds') or 0)
    passed = bool(payload.get('passed'))
    answers = payload.get('answers') or {}
    submit_id = str(payload.get('submitId') or payload.get('submit_id') or '').strip()
    question_order = payload.get('questionOrder') or payload.get('question_order') or []
    if not isinstance(question_order, list):
        question_order = []
    question_order = question_order[:1000]  # 单次模考最多 1000 题

    with get_db_connection() as conn:
        # 1. 首选 submit_id 唯一性幂等校验
        if submit_id:
            existing = conn.execute(
                'SELECT id FROM mini_exam_records WHERE submit_id = ?',
                (submit_id,)
            ).fetchone()
            if existing:
                return {'success': True, 'id': existing['id'], 'duplicate': True}
        # 2. 备选内容与时间幂等校验（防止无 submit_id 时，10秒内重复发起的相同答卷记录）
        else:
            ten_seconds_ago = (datetime.now() - timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S')
            existing = conn.execute(
                '''
                SELECT id FROM mini_exam_records
                WHERE openid = ? AND bank_id = ? AND score = ? AND total = ?
                  AND correct_count = ? AND duration_seconds = ? AND answers_json = ?
                  AND created_at >= ?
                ORDER BY id DESC LIMIT 1
                ''',
                (openid, bank_id, score, total, correct, duration, _json_dumps(answers), ten_seconds_ago)
            ).fetchone()
            if existing:
                return {'success': True, 'id': existing['id'], 'duplicate': True}

        try:
            cursor = conn.execute(
                '''
                INSERT INTO mini_exam_records (
                    openid, bank_id, score, total, correct_count,
                    duration_seconds, passed, answers_json, submit_id, question_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    openid, bank_id, score, total, correct,
                    duration, 1 if passed else 0, _json_dumps(answers),
                    submit_id if submit_id else None,
                    _json_dumps(question_order) if question_order else None,
                ),
            )
            return {'success': True, 'id': cursor.lastrowid}
        except sqlite3.IntegrityError:
            if submit_id:
                existing = conn.execute(
                    'SELECT id FROM mini_exam_records WHERE submit_id = ?',
                    (submit_id,)
                ).fetchone()
                if existing:
                    return {'success': True, 'id': existing['id'], 'duplicate': True}
            raise


def save_batch_question_states(openid, bank_id, payload):
    openid = str(openid or '').strip()
    bank_id = int(bank_id or 0)
    if not openid:
        raise ValueError('用户不存在')
    if bank_id <= 0:
        raise ValueError('题库不存在')

    payload = payload or {}
    mode = str(payload.get('mode') or '').strip()
    states_list = payload.get('states') or []
    if not isinstance(states_list, list):
        raise ValueError('参数 states 必须是数组')

    if not states_list:
        return {'success': True}

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 提取所有不为空的题目ID进行批量处理
    raw_ids = []
    for item in states_list:
        qid = item.get('questionId') or item.get('question_id')
        if qid:
            raw_ids.append(str(qid).strip())

    if not raw_ids:
        return {'success': True}

    with get_db_connection() as conn:
        bank = conn.execute(
            'SELECT id FROM exam_banks WHERE id = ?',
            (bank_id,),
        ).fetchone()
        if not bank:
            raise ValueError('题库不存在')

        # 1. 批量查询题目信息
        placeholders = ','.join(['?'] * len(raw_ids))
        question_rows = conn.execute(
            f'''
            SELECT id, source_question_id
            FROM exam_questions
            WHERE bank_id = ? AND is_active = 1 AND (
                CAST(id AS TEXT) IN ({placeholders})
                OR CAST(source_question_id AS TEXT) IN ({placeholders})
            )
            ''',
            [bank_id] + raw_ids + raw_ids
        ).fetchall()

        # 构建题目ID查找字典
        q_map = {}
        for r in question_rows:
            db_id = int(r['id'])
            q_map[str(db_id)] = db_id
            if r['source_question_id']:
                q_map[str(r['source_question_id']).strip()] = db_id

        # 2. 批量查询已有的学员答题状态记录
        resolved_qids = list(set(q_map.values()))
        existing_states = {}
        if resolved_qids:
            q_placeholders = ','.join(['?'] * len(resolved_qids))
            state_rows = conn.execute(
                f'''
                SELECT question_id, status, answer_count, correct_count, wrong_count, seen_at, last_answer_json, last_answered_at, consecutive_correct
                FROM mini_question_states
                WHERE openid = ? AND bank_id = ? AND question_id IN ({q_placeholders})
                ''',
                [openid, bank_id] + resolved_qids
            ).fetchall()
            for r in state_rows:
                existing_states[int(r['question_id'])] = dict(r)

        # 3. 内存中合并计算同一批内可能重复题目状态的更新（进行次数累加）
        merged_states = {}
        for item in states_list:
            question_id = item.get('questionId') or item.get('question_id')
            raw_question_id = str(question_id or '').strip()
            if not raw_question_id or raw_question_id not in q_map:
                continue

            state_question_id = q_map[raw_question_id]
            action = str(item.get('action') or 'answer').strip().lower()
            if action not in ('seen', 'answer'):
                continue

            is_correct = _as_bool(item.get('isCorrect') if 'isCorrect' in item else item.get('is_correct'))
            answer = _normalize_answer_payload(item.get('answer'))

            if state_question_id not in merged_states:
                merged_states[state_question_id] = {
                    'action': action,
                    'actions': [(action, is_correct, answer)]
                }
            else:
                # 只要包含任一 answer 就锁定为 answer，防止后续 seen 覆盖导致进度写入被吞
                if action == 'answer':
                    merged_states[state_question_id]['action'] = 'answer'
                merged_states[state_question_id]['actions'].append((action, is_correct, answer))

        states_to_update = []
        progress_to_update = []

        for state_question_id, info in merged_states.items():
            existing_dict = existing_states.get(state_question_id)

            status = (existing_dict or {}).get('status') or 'seen'
            answer_count = int((existing_dict or {}).get('answer_count') or 0)
            correct_count = int((existing_dict or {}).get('correct_count') or 0)
            wrong_count = int((existing_dict or {}).get('wrong_count') or 0)
            last_answer_json = (existing_dict or {}).get('last_answer_json') or _json_dumps([])
            seen_at = (existing_dict or {}).get('seen_at') or now
            last_answered_at = (existing_dict or {}).get('last_answered_at')
            consecutive_correct = int((existing_dict or {}).get('consecutive_correct') or 0)

            for action, is_correct, answer in info['actions']:
                if action == 'seen':
                    seen_at = seen_at or now
                else:
                    answer_count += 1
                    if is_correct:
                        correct_count += 1
                        consecutive_correct += 1
                    else:
                        wrong_count += 1
                        consecutive_correct = 0
                    if mode == 'wrong':
                        status = 'mastered' if consecutive_correct >= 2 else 'wrong'
                    else:
                        status = 'mastered' if is_correct else 'wrong'
                    last_answer_json = _json_dumps(answer)
                    seen_at = seen_at or now
                    last_answered_at = now

            states_to_update.append((
                openid, bank_id, state_question_id, status, answer_count,
                correct_count, wrong_count, last_answer_json, mode,
                seen_at, last_answered_at, consecutive_correct, now, now
            ))

            # 仅做非覆盖式的更新（只更新最后一个有效的进度）
            if info['action'] == 'answer' and mode in ('practice', 'sequential'):
                progress_to_update.append((
                    openid, bank_id, 'practice', state_question_id, now
                ))

        # 4. 执行批量批量插入更新 (executemany)
        if states_to_update:
            conn.executemany(
                '''
                INSERT INTO mini_question_states (
                    openid, bank_id, question_id, status, answer_count,
                    correct_count, wrong_count, last_answer_json, last_mode,
                    seen_at, last_answered_at, consecutive_correct, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(openid, bank_id, question_id) DO UPDATE SET
                    status = excluded.status,
                    answer_count = excluded.answer_count,
                    correct_count = excluded.correct_count,
                    wrong_count = excluded.wrong_count,
                    last_answer_json = excluded.last_answer_json,
                    last_mode = excluded.last_mode,
                    seen_at = excluded.seen_at,
                    last_answered_at = excluded.last_answered_at,
                    consecutive_correct = excluded.consecutive_correct,
                    updated_at = excluded.updated_at
                ''',
                states_to_update
            )

        if progress_to_update:
            # 使用 executemany 进行批量进度同步
            conn.executemany(
                '''
                INSERT INTO mini_practice_progress (
                    openid, bank_id, mode, last_question_id, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(openid, bank_id, mode) DO UPDATE SET
                    last_question_id = excluded.last_question_id,
                    updated_at = excluded.updated_at
                ''',
                progress_to_update
            )

    return {'success': True}


def get_exam_history(openid, bank_id, limit=200, offset=0):
    openid = str(openid or '').strip()
    bank_id = int(bank_id or 0)
    limit = max(1, min(int(limit or 200), 500))
    offset = max(0, int(offset or 0))
    with get_db_connection() as conn:
        total_row = conn.execute(
            'SELECT COUNT(*) as cnt FROM mini_exam_records WHERE openid = ? AND bank_id = ?',
            (openid, bank_id)
        ).fetchone()
        total_count = total_row['cnt'] if total_row else 0

        rows = conn.execute(
            '''
            SELECT id, score, total, correct_count, duration_seconds, passed, created_at
            FROM mini_exam_records
            WHERE openid = ? AND bank_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            ''',
            (openid, bank_id, limit, offset)
        ).fetchall()
    return {'success': True, 'list': [dict(row) for row in rows], 'total': total_count}


def get_exam_record_detail(openid, record_id, is_admin=False):
    openid = str(openid or '').strip()
    record_id = int(record_id or 0)
    with get_db_connection() as conn:
        record_row = conn.execute(
            'SELECT * FROM mini_exam_records WHERE id = ?',
            (record_id,)
        ).fetchone()
        if not record_row:
            raise ValueError('考试记录不存在')
        record = dict(record_row)
        if record['openid'] != openid:
            raise PermissionError('无权查看此考试记录')

        # 校验题库访问权限
        if not can_access_bank(openid, record['bank_id'], is_admin):
            raise PermissionError('无权限访问该题库')

        # 解析用户的作答 JSON
        answers = _json_loads(record.get('answers_json'), {})

        # 优先使用 question_order 确定题目展现顺序，兼容旧记录退化到 answers.keys()
        raw_order = _json_loads(record.get('question_order'), [])
        if isinstance(raw_order, list) and raw_order:
            question_ids = [str(qid) for qid in raw_order]
        else:
            question_ids = list(answers.keys())

        # 批量获取关联的题目明细，使用真实数据库字段名并复用 _row_to_question
        # 分块查询以防御 SQLite 参数上限（每块最多 500 个，留 1 个位给 bank_id）
        q_dict = {}
        CHUNK_SIZE = 500
        for i in range(0, len(question_ids), CHUNK_SIZE):
            chunk = question_ids[i:i + CHUNK_SIZE]
            placeholders = ','.join(['?'] * len(chunk))
            q_rows = conn.execute(
                f'''
                SELECT id, question, question_type, options_json, answer_json, analysis,
                       question_images_json, option_images_json
                FROM exam_questions
                WHERE bank_id = ? AND CAST(id AS TEXT) IN ({placeholders})
                ''',
                [record['bank_id']] + chunk
            ).fetchall()
            for r in q_rows:
                q_data = _row_to_question(r)
                q_dict[str(q_data['id'])] = q_data

        questions = []
        for qid in question_ids:
            if qid in q_dict:
                questions.append(q_dict[qid])

    return {
        'success': True,
        'record': {
            'id': record['id'],
            'score': record['score'],
            'total': record['total'],
            'correct_count': record['correct_count'],
            'duration_seconds': record['duration_seconds'],
            'passed': record['passed'],
            'created_at': record['created_at']
        },
        'answers': answers,
        'questions': questions
    }

