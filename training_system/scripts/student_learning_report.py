#!/usr/bin/env python3
"""
导出学员学习、练习、模拟考试统计报表。

服务器执行示例：
  python3 training_system/scripts/student_learning_report.py
  python3 training_system/scripts/student_learning_report.py --db /path/to/students.db --output /tmp/learning_report.csv
  python3 training_system/scripts/student_learning_report.py --all-statuses

脚本只读 SQLite 数据库，不会修改任何业务数据。
"""
import argparse
import csv
import html
import os
import sqlite3
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "database", "students.db")
ACTIVE_STUDENT_STATUSES = ("reviewed", "registered")
EXAM_BANK_TRAINING_TYPE = "special_equipment"

STATUS_LABELS = {
    "unreviewed": "待审核",
    "reviewed": "已通过",
    "registered": "已报名",
    "rejected": "已驳回",
}

TRAINING_TYPE_LABELS = {
    "special_equipment": "特种设备",
    "special_operation": "特种作业",
}

STATE_TEXTS = {
    "unbound": "未绑定用户",
    "no_bank": "未匹配题库",
    "not_started": "未开始",
    "practicing": "练习中",
    "exam_attempted": "已模拟考试",
    "passed": "已通过模拟考试",
}

CSV_HEADERS = [
    "学员ID",
    "姓名",
    "手机号",
    "身份证号",
    "单位",
    "培训类型",
    "报名状态",
    "作业类别",
    "考试项目",
    "项目代码",
    "报名时间",
    "小程序OpenID",
    "题库ID",
    "匹配题库",
    "题库题量",
    "学习状态",
    "已浏览题数",
    "已答题数",
    "已掌握题数",
    "错题数",
    "未学习题数",
    "学习覆盖率%",
    "答题进度%",
    "掌握率%",
    "当前正确率%",
    "练习答题次数",
    "练习答对次数",
    "练习答错次数",
    "最近练习时间",
    "模拟考试次数",
    "模考通过次数",
    "模考最高分",
    "模考平均分",
    "最近模考分数",
    "最近模考结果",
    "最近模考时间",
    "最近模考用时秒",
    "最后学习时间",
    "学习时长",
    "学习时长秒",
]


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _as_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _as_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _percent(numerator, denominator):
    denominator = _as_int(denominator)
    if denominator <= 0:
        return 0
    return round(_as_int(numerator) * 100 / denominator)


def _label(mapping, value):
    text = str(value or "").strip()
    return mapping.get(text, text)


def _format_time(value):
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:19].replace("T", " ")


def _latest_time(*values):
    candidates = [str(value or "").strip() for value in values if str(value or "").strip()]
    return max(candidates) if candidates else ""


def _default_output_path():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(BASE_DIR, "database", f"student_learning_report_{timestamp}.csv")


def _default_html_output_path():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(BASE_DIR, "database", f"student_learning_report_{timestamp}.html")


def _csv_output_for_html(html_path):
    base, _ext = os.path.splitext(os.path.abspath(html_path))
    return f"{base}.csv"


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def validate_database(conn):
    required_tables = [
        "students",
        "exam_banks",
        "exam_questions",
        "mini_question_states",
        "mini_exam_records",
    ]
    missing = [name for name in required_tables if not _table_exists(conn, name)]
    if missing:
        raise RuntimeError("数据库缺少必要表: " + ", ".join(missing))


def _student_filters(statuses=None, include_all_statuses=False):
    where = []
    params = []
    if not include_all_statuses:
        selected = tuple(statuses or ACTIVE_STUDENT_STATUSES)
        placeholders = ",".join(["?"] * len(selected))
        where.append(f"COALESCE(status, '') IN ({placeholders})")
        params.extend(selected)
    return where, params


def _load_students(conn, statuses=None, include_all_statuses=False):
    where, params = _student_filters(statuses, include_all_statuses)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    return conn.execute(
        f"""
        SELECT *
        FROM students
        {where_sql}
        ORDER BY created_at DESC, id DESC
        """,
        params,
    ).fetchall()


def _find_student_bank(conn, student):
    training_project_id = student["training_project_id"] if "training_project_id" in student.keys() else None
    project_code = str(student["project_code"] or "").strip() if "project_code" in student.keys() else ""
    exam_project = str(student["exam_project"] or "").strip() if "exam_project" in student.keys() else ""
    return conn.execute(
        """
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
        """,
        (
            EXAM_BANK_TRAINING_TYPE,
            training_project_id,
            training_project_id,
            project_code,
            exam_project,
            training_project_id,
            training_project_id,
        ),
    ).fetchone()


