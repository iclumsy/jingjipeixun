"""
学员对象序列化层 + 状态筛选拆分 + 配置接口的测试。

覆盖:
    - enrich_student: 状态/类型/标签/动作/文件名等派生字段
    - enrich_student: 旧字段一字未变、异常 fallback、批量处理
    - get_students:    撤销 reviewed→reviewed,registered 自动合并后行为
    - /api/config/student_filters: 4 个独立状态 tab 配置返回
"""
import os
import sys
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from services import student_serializer
from services.student_serializer import enrich_student, enrich_students
from models import student as student_model


# ======================== 测试基础数据 ========================

def base_student(**overrides):
    """构造一个完整的学员 dict 作为测试基线。"""
    d = {
        'id': 1,
        'name': '张三',
        'gender': '男',
        'education': '本科或同等学历',
        'id_card': '110101199001011234',
        'phone': '13800138000',
        'company': '测试单位',
        'company_address': '测试地址',
        'job_category': '电工作业',
        'exam_project': '低压电工作业',
        'project_code': '',
        'training_type': 'special_operation',
        'application_type': 'new_exam',
        'status': 'unreviewed',
        'card_activated': 0,
        'training_form_path': '',
        'submitter_openid': '',
        'reject_reason': '',
        'created_at': '2026-04-01 10:00:00',
    }
    d.update(overrides)
    return d


# ======================== 状态文案 ========================

class StatusTextTests(unittest.TestCase):
    def test_unreviewed(self):
        self.assertEqual(enrich_student(base_student(status='unreviewed'))['statusText'], '待审核')

    def test_reviewed(self):
        self.assertEqual(enrich_student(base_student(status='reviewed'))['statusText'], '已通过')

    def test_registered(self):
        self.assertEqual(enrich_student(base_student(status='registered'))['statusText'], '已报名')

    def test_rejected(self):
        self.assertEqual(enrich_student(base_student(status='rejected'))['statusText'], '已驳回')

    def test_unknown_status_falls_back_to_raw(self):
        self.assertEqual(enrich_student(base_student(status='custom'))['statusText'], 'custom')

    def test_empty_status_uses_dash(self):
        self.assertEqual(enrich_student(base_student(status=''))['statusText'], '-')


class StatusClassTests(unittest.TestCase):
    def test_status_class_equals_status(self):
        for st in ('unreviewed', 'reviewed', 'registered', 'rejected'):
            self.assertEqual(enrich_student(base_student(status=st))['statusClass'], st)


class StatusHintTests(unittest.TestCase):
    def test_each_known_status_has_hint(self):
        expected = {
            'unreviewed': '资料已提交，正在等待管理员审核',
            'reviewed': '资料已审核通过，可在后台继续办理',
            'registered': '已提交报名到省网平台',
            'rejected': '资料已被驳回，可修改后重新提交',
        }
        for status, hint in expected.items():
            self.assertEqual(enrich_student(base_student(status=status))['statusHint'], hint)

    def test_unknown_status_returns_empty_hint(self):
        self.assertEqual(enrich_student(base_student(status='custom'))['statusHint'], '')


# ======================== 培训类型 / 报名类型 ========================

class TrainingTypeTextTests(unittest.TestCase):
    def test_special_operation(self):
        self.assertEqual(
            enrich_student(base_student(training_type='special_operation'))['trainingTypeText'],
            '特种作业',
        )

    def test_special_equipment(self):
        self.assertEqual(
            enrich_student(base_student(training_type='special_equipment'))['trainingTypeText'],
            '特种设备',
        )


class ApplicationTypeTextTests(unittest.TestCase):
    def test_special_equipment_renewal(self):
        s = enrich_student(base_student(training_type='special_equipment', application_type='renewal'))
        self.assertEqual(s['applicationTypeText'], '复审')

    def test_special_equipment_new_exam(self):
        s = enrich_student(base_student(training_type='special_equipment', application_type='new_exam'))
        self.assertEqual(s['applicationTypeText'], '新考证')

    def test_special_operation_renewal_falls_back_to_new_exam(self):
        # 复审仅特种设备支持
        s = enrich_student(base_student(training_type='special_operation', application_type='renewal'))
        self.assertEqual(s['applicationTypeText'], '新考证')


# ======================== 能力位 actions ========================

