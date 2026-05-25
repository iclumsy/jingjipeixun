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
                    "job_categories": [
                        {
                            "name": "电工作业",
                            "exam_projects": [
                                {"name": "低压电工作业", "code": "T1", "is_active": 1},
                            ],
                        }
                    ],
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
        self.assertIn("mini_question_states", names)

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

    def test_list_training_projects_only_returns_special_equipment_for_exam_banks(self):
        projects = exam_bank_service.list_training_projects(include_inactive=True)

        self.assertEqual({item["training_type"] for item in projects}, {"special_equipment"})
        self.assertIn("叉车司机", {item["exam_project"] for item in projects})
        self.assertIn("锅炉水处理", {item["exam_project"] for item in projects})
        self.assertNotIn("低压电工作业", {item["exam_project"] for item in projects})

    def test_import_rejects_special_operation_project(self):
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT id FROM training_projects WHERE training_type = ?",
                ("special_operation",),
            ).fetchone()
        self.assertIsNotNone(row)

        with self.assertRaises(ValueError) as cm:
            exam_bank_service.import_exam_bank(
                io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
                "T1_低压电工作业.json",
                row["id"],
            )

        self.assertIn("特种设备", str(cm.exception))

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

    def test_update_exam_bank_changes_name_and_project(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
            display_name="旧名称",
        )

        updated = exam_bank_service.update_exam_bank(
            bank["id"],
            display_name="新名称",
            training_project_id=self.get_project_id("锅炉水处理"),
        )

        self.assertEqual(updated["display_name"], "新名称")
        self.assertEqual(updated["project_code"], "G3")
        self.assertEqual(updated["exam_project"], "锅炉水处理")

    def test_delete_exam_bank_removes_questions_and_progress(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        exam_bank_service.save_progress("student-openid", bank["id"], {
            "doneCount": 1,
            "correctCount": 1,
            "wrongQuestionIds": [],
        })
        exam_bank_service.save_question_state("student-openid", bank["id"], SAMPLE_QUESTIONS[0]["id"], {
            "action": "answer",
            "isCorrect": True,
            "answer": ["B"],
            "mode": "practice",
        })

        result = exam_bank_service.delete_exam_bank(bank["id"])

        self.assertTrue(result["success"])
        self.assertIsNone(exam_bank_service.get_exam_bank(bank["id"]))
        self.assertEqual(exam_bank_service.get_questions(bank["id"])["total"], 0)
        with get_db_connection() as conn:
            progress = conn.execute(
                "SELECT COUNT(*) FROM mini_practice_progress WHERE bank_id = ?",
                (bank["id"],),
            ).fetchone()[0]
            states = conn.execute(
                "SELECT COUNT(*) FROM mini_question_states WHERE bank_id = ?",
                (bank["id"],),
            ).fetchone()[0]
        self.assertEqual(progress, 0)
        self.assertEqual(states, 0)

    def test_save_question_state_tracks_seen_mastered_and_wrong_statuses(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        question_id = SAMPLE_QUESTIONS[0]["id"]

        seen = exam_bank_service.save_question_state("student-openid", bank["id"], question_id, {
            "action": "seen",
            "mode": "memorize",
        })
        wrong = exam_bank_service.save_question_state("student-openid", bank["id"], question_id, {
            "action": "answer",
            "isCorrect": False,
            "answer": ["A"],
            "mode": "practice",
        })
        mastered = exam_bank_service.save_question_state("student-openid", bank["id"], question_id, {
            "action": "answer",
            "isCorrect": True,
            "answer": ["B"],
            "mode": "wrong",
        })

        self.assertEqual(seen["state"]["status"], "seen")
        self.assertEqual(wrong["state"]["status"], "wrong")
        self.assertEqual(mastered["state"]["status"], "mastered")
        self.assertEqual(mastered["state"]["answerCount"], 2)
        self.assertEqual(mastered["state"]["correctCount"], 1)
        self.assertEqual(mastered["state"]["wrongCount"], 1)
        self.assertEqual(mastered["state"]["lastMode"], "wrong")
        self.assertEqual(mastered["state"]["lastAnswer"], ["B"])

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

    def test_admin_summary_ignores_legacy_special_operation_banks(self):
        with get_db_connection() as conn:
            project = conn.execute(
                "SELECT * FROM training_projects WHERE training_type = ?",
                ("special_operation",),
            ).fetchone()
            cursor = conn.execute(
                """
                INSERT INTO exam_banks (
                    training_project_id, bank_key, training_type, job_category,
                    exam_project, project_code, display_name, source_filename,
                    question_count, is_active, imported_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    project["id"], "T1_低压电工作业", project["training_type"],
                    project["job_category"], project["exam_project"], project["project_code"],
                    "低压电工作业题库", "T1_低压电工作业.json", 1, 1,
                ),
            )
            legacy_bank_id = cursor.lastrowid

        summary = exam_bank_service.get_practice_summary("admin-openid", is_admin=True)

        self.assertFalse(any(item["id"] == legacy_bank_id for item in summary["banks"]))
        self.assertFalse(exam_bank_service.can_access_bank("admin-openid", legacy_bank_id, True))

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

    def test_learning_status_aggregates_question_states_and_all_exam_records(self):
        sample_questions = [
            {**SAMPLE_QUESTIONS[0], "id": 101, "question": "1+1=?", "answer": ["B"]},
            {**SAMPLE_QUESTIONS[0], "id": 102, "question": "2+2=?", "answer": ["A"]},
            {**SAMPLE_QUESTIONS[0], "id": 103, "question": "3+3=?", "answer": ["B"]},
            {**SAMPLE_QUESTIONS[0], "id": 104, "question": "4+4=?", "answer": ["A"]},
        ]
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(sample_questions, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        with get_db_connection() as conn:
            project_id = self.get_project_id("叉车司机")
            student_id = conn.execute(
                """
                INSERT INTO students (
                    name, gender, education, id_card, phone, job_category,
                    exam_project, project_code, training_type, status,
                    submitter_openid, training_project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "王五", "男", "高中或同等学历", "110101199001011236", "13800138002",
                    "场(厂)内专用机动车辆作业", "叉车司机", "N1",
                    "special_equipment", "reviewed", "student-openid", project_id,
                ),
            ).lastrowid

        exam_bank_service.save_question_state("student-openid", bank["id"], 101, {
            "action": "seen",
            "mode": "memorize",
        })
        exam_bank_service.save_question_state("student-openid", bank["id"], 102, {
            "action": "answer",
            "isCorrect": True,
            "answer": ["A"],
            "mode": "practice",
        })
        exam_bank_service.save_question_state("student-openid", bank["id"], 103, {
            "action": "answer",
            "isCorrect": False,
            "answer": ["A"],
            "mode": "practice",
        })
        exam_bank_service.save_exam_record("student-openid", bank["id"], {
            "score": 70,
            "total": 100,
            "correctCount": 70,
            "durationSeconds": 1800,
            "passed": False,
        })
        exam_bank_service.save_exam_record("student-openid", bank["id"], {
            "score": 88,
            "total": 100,
            "correctCount": 88,
            "durationSeconds": 1700,
            "passed": True,
        })

        with get_db_connection() as conn:
            student = dict(conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone())
        result = exam_bank_service.get_student_learning_status(student)

        self.assertEqual(result["summary"]["seenCount"], 1)
        self.assertEqual(result["summary"]["masteredCount"], 1)
        self.assertEqual(result["summary"]["wrongCount"], 1)
        self.assertEqual(result["summary"]["untouchedCount"], 1)
        self.assertEqual(result["summary"]["answeredCount"], 2)
        self.assertEqual(result["summary"]["studyProgressPercent"], 75)
        self.assertEqual(result["summary"]["answerProgressPercent"], 50)
        self.assertEqual(result["summary"]["masteryPercent"], 25)
        self.assertEqual(result["summary"]["correctRate"], 50)
        self.assertEqual(result["examStats"]["count"], 2)
        self.assertEqual(result["examStats"]["bestScore"], 88)
        self.assertEqual(result["examStats"]["passCount"], 1)
        self.assertEqual([item["score"] for item in result["examStats"]["records"]], [88, 70])

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
