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
from utils.miniprogram_auth import sign_mini_token


class OpenidUpdateRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "students.db")
        self.students_dir = os.path.join(self.tmp_dir.name, "students")
        os.makedirs(self.students_dir, exist_ok=True)
        student_model.init_db(self.db_path)

        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"
        self.app.config["SECRET_KEY"] = "test-secret"
        self.app.config["DATABASE"] = self.db_path
        self.app.config["DATABASE_PATH"] = self.db_path
        self.app.config["BASE_DIR"] = self.tmp_dir.name
        self.app.config["STUDENTS_DIR"] = self.students_dir
        self.app.config["TESTING"] = True
        self.app.register_blueprint(student_routes.student_bp)

        from flask import g, request, session
        from utils.miniprogram_auth import extract_mini_token, verify_mini_token

        @self.app.before_request
        def auth_middleware():
            g.mini_user = None
            if session.get("auth_verified") is True:
                return None
            token = extract_mini_token(request)
            if token:
                g.mini_user = verify_mini_token(self.app.config["SECRET_KEY"], token)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def insert_student(self, name="程明", id_card="140101199001010011", phone="13800138000", submitter_openid="", exam_project="叉车司机"):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO students (
                    name, gender, education, id_card, phone, job_category, exam_project,
                    project_code, training_type, status, submitter_openid, photo_path, diploma_path,
                    id_card_front_path, id_card_back_path, hukou_residence_path, hukou_personal_path
                ) VALUES (?, '男', '高中', ?, ?, '特种设备', ?, 'N1', 'special_equipment', 'unreviewed', ?, '1', '1', '1', '1', '1', '1')
                """,
                (name, id_card, phone, exam_project, submitter_openid),
            )
            student_id = cursor.lastrowid
            conn.commit()
            return student_id
        finally:
            conn.close()

    def test_web_admin_can_update_openid_via_put(self):
        student_id = self.insert_student(submitter_openid="")

        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess["auth_verified"] = True
                sess["auth_user"] = "admin"

            response = client.put(
                f"/api/students/{student_id}",
                json={"submitter_openid": "oQRQz3ZDNo2ptLcKYQO608Q3wyx8"}
            )
            self.assertEqual(response.status_code, 200, response.get_json())
            data = response.get_json()
            self.assertEqual(data["submitter_openid"], "oQRQz3ZDNo2ptLcKYQO608Q3wyx8")

    def test_mini_user_cannot_modify_submitter_openid_via_put(self):
        original_openid = "oQRQz3_original_user_12345"
        student_id = self.insert_student(submitter_openid=original_openid)

        token = sign_mini_token(self.app.config["SECRET_KEY"], original_openid, is_admin=False)
        with self.app.test_client() as client:
            response = client.put(
                f"/api/students/{student_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"phone": "13900139000", "submitter_openid": "oQRQz3_hacker_forged_openid"}
            )
            self.assertEqual(response.status_code, 200, response.get_json())
            data = response.get_json()
            # The forged openid should be stripped/ignored
            self.assertEqual(data["submitter_openid"], original_openid)

    def test_update_openid_endpoint_updates_single_record(self):
        student_id = self.insert_student(submitter_openid="")

        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess["auth_verified"] = True
                sess["auth_user"] = "admin"

            response = client.post(
                f"/api/students/{student_id}/update_openid",
                json={"openid": "oQRQz3ZDNo2ptLcKYQO608Q3wyx8", "sync_all": False}
            )
            self.assertEqual(response.status_code, 200, response.get_json())
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["updated_count"], 1)
            self.assertEqual(data["student"]["submitter_openid"], "oQRQz3ZDNo2ptLcKYQO608Q3wyx8")

            # Check operation logs
            logs_res = client.get(f"/api/students/{student_id}/operation_logs")
            self.assertEqual(logs_res.status_code, 200)
            logs = logs_res.get_json()["logs"]
            self.assertTrue(any(l["action"] == "update_openid" for l in logs))

    def test_update_openid_endpoint_sync_all_updates_multiple_registrations(self):
        # Insert 2 registrations for 程明
        id1 = self.insert_student(name="程明", id_card="140101199001010011", exam_project="叉车司机", submitter_openid="")
        id2 = self.insert_student(name="程明", id_card="140101199001010011", exam_project="起重机指挥", submitter_openid="")
        # Insert another unrelated student
        id3 = self.insert_student(name="李四", id_card="140101199002020022", exam_project="叉车司机", submitter_openid="")

        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess["auth_verified"] = True
                sess["auth_user"] = "admin"

            response = client.post(
                f"/api/students/{id1}/update_openid",
                json={"openid": "oQRQz3ZDNo2ptLcKYQO608Q3wyx8", "sync_all": True}
            )
            self.assertEqual(response.status_code, 200, response.get_json())
            data = response.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["updated_count"], 2)

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                r1 = conn.execute("SELECT submitter_openid FROM students WHERE id = ?", (id1,)).fetchone()
                r2 = conn.execute("SELECT submitter_openid FROM students WHERE id = ?", (id2,)).fetchone()
                r3 = conn.execute("SELECT submitter_openid FROM students WHERE id = ?", (id3,)).fetchone()
                self.assertEqual(r1["submitter_openid"], "oQRQz3ZDNo2ptLcKYQO608Q3wyx8")
                self.assertEqual(r2["submitter_openid"], "oQRQz3ZDNo2ptLcKYQO608Q3wyx8")
                self.assertEqual(r3["submitter_openid"], "")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
