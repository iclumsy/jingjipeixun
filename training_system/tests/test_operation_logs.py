import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from models import student as student_model
from routes import student_routes
from utils.auth import resolve_web_admin_name, verify_admin_credentials


class AdminIdentityTests(unittest.TestCase):
    def test_comma_separated_admin_users_share_password(self):
        with patch.dict(os.environ, {
            "TRAINING_SYSTEM_ADMIN_USER": "admin,cc",
            "TRAINING_SYSTEM_ADMIN_PASSWORD": "secret",
            "TRAINING_SYSTEM_ADMIN_PASSWORD_HASH": "",
        }, clear=False):
            self.assertTrue(verify_admin_credentials("admin", "secret"))
            self.assertTrue(verify_admin_credentials("cc", "secret"))
            self.assertFalse(verify_admin_credentials("unknown", "secret"))
            self.assertFalse(verify_admin_credentials("chengchao", "secret"))
            self.assertFalse(verify_admin_credentials("cc", "wrong"))

    def test_chinese_comma_admin_user_separator_is_supported(self):
        with patch.dict(os.environ, {
            "TRAINING_SYSTEM_ADMIN_USER": "admin，cc",
            "TRAINING_SYSTEM_ADMIN_PASSWORD": "secret",
            "TRAINING_SYSTEM_ADMIN_PASSWORD_HASH": "",
        }, clear=False):
            self.assertTrue(verify_admin_credentials("admin", "secret"))
            self.assertTrue(verify_admin_credentials("cc", "secret"))

    def test_default_admin_display_names_include_admin_and_cc(self):
        with patch.dict(os.environ, {
            "TRAINING_SYSTEM_ADMIN_DISPLAY_NAMES": "",
            "TRAINING_SYSTEM_ADMIN_NAME": "",
        }, clear=False):
            self.assertEqual(resolve_web_admin_name("admin"), "单利亚(admin)")
            self.assertEqual(resolve_web_admin_name("cc"), "程超(cc)")
            self.assertEqual(resolve_web_admin_name("chengchao"), "chengchao")


class MiniprogramReviewOperationLogUiTests(unittest.TestCase):
    def read_file(self, relative_path):
        repo_dir = os.path.dirname(PROJECT_DIR)
        with open(os.path.join(repo_dir, relative_path), encoding="utf-8") as file_obj:
            return file_obj.read()

    def test_review_cards_expose_operation_log_modal(self):
        wxml = self.read_file("miniprogram/pages/admin/review/review.wxml")
        js = self.read_file("miniprogram/pages/admin/review/review.js")
        wxss = self.read_file("miniprogram/pages/admin/review/review.wxss")

        self.assertIn("btn-operation-log", wxml)
        self.assertIn("📋 操作记录", wxml)
        self.assertIn("catchtap=\"onOperationLogTap\"", wxml)
        self.assertIn("showOperationLogModal", wxml)
        self.assertIn("operation-modal-scroll", wxml)
        self.assertIn("scroll-y", wxml)

        self.assertIn("showOperationLogModal: false", js)
        self.assertIn("async onOperationLogTap", js)
        self.assertIn("api.getStudentOperationLogs", js)
        self.assertIn("closeOperationLogModal", js)

        self.assertIn(".btn-operation-log", wxss)
        self.assertIn("font-size: 18rpx", wxss)
        self.assertIn("gap: 6rpx", wxss)
        self.assertIn("width: 100%", wxss)
        self.assertNotIn("flex: 1 1 0;", wxss)
        self.assertIn(".btn-reject,\n.btn-delete", wxss)
        self.assertIn("width: 108rpx", wxss)
        self.assertIn(".btn-secondary,\n.btn-operation-log", wxss)
        self.assertIn("width: 160rpx", wxss)


class WebStudentDetailLearningStatusUiTests(unittest.TestCase):
    def read_file(self, relative_path):
        repo_dir = os.path.dirname(PROJECT_DIR)
        with open(os.path.join(repo_dir, relative_path), encoding="utf-8") as file_obj:
            return file_obj.read()

    def test_web_detail_shows_learning_summary_entry_near_status_badge(self):
        js = self.read_file("training_system/static/js/admin.js")
        css = self.read_file("training_system/static/css/style.css")

        self.assertIn("web-learning-status-btn", js)
        self.assertIn("showLearningStatusOverlay(student)", js)
        self.assertIn("statusBadge.insertBefore(learningBtn", js)
        self.assertIn("/api/students/${student.id}/learning_status", js)
        self.assertIn("已掌握", js)
        self.assertIn("考试动态", js)

        self.assertIn(".web-learning-status-btn", css)
        self.assertIn("order: -1", css)
        self.assertIn(".learning-status-modal", css)


