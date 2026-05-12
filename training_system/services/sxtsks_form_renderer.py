"""
山西省特种设备申请表 - 本地离线渲染。

在已经从省网拿到水印号后，本地完全自主用 Jinja 模板 + 数据库字段 +
本地照片 + weasyprint 转 PDF，不再访问省网。

入口:
    render_application_form_pdf(student, watermark_text) -> bytes

水印号提取:
    extract_watermark_text(html_str) -> str | None
"""
import os
import re
import base64
import logging
from flask import render_template, current_app

logger = logging.getLogger(__name__)


# ---------- 文化程度展示文本（数据库存值 → 申请表显示文字）----------
EDUCATION_DISPLAY = {
    '初中': '初中',
    '高中或同等学历': '高中',
    '中专或同等学历': '中专',
    '专科或同等学历': '大专',
    '本科或同等学历': '本科',
    '研究生及以上': '研究生',
}

# 阳泉固定参数
POSTAL_CODE = '045000'
OPERATION_GZJL = '从事特种设备工作三个月以上。'
MANAGEMENT_GZJL = '从事安全管理工作2年以上。'

# 与 document_service.HEALTH_CHECK_PROJECT_CODES 保持语义一致：仅叉车(N1)、锅炉水处理(G3)需体检
HEALTH_CHECK_PROJECT_CODES = {'N1', 'G3'}
HEALTH_CHECK_PROJECT_NAMES = {'叉车司机', '锅炉水处理'}


# ---------- 项目名称 / 代号映射到省网申请表的标准显示 ----------
# 起重机司机有 6 个子类型，省网展示用 "起重机司机(限xxx)" + "Q2(限xxx)" 格式
_CRANE_SUBTYPES = [
    ('桥式',   '起重机司机(限桥式起重机)',   'Q2(限桥式起重机)'),
    ('门式',   '起重机司机(限门式起重机)',   'Q2(限门式起重机)'),
    ('塔式',   '起重机司机(限塔式起重机)',   'Q2(限塔式起重机)'),
    ('门座式', '起重机司机(限门座式起重机)', 'Q2(限门座式起重机)'),
    ('缆索式', '起重机司机(限缆索式起重机)', 'Q2(限缆索式起重机)'),
    ('流动式', '起重机司机(限流动式起重机)', 'Q2(限流动式起重机)'),
]


def _normalize_crane_subtype(exam_project):
    """从本地的项目名（如"桥式起重机司机"或"起重机司机(限桥式起重机)"）解析出子类型。
    返回 (省网项目名, 省网代号) 或 None。"""
    if not exam_project:
        return None
    name = exam_project.strip()
    for keyword, sxtsks_name, sxtsks_code in _CRANE_SUBTYPES:
        if keyword in name:
            return sxtsks_name, sxtsks_code
    return None


def normalize_exam_project(student):
    """学员的作业项目名称转省网申请表的展示文本。"""
    name = (student.get('exam_project') or '').strip()
    if not name:
        return ''
    # 起重机司机子项目：需要 "起重机司机(限xxx)" 格式
    code = (student.get('project_code') or '').strip()
    if code == 'Q2' or '起重机司机' in name:
        crane = _normalize_crane_subtype(name)
        if crane:
            return crane[0]
    return name


def normalize_project_code(student):
    """学员的项目代号转省网申请表的展示文本。"""
    code = (student.get('project_code') or '').strip()
    if not code:
        return ''
    # Q2 需要带子类型后缀
    if code == 'Q2':
        crane = _normalize_crane_subtype(student.get('exam_project') or '')
        if crane:
            return crane[1]
    return code


# ---------- 水印号正则 ----------
_WATERMARK_RE = re.compile(r"watermark\.innerText\s*=\s*['\"]([^'\"]+)['\"]")


def extract_watermark_text(html_text):
    """从省网申请表 HTML 中解析水印文字。

    返回完整水印字符串（如 "山西省特种设备作业人员考核管理平台 26013999"），
    解析失败返回 None。
    """
    if not html_text:
        return None
    m = _WATERMARK_RE.search(html_text)
    return m.group(1) if m else None


