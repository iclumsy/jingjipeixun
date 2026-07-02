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
from utils.miniprogram_auth import sign_mini_token


class LearningStatsRouteTests(unittest.TestCase):
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
                                {"name": "起重机指挥", "code": "Q8", "is_active": 1},
                            ],
                        }
                    ],
                },
                "special_operation": {
                    "name": "特种作业",
                    "job_categories": [],
                },
            }, fp, ensure_ascii=False)

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["DATABASE"] = os.path.join(self.tmp.name, "students.db")
        with self.app.app_context():
            init_db(self.app.config["DATABASE"])
            
            # Setup active projects in the training_projects table
            with get_db_connection() as conn:
                # Clear default and insert our custom test projects
                conn.execute("DELETE FROM training_projects")
                conn.execute(
                    "INSERT INTO training_projects (training_type, job_category, exam_project, project_code, is_active) VALUES (?, ?, ?, ?, ?)",
                    ("special_equipment", "场(厂)内专用机动车辆作业", "叉车司机", "N1", 1)
                )
                conn.execute(
                    "INSERT INTO training_projects (training_type, job_category, exam_project, project_code, is_active) VALUES (?, ?, ?, ?, ?)",
                    ("special_equipment", "场(厂)内专用机动车辆作业", "起重机指挥", "Q8", 1)
                )
                # Inactive project
                conn.execute(
                    "INSERT INTO training_projects (training_type, job_category, exam_project, project_code, is_active) VALUES (?, ?, ?, ?, ?)",
                    ("special_equipment", "场(厂)内专用机动车辆作业", "电梯安全管理", "T3", 0)
                )
                conn.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("TRAINING_SYSTEM_ENV_FILE", None)
        else:
            os.environ["TRAINING_SYSTEM_ENV_FILE"] = self.old_env
        self.tmp.cleanup()

    def mini_headers(self, openid="admin-openid", is_admin=True):
        token = sign_mini_token(self.app.config["SECRET_KEY"], openid, is_admin=is_admin)
        return {"Authorization": f"Bearer {token}"}

    def create_student(self, name, exam_project, project_code, openid="student-openid", status="reviewed"):
        with self.app.app_context():
            with get_db_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO students (
                        name, gender, education, id_card, phone, job_category,
                        exam_project, project_code, training_type, status,
                        submitter_openid
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name, "男", "高中或同等学历", "110101199001011234", "13800138000",
                        "场(厂)内专用机动车辆作业", exam_project, project_code,
                        "special_equipment", status, openid,
                    ),
                )
                conn.commit()

    def test_learning_stats_without_project_filter(self):
        self.create_student("Student A", "叉车司机", "N1", "openid-a")
        self.create_student("Student B", "起重机指挥", "Q8", "openid-b")

        headers = self.mini_headers(is_admin=True)
        response = self.client.get("/api/miniprogram/admin/learning_stats", headers=headers)
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        self.assertTrue(data["success"])
        # Should return both students (order by id desc)
        students = [item["name"] for item in data["list"]]
        self.assertIn("Student A", students)
        self.assertIn("Student B", students)
        
        # Should return all active projects
        self.assertEqual(data["projects"], ["叉车司机", "起重机指挥"])

    def test_learning_stats_with_project_filter(self):
        self.create_student("Student A", "叉车司机", "N1", "openid-a")
        self.create_student("Student B", "起重机指挥", "Q8", "openid-b")

        headers = self.mini_headers(is_admin=True)
        response = self.client.get("/api/miniprogram/admin/learning_stats?project=叉车司机", headers=headers)
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        self.assertTrue(data["success"])
        
        # Should only return Student A
        students = [item["name"] for item in data["list"]]
        self.assertEqual(students, ["Student A"])
        
        # Project list should still contain all active projects
        self.assertEqual(data["projects"], ["叉车司机", "起重机指挥"])


if __name__ == "__main__":
    unittest.main()