class ActionsTests(unittest.TestCase):
    def test_unreviewed_can_approve_and_reject(self):
        a = enrich_student(base_student(status='unreviewed'))['actions']
        self.assertTrue(a['canApprove'])
        self.assertTrue(a['canReject'])
        self.assertFalse(a['canSubmitReg'])
        self.assertFalse(a['canActivateCard'])
        self.assertFalse(a['canQueryCard'])
        self.assertFalse(a['canDownloadHealthForm'])
        self.assertFalse(a['canDownloadRegForm'])
        self.assertFalse(a['canEdit'])

    def test_reviewed_se_can_submit_reg_and_activate(self):
        a = enrich_student(base_student(status='reviewed', training_type='special_equipment'))['actions']
        self.assertFalse(a['canApprove'])
        self.assertTrue(a['canReject'])
        self.assertTrue(a['canSubmitReg'])
        self.assertTrue(a['canActivateCard'])
        self.assertFalse(a['canQueryCard'])

    def test_reviewed_so_no_se_specific_actions(self):
        a = enrich_student(base_student(status='reviewed', training_type='special_operation'))['actions']
        self.assertFalse(a['canSubmitReg'])
        self.assertFalse(a['canActivateCard'])
        self.assertFalse(a['canQueryCard'])

    def test_registered_cannot_submit_or_reject(self):
        a = enrich_student(base_student(status='registered', training_type='special_equipment'))['actions']
        self.assertFalse(a['canApprove'])
        self.assertFalse(a['canReject'])
        self.assertFalse(a['canSubmitReg'])
        self.assertTrue(a['canActivateCard'])
        self.assertTrue(a['canDownloadRegForm'])

    def test_rejected_can_edit_and_reject(self):
        a = enrich_student(base_student(status='rejected'))['actions']
        self.assertTrue(a['canEdit'])
        self.assertTrue(a['canReject'])
        self.assertFalse(a['canApprove'])

    def test_card_activated_swaps_query_and_activate(self):
        s = base_student(status='reviewed', training_type='special_equipment', card_activated=1)
        a = enrich_student(s)['actions']
        self.assertFalse(a['canActivateCard'])
        self.assertTrue(a['canQueryCard'])

    def test_health_form_download_requires_path_and_passed_status(self):
        # reviewed + 有体检表 → True
        a = enrich_student(base_student(status='reviewed', training_form_path='students/x.docx'))['actions']
        self.assertTrue(a['canDownloadHealthForm'])
        # registered + 有体检表 → True
        a = enrich_student(base_student(status='registered', training_form_path='abc'))['actions']
        self.assertTrue(a['canDownloadHealthForm'])
        # unreviewed + 有体检表（理论上不应出现，但容错）→ False
        a = enrich_student(base_student(status='unreviewed', training_form_path='abc'))['actions']
        self.assertFalse(a['canDownloadHealthForm'])
        # rejected + 有体检表 → False
        a = enrich_student(base_student(status='rejected', training_form_path='abc'))['actions']
        self.assertFalse(a['canDownloadHealthForm'])
        # reviewed + 没体检表 → False
        a = enrich_student(base_student(status='reviewed', training_form_path=''))['actions']
        self.assertFalse(a['canDownloadHealthForm'])

    def test_can_delete_always_true(self):
        for st in ('unreviewed', 'reviewed', 'registered', 'rejected'):
            self.assertTrue(enrich_student(base_student(status=st))['actions']['canDelete'])


# ======================== actionList 顺序 ========================

class ActionListTests(unittest.TestCase):
    def test_unreviewed_starts_with_approve(self):
        items = enrich_student(base_student(status='unreviewed'))['actionList']
        keys = [it['key'] for it in items]
        self.assertEqual(keys[0], 'approve')
        self.assertIn('reject', keys)
        self.assertIn('delete', keys)

    def test_registered_omits_approve_and_reject(self):
        items = enrich_student(base_student(status='registered', training_type='special_equipment'))['actionList']
        keys = [it['key'] for it in items]
        self.assertNotIn('approve', keys)
        self.assertNotIn('reject', keys)
        self.assertIn('delete', keys)

    def test_reviewed_se_includes_submit_register(self):
        items = enrich_student(base_student(status='reviewed', training_type='special_equipment'))['actionList']
        keys = [it['key'] for it in items]
        self.assertIn('submit_register', keys)

    def test_reviewed_so_no_submit_register(self):
        items = enrich_student(base_student(status='reviewed', training_type='special_operation'))['actionList']
        keys = [it['key'] for it in items]
        self.assertNotIn('submit_register', keys)

    def test_action_items_have_required_fields(self):
        items = enrich_student(base_student(status='unreviewed'))['actionList']
        for it in items:
            self.assertIn('key', it)
            self.assertIn('label', it)
            self.assertIn('icon', it)
            self.assertIn('style', it)


