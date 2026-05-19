import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest

from flask import Flask


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from models.student import init_db, get_db_connection
from services import exam_bank_service


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


class ExamBankServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "students.db")
        self.config_dir = os.path.join(self.tmp.name, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        with open(os.path.join(self.config_dir, "job_categories.json"), "w", encoding="utf-8") as fp:
            json.dump({
                "special_equipment": {
                    "name": "特种设备",
                    "job_categories": [
                        {
                            "name": "场(厂)内专用机动车辆作业",
                            "exam_projects": [
                                {"name": "叉车司机", "code": "N1", "is_active": 1},
                                {"name": "锅炉水处理", "code": "G3", "is_active": 1},
                            ],
                        }
                    ],
                },
                "special_operation": {
                    "name": "特种作业",
                    "job_categories": [],
                },
            }, fp, ensure_ascii=False)

        self.app = Flask(__name__)
        self.app.config["DATABASE"] = self.db_path
        self.ctx = self.app.app_context()
        self.ctx.push()
        init_db(self.db_path)

    def tearDown(self):
        self.ctx.pop()
        self.tmp.cleanup()

    def get_project_id(self, exam_project="叉车司机"):
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT id FROM training_projects WHERE exam_project = ?",
                (exam_project,),
            ).fetchone()
        self.assertIsNotNone(row)
        return row["id"]

    def test_init_db_creates_exam_bank_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertIn("exam_banks", names)
        self.assertIn("exam_questions", names)
        self.assertIn("mini_practice_progress", names)
        self.assertIn("mini_exam_records", names)

    def test_import_exam_bank_creates_bank_and_questions(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
            display_name="叉车司机题库",
            is_active=True,
        )

        self.assertEqual(bank["question_count"], 1)
        self.assertEqual(bank["exam_project"], "叉车司机")

        questions = exam_bank_service.get_questions(bank["id"])
        self.assertEqual(len(questions["list"]), 1)
        self.assertEqual(questions["list"][0]["question"], "1+1=?")
        self.assertEqual(questions["list"][0]["answer"], ["B"])

    def test_reimport_replaces_existing_questions(self):
        project_id = self.get_project_id("叉车司机")
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            project_id,
        )
        replacement = [
            {
                **SAMPLE_QUESTIONS[0],
                "id": 202,
                "question": "2+2=?",
                "answer": ["A"],
                "options": {"A": "4", "B": "5"},
            }
        ]

        updated = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(replacement, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            project_id,
            replace_bank_id=bank["id"],
        )

        questions = exam_bank_service.get_questions(updated["id"])
        self.assertEqual(updated["id"], bank["id"])
        self.assertEqual(updated["question_count"], 1)
        self.assertEqual(questions["list"][0]["question"], "2+2=?")

    def test_import_uses_explicit_project_not_filename_guess(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("锅炉水处理"),
            display_name="自定义题库",
        )

        self.assertEqual(bank["project_code"], "G3")
        self.assertEqual(bank["exam_project"], "锅炉水处理")
        self.assertEqual(bank["display_name"], "自定义题库")

    def test_import_rejects_question_without_answer(self):
        invalid = [{**SAMPLE_QUESTIONS[0], "answer": []}]

        with self.assertRaises(ValueError) as cm:
            exam_bank_service.import_exam_bank(
                io.BytesIO(json.dumps(invalid, ensure_ascii=False).encode("utf-8")),
                "bad.json",
                self.get_project_id("叉车司机"),
            )

        self.assertIn("答案", str(cm.exception))

    def test_admin_summary_returns_all_active_banks(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )

        summary = exam_bank_service.get_practice_summary("admin-openid", is_admin=True)

        self.assertTrue(summary["practiceEnabled"])
        self.assertEqual([item["id"] for item in summary["banks"]], [bank["id"]])

    def test_student_summary_returns_only_owned_reviewed_matching_bank(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO students (
                    name, gender, education, id_card, phone, job_category,
                    exam_project, project_code, training_type, status,
                    submitter_openid, training_project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "张三", "男", "本科", "110101199001011234", "13800138000",
                    "场(厂)内专用机动车辆作业", "叉车司机", "N1",
                    "special_equipment", "reviewed", "student-openid",
                    self.get_project_id("叉车司机"),
                ),
            )

        summary = exam_bank_service.get_practice_summary("student-openid", is_admin=False)

        self.assertTrue(summary["practiceEnabled"])
        self.assertEqual([item["id"] for item in summary["banks"]], [bank["id"]])

    def test_student_cannot_access_unreviewed_or_inactive_bank(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO students (
                    name, gender, education, id_card, phone, job_category,
                    exam_project, project_code, training_type, status,
                    submitter_openid, training_project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "李四", "男", "本科", "110101199001011235", "13800138001",
                    "场(厂)内专用机动车辆作业", "叉车司机", "N1",
                    "special_equipment", "unreviewed", "student-openid",
                    self.get_project_id("叉车司机"),
                ),
            )

        self.assertFalse(exam_bank_service.can_access_bank("student-openid", bank["id"], False))

        exam_bank_service.set_exam_bank_active(bank["id"], False)
        self.assertFalse(exam_bank_service.can_access_bank("admin-openid", bank["id"], True))


if __name__ == "__main__":
    unittest.main()
