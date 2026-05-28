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


def make_question(question_id, question_text=None, answer=None, question_type="单选题", type_code=1):
    return {
        **SAMPLE_QUESTIONS[0],
        "id": question_id,
        "type": question_type,
        "type_code": type_code,
        "question": question_text or f"题目 {question_id}",
        "question_html": question_text or f"题目 {question_id}",
        "answer": answer or ["B"],
    }


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

    def test_browsed_and_mastered_counts_are_independent(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        question_id = SAMPLE_QUESTIONS[0]["id"]

        exam_bank_service.save_question_state("student-openid", bank["id"], question_id, {
            "action": "seen",
            "mode": "memorize",
        })
        exam_bank_service.save_question_state("student-openid", bank["id"], question_id, {
            "action": "answer",
            "isCorrect": True,
            "answer": ["B"],
            "mode": "practice",
        })

        summary = exam_bank_service.get_practice_summary("student-openid", is_admin=True)
        state = summary["banks"][0]["questionState"]

        self.assertEqual(state["seenCount"], 1)
        self.assertEqual(state["masteredCount"], 1)
        self.assertEqual(state["wrongCount"], 0)
        self.assertEqual(state["answeredCount"], 1)
        self.assertEqual(state["touchedCount"], 1)
        self.assertEqual(state["untouchedCount"], 0)

    def test_save_question_state_updates_practice_resume_cursor_for_answers_only(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps([
                make_question(101, "第一题"),
                make_question(102, "第二题"),
            ], ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )

        exam_bank_service.save_question_state("student-openid", bank["id"], 101, {
            "action": "seen",
            "mode": "memorize",
        })
        with get_db_connection() as conn:
            seen_progress = conn.execute(
                "SELECT * FROM mini_practice_progress WHERE openid = ? AND bank_id = ? AND mode = ?",
                ("student-openid", bank["id"], "practice"),
            ).fetchone()
        self.assertIsNone(seen_progress)

        exam_bank_service.save_question_state("student-openid", bank["id"], 102, {
            "action": "answer",
            "isCorrect": True,
            "answer": ["B"],
            "mode": "practice",
        })

        with get_db_connection() as conn:
            progress = conn.execute(
                "SELECT * FROM mini_practice_progress WHERE openid = ? AND bank_id = ? AND mode = ?",
                ("student-openid", bank["id"], "practice"),
            ).fetchone()
        self.assertIsNotNone(progress)
        self.assertEqual(progress["last_question_id"], 2)

    def test_memorize_questions_prioritize_unbrowsed_questions_for_openid(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps([
                make_question(101, "已浏览题"),
                make_question(102, "已掌握但未浏览题"),
                make_question(103, "未浏览题"),
                make_question(104, "另一道未浏览题"),
            ], ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        exam_bank_service.save_question_state("student-openid", bank["id"], 101, {
            "action": "seen",
            "mode": "memorize",
        })
        exam_bank_service.save_question_state("student-openid", bank["id"], 102, {
            "action": "answer",
            "isCorrect": True,
            "answer": ["B"],
            "mode": "practice",
        })

        result = exam_bank_service.get_questions(
            bank["id"],
            mode="memorize",
            limit=2,
            openid="student-openid",
        )

        self.assertEqual([item["source_question_id"] for item in result["list"]], ["103", "104"])

    def test_get_questions_returns_student_question_state_summary(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps([
                make_question(101, "已浏览题"),
                make_question(102, "已掌握题"),
                make_question(103, "错题"),
                make_question(104, "未做题"),
            ], ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        exam_bank_service.save_question_state("student-openid", bank["id"], 101, {
            "action": "seen",
            "mode": "memorize",
        })
        exam_bank_service.save_question_state("student-openid", bank["id"], 102, {
            "action": "answer",
            "isCorrect": True,
            "answer": ["B"],
            "mode": "practice",
        })
        exam_bank_service.save_question_state("student-openid", bank["id"], 103, {
            "action": "answer",
            "isCorrect": False,
            "answer": ["A"],
            "mode": "practice",
        })

        result = exam_bank_service.get_questions(
            bank["id"],
            mode="sequential",
            limit=4,
            openid="student-openid",
        )

        self.assertEqual(result["questionState"]["seenCount"], 3)
        self.assertEqual(result["questionState"]["masteredCount"], 1)
        self.assertEqual(result["questionState"]["wrongCount"], 1)
        self.assertEqual(result["questionState"]["answeredCount"], 2)
        self.assertEqual(result["questionState"]["touchedCount"], 3)
        self.assertEqual(result["questionState"]["studyProgressPercent"], 75)
        self.assertEqual(result["questionState"]["answerProgressPercent"], 50)
        states = {
            item["source_question_id"]: item.get("state")
            for item in result["list"]
        }
        self.assertEqual(states["101"]["status"], "seen")
        self.assertEqual(states["102"]["status"], "mastered")
        self.assertEqual(states["103"]["status"], "wrong")
        self.assertIsNone(states["104"])

    def test_get_questions_state_summary_respects_question_type_filter(self):
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps([
                make_question(101, "单选掌握题"),
                {**make_question(102, "判断错题"), "type": "判断题", "type_code": 3, "answer": ["B"]},
                {**make_question(103, "判断掌握题"), "type": "判断题", "type_code": 3, "answer": ["B"]},
            ], ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        exam_bank_service.save_question_state("student-openid", bank["id"], 101, {
            "action": "answer",
            "isCorrect": True,
            "answer": ["B"],
            "mode": "practice",
        })
        exam_bank_service.save_question_state("student-openid", bank["id"], 102, {
            "action": "answer",
            "isCorrect": False,
            "answer": ["A"],
            "mode": "practice",
        })
        exam_bank_service.save_question_state("student-openid", bank["id"], 103, {
            "action": "answer",
            "isCorrect": True,
            "answer": ["B"],
            "mode": "practice",
        })

        result = exam_bank_service.get_questions(
            bank["id"],
            mode="sequential",
            limit=3,
            question_type="judge",
            openid="student-openid",
        )

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["questionState"]["masteredCount"], 1)
        self.assertEqual(result["questionState"]["wrongCount"], 1)
        self.assertEqual(result["questionState"]["answeredCount"], 2)
        self.assertEqual(result["questionState"]["masteryPercent"], 50)

    def test_exam_questions_use_fixed_type_distribution(self):
        questions = []
        questions.extend(
            make_question(1000 + index, f"单选题 {index}", question_type="单选题", type_code=1)
            for index in range(60)
        )
        questions.extend(
            make_question(2000 + index, f"多选题 {index}", answer=["A", "B"], question_type="多选题", type_code=2)
            for index in range(40)
        )
        questions.extend(
            make_question(3000 + index, f"判断题 {index}", question_type="判断题", type_code=3)
            for index in range(30)
        )
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(questions, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )

        result = exam_bank_service.get_questions(bank["id"], mode="exam", limit=100)
        counts = {}
        for item in result["list"]:
            counts[item["question_type"]] = counts.get(item["question_type"], 0) + 1

        self.assertEqual(len(result["list"]), 100)
        self.assertEqual(counts, {"single": 50, "multi": 30, "judge": 20})

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

        self.assertEqual(result["summary"]["seenCount"], 3)
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

    def test_exam_record_detail_returns_correct_question_fields(self):
        """Item 4/11: get_exam_record_detail 应使用真实字段名，返回完整的题干、选项、答案"""
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
                    "测试生", "男", "本科", "110101199001011237", "13800138003",
                    "场(厂)内专用机动车辆作业", "叉车司机", "N1",
                    "special_equipment", "reviewed", "detail-openid",
                    self.get_project_id("叉车司机"),
                ),
            )
            # 获取题目真实的数据库 ID
            q_row = conn.execute("SELECT id FROM exam_questions WHERE bank_id = ?", (bank["id"],)).fetchone()
        real_qid = str(q_row["id"])

        result = exam_bank_service.save_exam_record("detail-openid", bank["id"], {
            "score": 100,
            "total": 1,
            "correctCount": 1,
            "durationSeconds": 60,
            "passed": True,
            "answers": {real_qid: ["B"]},
            "submitId": "test-detail-submit-1",
        })
        self.assertTrue(result["success"])

        detail = exam_bank_service.get_exam_record_detail("detail-openid", result["id"], is_admin=False)
        self.assertTrue(detail["success"])
        self.assertEqual(detail["record"]["score"], 100)
        self.assertEqual(len(detail["questions"]), 1)

        q = detail["questions"][0]
        self.assertEqual(q["question"], "1+1=?")
        self.assertIsInstance(q["options"], dict)
        self.assertIn("A", q["options"])
        self.assertEqual(q["answer"], ["B"])
        self.assertEqual(detail["answers"][real_qid], ["B"])

    def test_exam_record_detail_respects_question_order(self):
        """Item 1/11: 按 question_order 而非 answers.keys() 顺序排列"""
        questions = [make_question(201, "第一题"), make_question(202, "第二题"), make_question(203, "第三题")]
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(questions, ensure_ascii=False).encode("utf-8")),
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
                    "测试生2", "女", "本科", "110101199001011238", "13800138004",
                    "场(厂)内专用机动车辆作业", "叉车司机", "N1",
                    "special_equipment", "reviewed", "order-openid",
                    self.get_project_id("叉车司机"),
                ),
            )
            qids = [str(r["id"]) for r in conn.execute(
                "SELECT id FROM exam_questions WHERE bank_id = ? ORDER BY id",
                (bank["id"],)
            ).fetchall()]

        # 提交时传递一个与自然顺序不同的 question_order（反转）
        reversed_order = list(reversed(qids))
        result = exam_bank_service.save_exam_record("order-openid", bank["id"], {
            "score": 100, "total": 3, "correctCount": 3, "durationSeconds": 60, "passed": True,
            "answers": {qid: ["B"] for qid in qids},
            "questionOrder": [int(qid) for qid in reversed_order],
            "submitId": "test-order-submit-1",
        })

        detail = exam_bank_service.get_exam_record_detail("order-openid", result["id"], is_admin=False)
        returned_qids = [str(q["id"]) for q in detail["questions"]]
        self.assertEqual(returned_qids, reversed_order)

    def test_exam_record_detail_raises_permission_error_for_wrong_user(self):
        """Item 2/11: openid 不匹配时应抛出 PermissionError 而非 ValueError"""
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        result = exam_bank_service.save_exam_record("owner-openid", bank["id"], {
            "score": 50, "total": 1, "correctCount": 0, "durationSeconds": 30, "passed": False,
            "answers": {"1": ["A"]},
        })
        with self.assertRaises(PermissionError):
            exam_bank_service.get_exam_record_detail("other-openid", result["id"])

    def test_exam_history_supports_pagination(self):
        """Item 8/11: get_exam_history 应支持 limit/offset 分页"""
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        for i in range(5):
            exam_bank_service.save_exam_record("page-openid", bank["id"], {
                "score": 50 + i * 10, "total": 1, "correctCount": 0, "durationSeconds": 30, "passed": False,
                "answers": {"1": ["A"]},
            })

        full = exam_bank_service.get_exam_history("page-openid", bank["id"])
        self.assertEqual(len(full["list"]), 5)

        page1 = exam_bank_service.get_exam_history("page-openid", bank["id"], limit=2, offset=0)
        self.assertEqual(len(page1["list"]), 2)

        page2 = exam_bank_service.get_exam_history("page-openid", bank["id"], limit=2, offset=2)
        self.assertEqual(len(page2["list"]), 2)

        page3 = exam_bank_service.get_exam_history("page-openid", bank["id"], limit=2, offset=4)
        self.assertEqual(len(page3["list"]), 1)

    def test_summary_includes_exam_count_and_best_score(self):
        """Item 5/11: _format_summary_bank 应返回 examCount 和 bestScore"""
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        exam_bank_service.save_exam_record("admin-openid", bank["id"], {
            "score": 70, "total": 1, "correctCount": 0, "durationSeconds": 30, "passed": False,
            "answers": {"1": ["A"]},
        })
        exam_bank_service.save_exam_record("admin-openid", bank["id"], {
            "score": 92, "total": 1, "correctCount": 1, "durationSeconds": 30, "passed": True,
            "answers": {"1": ["B"]},
        })

        summary = exam_bank_service.get_practice_summary("admin-openid", is_admin=True)
        bank_data = summary["banks"][0]
        self.assertEqual(bank_data["questionState"]["examCount"], 2)
        self.assertEqual(bank_data["questionState"]["bestScore"], 92)

    def test_batch_states_action_merge_preserves_answer_over_seen(self):
        """Item 3/11: 同批内先 answer 再 seen 时，action 不应被覆盖为 seen"""
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps([
                make_question(301, "第一题"),
            ], ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        with get_db_connection() as conn:
            qid = conn.execute(
                "SELECT id FROM exam_questions WHERE bank_id = ?", (bank["id"],)
            ).fetchone()["id"]

        # 同批中先 answer 再 seen
        exam_bank_service.save_batch_question_states("student-openid", bank["id"], {
            "mode": "practice",
            "states": [
                {"questionId": qid, "action": "answer", "isCorrect": True, "answer": ["B"]},
                {"questionId": qid, "action": "seen"},
            ]
        })

        with get_db_connection() as conn:
            state = conn.execute(
                "SELECT status, answer_count FROM mini_question_states WHERE openid = ? AND bank_id = ? AND question_id = ?",
                ("student-openid", bank["id"], qid),
            ).fetchone()
        self.assertEqual(state["status"], "mastered")
        self.assertEqual(state["answer_count"], 1)

        # 同时验证 practice progress 已写入（action 为 answer 时才写进度）
        with get_db_connection() as conn:
            progress = conn.execute(
                "SELECT * FROM mini_practice_progress WHERE openid = ? AND bank_id = ? AND mode = ?",
                ("student-openid", bank["id"], "practice"),
            ).fetchone()
        self.assertIsNotNone(progress)
        self.assertEqual(progress["last_question_id"], qid)

    def test_save_exam_record_deduplicates_by_submit_id(self):
        """Item 4: 相同 submit_id 重复提交应返回 duplicate 且只产生一条记录"""
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        payload = {
            "score": 80, "total": 1, "correctCount": 1,
            "durationSeconds": 60, "passed": True,
            "answers": {"1": ["B"]},
            "submitId": "dedup-test-001",
        }
        first = exam_bank_service.save_exam_record("dedup-openid", bank["id"], payload)
        self.assertTrue(first["success"])
        self.assertNotIn("duplicate", first)

        second = exam_bank_service.save_exam_record("dedup-openid", bank["id"], payload)
        self.assertTrue(second["success"])
        self.assertTrue(second.get("duplicate"))
        self.assertEqual(second["id"], first["id"])

        with get_db_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM mini_exam_records WHERE submit_id = ?",
                ("dedup-test-001",)
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_save_exam_record_deduplicates_by_content_within_window(self):
        """Item 4: 无 submit_id 时，10 秒内内容完全相同应命中内容兜底幂等"""
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        payload = {
            "score": 60, "total": 1, "correctCount": 0,
            "durationSeconds": 30, "passed": False,
            "answers": {"1": ["A"]},
            # 不传 submitId
        }
        first = exam_bank_service.save_exam_record("content-dedup-openid", bank["id"], payload)
        self.assertTrue(first["success"])

        second = exam_bank_service.save_exam_record("content-dedup-openid", bank["id"], payload)
        self.assertTrue(second["success"])
        self.assertTrue(second.get("duplicate"))
        self.assertEqual(second["id"], first["id"])

    def test_save_exam_record_integrity_error_fallback(self):
        """Item 4: IntegrityError 竞态分支——模拟并发插入后的兜底"""
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(SAMPLE_QUESTIONS, ensure_ascii=False).encode("utf-8")),
            "N1_叉车司机.json",
            self.get_project_id("叉车司机"),
        )
        # 先正常插入一条
        first = exam_bank_service.save_exam_record("integrity-openid", bank["id"], {
            "score": 75, "total": 1, "correctCount": 1,
            "durationSeconds": 45, "passed": False,
            "answers": {"1": ["B"]},
            "submitId": "integrity-race-001",
        })
        self.assertTrue(first["success"])

        # 手动绕过前置查询直接插入同 submit_id，模拟竞态
        with get_db_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO mini_exam_records (openid, bank_id, score, total, correct_count, "
                    "duration_seconds, passed, answers_json, submit_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("integrity-openid", bank["id"], 75, 1, 1, 45, 0, '{"1":["B"]}', "integrity-race-001")
                )
                self.fail("应当抛出 IntegrityError")
            except sqlite3.IntegrityError:
                pass  # 预期行为：唯一索引阻止重复

    def test_exam_record_detail_falls_back_to_answer_keys_without_order(self):
        """Item 5: 旧记录无 question_order 时应退化到 answers.keys() 顺序"""
        questions = [make_question(401, "第一题"), make_question(402, "第二题")]
        bank = exam_bank_service.import_exam_bank(
            io.BytesIO(json.dumps(questions, ensure_ascii=False).encode("utf-8")),
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
                    "测试生3", "男", "本科", "110101199001011239", "13800138005",
                    "场(厂)内专用机动车辆作业", "叉车司机", "N1",
                    "special_equipment", "reviewed", "fallback-openid",
                    self.get_project_id("叉车司机"),
                ),
            )
            qids = [str(r["id"]) for r in conn.execute(
                "SELECT id FROM exam_questions WHERE bank_id = ? ORDER BY id",
                (bank["id"],)
            ).fetchall()]

        # 不传 questionOrder，模拟旧版前端提交
        result = exam_bank_service.save_exam_record("fallback-openid", bank["id"], {
            "score": 100, "total": 2, "correctCount": 2,
            "durationSeconds": 30, "passed": True,
            "answers": {qids[0]: ["B"], qids[1]: ["B"]},
            "submitId": "fallback-test-001",
        })

        # 确认 question_order 列为 NULL
        with get_db_connection() as conn:
            rec = conn.execute(
                "SELECT question_order FROM mini_exam_records WHERE id = ?",
                (result["id"],)
            ).fetchone()
        self.assertIsNone(rec["question_order"])

        detail = exam_bank_service.get_exam_record_detail(
            "fallback-openid", result["id"], is_admin=False
        )
        returned_qids = [str(q["id"]) for q in detail["questions"]]
        # 退化路径：顺序应与 answers dict 的 keys() 顺序一致
        self.assertEqual(returned_qids, list({qids[0]: ["B"], qids[1]: ["B"]}.keys()))
        self.assertEqual(len(detail["questions"]), 2)


if __name__ == "__main__":
    unittest.main()
