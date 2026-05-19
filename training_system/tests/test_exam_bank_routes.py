import io
import json
import os
import sys
import tempfile
import unittest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from app import create_app
from models.student import init_db, get_db_connection
from services import exam_bank_service
from utils.miniprogram_auth import sign_mini_token


SAMPLE_QUESTIONS = [
    {
        "id": 101,
        "type": "单选题",
        "type_code": 1,
        "question": "1+1=?",
        "question_html": "1+1=?",
        "options": {"A": "1", "B": "2"},
        "answer": ["B"],
        "analysis": "基础加法",
        "question_images": [],
        "option_images": {},
        "audio": "",
    }
]


class ExamBankRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env_path = os.path.join(self.tmp.name, ".env")
        self.old_env = os.environ.get("TRAINING_SYSTEM_ENV_FILE")
        os.environ["TRAINING_SYSTEM_ENV_FILE"] = self.env_path

        self.project_dir = os.path.join(self.tmp.name, "training_system")
        os.makedirs(os.path.join(self.project_dir, "config"), exist_ok=True)
        with open(os.path.join(self.project_dir, "config", "job_categories.json"), "w", encoding="utf-8") as fp:
            json.dump({
                "special_equipment": {
                    "name": "特种设备",
                    "job_categories": [
                        {
                            "name": "场(厂)内专用机动车辆作业",
                            "exam_projects": [
                                {"name": "叉车司机", "code": "N1", "is_active": 1},
                            ],
                        }
                    ],
                },
                "special_operation": {"name": "特种作业", "job_categories": []},
            }, fp, ensure_ascii=False)

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["DATABASE"] = os.path.join(self.tmp.name, "students.db")
        with self.app.app_context():
            init_db(self.app.config["DATABASE"])
        self.client = self.app.test_client()

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("TRAINING_SYSTEM_ENV_FILE", None)
        else:
            os.environ["TRAINING_SYSTEM_ENV_FILE"] = self.old_env
        self.tmp.cleanup()

    def login_web_admin(self):
        with self.client.session_transaction() as sess:
            sess["auth_verified"] = True
            sess["auth_user"] = "admin"

    def get_project_id(self):
        with self.app.app_context():
            with get_db_connection() as conn:
                row = conn.execute("SELECT id FROM training_projects LIMIT 1").fetchone()
                return row["id"]

    def create_bank(self):
        with self.app.app_context():
            return exam_bank_service.import_exam_bank(
                io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
                "N1_叉车司机.json",
                self.get_project_id(),
            )

    def mini_headers(self, openid="admin-openid", is_admin=True):
        token = sign_mini_token(self.app.config["SECRET_KEY"], openid, is_admin=is_admin)
        return {"Authorization": f"Bearer {token}"}

    def test_admin_page_renders_for_web_admin(self):
        self.login_web_admin()

        response = self.client.get("/admin/exam-banks")

        self.assertEqual(response.status_code, 200)
        self.assertIn("题库管理", response.get_data(as_text=True))

    def test_admin_import_and_reimport_and_toggle(self):
        self.login_web_admin()
        project_id = self.get_project_id()

        response = self.client.post(
            "/api/admin/exam_banks/import",
            data={
                "training_project_id": str(project_id),
                "display_name": "叉车司机题库",
                "is_active": "1",
                "file": (
                    io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
                    "N1_叉车司机.json",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        bank = response.get_json()["bank"]
        self.assertEqual(bank["question_count"], 1)

        replacement = [{**SAMPLE_QUESTIONS[0], "id": 202, "question": "2+2=?", "answer": ["B"]}]
        response = self.client.post(
            f"/api/admin/exam_banks/{bank['id']}/reimport",
            data={
                "training_project_id": str(project_id),
                "file": (
                    io.BytesIO(json.dumps(replacement, ensure_ascii=False).encode("utf-8")),
                    "N1_叉车司机.json",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["bank"]["question_count"], 1)

        response = self.client.post(
            f"/api/admin/exam_banks/{bank['id']}/toggle",
            json={"is_active": 0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["bank"]["is_active"], 0)

    def test_projects_and_banks_list(self):
        self.login_web_admin()
        self.create_bank()

        projects = self.client.get("/api/admin/exam_banks/projects")
        banks = self.client.get("/api/admin/exam_banks")

        self.assertEqual(projects.status_code, 200)
        self.assertGreaterEqual(len(projects.get_json()["projects"]), 1)
        self.assertEqual(banks.status_code, 200)
        self.assertEqual(len(banks.get_json()["banks"]), 1)

    def test_mini_admin_summary_and_questions(self):
        bank = self.create_bank()
        headers = self.mini_headers(is_admin=True)

        summary = self.client.get("/api/miniprogram/practice/summary", headers=headers)
        questions = self.client.get(f"/api/miniprogram/practice/banks/{bank['id']}/questions", headers=headers)

        self.assertEqual(summary.status_code, 200)
        self.assertTrue(summary.get_json()["practiceEnabled"])
        self.assertEqual(questions.status_code, 200)
        self.assertEqual(questions.get_json()["list"][0]["question"], "1+1=?")

    def test_mini_student_forbidden_without_matching_reviewed_record(self):
        bank = self.create_bank()
        headers = self.mini_headers(openid="student-openid", is_admin=False)

        summary = self.client.get("/api/miniprogram/practice/summary", headers=headers)
        questions = self.client.get(f"/api/miniprogram/practice/banks/{bank['id']}/questions", headers=headers)

        self.assertEqual(summary.status_code, 200)
        self.assertFalse(summary.get_json()["practiceEnabled"])
        self.assertEqual(questions.status_code, 403)


if __name__ == "__main__":
    unittest.main()