def _load_question_state_stats(conn, openid, bank_id):
    row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN COALESCE(qs.seen_at, '') != '' THEN 1 ELSE 0 END) AS seen_count,
            SUM(CASE WHEN qs.status = 'mastered' THEN 1 ELSE 0 END) AS mastered_count,
            SUM(CASE WHEN qs.status = 'wrong' THEN 1 ELSE 0 END) AS wrong_count,
            COUNT(*) AS touched_count,
            SUM(COALESCE(qs.answer_count, 0)) AS answer_attempt_count,
            SUM(COALESCE(qs.correct_count, 0)) AS answer_correct_count,
            SUM(COALESCE(qs.wrong_count, 0)) AS answer_wrong_count,
            MAX(COALESCE(qs.updated_at, qs.created_at, '')) AS latest_practice_at
        FROM mini_question_states qs
        JOIN exam_questions eq
          ON eq.id = qs.question_id
         AND eq.bank_id = qs.bank_id
        WHERE qs.openid = ?
          AND qs.bank_id = ?
          AND eq.is_active = 1
        """,
        (openid, bank_id),
    ).fetchone()
    return dict(row) if row else {}


def _load_exam_stats(conn, openid, bank_id):
    summary = conn.execute(
        """
        SELECT
            COUNT(*) AS exam_count,
            SUM(CASE WHEN COALESCE(passed, 0) = 1 THEN 1 ELSE 0 END) AS pass_count,
            MAX(score) AS best_score,
            ROUND(AVG(score), 1) AS avg_score
        FROM mini_exam_records
        WHERE openid = ?
          AND bank_id = ?
        """,
        (openid, bank_id),
    ).fetchone()
    latest = conn.execute(
        """
        SELECT *
        FROM mini_exam_records
        WHERE openid = ?
          AND bank_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (openid, bank_id),
    ).fetchone()
    return (dict(summary) if summary else {}), (dict(latest) if latest else None)


def _build_empty_row(student, state, bank=None):
    return {
        "学员ID": student["id"],
        "姓名": student["name"] or "",
        "手机号": student["phone"] or "",
        "身份证号": student["id_card"] or "",
        "单位": student["company"] or "",
        "培训类型": _label(TRAINING_TYPE_LABELS, student["training_type"]),
        "报名状态": _label(STATUS_LABELS, student["status"]),
        "作业类别": student["job_category"] or "",
        "考试项目": student["exam_project"] or "",
        "项目代码": student["project_code"] or "",
        "报名时间": _format_time(student["created_at"]),
        "小程序OpenID": student["submitter_openid"] or "",
        "题库ID": bank["id"] if bank else "",
        "匹配题库": (bank["display_name"] or bank["bank_key"] or "") if bank else "",
        "题库题量": _as_int(bank["question_count"]) if bank else 0,
        "学习状态": STATE_TEXTS[state],
        "已浏览题数": 0,
        "已答题数": 0,
        "已掌握题数": 0,
        "错题数": 0,
        "未学习题数": _as_int(bank["question_count"]) if bank else 0,
        "学习覆盖率%": 0,
        "答题进度%": 0,
        "掌握率%": 0,
        "当前正确率%": 0,
        "练习答题次数": 0,
        "练习答对次数": 0,
        "练习答错次数": 0,
        "最近练习时间": "",
        "模拟考试次数": 0,
        "模考通过次数": 0,
        "模考最高分": "",
        "模考平均分": "",
        "最近模考分数": "",
        "最近模考结果": "",
        "最近模考时间": "",
        "最近模考用时秒": "",
        "最后学习时间": "",
        "学习时长": "",
        "学习时长秒": 0,
    }