# ---------- 业务字段拼装 ----------
def _resolve_work_history(student):
    """根据培训类型 / 作业类别决定工作简历文本。"""
    job_category = (student.get('job_category') or '').strip()
    # 含「安全管理」字样的视为管理类
    if '安全管理' in job_category:
        return MANAGEMENT_GZJL
    return OPERATION_GZJL


def _resolve_needs_health(student):
    code = (student.get('project_code') or '').strip().upper()
    project = (student.get('exam_project') or '').strip()
    if code in HEALTH_CHECK_PROJECT_CODES:
        return True
    if project in HEALTH_CHECK_PROJECT_NAMES:
        return True
    return False


def _resolve_gender(student):
    """gender 缺失时从身份证号推断（17 位奇男偶女）。"""
    gender = (student.get('gender') or '').strip()
    if gender:
        return gender
    id_card = (student.get('id_card') or '').strip()
    if len(id_card) == 18 and id_card[16].isdigit():
        return '男' if int(id_card[16]) % 2 == 1 else '女'
    return ''


def _resolve_apply_date(student):
    """申请日期：优先用 created_at 的日期部分。"""
    created = (student.get('created_at') or '').strip()
    if created:
        # 兼容 "YYYY-MM-DD HH:MM:SS" 和 "YYYY-MM-DD"
        return created.split(' ')[0][:10]
    from datetime import date
    return date.today().strftime('%Y-%m-%d')


def _photo_data_url(photo_abs_path):
    """把本地照片转 data URL，weasyprint 直接消费，避免 file:// 权限/路径问题。"""
    if not photo_abs_path or not os.path.exists(photo_abs_path):
        return ''
    try:
        with open(photo_abs_path, 'rb') as f:
            raw = f.read()
        ext = os.path.splitext(photo_abs_path)[1].lower().lstrip('.')
        if ext == 'jpg':
            ext = 'jpeg'
        if ext not in ('jpeg', 'png', 'gif', 'bmp', 'webp'):
            ext = 'jpeg'
        return f'data:image/{ext};base64,{base64.b64encode(raw).decode("ascii")}'
    except Exception as e:
        logger.warning(f'读取照片失败 {photo_abs_path}: {e}')
        return ''


def _font_url():
    """字体文件的 file:// URL，weasyprint 可在 @font-face 加载。"""
    base_dir = current_app.config.get('BASE_DIR') if current_app else None
    if not base_dir:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    font_path = os.path.join(base_dir, 'static', 'fonts', 'NotoSansSC-Regular.ttf')
    return f'file://{font_path}'


def render_application_form_html(student, watermark_text, photo_abs_path=None):
    """渲染申请表 HTML（供调试或单元测试使用）。"""
    ctx = {
        'name': student.get('name', '') or '',
        'gender': _resolve_gender(student),
        'id_card': student.get('id_card', '') or '',
        'education_display': EDUCATION_DISPLAY.get(student.get('education', ''), student.get('education', '') or ''),
        'company': student.get('company', '') or '',
        'company_address': student.get('company_address', '') or '',
        'mailing_address': student.get('company_address', '') or '',
        'postal_code': POSTAL_CODE,
        'phone': student.get('phone', '') or '',
        'exam_project': normalize_exam_project(student),
        'project_code': normalize_project_code(student),
        'work_history': _resolve_work_history(student),
        'needs_health': _resolve_needs_health(student),
        'apply_date': _resolve_apply_date(student),
        'watermark_text': watermark_text or '山西省特种设备作业人员考核管理平台',
        'photo_url': _photo_data_url(photo_abs_path) if photo_abs_path else '',
        'font_url': _font_url(),
    }
    return render_template('sxtsks/application_form_new.html', **ctx)


def render_application_form_pdf(student, watermark_text, photo_abs_path=None):
    """渲染申请表 PDF，返回 bytes。"""
    import weasyprint
    html = render_application_form_html(student, watermark_text, photo_abs_path=photo_abs_path)
    return weasyprint.HTML(string=html).write_pdf()