# ======================== tags ========================

class TagsTests(unittest.TestCase):
    def test_special_equipment_renewal_has_renewal_tag(self):
        tags = enrich_student(base_student(training_type='special_equipment', application_type='renewal'))['tags']
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]['text'], '复审')

    def test_special_equipment_new_exam_no_tag(self):
        tags = enrich_student(base_student(training_type='special_equipment', application_type='new_exam'))['tags']
        self.assertEqual(tags, [])

    def test_special_operation_renewal_no_tag(self):
        # 仅特种设备支持复审
        tags = enrich_student(base_student(training_type='special_operation', application_type='renewal'))['tags']
        self.assertEqual(tags, [])


# ======================== 体检表文件名 ========================

class TrainingFormFilenameTests(unittest.TestCase):
    def test_with_path_returns_friendly_filename(self):
        s = enrich_student(base_student(training_form_path='abc', name='李四', id_card='1234567890'))
        self.assertEqual(s['trainingFormFilename'], '1234567890-李四-体检表.docx')

    def test_without_path_returns_empty(self):
        s = enrich_student(base_student(training_form_path=''))
        self.assertEqual(s['trainingFormFilename'], '')

    def test_missing_name_uses_default(self):
        s = enrich_student(base_student(training_form_path='abc', name='', id_card=''))
        self.assertEqual(s['trainingFormFilename'], 'id-学员-体检表.docx')


# ======================== 旧字段保留 ========================

class PreservesOriginalFieldsTests(unittest.TestCase):
    def test_all_original_fields_unchanged(self):
        original = base_student(
            id=99, name='王五', gender='女', status='reviewed',
            training_type='special_equipment', application_type='renewal',
            training_form_path='students/file.docx', card_activated=1,
            reject_reason='照片不清晰',
        )
        enriched = enrich_student(original)
        for k, v in original.items():
            self.assertEqual(enriched.get(k), v, f'original field "{k}" was mutated')

    def test_returned_dict_is_new_object(self):
        s = base_student()
        enriched = enrich_student(s)
        self.assertIsNot(enriched, s)
        # 修改 enriched 不应影响原对象
        enriched['statusText'] = 'X'
        self.assertNotIn('statusText', s)

    def test_no_unexpected_keys_dropped(self):
        original = base_student(extra_legacy_field='legacy_value')
        enriched = enrich_student(original)
        self.assertEqual(enriched['extra_legacy_field'], 'legacy_value')


# ======================== 异常 fallback ========================

class FailureFallbackTests(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(enrich_student(None))

    def test_non_dict_uncoercible_returns_as_is(self):
        # 字符串无法转 dict，应原样返回
        result = enrich_student('not a dict')
        self.assertEqual(result, 'not a dict')

    def test_missing_status_does_not_crash(self):
        s = enrich_student({'id': 1})
        self.assertIn('actions', s)
        self.assertEqual(s['statusText'], '-')

    def test_exception_returns_original(self):
        s = base_student()
        with patch.object(student_serializer, '_build_actions', side_effect=RuntimeError('boom')):
            result = enrich_student(s)
        # 失败时返回原 dict（不应有 actions 字段）
        self.assertEqual(result, s)
        self.assertNotIn('actions', result)


# ======================== 列表批量 ========================

class EnrichStudentsTests(unittest.TestCase):
    def test_batch_enrich(self):
        results = enrich_students([
            base_student(status='unreviewed'),
            base_student(status='reviewed', training_type='special_equipment'),
        ])
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]['actions']['canApprove'])
        self.assertFalse(results[1]['actions']['canApprove'])

    def test_non_list_returns_as_is(self):
        self.assertIsNone(enrich_students(None))
        self.assertEqual(enrich_students('x'), 'x')


# ======================== model 撤销合并 ========================