def _estimate_study_time(conn, openid, bank_id):
    # 1. 模拟考试总时长
    row = conn.execute(
        "SELECT SUM(COALESCE(duration_seconds, 0)) FROM mini_exam_records WHERE openid = ? AND bank_id = ?",
        (openid, bank_id)
    ).fetchone()
    exam_seconds = row[0] if row and row[0] is not None else 0

    # 2. 刷题练习估计时长
    states = conn.execute(
        """
        SELECT last_answered_at
        FROM mini_question_states
        WHERE openid = ?
          AND bank_id = ?
          AND last_answered_at IS NOT NULL
          AND last_answered_at != ''
        ORDER BY last_answered_at ASC
        """,
        (openid, bank_id)
    ).fetchall()
    
    practice_seconds = 0
    if states:
        parsed_times = []
        for s in states:
            ts = s[0]
            try:
                ts_clean = ts.split(".")[0]
                parsed_times.append(datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S"))
            except Exception:
                continue
        
        if parsed_times:
            parsed_times.sort()
            practice_seconds += 15  # 第一题计 15 秒
            for i in range(1, len(parsed_times)):
                diff = (parsed_times[i] - parsed_times[i - 1]).total_seconds()
                if 0 < diff <= 300:
                    practice_seconds += diff
                else:
                    practice_seconds += 15

    total_seconds = int(exam_seconds + practice_seconds)
    if total_seconds <= 0:
        return total_seconds, "-"
    elif total_seconds < 60:
        return total_seconds, f"{total_seconds}秒"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return total_seconds, f"{minutes}分钟"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if minutes > 0:
            return total_seconds, f"{hours}小时{minutes}分"
        return total_seconds, f"{hours}小时"


def _build_report_row(conn, student):
    openid = str(student["submitter_openid"] or "").strip()
    bank = _find_student_bank(conn, student)

    if not openid:
        return _build_empty_row(student, "unbound", bank)
    if not bank:
        return _build_empty_row(student, "no_bank", None)

    question_count = _as_int(bank["question_count"])
    state_stats = _load_question_state_stats(conn, openid, bank["id"])
    exam_stats, latest_exam = _load_exam_stats(conn, openid, bank["id"])

    seen_count = _as_int(state_stats.get("seen_count"))
    mastered_count = _as_int(state_stats.get("mastered_count"))
    wrong_count = _as_int(state_stats.get("wrong_count"))
    touched_count = _as_int(state_stats.get("touched_count"))
    if touched_count <= 0:
        touched_count = seen_count + mastered_count + wrong_count
    answered_count = mastered_count + wrong_count
    untouched_count = max(0, question_count - touched_count)
    answer_attempt_count = _as_int(state_stats.get("answer_attempt_count"))
    answer_correct_count = _as_int(state_stats.get("answer_correct_count"))
    answer_wrong_count = _as_int(state_stats.get("answer_wrong_count"))

    exam_count = _as_int(exam_stats.get("exam_count"))
    pass_count = _as_int(exam_stats.get("pass_count"))
    latest_practice_at = _format_time(state_stats.get("latest_practice_at"))
    latest_exam_at = _format_time(latest_exam.get("created_at") if latest_exam else "")
    last_study_at = _format_time(_latest_time(latest_practice_at, latest_exam_at))

    if pass_count > 0:
        state = "passed"
    elif exam_count > 0:
        state = "exam_attempted"
    elif touched_count > 0:
        state = "practicing"
    else:
        state = "not_started"

    row = _build_empty_row(student, state, bank)
    duration_sec, duration_str = _estimate_study_time(conn, openid, bank["id"])
    row.update({
        "已浏览题数": seen_count,
        "已答题数": answered_count,
        "已掌握题数": mastered_count,
        "错题数": wrong_count,
        "未学习题数": untouched_count,
        "学习覆盖率%": _percent(touched_count, question_count),
        "答题进度%": _percent(answered_count, question_count),
        "掌握率%": _percent(mastered_count, question_count),
        "当前正确率%": _percent(mastered_count, answered_count),
        "练习答题次数": answer_attempt_count,
        "练习答对次数": answer_correct_count,
        "练习答错次数": answer_wrong_count,
        "最近练习时间": latest_practice_at,
        "模拟考试次数": exam_count,
        "模考通过次数": pass_count,
        "模考最高分": _as_int(exam_stats.get("best_score")) if exam_count else "",
        "模考平均分": exam_stats.get("avg_score") if exam_count else "",
        "最近模考分数": _as_int(latest_exam.get("score")) if latest_exam else "",
        "最近模考结果": ("通过" if _as_int(latest_exam.get("passed")) == 1 else "未通过") if latest_exam else "",
        "最近模考时间": latest_exam_at,
        "最近模考用时秒": _as_int(latest_exam.get("duration_seconds")) if latest_exam else "",
        "最后学习时间": last_study_at,
        "学习时长": duration_str,
        "学习时长秒": duration_sec,
    })
    return row


def collect_report_rows(db_path=DEFAULT_DB_PATH, statuses=None, include_all_statuses=False):
    """返回每个学员一行的学习统计数据。"""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")

    with _connect(db_path) as conn:
        validate_database(conn)
        students = _load_students(conn, statuses=statuses, include_all_statuses=include_all_statuses)
        return [_build_report_row(conn, student) for student in students]


def write_csv(rows, output_path, encoding="utf-8-sig"):
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", newline="", encoding=encoding) as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def summarize_rows(rows):
    total = len(rows)
    coverage_values = [_as_int(row.get("学习覆盖率%")) for row in rows]
    exam_values = [_as_int(row.get("模拟考试次数")) for row in rows]
    return {
        "total": total,
        "matched_bank": sum(1 for row in rows if row.get("题库ID")),
        "started": sum(1 for row in rows if row.get("学习状态") in ("练习中", "已模拟考试", "已通过模拟考试")),
        "not_started": sum(1 for row in rows if row.get("学习状态") in ("未开始", "未绑定用户", "未匹配题库")),
        "exam_attempted": sum(1 for value in exam_values if value > 0),
        "passed": sum(1 for row in rows if _as_int(row.get("模考通过次数")) > 0),
        "avg_coverage": round(sum(coverage_values) / total) if total else 0,
    }


def _h(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def _fmt(value, empty="-"):
    if value is None or value == "":
        return empty
    return str(value)


def _state_class(row):
    state = str(row.get("学习状态") or "")
    coverage = _as_int(row.get("学习覆盖率%"))
    exam_count = _as_int(row.get("模拟考试次数"))
    pass_count = _as_int(row.get("模考通过次数"))
    if pass_count > 0 or state == "已通过模拟考试":
        return "passed"
    if exam_count > 0:
        return "failed"
    if state in ("未开始", "未绑定用户", "未匹配题库"):
        return "not-started"
    if coverage < 30:
        return "low"
    return "active"


def _attention_groups(rows):
    return [
        {
            "title": "未开始学习",
            "tone": "danger",
            "rows": [
                row for row in rows
                if row.get("学习状态") in ("未开始", "未绑定用户", "未匹配题库")
            ],
        },
        {
            "title": "学习进度低于 30%",
            "tone": "warning",
            "rows": [
                row for row in rows
                if row.get("学习状态") not in ("未开始", "未绑定用户", "未匹配题库")
                and _as_int(row.get("学习覆盖率%")) < 30
                and _as_int(row.get("模考通过次数")) <= 0
            ],
        },
        {
            "title": "已练习但未模考",
            "tone": "info",
            "rows": [
                row for row in rows
                if _as_int(row.get("学习覆盖率%")) > 0
                and _as_int(row.get("模拟考试次数")) <= 0
            ],
        },
        {
            "title": "模考未通过",
            "tone": "warning",
            "rows": [
                row for row in rows
                if _as_int(row.get("模拟考试次数")) > 0
                and _as_int(row.get("模考通过次数")) <= 0
            ],
        },
        {
            "title": "已通过模考",
            "tone": "success",
            "rows": [
                row for row in rows
                if _as_int(row.get("模考通过次数")) > 0
            ],
        },
    ]


def _render_metric(label, value, detail="", class_name=""):
    return f"""
      <div class="metric {class_name}">
        <div class="metric-label">{_h(label)}</div>
        <div class="metric-value">{_h(value)}</div>
        <div class="metric-detail">{_h(detail)}</div>
      </div>
    """


def _render_attention_card(group):
    rows = group["rows"]
    preview = rows[:8]
    if preview:
        items = "\n".join(
            f"""
            <li>
              <span>{_h(row.get("姓名"))}</span>
              <strong>{_h(row.get("学习覆盖率%"))}%</strong>
            </li>
            """
            for row in preview
        )
        if len(rows) > len(preview):
            items += f'<li class="muted">还有 {len(rows) - len(preview)} 人</li>'
    else:
        items = '<li class="muted">暂无</li>'
    return f"""
      <section class="attention-card {group["tone"]}">
        <div class="attention-head">
          <h3>{_h(group["title"])}</h3>
          <span>{len(rows)} 人</span>
        </div>
        <ul>{items}</ul>
      </section>
    """


def _render_progress(percent):
    value = max(0, min(100, _as_int(percent)))
    return f"""
      <div class="progress">
        <div class="progress-bar" style="width: {value}%"></div>
      </div>
      <span class="progress-text">{value}%</span>
    """


def _render_detail_rows(rows):
    if not rows:
        return '<tr><td colspan="10" class="empty">暂无学员记录</td></tr>'
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            str(row.get("报名时间") or ""),
            _as_int(row.get("学员ID")),
        ),
        reverse=True,
    )
    return "\n".join(
        f"""
        <tr class="{_state_class(row)}" data-state="{_state_class(row)}" data-search="{_h(row.get("姓名"))} {_h(row.get("手机号"))} {_h(row.get("考试项目"))} {_h(row.get("项目代码"))}">
          <td>{_h(row.get("姓名"))}</td>
          <td>{_h(row.get("考试项目"))} <span class="muted">({_h(row.get("项目代码"))})</span></td>
          <td><span class="badge {_state_class(row)}">{_h(row.get("学习状态"))}</span></td>
          <td class="progress-cell">{_render_progress(row.get("学习覆盖率%"))}</td>
          <td>{_h(row.get("已答题数"))}/{_h(row.get("题库题量"))} <span class="muted">(掌握: {_h(row.get("已掌握题数"))}，{_h(row.get("掌握率%"))}%)</span></td>
          <td>{_h(row.get("错题数"))}</td>
          <td data-seconds="{row.get('学习时长秒')}">{_h(row.get("学习时长"))}</td>
          <td>{_h(row.get("模拟考试次数"))}</td>
          <td>{_h(_fmt(row.get("模考最高分")))}</td>
          <td>{_h(_fmt(row.get("最后学习时间")))}</td>
        </tr>
        """
        for row in sorted_rows
    )


