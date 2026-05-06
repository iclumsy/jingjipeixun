import os
import sys
import tempfile
import unittest
from unittest import mock


TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from services.sxtsks_service import EDUCATION_MAP, EDUCATION_RANK, SxtsksClient


class FakeResponse:
    def __init__(self, text="", status_code=200, url="http://www.sxtsks.com/test"):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.content = text.encode("utf-8")


class SxtsksSubmitTests(unittest.TestCase):
    def build_student(self):
        return {
            "name": "张三",
            "gender": "男",
            "id_card": "110101199001011234",
            "education": "中专或同等学历",
            "phone": "13800138000",
            "company": "测试单位",
            "company_address": "测试地址",
            "project_code": "N1",
        }

    def run_submit_with_final_response(self, final_response, student_overrides=None):
        client = SxtsksClient()
        client.logged_in = True
        client.userid = "13253"
        query_must_response = FakeResponse('{"code":"0"}')
        captured = {}
        student = self.build_student()
        if student_overrides:
            student.update(student_overrides)

        def post_side_effect(url, **kwargs):
            if url.endswith("/queryKsjgIsMust.do"):
                return query_must_response
            if url.endswith("/dwbm_savekzbmb.do"):
                captured["save_kwargs"] = kwargs
                return final_response
            raise AssertionError(f"unexpected POST {url}")

        with tempfile.NamedTemporaryFile(suffix=".jpg") as photo:
            photo.write(b"photo-bytes")
            photo.flush()
            client.session.post = mock.Mock(side_effect=post_side_effect)

            with mock.patch.object(client, "_ensure_login", return_value=None), \
                    mock.patch.object(client, "upload_photo", return_value="tmp/photo.jpg"), \
                    mock.patch.object(client, "_get_form_token", return_value="form-token"), \
                    mock.patch.object(client, "_run_pre_checks", return_value={
                        "verCode": "abcd",
                        "bmVerriToken": "captcha-token",
                    }), \
                    mock.patch.object(client, "_upload_attachment", return_value=None):
                result = client.submit_registration(student, photo.name)

        return result, captured["save_kwargs"]

    def test_submit_uses_real_student_id_card_and_returns_it(self):
        result, save_kwargs = self.run_submit_with_final_response(
            FakeResponse("保存并上报成功,645199")
        )

        self.assertTrue(result["success"])
        sfzh_parts = [
            value[1]
            for name, value in save_kwargs["files"]
            if name == "sfzh"
        ]
        self.assertEqual(sfzh_parts, ["110101199001011234"])
        self.assertEqual(result["submitted_id_card"], "110101199001011234")

    def test_management_projects_use_management_work_resume(self):
        _, save_kwargs = self.run_submit_with_final_response(
            FakeResponse("保存并上报成功,645199"),
            {
                "exam_project": "电梯安全管理",
                "project_code": "A",
                "education": "高中或同等学历",
            },
        )

        gzjl_parts = [
            value[1]
            for name, value in save_kwargs["files"]
            if name == "gzjl"
        ]
        self.assertEqual(gzjl_parts, ["从事安全管理工作2年以上。"])

    def test_operation_projects_use_operation_work_resume(self):
        _, save_kwargs = self.run_submit_with_final_response(
            FakeResponse("保存并上报成功,645199"),
            {
                "exam_project": "叉车司机",
                "project_code": "N1",
                "education": "初中",
            },
        )

        gzjl_parts = [
            value[1]
            for name, value in save_kwargs["files"]
            if name == "gzjl"
        ]
        self.assertEqual(gzjl_parts, ["从事特种设备工作三个月以上。"])

    def test_project_blocks_education_below_requirement_before_submit(self):
        client = SxtsksClient()
        client.logged_in = True
        student = self.build_student()
        student.update({
            "exam_project": "工业锅炉司炉",
            "project_code": "G1",
            "education": "初中",
        })

        with tempfile.NamedTemporaryFile(suffix=".jpg") as photo:
            photo.write(b"photo-bytes")
            photo.flush()
            client.session.post = mock.Mock(side_effect=AssertionError("should not call platform submit"))
            with mock.patch.object(client, "_ensure_login", return_value=None):
                result = client.submit_registration(student, photo.name)

        self.assertFalse(result["success"])
        self.assertIn("学历要求", result["message"])
        client.session.post.assert_not_called()

    def test_final_save_includes_photo_binary_part(self):
        _, save_kwargs = self.run_submit_with_final_response(
            FakeResponse("保存并上报成功,645199")
        )

        photo_parts = [
            value
            for name, value in save_kwargs["files"]
            if name == "files" and len(value) >= 3
        ]
        self.assertEqual(len(photo_parts), 1)
        self.assertEqual(photo_parts[0][1], b"photo-bytes")

    def test_platform_html_callback_success_is_treated_as_success(self):
        html_response = '''
        <html><script>
        var info = "填报信息保存并上报后，请务必在“我的报名”处点击“申请表打印”下载申请表";
        if (info == "验证码校验失败！") { alert(info); }
        window.parent.dwbm_cellback(info);
        </script></html>
        '''

        result, _ = self.run_submit_with_final_response(FakeResponse(html_response))

        self.assertTrue(result["success"])
        self.assertEqual(result["bmid"], "")


