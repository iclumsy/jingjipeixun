"""
学员对象序列化层。

将原始的 student dict 增加前端渲染所需的派生字段，使前端不必再硬编码
状态枚举、按钮显隐逻辑、培训类型/报名类型文案、标签规则等。

派生字段清单（仅追加，绝不修改原字段）:
    - statusText            状态文案（"待审核"/"已审核"/"已报名"/"已驳回"/"考试通过"）
    - statusClass           状态 CSS 类（直接等于 status）
    - statusHint            用户端详情页提示文案
    - trainingTypeText      培训类型文案（"特种作业"/"特种设备"）
    - applicationTypeText   报名类型文案（"新考证"/"复审"）
    - actions               能力位 dict（canApprove/canReject/...）
    - actionList            按钮循环渲染数组
    - tags                  标签数组（如复审标签）
    - trainingFormFilename  体检表友好文件名（避免转发乱码）

设计原则:
    1. 只增字段不动旧字段。任何 enrich 失败时返回原 dict，绝不破坏现有响应。
    2. 所有取值用 .get(key, default)，容忍字段缺失。
    3. 业务逻辑变更只改本文件，不动路由、不动小程序、不动网页端。
"""
from flask import current_app


# ======================== 文案映射 ========================

_STATUS_TEXT = {
    'unreviewed': '待审核',
    'reviewed': '已审核',
    'registered': '已报名',
    'rejected': '已驳回',
    'exam_passed': '考试通过',
}

_STATUS_HINT = {
    'unreviewed': '资料已提交，正在等待管理员审核',
    'reviewed': '资料已审核通过，可在后台继续办理',
    'registered': '已提交报名到省网平台',
    'rejected': '资料已被驳回，可修改后重新提交',
    'exam_passed': '理论考试已通过',
}

_TRAINING_TYPE_TEXT = {
    'special_operation': '特种作业',
    'special_equipment': '特种设备',
}


# ======================== 派生字段构造 ========================

def _build_actions(s):
    """根据学员当前状态计算可执行动作能力位。

    所有业务规则集中在这里，前端只读结果不做判断。
    """
    status = s.get('status') or ''
    tt = s.get('training_type') or ''
    is_se = tt == 'special_equipment'
    is_passed = status in ('reviewed', 'registered', 'exam_passed')
    has_health_form = bool(s.get('training_form_path'))
    card_activated = bool(s.get('card_activated'))

    return {
        'canApprove': status == 'unreviewed',
        # 已报名或考试通过的学员不可直接驳回
        'canReject': status not in ('registered', 'exam_passed'),
        'canDelete': True,
        # 仅特种设备且已审核（未报名）可触发省网报名
        'canSubmitReg': is_se and status == 'reviewed',
        # 已审核或已报名的学员可推进为理论考试通过
        'canMarkExamPassed': status in ('reviewed', 'registered'),
        # 特种设备已审核/已报名且未开过卡，可开学习卡
        'canActivateCard': is_se and is_passed and not card_activated,
        # 已开卡后可查询卡信息
        'canQueryCard': is_se and is_passed and card_activated,
        # 已报名或考试通过后才能下载省网申请表
        'canDownloadRegForm': status in ('registered', 'exam_passed'),
        # 已审核、已报名或考试通过且体检表存在时可下载
        'canDownloadHealthForm': is_passed and has_health_form,
        # 用户端：仅被驳回可跳编辑页（与小程序当前行为一致）
        'canEdit': status == 'rejected',
    }


def _build_tags(s):
    """根据学员属性生成展示标签数组。"""
    tags = []
    tt = s.get('training_type') or ''
    at = s.get('application_type') or ''
    if tt == 'special_equipment' and at == 'renewal':
        tags.append({
            'text': '复审',
            'color': '#e65100',
            'bg': '#fff3e0',
        })
    return tags


def _build_action_list(actions):
    """构造按钮循环渲染数组，前端按 key 决定回调。

    顺序与现有小程序 review.wxml 保持一致：
    审核通过 → 驳回 → 删除 → 提交报名
    """
    items = []
    if actions.get('canApprove'):
        items.append({'key': 'approve', 'label': '审核通过', 'icon': '✅', 'style': 'primary'})
    if actions.get('canReject'):
        items.append({'key': 'reject', 'label': '驳回', 'icon': '↩️', 'style': 'warning'})
    items.append({'key': 'delete', 'label': '删除', 'icon': '🗑️', 'style': 'danger'})
    if actions.get('canSubmitReg'):
        items.append({'key': 'submit_register', 'label': '提交报名', 'icon': '🚀', 'style': 'secondary'})
    if actions.get('canMarkExamPassed'):
        items.append({'key': 'mark_exam_passed', 'label': '考试通过', 'icon': '✅', 'style': 'secondary'})
    return items


def _build_training_form_filename(s):
    """构造友好的体检表文件名（避免微信转发时显示乱码）。"""
    if not s.get('training_form_path'):
        return ''
    id_card = (s.get('id_card') or '').strip() or 'id'
    name = (s.get('name') or '').strip() or '学员'
    return f"{id_card}-{name}-体检表.docx"


# ======================== 主入口 ========================

def enrich_student(student):
    """在原始 student dict 上追加渲染所需字段，返回新的 dict。

    出现任何异常时记录日志并退回原始 dict，确保不破坏现有响应。
    """
    if student is None:
        return student
    if not isinstance(student, dict):
        try:
            student = dict(student)
        except Exception:
            return student

    try:
        s = dict(student)
        status = s.get('status') or ''
        tt = s.get('training_type') or ''
        at = s.get('application_type') or ''

        s['statusText'] = _STATUS_TEXT.get(status, status or '-')
        s['statusClass'] = status or ''
        s['statusHint'] = _STATUS_HINT.get(status, '')
        s['trainingTypeText'] = _TRAINING_TYPE_TEXT.get(tt, tt or '-')
        s['applicationTypeText'] = (
            '复审' if (tt == 'special_equipment' and at == 'renewal') else '新考证'
        )

        actions = _build_actions(s)
        s['actions'] = actions
        s['actionList'] = _build_action_list(actions)
        s['tags'] = _build_tags(s)
        s['trainingFormFilename'] = _build_training_form_filename(s)

        return s
    except Exception as e:
        try:
            current_app.logger.warning('enrich_student failed: %s', e)
        except Exception:
            pass
        return student


def enrich_students(students):
    """对学员列表批量 enrich。非列表原样返回。"""
    if not isinstance(students, list):
        return students
    return [enrich_student(s) for s in students]