def write_html_report(rows, output_path, generated_at=None):
    """写入适合管理端阅读的静态 HTML 报表。"""
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    summary = summarize_rows(rows)
    groups = _attention_groups(rows)
    pass_rate = _percent(summary["passed"], summary["total"])
    start_rate = _percent(summary["started"], summary["total"])

    metric_html = "\n".join([
        _render_metric("总学员", summary["total"], "当前筛选范围内"),
        _render_metric("已开始", summary["started"], f"启动率 {start_rate}%", "info"),
        _render_metric("未开始", summary["not_started"], "需要跟进提醒", "danger"),
        _render_metric("模考通过", summary["passed"], f"通过率 {pass_rate}%", "success"),
        _render_metric("平均覆盖率", f"{summary['avg_coverage']}%", "学习覆盖均值", "warning"),
    ])
    attention_html = "\n".join(_render_attention_card(group) for group in groups)
    detail_html = _render_detail_rows(rows)

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>学员学习报表</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #172033;
      --muted: #667085;
      --line: #d9dee7;
      --green: #15803d;
      --green-soft: #e9f7ee;
      --red: #b42318;
      --red-soft: #fff0ed;
      --amber: #b45309;
      --amber-soft: #fff7e6;
      --teal: #0f766e;
      --teal-soft: #e7f7f5;
      --blue: #2563eb;
      --blue-soft: #edf3ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
      font-size: 14px;
      line-height: 1.5;
    }}
    .page {{
      max-width: 1680px;
      margin: 0 auto;
      padding: 24px;
    }}
    .header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 18px;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{ font-size: 28px; letter-spacing: 0; }}
    .subtitle {{ color: var(--muted); margin-top: 6px; }}
    .stamp {{ color: var(--muted); font-size: 13px; white-space: nowrap; }}
    .section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin-top: 16px;
    }}
    .section-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
    }}
    .section h2 {{ font-size: 18px; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-left: 4px solid #475467;
      border-radius: 8px;
      padding: 14px;
      min-height: 106px;
      background: #fff;
    }}
    .metric.info {{ border-left-color: var(--blue); background: var(--blue-soft); }}
    .metric.success {{ border-left-color: var(--green); background: var(--green-soft); }}
    .metric.warning {{ border-left-color: var(--amber); background: var(--amber-soft); }}
    .metric.danger {{ border-left-color: var(--red); background: var(--red-soft); }}
    .metric-label {{ color: var(--muted); font-size: 13px; }}
    .metric-value {{ font-size: 30px; font-weight: 750; margin-top: 8px; }}
    .metric-detail {{ color: var(--muted); margin-top: 4px; font-size: 13px; }}
    .attention-grid {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
    }}
    .attention-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 190px;
      background: #fff;
    }}
    .attention-card.danger {{ border-top: 4px solid var(--red); }}
    .attention-card.warning {{ border-top: 4px solid var(--amber); }}
    .attention-card.info {{ border-top: 4px solid var(--teal); }}
    .attention-card.success {{ border-top: 4px solid var(--green); }}
    .attention-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
    }}
    .attention-head h3 {{ font-size: 15px; }}
    .attention-head span {{
      color: var(--muted);
      font-weight: 700;
    }}
    ul {{ list-style: none; padding: 0; margin: 0; }}
    li {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 5px 0;
      border-top: 1px solid #edf0f4;
    }}
    li:first-child {{ border-top: 0; }}
    li strong {{ color: var(--muted); }}
    .muted {{ color: var(--muted); }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1080px;
      background: #fff;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid #edf0f4;
      text-align: left;
      vertical-align: middle;
      white-space: nowrap;
    }}
    th {{
      background: #f8fafc;
      color: #475467;
      font-size: 13px;
      font-weight: 700;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    tr.not-started td:first-child {{ border-left: 4px solid var(--red); }}
    tr.low td:first-child, tr.failed td:first-child {{ border-left: 4px solid var(--amber); }}
    tr.active td:first-child {{ border-left: 4px solid var(--teal); }}
    tr.passed td:first-child {{ border-left: 4px solid var(--green); }}
    .student-name {{ font-weight: 750; }}
    .student-sub {{ color: var(--muted); font-size: 12px; margin-top: 2px; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 0 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid var(--line);
    }}
    .badge.passed {{ color: var(--green); background: var(--green-soft); border-color: #b7e3c4; }}
    .badge.failed, .badge.low {{ color: var(--amber); background: var(--amber-soft); border-color: #f3d28f; }}
    .badge.not-started {{ color: var(--red); background: var(--red-soft); border-color: #fac7bd; }}
    .badge.active {{ color: var(--teal); background: var(--teal-soft); border-color: #ace7df; }}
    .progress-cell {{
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 150px;
    }}
    .progress {{
      width: 92px;
      height: 8px;
      background: #e8ecf2;
      border-radius: 999px;
      overflow: hidden;
    }}
    .progress-bar {{
      height: 100%;
      background: linear-gradient(90deg, #0f766e, #15803d);
      border-radius: 999px;
    }}
    .progress-text {{
      width: 40px;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }}
    .empty {{ text-align: center; color: var(--muted); padding: 34px; }}
    
    /* 搜索与过滤交互 */
    .filter-section {{
      padding: 12px 18px;
      margin-top: 16px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .filter-grid {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .search-box {{
      position: relative;
      flex: 1;
      min-width: 260px;
    }}
    .search-box input {{
      width: 100%;
      padding: 8px 12px 8px 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
    }}
    .search-box input:focus {{
      border-color: var(--blue);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }}
    .search-icon {{
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      pointer-events: none;
    }}
    .filter-box {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .filter-select {{
      background: #fff;
      border: 1px solid var(--line);
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      color: var(--text);
      outline: none;
      transition: all 0.2s;
      appearance: none;
      -webkit-appearance: none;
      padding-right: 32px;
      background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='16' height='16'%3E%3Cpath fill='%23667085' d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 8px center;
    }}
    .filter-select:hover {{
      background-color: var(--bg);
      border-color: #b4bee7;
    }}
    .filter-select:focus {{
      border-color: var(--blue);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }}
    .metric, .attention-card {{
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    .metric:hover, .attention-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    }}
    th.sortable {{
      cursor: pointer;
      user-select: none;
    }}
    th.sortable:hover {{
      background: #f1f5f9;
    }}
    th.sortable::after {{
      content: ' ↕';
      color: #cbd5e1;
      font-size: 11px;
    }}
    th.sortable.asc::after {{
      content: ' ↑';
      color: var(--blue);
    }}
    th.sortable.desc::after {{
      content: ' ↓';
      color: var(--blue);
    }}

    @media (max-width: 980px) {{
      .page {{ padding: 18px; }}
      .header {{ display: block; }}
      .stamp {{ margin-top: 8px; }}
      .metric-grid, .attention-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 640px) {{
      .metric-grid, .attention-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="header">
      <div>
        <h1>学员学习报表</h1>
        <p class="subtitle">学习、练习与模拟考试进度汇总</p>
      </div>
      <div class="stamp">生成时间：{_h(generated_at)}</div>
    </header>

    <section class="section">
      <div class="section-head">
        <h2>学习概览</h2>
        <span class="muted">先看趋势，再看名单</span>
      </div>
      <div class="metric-grid">{metric_html}</div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>重点关注</h2>
        <span class="muted">按跟进优先级分组</span>
      </div>
      <div class="attention-grid">{attention_html}</div>
    </section>

    <div class="filter-section">
      <div class="filter-grid">
        <div class="search-box">
          <svg class="search-icon" viewBox="0 0 24 24" width="16" height="16"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="currentColor"/></svg>
          <input type="text" id="studentSearch" placeholder="搜索姓名、手机号、项目代码..." oninput="onFilterChange()">
        </div>
        <div class="filter-box">
          <select id="statusFilter" class="filter-select" onchange="onFilterChange()">
            <option value="started" selected>已开始学习 (排除未开始)</option>
            <option value="all">全部学员</option>
            <option value="not-started">未开始学习</option>
            <option value="active">学习中</option>
            <option value="failed">模考未通过</option>
            <option value="passed">模考已通过</option>
          </select>
        </div>
      </div>
    </div>

    <section class="section" style="margin-top: 16px;">
      <div class="section-head">
        <h2>学员明细</h2>
        <span class="muted">共 {_h(len(rows))} 条</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>学员</th>
              <th>项目</th>
              <th>状态</th>
              <th>学习覆盖</th>
              <th>已答/题量</th>
              <th>错题</th>
              <th>学习时长</th>
              <th>模考</th>
              <th>最高分</th>
              <th>最后学习</th>
            </tr>
          </thead>
          <tbody>{detail_html}</tbody>
        </table>
      </div>
    </section>
  </main>

  <script>
    let currentFilter = 'started';

    function onFilterChange() {{
      const select = document.getElementById('statusFilter');
      currentFilter = select.value;
      filterTable();
    }}

    function setFilter(filterType) {{
      const select = document.getElementById('statusFilter');
      select.value = filterType;
      currentFilter = filterType;
      filterTable();
    }}

    function filterTable() {{
      const searchText = document.getElementById('studentSearch').value.toLowerCase().trim();
      const rows = document.querySelectorAll('tbody tr');
      let visibleCount = 0;

      rows.forEach(row => {{
        if (row.classList.contains('empty') || row.id === 'js-empty-row') return;
        
        const searchData = row.getAttribute('data-search').toLowerCase();
        const rowState = row.getAttribute('data-state');
        
        const matchesSearch = !searchText || searchData.includes(searchText);
        let matchesFilter = false;

        if (currentFilter === 'all' || (currentFilter === 'started' && searchText.length > 0)) {{
          matchesFilter = true;
        }} else if (currentFilter === 'started') {{
          matchesFilter = (rowState !== 'not-started');
        }} else if (currentFilter === 'not-started') {{
          matchesFilter = (rowState === 'not-started');
        }} else if (currentFilter === 'active') {{
          matchesFilter = (rowState === 'active' || rowState === 'low');
        }} else if (currentFilter === 'failed') {{
          matchesFilter = (rowState === 'failed');
        }} else if (currentFilter === 'passed') {{
          matchesFilter = (rowState === 'passed');
        }}

        if (matchesSearch && matchesFilter) {{
          row.style.display = '';
          visibleCount++;
        }} else {{
          row.style.display = 'none';
        }}
      }});

      let emptyRow = document.getElementById('js-empty-row');
      if (visibleCount === 0) {{
        if (!emptyRow) {{
          emptyRow = document.createElement('tr');
          emptyRow.id = 'js-empty-row';
          emptyRow.innerHTML = '<td colspan="10" class="empty">无匹配的学员记录</td>';
          document.querySelector('tbody').appendChild(emptyRow);
        }} else {{
          emptyRow.style.display = '';
        }}
      }} else if (emptyRow) {{
        emptyRow.style.display = 'none';
      }}

      const detailHeaderSpan = document.querySelector('section:nth-of-type(4) .section-head span.muted');
      if (detailHeaderSpan) {{
        detailHeaderSpan.textContent = `共 ${{visibleCount}} 条`;
      }}
    }}

    document.addEventListener('DOMContentLoaded', () => {{
      const metrics = document.querySelectorAll('.metric');
      if (metrics.length >= 4) {{
        metrics[0].addEventListener('click', () => {{ document.getElementById('studentSearch').value = ''; setFilter('all'); }});
        metrics[1].addEventListener('click', () => setFilter('active'));
        metrics[2].addEventListener('click', () => setFilter('not-started'));
        metrics[3].addEventListener('click', () => setFilter('passed'));
      }}

      const cards = document.querySelectorAll('.attention-card');
      cards.forEach(card => {{
        if (card.classList.contains('danger')) {{
          card.addEventListener('click', () => setFilter('not-started'));
        }} else if (card.classList.contains('warning')) {{
          if (card.querySelector('h3').textContent.includes('模考未通过')) {{
            card.addEventListener('click', () => setFilter('failed'));
          }} else {{
            card.addEventListener('click', () => setFilter('active'));
          }}
        }} else if (card.classList.contains('info')) {{
          card.addEventListener('click', () => setFilter('active'));
        }} else if (card.classList.contains('success')) {{
          card.addEventListener('click', () => setFilter('passed'));
        }}
      }});

      makeTableSortable();
      filterTable();
    }});

    function makeTableSortable() {{
      const table = document.querySelector('table');
      const headers = table.querySelectorAll('th');
      
      const sortableCols = [0, 2, 3, 4, 5, 6, 7, 8, 9];
      headers.forEach((header, index) => {{
        if (index === 1) return;
        header.classList.add('sortable');
        header.addEventListener('click', () => {{
          const isAsc = header.classList.contains('asc');
          headers.forEach(h => h.classList.remove('asc', 'desc'));
          
          if (isAsc) {{
            header.classList.add('desc');
            sortTable(index, false);
          }} else {{
            header.classList.add('asc');
            sortTable(index, true);
          }}
        }});
      }});
    }}

    function sortTable(colIndex, asc) {{
      const table = document.querySelector('table');
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr')).filter(r => r.id !== 'js-empty-row' && !r.classList.contains('empty'));
      
      rows.sort((a, b) => {{
        let valA = getCellValue(a, colIndex);
        let valB = getCellValue(b, colIndex);
        
        if (colIndex === 3) {{
          valA = parseFloat(a.querySelector('.progress-text').textContent) || 0;
          valB = parseFloat(b.querySelector('.progress-text').textContent) || 0;
        }} else if (colIndex === 4) {{
          const partsA = valA.split('/');
          const partsB = valB.split('/');
          valA = parseInt(partsA[0]) || 0;
          valB = parseInt(partsB[0]) || 0;
        }} else if (colIndex === 6) {{
          valA = parseInt(a.children[6].getAttribute('data-seconds')) || 0;
          valB = parseInt(b.children[6].getAttribute('data-seconds')) || 0;
        }} else if ([5, 7, 8].includes(colIndex)) {{
          valA = valA === '-' ? -1 : parseFloat(valA) || 0;
          valB = valB === '-' ? -1 : parseFloat(valB) || 0;
        }}
        
        if (valA === valB) return 0;
        if (valA > valB) return asc ? 1 : -1;
        return asc ? -1 : 1;
      }});
      
      rows.forEach(row => tbody.appendChild(row));
      
      const emptyRow = document.getElementById('js-empty-row');
      if (emptyRow) tbody.appendChild(emptyRow);
    }}

    function getCellValue(row, index) {{
      return row.children[index].textContent.trim();
    }}
  </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as fp:
        fp.write(html_doc)


def resolve_output_paths(args):
    output = (args.output or "").strip()
    html_output = (args.html_output or "").strip()
    csv_output = (args.csv_output or "").strip()

    if html_output:
        html_path = html_output
    elif output and not output.lower().endswith(".csv"):
        html_path = output
    else:
        html_path = _default_html_output_path()

    if csv_output:
        csv_path = csv_output
    elif output and output.lower().endswith(".csv"):
        csv_path = output
    else:
        csv_path = _csv_output_for_html(html_path)

    return html_path, csv_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="导出学员学习、练习、模拟考试统计 HTML 报表")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help=f"SQLite 数据库路径，默认: {DEFAULT_DB_PATH}")
    parser.add_argument("--output", default="", help="HTML 输出路径；若以 .csv 结尾则兼容为 CSV 输出路径")
    parser.add_argument("--html-output", default="", help="HTML 输出路径")
    parser.add_argument("--csv-output", default="", help="CSV 明细输出路径，默认与 HTML 同名")
    parser.add_argument("--no-csv", action="store_true", help="只生成 HTML，不生成 CSV 明细")
    parser.add_argument(
        "--status",
        action="append",
        choices=["unreviewed", "reviewed", "registered", "rejected"],
        help="只统计指定报名状态；可重复传入。默认统计 reviewed/registered",
    )
    parser.add_argument("--all-statuses", action="store_true", help="统计全部报名状态")
    parser.add_argument("--encoding", default="utf-8-sig", help="CSV 编码，默认 utf-8-sig")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    html_output, _ = resolve_output_paths(args)
    rows = collect_report_rows(
        db_path=args.db,
        statuses=args.status,
        include_all_statuses=args.all_statuses,
    )
    write_html_report(rows, html_output)
    summary = summarize_rows(rows)
    print("学员学习统计导出完成")
    print(f"数据库: {os.path.abspath(args.db)}")
    print(f"HTML: {os.path.abspath(html_output)}")
    print(f"学员记录: {summary['total']}")
    print(f"匹配题库: {summary['matched_bank']}")
    print(f"已开始练习/考试: {summary['started']}")
    print(f"模考已通过: {summary['passed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