class SxtsksPreCheckTests(unittest.TestCase):
    def test_pre_checks_use_student_education_and_verify_uploaded_portrait(self):
        client = SxtsksClient()
        seen = []

        def fake_get(url, **kwargs):
            seen.append(("GET", url, kwargs))
            return FakeResponse("{}")

        def fake_post(url, **kwargs):
            seen.append(("POST", url, kwargs))
            return FakeResponse('{"code":"0","text":"token"}')

        client.session.get = mock.Mock(side_effect=fake_get)
        client.session.post = mock.Mock(side_effect=fake_post)
        with mock.patch.object(client, "_get_captcha_code", return_value="abcd"):
            client._run_pre_checks("110101199001011234", "1095", "0408")

        whcd_values = [
            call[2]["params"]["whcd"]
            for call in seen
            if call[1].endswith("/dwbm_validateWhcd.do")
        ]
        self.assertEqual(whcd_values, ["0408"])

        portrait_calls = [
            call
            for call in seen
            if call[1].endswith("/wbapplycheckUserPortrait.do")
        ]
        self.assertEqual(len(portrait_calls), 1)
        self.assertEqual(portrait_calls[0][2]["params"], {"bmid": ""})
        self.assertEqual(
            portrait_calls[0][2]["data"],
            {
                "bmlb": "0",
                "jgdm": "140300111",
                "sfz": "110101199001011234",
            },
        )


class SxtsksEducationRuleTests(unittest.TestCase):
    SUPPORTED_SYSTEM_EDUCATION_OPTIONS = {
        "初中",
        "高中或同等学历",
        "中专或同等学历",
        "专科或同等学历",
        "本科或同等学历",
        "研究生及以上",
    }

    def test_education_rank_only_contains_supported_system_options(self):
        self.assertEqual(set(EDUCATION_RANK), self.SUPPORTED_SYSTEM_EDUCATION_OPTIONS)

    def test_education_map_only_contains_supported_system_options(self):
        self.assertEqual(set(EDUCATION_MAP), self.SUPPORTED_SYSTEM_EDUCATION_OPTIONS)


class SxtsksSubmitAndDownloadTests(unittest.TestCase):
    def test_submit_and_download_queries_by_submitted_random_id_card(self):
        client = SxtsksClient()
        client.submit_registration = mock.Mock(return_value={
            "success": True,
            "message": "报名提交成功",
            "bmid": "",
            "submitted_id_card": "140302197508291331",
        })
        client.query_registrations = mock.Mock(return_value=[
            {
                "bmid": "645199",
                "id_card": "140302197508291331",
            }
        ])
        client.download_application_form = mock.Mock(return_value=(
            b"form",
            "application/pdf",
            "申请表-645199.pdf",
        ))

        student = {
            "id_card": "110101199001011234",
            "name": "张三",
        }

        result = client.submit_and_download(student, "/tmp/photo.jpg")

        self.assertTrue(result["success"])
        client.query_registrations.assert_called_once_with(sfzh="140302197508291331")
        client.download_application_form.assert_called_once_with("645199")


if __name__ == "__main__":
    unittest.main()
