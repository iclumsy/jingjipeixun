import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from flask import Flask


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from routes.sxtsks_routes import sxtsks_bp


class FakeSxtsksClient:
    def __init__(self):
        self.calls = []

    def download_application_form(self, bmid):
        self.calls.append(bmid)
        html = b"<html><head></head><body><table></table></body></html>"
        return html, "text/html", "platform.html"


class FakeWeasyHtml:
    def __init__(self, string):
        self.string = string

    def write_pdf(self):
        return b"%PDF-fresh"


class SxtsksApplicationFormRouteTests(unittest.TestCase):
    def test_application_form_download_ignores_local_pdf_cache(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = os.path.join(tmp_dir, "training_system")
            os.makedirs(base_dir, exist_ok=True)

            student = {
                "id": 3,
                "id_card": "140101199001010011",
                "name": "张三",
                "company": "测试公司",
                "exam_project": "叉车司机",
                "project_code": "N1",
            }
            output_dir = os.path.join(
                base_dir,
                "students",
                "特种设备-测试公司-张三",
                "140101199001010011-张三-报名材料",
            )
            os.makedirs(output_dir, exist_ok=True)
            cached_path = os.path.join(output_dir, "140101199001010011-张三-报名申请表.pdf")
            with open(cached_path, "wb") as cached_file:
                cached_file.write(b"%PDF-stale")

            app = Flask(__name__)
            app.config["BASE_DIR"] = base_dir
            app.register_blueprint(sxtsks_bp)
            fake_client = FakeSxtsksClient()
            fake_weasyprint = types.SimpleNamespace(HTML=FakeWeasyHtml)

            with patch("models.student.get_student_by_id", return_value=student), \
                    patch("routes.sxtsks_routes._get_client", return_value=fake_client), \
                    patch.dict(sys.modules, {"weasyprint": fake_weasyprint}):
                response = app.test_client().get("/api/sxtsks/form/9?student_id=3")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"%PDF-fresh")
            self.assertEqual(fake_client.calls, [9])
            self.assertIn("no-store", response.headers.get("Cache-Control", ""))
            with open(cached_path, "rb") as cached_file:
                self.assertEqual(cached_file.read(), b"%PDF-stale")


if __name__ == "__main__":
    unittest.main()