class OperationLogTests(unittest.TestCase):
    def build_app(self, tmp_dir, db_path, students_dir):
        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            DATABASE=db_path,
            BASE_DIR=tmp_dir,
            STUDENTS_FOLDER=students_dir,
        )
        app.register_blueprint(student_routes.student_bp)
        student_routes.broadcast_new_student_to_admins = lambda *args, **kwargs: None
        return app

    def get_first_special_equipment_project(self, db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(
                "SELECT id FROM training_projects "
                "WHERE training_type = 'special_equipment' AND is_active = 1 "
                "ORDER BY id LIMIT 1"
            ).fetchone()
        finally:
            conn.close()

    def write_tmp_files(self, tmp_dir, names):
        files = {
            name: f"students/tmp/{name}.jpg"
            for name in names
        }
        for rel_path in files.values():
            abs_path = os.path.join(tmp_dir, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "wb") as file_obj:
                file_obj.write(b"image")
        return files

    def build_payload(self, project_id, files):
        return {
            "name": "张三",
            "gender": "男",
            "education": "高中或同等学历",
            "id_card": "110101199001011234",
            "phone": "13800138000",
            "company": "测试单位",
            "company_address": "测试地址",
            "training_project_id": project_id,
            "application_type": "new_exam",
            "files": files,
        }

    def test_init_db_creates_operation_logs_table(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "students.db")
            student_model.init_db(db_path)

            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'operation_logs'"
                ).fetchone()
            finally:
                conn.close()

        self.assertIsNotNone(row)

    def test_operation_log_service_returns_student_timeline_newest_first(self):
        from services.operation_log_service import create_operation_log, get_student_operation_logs

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "students.db")
            student_model.init_db(db_path)
            app = Flask(__name__)
            app.config.update(TESTING=True, DATABASE=db_path)

            with app.app_context():
                create_operation_log(
                    7,
                    "student_created",
                    "提交报名",
                    actor_name="张三",
                    actor_source="小程序",
                    status="success",
                    message="报名已提交",
                    metadata={"field": "first"},
                )
                create_operation_log(
                    7,
                    "student_approved",
                    "审核通过",
                    actor_name="单利亚(admin)",
                    actor_source="网页端",
                    status="success",
                    message="审核通过",
                    metadata={"field": "second"},
                )
                create_operation_log(8, "student_created", "提交报名")

                logs = get_student_operation_logs(7)

        self.assertEqual([item["action"] for item in logs], ["student_approved", "student_created"])
        self.assertEqual(logs[0]["metadata"]["field"], "second")
        self.assertEqual(logs[0]["actor_name"], "单利亚(admin)")

    def test_student_operation_logs_route_returns_student_timeline(self):
        from services.operation_log_service import create_operation_log

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "students.db")
            students_dir = os.path.join(tmp_dir, "students")
            student_model.init_db(db_path)
            app = self.build_app(tmp_dir, db_path, students_dir)

            with app.app_context():
                create_operation_log(3, "student_created", "提交报名", message="报名已提交")

            response = app.test_client().get("/api/students/3/operation_logs")

        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertEqual(data["logs"][0]["action"], "student_created")
        self.assertEqual(data["logs"][0]["action_label"], "提交报名")

    def test_create_student_route_records_submit_log(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "students.db")
            students_dir = os.path.join(tmp_dir, "students")
            os.makedirs(os.path.join(students_dir, "tmp"), exist_ok=True)
            student_model.init_db(db_path)
            project = self.get_first_special_equipment_project(db_path)
            files = self.write_tmp_files(
                tmp_dir,
                ["photo", "diploma", "id_card_front", "id_card_back", "hukou_residence", "hukou_personal"],
            )
            app = self.build_app(tmp_dir, db_path, students_dir)

            response = app.test_client().post(
                "/api/students",
                json=self.build_payload(project["id"], files),
            )

            self.assertEqual(response.status_code, 201, response.get_json())
            student_id = response.get_json()["id"]

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT action, action_label, student_id, status FROM operation_logs WHERE student_id = ?",
                    (student_id,),
                ).fetchone()
            finally:
                conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["action"], "student_created")
        self.assertEqual(row["action_label"], "提交报名")
        self.assertEqual(row["status"], "success")


if __name__ == "__main__":
    unittest.main()
