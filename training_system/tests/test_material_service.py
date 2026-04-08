import os
import sys
import tempfile
import unittest

import numpy as np

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


if __name__ == "__main__":
    unittest.main()
