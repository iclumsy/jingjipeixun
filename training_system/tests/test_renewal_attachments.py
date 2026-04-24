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

from routes import student_routes
from models import student as student_model
from services import image_service


class RenewalAttachmentRuleTests(unittest.TestCase):
    def test_special_equipment_new_exam_keeps_existing_required_files(self):
        self.assertEqual(
            student_routes.get_required_attachments("special_equipment", "new_exam"),
            [
                "photo",
                "diploma",
                "id_card_front",
                "id_card_back",
                "hukou_residence",
                "hukou_personal",
            ],
        )

    def test_special_equipment_renewal_requires_photo_and_certificate_pages(self):
        self.assertEqual(
            student_routes.get_required_attachments("special_equipment", "renewal"),
            [
                "photo",
                "certificate_info_page",
                "certificate_records_page",
            ],
        )

    def test_renewal_certificate_labels_are_human_readable(self):
        self.assertEqual(
            image_service.get_attachment_label("certificate_info_page"),
            "原证件说明和个人信息页",
        )
        self.assertEqual(
            image_service.get_attachment_label("certificate_records_page"),
            "原证件作业项目和聘用记录页",
        )


class RenewalPersistenceTests(unittest.TestCase):
    def build_test_app(self, tmp_dir, db_path, students_dir):
        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            DATABASE=db_path,
            BASE_DIR=tmp_dir,
            STUDENTS_FOLDER=students_dir,
        )
        app.register_blueprint(student_routes.student_bp)
        student_routes.broadcast_new_student_to_admins = lambda **kwargs: None
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

    def build_renewal_payload(self, project_id, files):
        return {
            "name": "张三",
            "gender": "男",
            "education": "高中或同等学历",
            "id_card": "110101199001011234",
            "phone": "13800138000",
            "company": "测试单位",
            "company_address": "测试地址",
            "training_project_id": project_id,
            "application_type": "renewal",
            "files": files,
        }

    def test_init_db_adds_application_type_and_renewal_attachment_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "students.db")

            student_model.init_db(db_path)

            conn = sqlite3.connect(db_path)
            try:
                columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(students)").fetchall()
                }
            finally:
                conn.close()

        self.assertIn("application_type", columns)
        self.assertIn("certificate_info_page_path", columns)
        self.assertIn("certificate_records_page_path", columns)

    def test_create_student_route_accepts_special_equipment_renewal_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "students.db")
            students_dir = os.path.join(tmp_dir, "students")
            os.makedirs(os.path.join(students_dir, "tmp"), exist_ok=True)
            student_model.init_db(db_path)

            project = self.get_first_special_equipment_project(db_path)

            self.assertIsNotNone(project)

            tmp_files = self.write_tmp_files(
                tmp_dir,
                ["photo", "certificate_info_page", "certificate_records_page"],
            )
            app = self.build_test_app(tmp_dir, db_path, students_dir)
            payload = self.build_renewal_payload(project["id"], tmp_files)

            response = app.test_client().post("/api/students", json=payload)

            self.assertEqual(response.status_code, 201, response.get_json())
            student_id = response.get_json()["id"]

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT application_type, photo_path, certificate_info_page_path, "
                    "certificate_records_page_path, diploma_path "
                    "FROM students WHERE id = ?",
                    (student_id,),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(row["application_type"], "renewal")
        self.assertTrue(row["photo_path"])
        self.assertTrue(row["certificate_info_page_path"])
        self.assertTrue(row["certificate_records_page_path"])
        self.assertFalse(row["diploma_path"])

    def test_update_student_route_preserves_renewal_attachment_rules(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "students.db")
            students_dir = os.path.join(tmp_dir, "students")
            os.makedirs(os.path.join(students_dir, "tmp"), exist_ok=True)
            student_model.init_db(db_path)
            project = self.get_first_special_equipment_project(db_path)
            self.assertIsNotNone(project)

            app = self.build_test_app(tmp_dir, db_path, students_dir)
            client = app.test_client()
            create_files = self.write_tmp_files(
                tmp_dir,
                ["photo", "certificate_info_page", "certificate_records_page"],
            )
            create_response = client.post(
                "/api/students",
                json=self.build_renewal_payload(project["id"], create_files),
            )
            self.assertEqual(create_response.status_code, 201, create_response.get_json())
            student_id = create_response.get_json()["id"]

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
            finally:
                conn.close()

            update_payload = self.build_renewal_payload(
                project["id"],
                {
                    "photo": row["photo_path"],
                    "certificate_info_page": row["certificate_info_page_path"],
                    "certificate_records_page": row["certificate_records_page_path"],
                },
            )
            update_payload["phone"] = "13900139000"

            response = client.put(f"/api/students/{student_id}", json=update_payload)

            self.assertEqual(response.status_code, 200, response.get_json())
            data = response.get_json()
            self.assertEqual(data["application_type"], "renewal")
            self.assertEqual(data["phone"], "13900139000")

    def test_delete_student_files_includes_renewal_certificate_paths(self):
        deleted = []
        original_delete = image_service.storage_service.delete_file
        image_service.storage_service.delete_file = lambda key: deleted.append(key) or True
        try:
            image_service.delete_student_files(
                {
                    "certificate_info_page_path": "students/a/info.jpg",
                    "certificate_records_page_path": "students/a/records.jpg",
                },
                "/unused",
            )
        finally:
            image_service.storage_service.delete_file = original_delete

        self.assertIn("students/a/info.jpg", deleted)
        self.assertIn("students/a/records.jpg", deleted)


if __name__ == "__main__":
    unittest.main()
