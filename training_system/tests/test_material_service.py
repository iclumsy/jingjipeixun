import os
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from services import material_service


class MaterialServiceTests(unittest.TestCase):
    def test_log_collector_builds_summary_counts(self):
        collector = material_service.MaterialGenerationLogger()

        collector.emit(
            "info",
            "global",
            "start",
            "开始生成",
            "开始处理报名材料",
        )
        collector.emit(
            "success",
            "diploma",
            "write_output",
            "学历证书输出成功",
            "已生成学历证书 A4 图",
            details={"output_path": "/tmp/a.jpg"},
        )
        collector.emit(
            "warning",
            "id_card",
            "auto_crop",
            "身份证边缘识别一般",
            "已回退到矩形裁剪",
        )
        collector.emit(
            "error",
            "hukou",
            "write_output",
            "户口本输出失败",
            "未能写出户口本图片",
        )

        summary = collector.build_summary()

        self.assertEqual(summary["success_count"], 1)
        self.assertEqual(summary["warning_count"], 1)
        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["material_count"], 3)
        self.assertEqual(summary["output_files"], ["/tmp/a.jpg"])

    def test_rect_only_manual_crop_uses_bounding_box(self):
        image = np.arange(100 * 100 * 3, dtype=np.uint8).reshape(100, 100, 3)
        points = np.array([[10, 20], [60, 10], [80, 70], [20, 80]], dtype=np.float32)

        cropped = material_service.crop_image_with_points(image, points, mode="rect_only")

        self.assertEqual(cropped.shape[:2], (70, 70))
        np.testing.assert_array_equal(cropped[0, 0], image[10, 10])
        np.testing.assert_array_equal(cropped[-1, -1], image[79, 79])

    def test_cleanup_generated_outputs_removes_stale_outputs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            name_prefix = "123-张三"
            diploma = os.path.join(tmp_dir, f"{name_prefix}-学历证书.jpg")
            id_card = os.path.join(tmp_dir, f"{name_prefix}-身份证.jpg")
            health_form = os.path.join(tmp_dir, f"{name_prefix}-体检表.docx")

            for path in (diploma, id_card, health_form):
                with open(path, "wb") as file_obj:
                    file_obj.write(b"stale")

            material_service.cleanup_generated_outputs(
                tmp_dir,
                name_prefix,
                material_type="diploma",
            )

            self.assertFalse(os.path.exists(diploma))
            self.assertTrue(os.path.exists(id_card))
            self.assertTrue(os.path.exists(health_form))

            material_service.cleanup_generated_outputs(tmp_dir, name_prefix)

            self.assertFalse(os.path.exists(id_card))
            self.assertFalse(os.path.exists(health_form))

    def test_build_generation_report_marks_failed_results(self):
        collector = material_service.MaterialGenerationLogger()
        collector.emit("success", "diploma", "write_output", "学历证书输出成功", "已输出")

        report = material_service.build_generation_report(
            "/tmp/materials",
            collector,
            [
                {"scope": "diploma", "success": True, "output_path": "/tmp/materials/a.jpg", "error": None},
                {"scope": "hukou", "success": False, "output_path": None, "error": "write failed"},
            ],
        )

        self.assertFalse(report["success"])
        self.assertEqual(report["output_dir"], "/tmp/materials")
        self.assertEqual(report["errors"][0]["scope"], "hukou")
        self.assertEqual(report["errors"][0]["error"], "write failed")

    def test_resize_document_to_fit_keeps_tall_document_inside_a4_bounds(self):
        image = np.zeros((800, 200, 3), dtype=np.uint8)

        resized, width, height = material_service.resize_document_to_fit(
            image,
            max_width=400,
            max_height=300,
        )

        self.assertEqual((width, height), (75, 300))
        self.assertEqual(resized.shape[:2], (300, 75))

    def test_process_renewal_certificate_pages_stitches_two_pages_on_a4(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            info_page = os.path.join(tmp_dir, "info.jpg")
            records_page = os.path.join(tmp_dir, "records.jpg")
            Image.new("RGB", (1200, 800), "white").save(info_page)
            Image.new("RGB", (1200, 800), "white").save(records_page)

            result = material_service.process_renewal_certificate_pages(
                info_page,
                records_page,
                tmp_dir,
                "123-张三",
            )

            self.assertTrue(result["success"])
            self.assertTrue(os.path.exists(result["output_path"]))
            with Image.open(result["output_path"]) as output:
                self.assertEqual(output.size, (material_service.A4_WIDTH, material_service.A4_HEIGHT))

    def test_generate_student_materials_outputs_renewal_certificate_material(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_root = os.path.join(tmp_dir, "students", "特种设备-测试单位-张三")
            os.makedirs(output_root, exist_ok=True)
            source_dir = os.path.join(tmp_dir, "source")
            os.makedirs(source_dir, exist_ok=True)

            photo = os.path.join(source_dir, "photo.jpg")
            info_page = os.path.join(source_dir, "info.jpg")
            records_page = os.path.join(source_dir, "records.jpg")
            Image.new("RGB", (300, 400), "white").save(photo)
            Image.new("RGB", (1200, 800), "white").save(info_page)
            Image.new("RGB", (1200, 800), "white").save(records_page)

            student = {
                "id_card": "110101199001011234",
                "name": "张三",
                "training_type": "special_equipment",
                "application_type": "renewal",
                "photo_path": os.path.relpath(photo, tmp_dir),
                "certificate_info_page_path": os.path.relpath(info_page, tmp_dir),
                "certificate_records_page_path": os.path.relpath(records_page, tmp_dir),
            }

            report = material_service.generate_student_materials(student, tmp_dir, output_root)

            self.assertTrue(report["success"])
            output_files = [os.path.basename(path) for path in report["log_summary"]["output_files"]]
            self.assertIn("110101199001011234-张三-个人照片.jpg", output_files)
            self.assertIn("110101199001011234-张三-复审材料.jpg", output_files)


if __name__ == "__main__":
    unittest.main()
