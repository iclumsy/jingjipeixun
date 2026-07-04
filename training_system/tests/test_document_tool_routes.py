import io
import os
import sys
import tempfile
import unittest
import zipfile

from PIL import Image


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from app import create_app
from models.student import init_db


def make_image_bytes(color=(240, 240, 240), border=(20, 20, 20), size=(640, 420)):
    image = Image.new("RGB", size, color)
    pixels = image.load()
    for x in range(size[0]):
        for y in range(size[1]):
            if x < 8 or y < 8 or x >= size[0] - 8 or y >= size[1] - 8:
                pixels[x, y] = border
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=92)
    buffer.seek(0)
    return buffer


class DocumentToolRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_env = os.environ.get("TRAINING_SYSTEM_ENV_FILE")
        self.env_path = os.path.join(self.tmp.name, ".env")
        os.environ["TRAINING_SYSTEM_ENV_FILE"] = self.env_path

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["BASE_DIR"] = self.tmp.name
        self.app.config["STUDENTS_FOLDER"] = os.path.join(self.tmp.name, "students")
        self.app.config["DATABASE"] = os.path.join(self.tmp.name, "students.db")
        os.makedirs(self.app.config["STUDENTS_FOLDER"], exist_ok=True)
        with self.app.app_context():
            init_db(self.app.config["DATABASE"])
        self.client = self.app.test_client()

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("TRAINING_SYSTEM_ENV_FILE", None)
        else:
            os.environ["TRAINING_SYSTEM_ENV_FILE"] = self.old_env
        self.tmp.cleanup()

    def login_web_admin(self, client=None):
        target = client or self.client
        with target.session_transaction() as sess:
            sess["auth_verified"] = True
            sess["auth_user"] = "admin"

    def create_id_card_task(self, client=None):
        target = client or self.client
        return target.post(
            "/api/admin/document_tools/tasks",
            data={
                "document_type": "id_card",
                "id_card_front": (make_image_bytes(), "front.jpg"),
                "id_card_back": (make_image_bytes(color=(248, 248, 248)), "back.jpg"),
            },
            content_type="multipart/form-data",
        )

    def create_hukou_task(self, client=None):
        target = client or self.client
        return target.post(
            "/api/admin/document_tools/tasks",
            data={
                "document_type": "hukou",
                "hukou_residence": (make_image_bytes(size=(500, 720)), "home.jpg"),
                "hukou_personal": (make_image_bytes(color=(248, 248, 248), size=(500, 720)), "personal.jpg"),
            },
            content_type="multipart/form-data",
        )

    def test_admin_page_renders_for_web_admin(self):
        self.login_web_admin()

        response = self.client.get("/admin/document-tools")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("证件处理", html)
        self.assertIn('id="resultActions"', html)
        self.assertIn('id="openAdjustBtn"', html)
        self.assertNotIn('id="adjustPanel"', html)
        self.assertNotIn('id="cropModal"', html)

    def test_uploading_id_card_images_creates_session_scoped_outputs(self):
        self.login_web_admin()

        response = self.create_id_card_task()

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["task"]["document_type"], "id_card")
        self.assertEqual(len(data["task"]["outputs"]), 1)
        output = data["task"]["outputs"][0]
        self.assertTrue(output["filename"].endswith("-身份证.jpg"))

        preview = self.client.get(output["url"])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.mimetype, "image/jpeg")

    def test_uploading_hukou_images_creates_outputs(self):
        self.login_web_admin()

        response = self.create_hukou_task()

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["task"]["document_type"], "hukou")
        self.assertTrue(data["task"]["outputs"][0]["filename"].endswith("-户口本.jpg"))

    def test_document_tool_api_requires_web_admin_session(self):
        response = self.client.post(
            "/api/admin/document_tools/tasks",
            data={
                "document_type": "id_card",
                "id_card_front": (make_image_bytes(), "front.jpg"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 401)

    def test_task_files_are_not_accessible_from_another_admin_session(self):
        self.login_web_admin()
        data = self.create_id_card_task().get_json()
        output_url = data["task"]["outputs"][0]["url"]

        other_client = self.app.test_client()
        self.login_web_admin(other_client)

        response = other_client.get(output_url)

        self.assertEqual(response.status_code, 404)

    def test_outputs_can_be_downloaded_as_zip(self):
        self.login_web_admin()
        data = self.create_id_card_task().get_json()
        zip_url = data["task"]["zip_url"]

        response = self.client.get(zip_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
            names = zf.namelist()
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].endswith("-身份证.jpg"))

    def test_logout_removes_current_session_document_tool_files(self):
        self.login_web_admin()
        data = self.create_id_card_task().get_json()
        task_id = data["task"]["id"]

        session_root = os.path.join(
            self.app.config["STUDENTS_FOLDER"],
            "tmp",
            "document_tools",
        )
        self.assertTrue(os.path.exists(session_root))

        self.client.get("/auth/logout")

        remaining = []
        for root, _dirs, files in os.walk(session_root):
            remaining.extend(os.path.join(root, name) for name in files if task_id in root)
        self.assertEqual(remaining, [])


if __name__ == "__main__":
    unittest.main()
