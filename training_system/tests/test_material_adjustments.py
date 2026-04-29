import json
import logging
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask, g, session


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from models import student as student_model
from routes import student_routes
from utils.logger import SourceContextFilter
from utils.auth import resolve_web_admin_name


class MaterialAdjustmentModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "students.db")
        student_model.init_db(self.db_path)
        self.app = Flask(__name__)
        self.app.config["DATABASE"] = self.db_path

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_db_creates_material_adjustments_table(self):
        conn = sqlite3.connect(self.db_path)
        try:
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(material_adjustments)").fetchall()
            }
        finally:
            conn.close()

        self.assertIn("student_id", columns)
        self.assertIn("material_type", columns)
        self.assertIn("adjustments_json", columns)
        self.assertIn("points_json", columns)
        self.assertIn("operator_name", columns)

    def test_save_material_adjustment_upserts_latest_adjustment(self):
        with self.app.app_context():
            student_model.save_material_adjustment(
                7,
                "photo",
                {"rotate": 90},
                {"points": [{"x": 1, "y": 2}]},
                operator_name="程超",
                operator_source="小程序",
            )
            student_model.save_material_adjustment(
                7,
                "photo",
                {"rotate": 180},
                {"points": [{"x": 3, "y": 4}]},
                operator_name="单利亚",
                operator_source="网页端",
            )
            adjustments = student_model.get_material_adjustments(7)

        self.assertEqual(adjustments["photo"]["adjustments"], {"rotate": 180})
        self.assertEqual(adjustments["photo"]["points"], {"points": [{"x": 3, "y": 4}]})
        self.assertEqual(adjustments["photo"]["operator_name"], "单利亚")
        self.assertEqual(adjustments["photo"]["operator_source"], "网页端")


class MaterialTypeNormalizationTests(unittest.TestCase):
    def test_material_type_aliases_normalize_to_canonical_values(self):
        self.assertEqual(student_routes.normalize_material_type("personal_photo"), "photo")
        self.assertEqual(student_routes.normalize_material_type("idcard"), "id_card")
        self.assertEqual(student_routes.normalize_material_type("hukou_book"), "hukou")
        self.assertEqual(student_routes.normalize_material_type("education"), "diploma")
        self.assertEqual(student_routes.normalize_material_type("体检表"), "training_form")
        self.assertEqual(student_routes.normalize_material_type("unknown"), "")


class LogActorContextTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test"

    def test_web_session_actor_name_is_added_to_every_log_record(self):
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", (), None)

        with self.app.test_request_context("/admin"):
            session["auth_verified"] = True
            session["auth_user"] = "admin"
            SourceContextFilter().filter(record)

        self.assertEqual(record.sys_source, "网页端")
        self.assertEqual(record.actor_name, "单利亚(admin)")

    def test_web_admin_display_name_can_be_configured(self):
        with patch.dict(os.environ, {"TRAINING_SYSTEM_ADMIN_DISPLAY_NAMES": "admin=程超"}):
            self.assertEqual(resolve_web_admin_name("admin"), "程超(admin)")

    def test_mini_actor_name_is_added_to_every_log_record(self):
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", (), None)

        with self.app.test_request_context("/api/students/1/approve"):
            g.mini_user = {"openid": "oQRQz3VglMF63fWRtTCX8gbl21jo", "is_admin": True}
            SourceContextFilter().filter(record)

        self.assertEqual(record.sys_source, "小程序")
        self.assertIn("程超", record.actor_name)


if __name__ == "__main__":
    unittest.main()