class StatusFilterModelTests(unittest.TestCase):
    """验证 get_students 不再自动合并 reviewed/registered。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, 'students.db')
        student_model.init_db(self.db_path)
        self.app = Flask(__name__)
        self.app.config['DATABASE'] = self.db_path

    def tearDown(self):
        self.tmp.cleanup()

    def _insert_student(self, status, suffix='0001', training_type='special_equipment'):
        with self.app.app_context():
            with student_model.get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO students (name, gender, education, id_card, phone, "
                    "company, job_category, training_type, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ('测试', '男', '本科或同等学历',
                     '11010119900101' + suffix.rjust(4, '0'),
                     '13800138000', '甲公司', '电工作业', training_type, status)
                )

    def test_reviewed_filter_excludes_registered(self):
        self._insert_student('reviewed', '0001')
        self._insert_student('registered', '0002')
        with self.app.app_context():
            students = student_model.get_students(status='reviewed')
        statuses = sorted([s['status'] for s in students])
        self.assertEqual(statuses, ['reviewed'])

    def test_registered_filter_excludes_reviewed(self):
        self._insert_student('reviewed', '0001')
        self._insert_student('registered', '0002')
        with self.app.app_context():
            students = student_model.get_students(status='registered')
        statuses = sorted([s['status'] for s in students])
        self.assertEqual(statuses, ['registered'])

    def test_compound_status_still_supported(self):
        """旧版小程序仍可用 'reviewed,registered' 复合查询。"""
        self._insert_student('reviewed', '0001')
        self._insert_student('registered', '0002')
        self._insert_student('rejected', '0003')
        with self.app.app_context():
            students = student_model.get_students(status='reviewed,registered')
        statuses = sorted([s['status'] for s in students])
        self.assertEqual(statuses, ['registered', 'reviewed'])

    def test_pending_includes_unreviewed_and_rejected(self):
        self._insert_student('unreviewed', '0001')
        self._insert_student('rejected', '0002')
        self._insert_student('reviewed', '0003')
        with self.app.app_context():
            students = student_model.get_students(status='pending')
        statuses = sorted([s['status'] for s in students])
        self.assertEqual(statuses, ['rejected', 'unreviewed'])

    def test_get_companies_reviewed_excludes_registered(self):
        self._insert_student('reviewed', '0001', training_type='special_equipment')
        self._insert_student('registered', '0002', training_type='special_equipment')
        with self.app.app_context():
            with student_model.get_db_connection() as conn:
                conn.execute(
                    "UPDATE students SET company = ? WHERE id = ?",
                    ('A公司', 1)
                )
                conn.execute(
                    "UPDATE students SET company = ? WHERE id = ?",
                    ('B公司', 2)
                )
            companies = student_model.get_companies(status='reviewed')
        self.assertEqual(companies, ['A公司'])


# ======================== 配置接口 ========================

class StudentFiltersConfigTests(unittest.TestCase):
    """验证 /api/config/student_filters 返回 4 个独立 tab。"""

    def setUp(self):
        from routes.config_routes import config_bp
        self.app = Flask(__name__)
        self.app.register_blueprint(config_bp)
        self.client = self.app.test_client()

    def test_admin_returns_four_status_tabs(self):
        resp = self.client.get('/api/config/student_filters?role=admin')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        labels = [t['label'] for t in data['status_filters']]
        self.assertEqual(labels, ['待审核', '已通过', '已报名', '已驳回'])
        values = [t['value'] for t in data['status_filters']]
        self.assertEqual(values, ['unreviewed', 'reviewed', 'registered', 'rejected'])

    def test_default_filters(self):
        resp = self.client.get('/api/config/student_filters?role=admin')
        data = resp.get_json()
        self.assertEqual(data['default']['status'], 'unreviewed')
        self.assertEqual(data['default']['training_type'], 'special_equipment')

    def test_training_type_filters_present(self):
        resp = self.client.get('/api/config/student_filters?role=admin')
        data = resp.get_json()
        types = [t['value'] for t in data['training_type_filters']]
        self.assertIn('special_equipment', types)
        self.assertIn('special_operation', types)

    def test_default_role_is_admin(self):
        resp = self.client.get('/api/config/student_filters')
        data = resp.get_json()
        self.assertEqual(len(data['status_filters']), 4)


if __name__ == '__main__':
    unittest.main()
