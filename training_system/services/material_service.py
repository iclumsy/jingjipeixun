import io
import os
import shutil
import subprocess
import tempfile
from datetime import datetime

import cv2
import numpy as np
from PIL import Image
from services import storage_service

A4_WIDTH = 2480
A4_HEIGHT = 3508
CM_IN_PX = 118  # roughly 300 DPI
ANALYSIS_MAX_SIDE = 1800
MIN_CROP_DIM = 24
ID_CARD_RATIO = 85.6 / 54.0
HUKOU_PAGE_RATIO = 20.5 / 14.5  # ~1.414, 户口本页面标准长宽比
TESSERACT_BINARY = shutil.which("tesseract")
HUKOU_OSD_MIN_CONFIDENCE = 0.9
HUKOU_OSD_STRONG_CONFIDENCE = 1.6
HUKOU_OSD_TIMEOUT_SEC = 8

ANALYSIS_MAX_SIDES = {
    "id_card": 2400,
    "hukou": 1800,
    "diploma": 1800,
}

CROP_PROFILES = {
    "id_card": {
        "target_ratio": ID_CARD_RATIO,
        "ratio_tolerance": 0.22,
        "post_ratio_tolerance": 0.12,
        "min_area_ratio": 0.08,
        "max_area_ratio": 0.75,
        "preferred_area_ratio": 0.32,
        "preferred_border_margin": 0.025,
        "allow_table_suppression": False,
        "allow_perspective": True,
        "perspective_threshold": 0.62,
        "analysis_enhancement": True,
        "export_enhancement": True,
        "expand_ratio": 0.012,
    },
    "hukou": {
        "target_ratio": HUKOU_PAGE_RATIO,
        "ratio_tolerance": 0.30,
        "post_ratio_tolerance": 0.30,
        "min_area_ratio": 0.18,
        "max_area_ratio": 0.95,
        "preferred_area_ratio": 0.58,
        "preferred_border_margin": 0.015,
        "allow_table_suppression": True,
        "allow_perspective": False,
        "perspective_threshold": 0.68,
        "analysis_enhancement": True,
        "export_enhancement": True,
        "expand_ratio": 0.06,
    },
    "diploma": {
        "target_ratio": None,
        "ratio_tolerance": None,
        "post_ratio_tolerance": None,
        "min_area_ratio": 0.18,
        "max_area_ratio": 0.95,
        "preferred_area_ratio": 0.60,
        "preferred_border_margin": 0.015,
        "allow_table_suppression": False,
        "allow_perspective": True,
        "perspective_threshold": 0.64,
        "analysis_enhancement": True,
        "export_enhancement": True,
        "expand_ratio": 0.015,
    },
}

MATERIAL_OUTPUT_LABELS = {
    "photo": "个人照片",
    "diploma": "学历证书",
    "id_card": "身份证",
    "hukou": "户口本",
    "renewal_certificate": "复审材料",
    "training_form": "体检表",
}

MATERIAL_SCOPE_LABELS = {
    "global": "全局流程",
    "photo": "个人照片",
    "diploma": "学历证书",
    "id_card": "身份证",
    "id_card_front": "身份证正面",
    "id_card_back": "身份证反面",
    "hukou": "户口本",
    "hukou_home": "户口本首页",
    "hukou_personal": "户口本人页",
    "renewal_certificate": "复审材料",
    "certificate_info_page": "原证件说明和个人信息页",
    "certificate_records_page": "原证件作业项目和聘用记录页",
    "training_form": "体检表",
}


class MaterialGenerationLogger:
    def __init__(self):
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.finished_at = None
        self.events = []
        self.output_files = []

    def emit(self, level, scope, step, title, message, details=None, raw=None):
        event = {
            "level": level,
            "scope": scope,
            "scope_label": MATERIAL_SCOPE_LABELS.get(scope, scope),
            "step": step,
            "title": title,
            "message": message,
            "details": details or {},
            "raw": raw,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        output_path = event["details"].get("output_path")
        if output_path and output_path not in self.output_files:
            self.output_files.append(output_path)
        self.events.append(event)
        return event

    def build_summary(self):
        if self.finished_at is None:
            self.finished_at = datetime.now().isoformat(timespec="seconds")

        success_count = sum(1 for event in self.events if event["level"] == "success")
        warning_count = sum(1 for event in self.events if event["level"] == "warning")
        error_count = sum(1 for event in self.events if event["level"] == "error")
        material_scopes = {
            event["scope"]
            for event in self.events
            if event["scope"] != "global"
        }
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "material_count": len(material_scopes),
            "success_count": success_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "output_files": list(self.output_files),
        }


def crop_image_with_points(image, points, mode="perspective"):
    points_array = np.array(points, dtype=np.float32)
    if mode == "rect_only":
        x1 = int(np.floor(np.min(points_array[:, 0])))
        y1 = int(np.floor(np.min(points_array[:, 1])))
        x2 = int(np.ceil(np.max(points_array[:, 0])))
        y2 = int(np.ceil(np.max(points_array[:, 1])))
        h, w = image.shape[:2]
        x1 = int(np.clip(x1, 0, w - 1))
        y1 = int(np.clip(y1, 0, h - 1))
        x2 = int(np.clip(x2, x1 + 1, w))
        y2 = int(np.clip(y2, y1 + 1, h))
        return image[y1:y2, x1:x2].copy()
    return four_point_transform(image, points_array, inpaint=True)


def cleanup_generated_outputs(output_dir, name_prefix, material_type=None):
    if not os.path.isdir(output_dir):
        return []

    target_names = {
        "photo": [f"{name_prefix}-{MATERIAL_OUTPUT_LABELS['photo']}.jpg"],
        "diploma": [f"{name_prefix}-{MATERIAL_OUTPUT_LABELS['diploma']}.jpg"],
        "id_card": [f"{name_prefix}-{MATERIAL_OUTPUT_LABELS['id_card']}.jpg"],
        "hukou": [f"{name_prefix}-{MATERIAL_OUTPUT_LABELS['hukou']}.jpg"],
        "renewal_certificate": [f"{name_prefix}-{MATERIAL_OUTPUT_LABELS['renewal_certificate']}.jpg"],
        "training_form": [f"{name_prefix}-{MATERIAL_OUTPUT_LABELS['training_form']}"],
    }

    removed = []
    for filename in os.listdir(output_dir):
        abs_path = os.path.join(output_dir, filename)
        if not os.path.isfile(abs_path):
            continue

        should_remove = False
        if material_type is None:
            should_remove = filename.startswith(f"{name_prefix}-")
        elif material_type == "training_form":
            should_remove = filename.startswith(target_names["training_form"][0])
        else:
            should_remove = filename in target_names.get(material_type, [])

        if should_remove:
            os.remove(abs_path)
            removed.append(abs_path)

    return removed


def _build_process_result(scope, success, output_path=None, error=None):
    return {
        "scope": scope,
        "success": success,
        "output_path": output_path,
        "error": error,
    }


def build_generation_report(output_dir, logger, results):
    logger.finished_at = datetime.now().isoformat(timespec="seconds")
    errors = [result for result in results if not result.get("success")]
    summary = logger.build_summary()
    warning_scopes = {
        event["scope"]
        for event in logger.events
        if event["level"] == "warning" and event["scope"] != "global"
    }
    summary.update({
        "material_count": len(results),
        "success_count": sum(1 for result in results if result.get("success")),
        "warning_count": len(warning_scopes),
        "error_count": len(errors),
    })
    return {
        "success": not errors,
        "output_dir": output_dir,
        "results": results,
        "errors": errors,
        "log_events": list(logger.events),
        "log_summary": summary,
    }


def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


def four_point_transform(image, pts, inpaint=False):
    rect = order_points(pts.astype("float32"))
    (tl, tr, br, bl) = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(round(width_a)), int(round(width_b)))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(round(height_a)), int(round(height_b)))

    max_width = max(max_width, MIN_CROP_DIM)
    max_height = max(max_height, MIN_CROP_DIM)

    dst = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )

    transform = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, transform, (max_width, max_height))

    if inpaint:
        src_mask = np.full(image.shape[:2], 255, dtype=np.uint8)
        warped_mask = cv2.warpPerspective(src_mask, transform, (max_width, max_height))
        inpaint_mask = cv2.bitwise_not(warped_mask)
        # 边界向内膨胀几像素，避免 inpaint 残留 warp 时的边缘黑线
        kernel = np.ones((3, 3), np.uint8)
        inpaint_mask = cv2.dilate(inpaint_mask, kernel, iterations=1)
        if inpaint_mask.any():
            missing_ratio = float(inpaint_mask.sum()) / (max_width * max_height * 255)
            print(f"[four_point_transform] inpaint missing ratio={missing_ratio:.3f}")
            warped = cv2.inpaint(warped, inpaint_mask, 5, cv2.INPAINT_TELEA)

    return warped


def resize_for_analysis(image, max_side=ANALYSIS_MAX_SIDE):
    h, w = image.shape[:2]
    if max(h, w) <= max_side:
        return image.copy(), 1.0

    scale = max(h, w) / float(max_side)
    resized = cv2.resize(
        image,
        (int(round(w / scale)), int(round(h / scale))),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def analyze_image_stats(image):
    if image is None or image.size == 0:
        return {"mean": 0.0, "std": 0.0, "p5": 0.0, "p95": 0.0, "dynamic_range": 0.0}

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    p5 = float(np.percentile(gray, 5))
    p95 = float(np.percentile(gray, 95))
    return {
        "mean": float(gray.mean()),
        "std": float(gray.std()),
        "p5": p5,
        "p95": p95,
        "dynamic_range": p95 - p5,
    }


def apply_clahe_to_bgr(image, clip_limit=2.0, tile_grid_size=(8, 8)):
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    enhanced_l = clahe.apply(l_channel)
    merged = cv2.merge((enhanced_l, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def apply_gamma(image, gamma):
    gamma = max(gamma, 0.1)
    table = np.array(
        [((i / 255.0) ** (1.0 / gamma)) * 255 for i in np.arange(256)],
        dtype=np.uint8,
    )
    return cv2.LUT(image, table)


def blend_images(base, overlay, alpha):
    alpha = float(np.clip(alpha, 0.0, 1.0))
    return cv2.addWeighted(base, 1.0 - alpha, overlay, alpha, 0)


def apply_low_light_enhancement_if_needed(image, stage="analysis"):
    stats_before = analyze_image_stats(image)

    if stage == "analysis":
        mean_threshold = 130
        dynamic_threshold = 88
        clip_limit = 2.8
        blend_alpha = 0.80
        gamma_value = 1.20
    else:
        mean_threshold = 112
        dynamic_threshold = 72
        clip_limit = 2.0
        blend_alpha = 0.60
        gamma_value = 1.12

    # 若图像已有高动态范围（暗背景+亮证件场景），跳过增强：
    # CLAHE 会给纯黑背景引入杂乱纹理，破坏 Canny 边缘检测和 Otsu 前景分割
    high_dynamic_range = stats_before["dynamic_range"] > 150
    needs_enhancement = (
        (stats_before["mean"] < mean_threshold or stats_before["dynamic_range"] < dynamic_threshold)
        and not high_dynamic_range
    )
    if not needs_enhancement:
        return image.copy(), {
            "enabled": False,
            "stage": stage,
            "mean_before": stats_before["mean"],
            "mean_after": stats_before["mean"],
            "dynamic_before": stats_before["dynamic_range"],
            "dynamic_after": stats_before["dynamic_range"],
        }

    enhanced = apply_clahe_to_bgr(image, clip_limit=clip_limit)
    if stats_before["mean"] < 95:
        enhanced = apply_gamma(enhanced, gamma_value)
    enhanced = blend_images(image, enhanced, blend_alpha)

    stats_after = analyze_image_stats(enhanced)
    if (
        stats_after["mean"] <= stats_before["mean"] + 2
        and stats_after["dynamic_range"] <= stats_before["dynamic_range"] + 4
    ) or stats_after["p95"] > 252:
        return image.copy(), {
            "enabled": False,
            "stage": stage,
            "mean_before": stats_before["mean"],
            "mean_after": stats_before["mean"],
            "dynamic_before": stats_before["dynamic_range"],
            "dynamic_after": stats_before["dynamic_range"],
        }

    return enhanced, {
        "enabled": True,
        "stage": stage,
        "mean_before": stats_before["mean"],
        "mean_after": stats_after["mean"],
        "dynamic_before": stats_before["dynamic_range"],
        "dynamic_after": stats_after["dynamic_range"],
    }


def prepare_analysis_image(image, enable_low_light=True, max_side=ANALYSIS_MAX_SIDE):
    analysis_image, scale = resize_for_analysis(image, max_side=max_side)
    enhancement_meta = {
        "enabled": False,
        "stage": "analysis",
        "mean_before": analyze_image_stats(analysis_image)["mean"],
        "mean_after": analyze_image_stats(analysis_image)["mean"],
        "dynamic_before": analyze_image_stats(analysis_image)["dynamic_range"],
        "dynamic_after": analyze_image_stats(analysis_image)["dynamic_range"],
    }
    if enable_low_light:
        analysis_image, enhancement_meta = apply_low_light_enhancement_if_needed(
            analysis_image,
            stage="analysis",
        )
    gray = cv2.cvtColor(analysis_image, cv2.COLOR_BGR2GRAY)
    return analysis_image, gray, enhancement_meta, scale


def suppress_table_lines_for_hukou(gray):
    h, w = gray.shape[:2]
    block_size = max(15, int(min(h, w) * 0.03))
    if block_size % 2 == 0:
        block_size += 1

    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        10,
    )
    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(25, w // 10), 1),
    )
    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (1, max(25, h // 10)),
    )
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    line_mask = cv2.bitwise_or(horizontal, vertical)

    softened = cv2.GaussianBlur(gray, (9, 9), 0)
    suppressed = gray.copy()
    suppressed[line_mask > 0] = softened[line_mask > 0]
    return suppressed, line_mask


def detect_edges(gray, profile_name, canny_scale=1.0):
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    median = float(np.median(blurred))
    lower = int(max(25, 0.66 * median) * canny_scale)
    upper = int(min(255, max(90, 1.33 * median)) * canny_scale)
    # 防止 scale 过大时 upper 超限
    lower = max(8, min(lower, 200))
    upper = max(lower + 20, min(upper, 255))

    edges_high = cv2.Canny(blurred, lower, upper)
    edges_low = cv2.Canny(blurred, int(lower * 0.6), int(upper * 0.6))
    edges = cv2.bitwise_or(edges_high, edges_low)

    h, w = gray.shape[:2]
    kernel_size = max(5, int(round(min(h, w) * 0.012)))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    if profile_name != "id_card":
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, dilate_kernel, iterations=1)
    return edges


def polygon_angle_quality(points):
    ordered = order_points(points.astype("float32"))
    quality = []
    for index in range(4):
        prev_pt = ordered[index - 1]
        curr_pt = ordered[index]
        next_pt = ordered[(index + 1) % 4]
        v1 = prev_pt - curr_pt
        v2 = next_pt - curr_pt
        denom = np.linalg.norm(v1) * np.linalg.norm(v2)
        if denom <= 1e-6:
            return 0.0
        cosine = np.clip(np.dot(v1, v2) / denom, -1.0, 1.0)
        angle = np.degrees(np.arccos(cosine))
        quality.append(max(0.0, 1.0 - abs(angle - 90.0) / 45.0))
    return float(np.mean(quality))


def compute_aspect_ratio(points):
    ordered = order_points(points.astype("float32"))
    width = max(np.linalg.norm(ordered[1] - ordered[0]), np.linalg.norm(ordered[2] - ordered[3]))
    height = max(np.linalg.norm(ordered[3] - ordered[0]), np.linalg.norm(ordered[2] - ordered[1]))
    if min(width, height) <= 1e-6:
        return 0.0
    return float(max(width, height) / min(width, height))


def compute_border_edge_density(edges, points):
    mask = np.zeros(edges.shape[:2], dtype=np.uint8)
    thickness = max(2, int(round(min(edges.shape[:2]) * 0.005)))
    cv2.polylines(mask, [points.astype(np.int32)], True, 255, thickness)
    border_pixels = cv2.countNonZero(mask)
    if border_pixels <= 0:
        return 0.0
    edge_pixels = cv2.countNonZero(cv2.bitwise_and(edges, mask))
    return float(min(1.0, (edge_pixels / float(border_pixels)) * 4.0))


def compute_inner_line_density(line_mask, points):
    if line_mask is None:
        return 0.0
    mask = np.zeros(line_mask.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [points.astype(np.int32)], 255)
    mask = cv2.erode(mask, np.ones((5, 5), dtype=np.uint8), iterations=1)
    area = cv2.countNonZero(mask)
    if area <= 0:
        return 0.0
    line_pixels = cv2.countNonZero(cv2.bitwise_and(line_mask, mask))
    raw_density = line_pixels / float(area)
    return float(min(1.0, raw_density * 10.0))


def interval_score(value, min_value, max_value):
    if min_value <= value <= max_value:
        return 1.0
    if value < min_value:
        if min_value <= 1e-6:
            return 0.0
        return float(max(0.0, value / min_value))
    overflow = value - max_value
    return float(max(0.0, 1.0 - overflow / max(1.0 - max_value, 1e-6)))


def preferred_score(value, preferred, tolerance):
    if tolerance <= 1e-6:
        return 1.0
    return float(max(0.0, 1.0 - abs(value - preferred) / tolerance))


def preferred_score_asymmetric(value, preferred, tolerance_low, tolerance_high):
    if value <= preferred:
        if tolerance_low <= 1e-6:
            return 1.0
        return float(max(0.0, 1.0 - (preferred - value) / tolerance_low))
    if tolerance_high <= 1e-6:
        return 1.0
    return float(max(0.0, 1.0 - (value - preferred) / tolerance_high))


def expand_quad(points, expand_px, image_shape):
    if expand_px <= 0:
        return points.astype(np.float32)

    ordered = order_points(points.astype(np.float32))
    center = ordered.mean(axis=0)

    edge_normals = []
    for i in range(4):
        p1 = ordered[i]
        p2 = ordered[(i + 1) % 4]
        edge = p2 - p1
        normal = np.array([-edge[1], edge[0]], dtype=np.float32)
        norm_len = np.linalg.norm(normal)
        if norm_len > 1e-6:
            normal /= norm_len
        mid = (p1 + p2) / 2.0
        if np.dot(normal, mid - center) < 0:
            normal = -normal
        edge_normals.append(normal)

    expanded = ordered.copy()
    for i in range(4):
        n_prev = edge_normals[(i - 1) % 4]
        n_curr = edge_normals[i]
        direction = n_prev + n_curr
        dir_len = np.linalg.norm(direction)
        if dir_len > 1e-6:
            direction /= dir_len
            cos_half = max(float(np.dot(direction, n_curr)), 0.3)
            expanded[i] = ordered[i] + direction * (expand_px / cos_half)
        else:
            expanded[i] = ordered[i] + n_curr * expand_px

    h, w = image_shape[:2]
    expanded[:, 0] = np.clip(expanded[:, 0], 0, w - 1)
    expanded[:, 1] = np.clip(expanded[:, 1], 0, h - 1)
    return expanded


def normalize_output_orientation(image, profile_name):
    if profile_name == "id_card" and image.shape[0] > image.shape[1]:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    return image


def estimate_skin_centroid(image):
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    y_channel, cr_channel, cb_channel = cv2.split(ycrcb)
    skin_mask = (
        (cr_channel > 135)
        & (cr_channel < 185)
        & (cb_channel > 85)
        & (cb_channel < 135)
        & (y_channel > 60)
    )
    ys, xs = np.where(skin_mask)
    min_pixels = max(500, int(image.shape[0] * image.shape[1] * 0.005))
    if len(xs) < min_pixels:
        return None
    return float(xs.mean() / float(image.shape[1])), float(ys.mean() / float(image.shape[0]))


def estimate_red_centroid(image):
    b_channel, g_channel, r_channel = cv2.split(image)
    red_mask = (r_channel > 130) & (r_channel > g_channel + 30) & (r_channel > b_channel + 30)
    ys, xs = np.where(red_mask)
    min_pixels = max(400, int(image.shape[0] * image.shape[1] * 0.002))
    if len(xs) < min_pixels:
        return None
    return float(xs.mean() / float(image.shape[1])), float(ys.mean() / float(image.shape[0]))


def normalize_id_card_side(image, side):
    if image is None or image.size == 0:
        return image

    normalized = normalize_output_orientation(image, "id_card")
    if side == "front":
        skin_centroid = estimate_skin_centroid(normalized)
        if skin_centroid and skin_centroid[0] < 0.5:
            return cv2.rotate(normalized, cv2.ROTATE_180)
    elif side == "back":
        red_centroid = estimate_red_centroid(normalized)
        if red_centroid and red_centroid[0] > 0.5:
            return cv2.rotate(normalized, cv2.ROTATE_180)
    return normalized


def rotate_image_by_degrees(image, degrees):
    degrees = int(degrees) % 360
    if degrees == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image


def detect_text_osd_rotation(image):
    if TESSERACT_BINARY is None or image is None or image.size == 0:
        return None

    osd_image, _ = resize_for_analysis(image, max_side=2200)
    osd_image, _ = apply_low_light_enhancement_if_needed(osd_image, stage="analysis")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
        if not cv2.imwrite(temp_path, osd_image):
            return None

        process = subprocess.run(
            [TESSERACT_BINARY, temp_path, "stdout", "--psm", "0"],
            capture_output=True,
            text=True,
            timeout=HUKOU_OSD_TIMEOUT_SEC,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

    output = "\n".join(part for part in (process.stdout, process.stderr) if part)
    rotate_degrees = None
    confidence = None
    for line in output.splitlines():
        if line.startswith("Rotate:"):
            try:
                rotate_degrees = int(line.split(":", 1)[1].strip())
            except ValueError:
                rotate_degrees = None
        elif line.startswith("Orientation confidence:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
            except ValueError:
                confidence = None

    if rotate_degrees is None or confidence is None:
        return None
    return {"rotate_degrees": rotate_degrees % 360, "confidence": confidence}


def detect_hukou_home_stamp_centers(image):
    b_channel, g_channel, r_channel = cv2.split(image)
    red_mask = (
        (r_channel > 110)
        & (r_channel > g_channel + 25)
        & (r_channel > b_channel + 25)
    ).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(image.shape[0] * image.shape[1])
    min_area = max(1500, int(image_area * 0.01))
    max_area = int(image_area * 0.12)
    components = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = max(w, h) / float(max(1, min(w, h)))
        fill_ratio = area / float(max(1, w * h))
        if aspect_ratio > 1.8 or fill_ratio < 0.15:
            continue
        perimeter = cv2.arcLength(contour, True)
        circularity = (4.0 * np.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0
        if circularity < 0.25:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] <= 1e-6:
            continue
        components.append(
            {
                "area": float(area),
                "center_x": float(moments["m10"] / moments["m00"]),
                "center_y": float(moments["m01"] / moments["m00"]),
            }
        )

    components.sort(key=lambda item: item["area"], reverse=True)
    return components[:2]


def normalize_hukou_home_page(image):
    stamps = detect_hukou_home_stamp_centers(image)
    if len(stamps) < 2:
        return image

    primary, secondary = stamps[0], stamps[1]
    dx = abs(primary["center_x"] - secondary["center_x"])
    dy = abs(primary["center_y"] - secondary["center_y"])

    if dy > dx * 1.15:
        if primary["center_y"] < secondary["center_y"]:
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)

    if primary["center_x"] > secondary["center_x"]:
        return cv2.rotate(image, cv2.ROTATE_180)
    return image


def estimate_orientation_by_projection(image):
    """
    纯视觉方向检测：通过水平/垂直方向的文字行投影得分，
    判断图像是否需要旋转。不依赖 Tesseract。

    返回 0/90/180/270 中最可能正确的旋转角度（apply 后图片方向正确）。
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # 二值化提取暗色区域（文字）
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    def horizontal_line_score(img):
        """
        对水平方向投影每行的前景像素数求"方差"——文字行投影方差越大说明
        行与行之间有明显的空白间隔，即方向正确的概率大。
        """
        row_sums = img.sum(axis=1).astype(np.float32)
        return float(np.var(row_sums))

    scores = {}
    for angle in (0, 90, 180, 270):
        rotated = rotate_image_by_degrees(binary, angle)
        scores[angle] = horizontal_line_score(rotated)

    best = max(scores, key=scores.get)
    sorted_scores = sorted(scores.values(), reverse=True)
    if sorted_scores[0] < sorted_scores[1] * 1.15:
        return 0, scores
    return best, scores


def normalize_hukou_page_orientation(image, original_image=None, page_kind="personal"):
    source_image = original_image if original_image is not None else image
    kind_label = "首页" if page_kind == "home" else "本人页"
    tag = f"[hukou][{kind_label}]"

    # 优先用 Tesseract OSD（精度最高）
    raw_osd = detect_text_osd_rotation(source_image)
    if raw_osd:
        print(f"{tag} Tesseract OSD: rotate={raw_osd['rotate_degrees']}°  confidence={raw_osd['confidence']:.2f}  (threshold={HUKOU_OSD_MIN_CONFIDENCE})")
    else:
        print(f"{tag} Tesseract OSD: 不可用（未安装或反馈为空）")

    if raw_osd and raw_osd["confidence"] >= HUKOU_OSD_MIN_CONFIDENCE:
        rotate_degrees = raw_osd["rotate_degrees"]
        if rotate_degrees in (90, 270):
            print(f"{tag} 决策: OSD 旋转 {rotate_degrees}°（横向竖放图片）")
            return rotate_image_by_degrees(image, rotate_degrees)
        if page_kind != "home" or raw_osd["confidence"] >= HUKOU_OSD_STRONG_CONFIDENCE:
            print(f"{tag} 决策: OSD 旋转 {rotate_degrees}°")
            return rotate_image_by_degrees(image, rotate_degrees)
        print(f"{tag} OSD 置信度不足（{raw_osd['confidence']:.2f} < {HUKOU_OSD_STRONG_CONFIDENCE}），跳过 OSD 结果")
    elif raw_osd:
        print(f"{tag} OSD 置信度不足（{raw_osd['confidence']:.2f} < {HUKOU_OSD_MIN_CONFIDENCE}），进入备选逻辑")

    # home 页：先试印章颜色方案
    if page_kind == "home":
        before_shape = image.shape
        stamped = normalize_hukou_home_page(image)
        if stamped.shape != before_shape or not np.array_equal(stamped, image):
            print(f"{tag} 决策: 印章颜色检测成功，已旋转调整方向")
            return stamped
        print(f"{tag} 印章颜色检测: 未触发（印章不够清晰或不存在），进入投影方法")

    # 纯视觉投影方向检测
    best_angle, proj_scores = estimate_orientation_by_projection(image)
    sorted_proj = sorted(proj_scores.items(), key=lambda kv: -kv[1])
    scores_str = "  ".join(f"{ang}°={s:.1f}" for ang, s in sorted_proj)
    print(f"{tag} 投影得分: {scores_str}")
    if best_angle != 0:
        print(f"{tag} 决策: 投影备选旋转 {best_angle}°")
        return rotate_image_by_degrees(image, best_angle)
    print(f"{tag} 投影方法: 得分差异不显著，不旋转")


    # 如果裁剪图和原图都没能确定方向，再试一次裁剪后的 OSD
    if original_image is not None:
        crop_osd = detect_text_osd_rotation(image)
        if crop_osd:
            print(f"{tag} 裁剪后二次 OSD: rotate={crop_osd['rotate_degrees']}°  confidence={crop_osd['confidence']:.2f}")
        if crop_osd and crop_osd["confidence"] >= HUKOU_OSD_MIN_CONFIDENCE:
            print(f"{tag} 决策: 二次 OSD 旋转 {crop_osd['rotate_degrees']}°")
            return rotate_image_by_degrees(image, crop_osd["rotate_degrees"])

    print(f"{tag} 所有方法均未成功识别方向，保持原图不动")
    return image


def trim_hukou_home_page_margins(image):
    if image is None or image.size == 0:
        return image

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 60, 150)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=120,
        minLineLength=max(120, int(image.shape[1] * 0.22)),
        maxLineGap=20,
    )
    if lines is None:
        return image

    h, w = image.shape[:2]
    vertical_threshold = max(18, int(h * 0.03))
    horizontal_threshold = max(18, int(w * 0.03))

    left_candidates = []
    right_candidates = []
    for line in lines[:, 0]:
        x1, y1, x2, y2 = map(int, line)
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx <= vertical_threshold and dy >= int(h * 0.30):
            center_x = int(round((x1 + x2) / 2.0))
            if center_x <= int(w * 0.45):
                left_candidates.append(center_x)
            if center_x >= int(w * 0.55):
                right_candidates.append(center_x)

    if not right_candidates:
        col_energy = edges.mean(axis=0)
        kernel_size = max(9, int(w * 0.01))
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = np.ones(kernel_size, dtype=np.float32) / float(kernel_size)
        smoothed_cols = np.convolve(col_energy, kernel, mode="same")
        right_start = int(w * 0.55)
        right_end = int(w * 0.97)
        if right_end - right_start > 20:
            right_band = smoothed_cols[right_start:right_end]
            threshold = float(np.percentile(right_band, 90))
            strong_cols = np.where(right_band >= threshold)[0]
            if strong_cols.size > 0:
                right_candidates.append(right_start + int(np.median(strong_cols)))

    if not right_candidates and not left_candidates:
        return image

    pad_x = max(12, int(w * 0.015))
    left = max(0, min(left_candidates) - pad_x) if left_candidates else 0
    right = min(w, max(right_candidates) + pad_x) if right_candidates else w
    top = 0
    bottom = h

    if right - left < int(w * 0.62) or bottom - top < int(h * 0.55):
        return image
    if right - left >= int(w * 0.99) and bottom - top >= int(h * 0.99):
        return image
    return image[top:bottom, left:right].copy()


def prepare_hukou_output_page(image, page_kind, crop_mode="auto", expand_level=None, skip_ratio_trim=False, canny_scale=1.0, manual_crop_applied=False):
    kind_label = "首页" if page_kind == "home" else "本人页"
    tag = f"[hukou][{kind_label}]"
    h0, w0 = image.shape[:2]
    print(f"{tag} 原图尺寸: {w0}x{h0}")

    if manual_crop_applied:
        page = image.copy()
        meta = {"crop_mode": "manual", "selected_candidate": None}
    elif crop_mode == "none":
        page = image.copy()
        meta = {"crop_mode": "original", "selected_candidate": None}
    else:
        _allow_persp = None if crop_mode == "auto" else False
        page, meta = auto_crop_hukou_page(image, return_meta=True, allow_perspective=_allow_persp, expand_level=expand_level, skip_ratio_trim=skip_ratio_trim, canny_scale=canny_scale)
    selected = meta.get("selected_candidate") or {}
    h1, w1 = page.shape[:2]
    print(
        f"{tag} 裁剪后: {w1}x{h1}  "
        f"mode={meta.get('crop_mode')}  "
        f"detector={selected.get('detector', 'N/A')}  "
        f"area_ratio={selected.get('area_ratio', 0):.3f}  "
        f"confidence={selected.get('confidence', 0):.3f}  "
        f"edge_density={selected.get('edge_density_on_border', 0):.3f}  "
        f"analysis_enhanced={meta.get('analysis_enhancement_enabled', False)}"
    )

    if (
        not manual_crop_applied
        and
        page_kind == "home"
        and selected.get("detector") == "foreground_mask"
        and selected.get("area_ratio", 0.0) < 0.85
    ):
        refined_page, refined_meta = auto_crop_hukou_page(page, return_meta=True, canny_scale=canny_scale)
        h2, w2 = refined_page.shape[:2]
        if refined_page.shape[0] * refined_page.shape[1] < page.shape[0] * page.shape[1] * 0.96:
            print(f"{tag} 二次精细裁剪生效: {w2}x{h2}")
            page = refined_page
            meta = refined_meta
            selected = meta.get("selected_candidate") or selected
        else:
            print(f"{tag} 二次精细裁剪未生效（面积没有明显缩小），保持第一次结果")

    if not manual_crop_applied:
        page = normalize_hukou_page_orientation(page, original_image=image, page_kind=page_kind)
    h3, w3 = page.shape[:2]
    if (h3, w3) != (h1, w1):
        print(f"{tag} 方向校正后: {w3}x{h3}")

    if (
        not manual_crop_applied
        and
        page_kind == "home"
        and selected.get("detector") == "foreground_mask"
        and selected.get("area_ratio", 0.0) >= 0.82
        and selected.get("edge_density_on_border", 1.0) < 0.40
    ):
        print(f"{tag} 触发边缘修剪（area_ratio={selected.get('area_ratio', 0):.3f}, edge_density={selected.get('edge_density_on_border', 0):.3f}）")
        page = trim_hukou_home_page_margins(page)
        h4, w4 = page.shape[:2]
        print(f"{tag} 边缘修剪后: {w4}x{h4}")
    return page


def is_valid_perspective_result(image, profile_name):
    h, w = image.shape[:2]
    if h < MIN_CROP_DIM or w < MIN_CROP_DIM:
        return False

    profile = CROP_PROFILES[profile_name]
    target_ratio = profile.get("target_ratio")
    if not target_ratio:
        return True

    ratio = max(w, h) / float(max(1, min(w, h)))
    ratio_delta = abs(ratio - target_ratio) / target_ratio
    return ratio_delta <= profile.get("post_ratio_tolerance", 0.15)


def summarize_candidate(candidate):
    if not candidate:
        return None
    return {
        "area_ratio": round(candidate["area_ratio"], 4),
        "aspect_ratio": round(candidate["aspect_ratio"], 4),
        "rectangularity": round(candidate["rectangularity"], 4),
        "corner_quality": round(candidate["corner_quality"], 4),
        "border_margin": round(candidate["border_margin"], 4),
        "edge_density_on_border": round(candidate["edge_density_on_border"], 4),
        "inner_line_density": round(candidate["inner_line_density"], 4),
        "confidence": round(candidate["confidence"], 4),
        "detector": candidate.get("detector", "edge"),
        "source": candidate["source"],
        "points_orig": candidate.get("points_orig").tolist() if "points_orig" in candidate else None
    }


def build_candidate_from_contour(contour, edges, image_shape, scale, line_mask=None, detector="edge"):
    hull = cv2.convexHull(contour)
    contour_area = cv2.contourArea(hull)
    if contour_area <= 0:
        return None

    perimeter = cv2.arcLength(hull, True)
    points = None
    source = "min_rect"
    for eps_factor in (0.015, 0.02, 0.03, 0.04, 0.05):
        approx = cv2.approxPolyDP(hull, eps_factor * perimeter, True)
        if len(approx) == 4:
            points = approx.reshape(4, 2).astype(np.float32)
            source = "approx"
            break
    if points is None:
        rect = cv2.minAreaRect(hull)
        points = cv2.boxPoints(rect).astype(np.float32)

    ordered = order_points(points)
    box_area = cv2.contourArea(ordered)
    if box_area <= 0:
        return None

    image_area = float(image_shape[0] * image_shape[1])
    border_margin = min(
        np.min(ordered[:, 0]),
        np.min(ordered[:, 1]),
        image_shape[1] - 1 - np.max(ordered[:, 0]),
        image_shape[0] - 1 - np.max(ordered[:, 1]),
    ) / float(max(1, min(image_shape[:2])))

    return {
        "points_analysis": ordered,
        "points_orig": ordered * scale,
        "contour_area": float(contour_area),
        "area_ratio": float(contour_area / image_area),
        "aspect_ratio": compute_aspect_ratio(ordered),
        "rectangularity": float(min(1.0, contour_area / box_area)),
        "corner_quality": polygon_angle_quality(ordered),
        "border_margin": float(max(0.0, border_margin)),
        "edge_density_on_border": compute_border_edge_density(edges, ordered),
        "inner_line_density": compute_inner_line_density(line_mask, ordered),
        "detector": detector,
        "source": source,
    }


def detect_foreground_mask_contours(gray):
    h, w = gray.shape[:2]
    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(9, w // 120), max(9, h // 120)),
    )
    open_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(5, w // 200), max(5, h // 200)),
    )

    _, otsu_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    otsu_mask = cv2.morphologyEx(otsu_mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
    otsu_mask = cv2.morphologyEx(otsu_mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
    otsu_contours, _ = cv2.findContours(otsu_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    block_size = max(51, int(min(h, w) * 0.08))
    if block_size % 2 == 0:
        block_size += 1
    adaptive_mask = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, block_size, -5,
    )
    adaptive_mask = cv2.morphologyEx(adaptive_mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
    adaptive_mask = cv2.morphologyEx(adaptive_mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
    adaptive_contours, _ = cv2.findContours(adaptive_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    return list(otsu_contours) + list(adaptive_contours)


def detect_background_color_contours(image):
    h, w = image.shape[:2]
    sigma = max(3.0, min(h, w) / 120.0)
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma)
    lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB).astype(np.float32)

    # 加入 L 通道（亮度），权重 0.6 以平衡色度通道：
    # 原来只用 a/b 色度，无法区分纯黑背景（L≈0）和白色卡片（L≈255），
    # 导致"暗背景+亮证件"场景距离 ≈ 0，检测完全失效
    lab_weighted = lab.copy()
    lab_weighted[:, :, 0] *= 0.6  # L 通道降权，避免亮度差异掩盖色彩差异

    margin = max(12, min(h, w) // 18)
    border = np.concatenate(
        [
            lab_weighted[:margin, :, :].reshape(-1, 3),
            lab_weighted[-margin:, :, :].reshape(-1, 3),
            lab_weighted[:, :margin, :].reshape(-1, 3),
            lab_weighted[:, -margin:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    background_color = np.median(border, axis=0)

    color_std = float(np.std(border, axis=0).mean())
    if color_std > 18:  # 边框颜色不均匀，背景色无法确定
        return []

    distance = np.linalg.norm(lab_weighted - background_color, axis=2)
    max_distance = float(distance.max())
    if max_distance <= 1e-6:
        return []

    distance_u8 = np.clip(distance / max_distance * 255.0, 0, 255).astype(np.uint8)
    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(9, w // 70), max(9, h // 70)),
    )
    open_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(5, w // 180), max(5, h // 180)),
    )

    contours = []
    for percentile in (74, 82):
        threshold = max(int(np.percentile(distance_u8, percentile)), 24)
        _, mask = cv2.threshold(distance_u8, threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
        threshold_contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours.extend(threshold_contours)
    return contours


def deduplicate_candidates(candidates, iou_threshold=0.85):
    if len(candidates) <= 1:
        return candidates
    keep = []
    for candidate in candidates:
        is_dup = False
        for kept in keep:
            if abs(candidate["area_ratio"] - kept["area_ratio"]) > 0.15:
                continue
            pts1 = candidate["points_analysis"].astype(np.int32)
            pts2 = kept["points_analysis"].astype(np.int32)
            r1 = cv2.boundingRect(pts1)
            r2 = cv2.boundingRect(pts2)
            x_overlap = max(0, min(r1[0] + r1[2], r2[0] + r2[2]) - max(r1[0], r2[0]))
            y_overlap = max(0, min(r1[1] + r1[3], r2[1] + r2[3]) - max(r1[1], r2[1]))
            inter = x_overlap * y_overlap
            union = r1[2] * r1[3] + r2[2] * r2[3] - inter
            if union > 0 and inter / float(union) >= iou_threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append(candidate)
    return keep


def detect_document_candidates(analysis_image, gray, profile_name, scale=1.0, line_mask=None, canny_scale=1.0):
    edges = detect_edges(gray, profile_name, canny_scale=canny_scale)
    retrieval_mode = cv2.RETR_LIST if profile_name == "id_card" else cv2.RETR_EXTERNAL
    contours, _ = cv2.findContours(edges.copy(), retrieval_mode, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:18]

    threshold_contours = []
    background_color_contours = []
    if profile_name in {"id_card", "hukou"}:
        threshold_contours = detect_foreground_mask_contours(gray)
        threshold_contours = sorted(threshold_contours, key=cv2.contourArea, reverse=True)[:8]
    if profile_name == "id_card":
        background_color_contours = detect_background_color_contours(analysis_image)
        background_color_contours = sorted(background_color_contours, key=cv2.contourArea, reverse=True)[:8]

    candidates = []
    for contour in contours:
        candidate = build_candidate_from_contour(
            contour,
            edges,
            analysis_image.shape[:2],
            scale,
            line_mask=line_mask,
            detector="edge",
        )
        if candidate is not None:
            candidates.append(candidate)

    if profile_name in {"id_card", "hukou"}:
        for contour in threshold_contours:
            candidate = build_candidate_from_contour(
                contour,
                edges,
                analysis_image.shape[:2],
                scale,
                line_mask=line_mask,
                detector="foreground_mask",
            )
            if candidate is not None:
                candidates.append(candidate)
        for contour in background_color_contours:
            candidate = build_candidate_from_contour(
                contour,
                edges,
                analysis_image.shape[:2],
                scale,
                line_mask=line_mask,
                detector="background_color",
            )
            if candidate is not None:
                candidates.append(candidate)
    return deduplicate_candidates(candidates)


def score_candidate(candidate, profile_name):
    profile = CROP_PROFILES[profile_name]
    target_ratio = profile.get("target_ratio")
    aspect_ratio_delta = 0.0

    if candidate["area_ratio"] < profile["min_area_ratio"] * 0.35:
        return None
    if candidate["area_ratio"] > min(1.0, profile["max_area_ratio"] * 1.08):
        return None

    if target_ratio:
        aspect_ratio_delta = abs(candidate["aspect_ratio"] - target_ratio) / target_ratio
        if aspect_ratio_delta > profile["ratio_tolerance"]:
            return None
        ratio_score = preferred_score(
            candidate["aspect_ratio"],
            target_ratio,
            target_ratio * profile["ratio_tolerance"],
        )
    else:
        ratio_score = 0.6

    area_score = interval_score(
        candidate["area_ratio"],
        profile["min_area_ratio"],
        profile["max_area_ratio"],
    )
    preferred_area_score = preferred_score_asymmetric(
        candidate["area_ratio"],
        profile["preferred_area_ratio"],
        max(profile["preferred_area_ratio"] - profile["min_area_ratio"], 0.08),
        max(profile["max_area_ratio"] - profile["preferred_area_ratio"], 0.08) * 1.5,
    )
    border_score = min(1.0, candidate["border_margin"] / profile["preferred_border_margin"])
    edge_score = candidate["edge_density_on_border"]
    rect_score = candidate["rectangularity"]
    corner_score = candidate["corner_quality"]

    if profile_name == "id_card":
        confidence = (
            0.34 * ratio_score
            + 0.14 * area_score
            + 0.12 * preferred_area_score
            + 0.16 * rect_score
            + 0.12 * corner_score
            + 0.08 * edge_score
            + 0.04 * border_score
        )
    elif profile_name == "hukou":
        confidence = (
            0.14 * ratio_score
            + 0.20 * area_score
            + 0.16 * preferred_area_score
            + 0.19 * rect_score
            + 0.16 * edge_score
            + 0.09 * corner_score
            + 0.06 * border_score
            - 0.16 * candidate["inner_line_density"]
        )
    else:
        confidence = (
            0.26 * area_score
            + 0.20 * preferred_area_score
            + 0.22 * rect_score
            + 0.18 * edge_score
            + 0.10 * corner_score
            + 0.04 * border_score
        )

    if candidate["area_ratio"] > 0.88 and candidate["border_margin"] < 0.01:
        confidence -= 0.25
    if candidate["source"] == "min_rect":
        confidence -= 0.03

    scored = dict(candidate)
    scored["aspect_ratio_delta"] = float(aspect_ratio_delta)
    scored["confidence"] = float(np.clip(confidence, 0.0, 1.0))
    scored["perspective_threshold"] = profile["perspective_threshold"]
    return scored


def select_best_candidate(candidates, profile_name):
    scored = []
    for candidate in candidates:
        result = score_candidate(candidate, profile_name)
        if result is not None:
            scored.append(result)
    if not scored:
        return None

    if profile_name == "hukou":
        foreground_page_candidates = [
            item
            for item in scored
            if item.get("detector") == "foreground_mask"
            and item["area_ratio"] >= 0.55
            and item["rectangularity"] >= 0.90
            and item["corner_quality"] >= 0.72
            and item["edge_density_on_border"] >= 0.75
        ]
        if foreground_page_candidates:
            foreground_page_candidates.sort(
                key=lambda item: (
                    item["area_ratio"],
                    item["edge_density_on_border"],
                    item["corner_quality"],
                    item["confidence"],
                ),
                reverse=True,
            )
            return foreground_page_candidates[0]

    scored.sort(
        key=lambda item: (
            item["confidence"],
            item["edge_density_on_border"],
            item["rectangularity"],
        ),
        reverse=True,
    )
    if profile_name == "hukou":
        best = scored[0]
        if best["area_ratio"] < 0.28:
            large_foreground_candidates = [
                item
                for item in scored[1:]
                if item.get("detector") == "foreground_mask"
                and item["area_ratio"] >= 0.82
                and item["rectangularity"] >= 0.94
                and item["corner_quality"] >= 0.90
            ]
            if large_foreground_candidates:
                large_foreground_candidates.sort(
                    key=lambda item: (
                        item["area_ratio"],
                        item["confidence"],
                        item["rectangularity"],
                    ),
                    reverse=True,
                )
                if large_foreground_candidates[0]["confidence"] >= best["confidence"] - 0.40:
                    return large_foreground_candidates[0]
    if profile_name == "id_card":
        best = scored[0]
        if best["area_ratio"] < 0.18:
            larger_card_candidates = [
                item
                for item in scored[1:]
                if item["area_ratio"] >= 0.20
                and item["rectangularity"] >= 0.92
                and item["corner_quality"] >= 0.80
            ]
            if larger_card_candidates:
                larger_card_candidates.sort(
                    key=lambda item: (
                        item["confidence"],
                        item["area_ratio"],
                        item["edge_density_on_border"],
                    ),
                    reverse=True,
                )
                if larger_card_candidates[0]["confidence"] >= best["confidence"] - 0.18:
                    return larger_card_candidates[0]
    return scored[0]


def crop_with_fallback(orig, candidate, *, allow_perspective, expand_ratio, profile_name):
    meta = {"crop_mode": "original"}
    if candidate is None:
        return orig.copy(), meta

    expand_px = max(4, int(min(orig.shape[:2]) * expand_ratio))
    expanded = expand_quad(candidate["points_orig"], expand_px, orig.shape)
    if allow_perspective and candidate["confidence"] >= candidate["perspective_threshold"]:
        warped = four_point_transform(orig, expanded)
        warped = normalize_output_orientation(warped, profile_name)
        if is_valid_perspective_result(warped, profile_name):
            return warped, {"crop_mode": "perspective"}

    x1 = int(np.floor(np.min(expanded[:, 0])))
    y1 = int(np.floor(np.min(expanded[:, 1])))
    x2 = int(np.ceil(np.max(expanded[:, 0])))
    y2 = int(np.ceil(np.max(expanded[:, 1])))
    h, w = orig.shape[:2]
    x1 = int(np.clip(x1, 0, w - 1))
    y1 = int(np.clip(y1, 0, h - 1))
    x2 = int(np.clip(x2, x1 + 1, w))
    y2 = int(np.clip(y2, y1 + 1, h))

    if (x2 - x1) >= MIN_CROP_DIM and (y2 - y1) >= MIN_CROP_DIM:
        cropped = orig[y1:y2, x1:x2].copy()
        cropped = normalize_output_orientation(cropped, profile_name)
        return cropped, {"crop_mode": "rect"}
    return orig.copy(), meta


def enhance_document_output_if_needed(image):
    return apply_low_light_enhancement_if_needed(image, stage="export")


def trim_to_target_ratio(image, target_ratio, max_trim_fraction=0.18):
    """裁剪后修剪：如果长宽比偏离目标，沿过长的轴用投影法找到内容边界并修剪。"""
    if target_ratio is None:
        return image

    h, w = image.shape[:2]
    current_ratio = max(h, w) / float(max(1, min(h, w)))
    if current_ratio <= target_ratio * 1.08:
        return image

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    if w >= h:
        target_w = max(MIN_CROP_DIM, int(round(h * target_ratio)))
        if target_w >= w:
            return image
        trim_total = w - target_w
        if trim_total > w * max_trim_fraction:
            target_w = w - int(w * max_trim_fraction)
        col_sums = binary.astype(np.float64).sum(axis=0)
        kernel = np.ones(max(3, w // 60), dtype=np.float64)
        col_sums = np.convolve(col_sums, kernel / kernel.sum(), mode="same")
        peak = float(col_sums.max())
        if peak <= 0:
            return image
        threshold = peak * 0.08
        content_cols = np.where(col_sums > threshold)[0]
        if len(content_cols) == 0:
            return image
        content_center = (int(content_cols[0]) + int(content_cols[-1])) // 2
        half = target_w // 2
        left = max(0, content_center - half)
        right = min(w, left + target_w)
        left = max(0, right - target_w)
        if right - left < MIN_CROP_DIM:
            return image
        return image[:, left:right].copy()
    else:
        target_h = max(MIN_CROP_DIM, int(round(w * target_ratio)))
        if target_h >= h:
            return image
        trim_total = h - target_h
        if trim_total > h * max_trim_fraction:
            target_h = h - int(h * max_trim_fraction)
        row_sums = binary.astype(np.float64).sum(axis=1)
        kernel = np.ones(max(3, h // 60), dtype=np.float64)
        row_sums = np.convolve(row_sums, kernel / kernel.sum(), mode="same")
        peak = float(row_sums.max())
        if peak <= 0:
            return image
        threshold = peak * 0.08
        content_rows = np.where(row_sums > threshold)[0]
        if len(content_rows) == 0:
            return image
        content_center = (int(content_rows[0]) + int(content_rows[-1])) // 2
        half = target_h // 2
        top = max(0, content_center - half)
        bottom = min(h, top + target_h)
        top = max(0, bottom - target_h)
        if bottom - top < MIN_CROP_DIM:
            return image
        return image[top:bottom, :].copy()


def log_crop_decision(profile_name, meta):
    selected = meta.get("selected_candidate") or {}
    print(
        "[material_crop] "
        f"profile={profile_name} "
        f"mode={meta.get('crop_mode', 'original')} "
        f"analysis_enhanced={meta.get('analysis_enhancement_enabled', False)} "
        f"export_enhanced={meta.get('export_enhancement_enabled', False)} "
        f"candidates={meta.get('candidate_count', 0)} "
        f"score={selected.get('confidence', 0)}"
    )


def auto_crop_with_profile(image, profile_name, expand_ratio=None, return_meta=False, allow_perspective=None, expand_level=None, skip_ratio_trim=False, canny_scale=1.0):
    try:
        profile = CROP_PROFILES[profile_name]
        analysis_max_side = ANALYSIS_MAX_SIDES.get(profile_name, ANALYSIS_MAX_SIDE)
        analysis_image, gray, preprocess_meta, scale = prepare_analysis_image(
            image,
            enable_low_light=profile.get("analysis_enhancement", True),
            max_side=analysis_max_side,
        )

        line_mask = None
        if profile.get("allow_table_suppression"):
            gray, line_mask = suppress_table_lines_for_hukou(gray)

        candidates = detect_document_candidates(
            analysis_image,
            gray,
            profile_name,
            scale=scale,
            line_mask=line_mask,
            canny_scale=canny_scale,
        )
        best = select_best_candidate(candidates, profile_name)
        _allow_perspective = allow_perspective if allow_perspective is not None else profile.get("allow_perspective", True)
        _expand_ratio = expand_ratio if expand_ratio is not None else profile["expand_ratio"]
        if expand_level == "tight":
            _expand_ratio *= 0.3
        elif expand_level == "loose":
            _expand_ratio *= 2.5
        elif expand_level == "x-loose":
            _expand_ratio *= 4.0
        cropped, crop_meta = crop_with_fallback(
            image,
            best,
            allow_perspective=_allow_perspective,
            expand_ratio=_expand_ratio,
            profile_name=profile_name,
        )

        if not skip_ratio_trim and crop_meta["crop_mode"] != "original" and profile.get("target_ratio"):
            cropped = trim_to_target_ratio(cropped, profile["target_ratio"])

        export_meta = {"enabled": False, "stage": "export"}
        if profile.get("export_enhancement", True):
            cropped, export_meta = enhance_document_output_if_needed(cropped)

        meta = {
            "profile": profile_name,
            "candidate_count": len(candidates),
            "selected_candidate": summarize_candidate(best),
            "crop_mode": crop_meta["crop_mode"],
            "analysis_enhancement_enabled": preprocess_meta.get("enabled", False),
            "export_enhancement_enabled": export_meta.get("enabled", False),
        }
        log_crop_decision(profile_name, meta)
        if return_meta:
            return cropped, meta
        return cropped
    except Exception as exc:
        print(f"Auto crop error ({profile_name}):", exc)
        if return_meta:
            return image, {
                "profile": profile_name,
                "candidate_count": 0,
                "selected_candidate": None,
                "crop_mode": "original",
                "analysis_enhancement_enabled": False,
                "export_enhancement_enabled": False,
            }
        return image


def auto_crop_id_card(image, return_meta=False, allow_perspective=None, expand_level=None, skip_ratio_trim=False, canny_scale=1.0):
    return auto_crop_with_profile(image, "id_card", return_meta=return_meta, allow_perspective=allow_perspective, expand_level=expand_level, skip_ratio_trim=skip_ratio_trim, canny_scale=canny_scale)


def auto_crop_hukou_page(image, expand_ratio=None, return_meta=False, allow_perspective=None, expand_level=None, skip_ratio_trim=False, canny_scale=1.0):
    return auto_crop_with_profile(image, "hukou", expand_ratio=expand_ratio, return_meta=return_meta, allow_perspective=allow_perspective, expand_level=expand_level, skip_ratio_trim=skip_ratio_trim, canny_scale=canny_scale)


def auto_crop_diploma(image, return_meta=False, allow_perspective=None, expand_level=None, skip_ratio_trim=False):
    return auto_crop_with_profile(image, "diploma", return_meta=return_meta, allow_perspective=allow_perspective, expand_level=expand_level, skip_ratio_trim=skip_ratio_trim)


def auto_crop_document(image):
    return auto_crop_diploma(image)


def read_cv_image(path):
    try:
        from PIL import Image, ImageOps
        with Image.open(path) as pil_img:
            # 自动应用 EXIF 旋转属性
            pil_img = ImageOps.exif_transpose(pil_img)
            img_np = np.array(pil_img)
            if len(img_np.shape) == 2:  # 灰度图
                return cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
            elif img_np.shape[2] == 4:  # 带透明通道的 RGBA
                return cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
            else:  # 标准 RGB
                return cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"[read_cv_image] Pillow 读取/校正 EXIF 失败，退回默认读取: {e}")
        img_np = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(img_np, cv2.IMREAD_COLOR)


def write_cv_image(path, img, quality=95):
    ret, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if ret:
        with open(path, "wb") as file_obj:
            buf.tofile(file_obj)


def create_a4_canvas():
    return np.full((A4_HEIGHT, A4_WIDTH, 3), 255, dtype=np.uint8)


def resize_document_to_width(image, target_width):
    h, w = image.shape[:2]
    target_width = max(MIN_CROP_DIM, int(target_width))
    target_height = max(MIN_CROP_DIM, int(round(h * (target_width / float(w)))))
    resized = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)
    return resized, target_height


def resize_document_to_fit(image, max_width, max_height):
    h, w = image.shape[:2]
    max_width = max(MIN_CROP_DIM, int(max_width))
    max_height = max(MIN_CROP_DIM, int(max_height))
    scale = min(max_width / float(w), max_height / float(h))
    target_width = max(MIN_CROP_DIM, int(round(w * scale)))
    target_height = max(MIN_CROP_DIM, int(round(h * scale)))
    resized = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)
    return resized, target_width, target_height


def _size_details(image, key_prefix="size"):
    h, w = image.shape[:2]
    return {
        f"{key_prefix}_width": int(w),
        f"{key_prefix}_height": int(h),
    }


def process_personal_photo(input_path, output_dir, name_prefix, logger=None, adjustments=None):
    """个人照片处理：可选白底替换、旋转、压缩到 1MB 以下

    adjustments 可包含:
        skip_white_bg (bool): 跳过白底替换
        rotate (int): 手动旋转角度 0/90/180/270
        manual_crop_applied (bool): 是否已手动裁剪
    """
    adjustments = adjustments or {}
    scope = "photo"
    temp_bg_path = None
    skip_white_bg = adjustments.get("skip_white_bg", False)
    extra_rotate = int(adjustments.get("rotate", 0) or 0)
    try:
        if logger is not None:
            logger.emit("info", scope, "start", "开始处理个人照片", os.path.basename(input_path))

        # 旋转原图（如果指定了旋转角度）
        effective_path = input_path
        if extra_rotate:
            try:
                img_cv = read_cv_image(input_path)
                if img_cv is not None:
                    img_cv = rotate_image_by_degrees(img_cv, extra_rotate)
                    import tempfile as _tf2
                    temp_rot_fd, temp_rot_path = _tf2.mkstemp(suffix='.jpg')
                    os.close(temp_rot_fd)
                    write_cv_image(temp_rot_path, img_cv)
                    effective_path = temp_rot_path
                    if logger is not None:
                        logger.emit("info", scope, "rotate", f"照片已旋转 {extra_rotate}°", "")
            except Exception as rot_exc:
                print(f"[photo] 旋转失败，使用原图: {rot_exc}")

        # 白底替换（可选）
        if not skip_white_bg:
            try:
                from services.image_service import change_id_photo_bg
                import tempfile as _tf
                temp_fd, temp_bg_path = _tf.mkstemp(suffix='.jpg')
                os.close(temp_fd)
                result_path = change_id_photo_bg(effective_path, temp_bg_path)
                if result_path == temp_bg_path and os.path.exists(temp_bg_path):
                    effective_path = temp_bg_path
                    if logger is not None:
                        logger.emit("info", scope, "bg_remove", "个人照片已替换为白底", "使用 rembg 完成背景白色替换")
                else:
                    if logger is not None:
                        logger.emit("warning", scope, "bg_remove", "白底替换跳过", "rembg 依赖不可用，使用原图")
            except Exception as bg_exc:
                print(f"[photo] 白底处理失败，使用原图: {bg_exc}")
                if logger is not None:
                    logger.emit("warning", scope, "bg_remove", "白底替换失败", f"降级使用原图: {bg_exc}")
        else:
            if logger is not None:
                logger.emit("info", scope, "bg_remove", "白底处理已跳过", "用户手动关闭了白底处理功能")

        img = Image.open(effective_path)
        if img.mode != "RGB":
            img = img.convert("RGB")

        output_path = os.path.join(output_dir, f"{name_prefix}-个人照片.jpg")
        if logger is not None:
            logger.emit(
                "info",
                scope,
                "read_input",
                "个人照片读取成功",
                "已读取个人照片，准备压缩输出",
                details={
                    "input_width": int(img.width),
                    "input_height": int(img.height),
                },
            )

        quality = 95
        while True:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            size_kb = len(buffer.getvalue()) / 1024
            if size_kb < 1000 or quality <= 30:
                with open(output_path, "wb") as file_obj:
                    file_obj.write(buffer.getvalue())
                if logger is not None:
                    logger.emit(
                        "success",
                        scope,
                        "write_output",
                        "个人照片输出成功",
                        "已生成符合大小要求的个人照片",
                        details={
                            "output_path": output_path,
                            "jpeg_quality": quality,
                            "output_kb": round(size_kb, 1),
                        },
                    )
                break
            quality -= 10
        return _build_process_result(scope, True, output_path=output_path)
    except Exception as exc:
        print("Error processing personal photo:", exc)
        if logger is not None:
            logger.emit(
                "error",
                scope,
                "write_output",
                "个人照片处理失败",
                "压缩或写出个人照片时发生错误",
                details={"input_path": input_path},
            )
        return _build_process_result(scope, False, error=str(exc))
    finally:
        if temp_bg_path and os.path.exists(temp_bg_path):
            try:
                os.remove(temp_bg_path)
            except Exception:
                pass


def process_diploma(input_path, output_dir, name_prefix, adjustments=None, logger=None):
    """学历证书照片，裁边，A4白色底，水平居中，宽两边留 1cm，水平校正"""
    adjustments = adjustments or {}
    crop_mode = adjustments.get("crop_mode", "auto")
    extra_rotate = int(adjustments.get("rotate", 0) or 0)
    expand_level = adjustments.get("expand_level")
    skip_ratio_trim = adjustments.get("skip_ratio_trim", False)
    manual_crop_applied = adjustments.get("manual_crop_applied", False)
    tag = "[diploma]"
    scope = "diploma"
    try:
        print(f"{tag} 开始处理: {os.path.basename(input_path)}")
        if logger is not None:
            logger.emit("info", scope, "start", "开始处理学历证书", os.path.basename(input_path))
        img = read_cv_image(input_path)
        if img is None:
            print(f"{tag} 读图失败，终止")
            if logger is not None:
                logger.emit("error", scope, "read_input", "学历证书读取失败", "未能读取学历证书图片")
            return _build_process_result(scope, False, error="read failed")
        h0, w0 = img.shape[:2]
        print(f"{tag} 原图尺寸: {w0}x{h0}")
        if logger is not None:
            logger.emit(
                "info",
                scope,
                "read_input",
                "学历证书读取成功",
                "已读取学历证书原图",
                details=_size_details(img, "input"),
            )

        if manual_crop_applied:
            if logger is not None:
                logger.emit(
                    "info",
                    scope,
                    "auto_crop",
                    "使用手动确认的裁剪区域",
                    "该图片已按手动框选结果裁好，跳过自动裁剪",
                    details={"crop_mode": crop_mode},
                )
        elif crop_mode == "none":
            if logger is not None:
                logger.emit(
                    "info",
                    scope,
                    "auto_crop",
                    "已按不裁剪模式处理",
                    "本次保留学历证书原图，不执行自动裁剪",
                    details={"crop_mode": crop_mode},
                )
        else:
            _allow_persp = None if crop_mode == "auto" else False
            img, meta = auto_crop_diploma(img, return_meta=True, allow_perspective=_allow_persp, expand_level=expand_level, skip_ratio_trim=skip_ratio_trim)
            sel = meta.get("selected_candidate") or {}
            hc, wc = img.shape[:2]
            print(
                f"{tag} 裁剪后: {wc}x{hc}  "
                f"mode={meta.get('crop_mode')}  "
                f"detector={sel.get('detector', 'N/A')}  "
                f"area_ratio={sel.get('area_ratio', 0):.3f}  "
                f"confidence={sel.get('confidence', 0):.3f}  "
                f"edge_density={sel.get('edge_density_on_border', 0):.3f}  "
                f"analysis_enhanced={meta.get('analysis_enhancement_enabled', False)}"
            )
            if logger is not None:
                logger.emit(
                    "success",
                    scope,
                    "auto_crop",
                    "学历证书裁边完成",
                    "已完成学历证书裁边并准备排版",
                    details={
                        "crop_mode": meta.get("crop_mode"),
                        "detector": sel.get("detector", "N/A"),
                        "confidence": sel.get("confidence", 0),
                        "area_ratio": sel.get("area_ratio", 0),
                        **_size_details(img, "cropped"),
                    },
                )

        if extra_rotate:
            img = rotate_image_by_degrees(img, extra_rotate)
            print(f"{tag} 额外旋转 {extra_rotate}°")
            if logger is not None:
                logger.emit(
                    "info",
                    scope,
                    "normalize_orientation",
                    f"学历证书额外旋转 {extra_rotate}°",
                    "已按人工设置旋转学历证书方向",
                    details={"rotation": int(extra_rotate)},
                )

        max_width = A4_WIDTH - 2 * CM_IN_PX
        max_height = A4_HEIGHT - 2 * CM_IN_PX
        img_resized, target_width, target_height = resize_document_to_fit(img, max_width, max_height)
        print(f"{tag} 缩放适配 A4 画布: 宽={target_width}px  高={target_height}px")
        if logger is not None:
            logger.emit(
                "info",
                scope,
                "layout_a4",
                "学历证书已适配 A4 版面",
                "已按 A4 可用区域等比缩放学历证书，避免底部被截断",
                details={"target_width": target_width, "target_height": target_height, "max_width": max_width, "max_height": max_height},
            )

        canvas = create_a4_canvas()
        x_offset = max(0, (A4_WIDTH - target_width) // 2)
        y_offset = max(0, (A4_HEIGHT - target_height) // 2)

        canvas[y_offset:y_offset + target_height, x_offset:x_offset + target_width] = img_resized
        print(f"{tag} 排版位置: x={x_offset}  y={y_offset}")

        output_path = os.path.join(output_dir, f"{name_prefix}-学历证书.jpg")
        write_cv_image(output_path, canvas)
        print(f"{tag} 已输出: {output_path}")
        if logger is not None:
            logger.emit(
                "success",
                scope,
                "write_output",
                "学历证书输出成功",
                "已生成学历证书报名材料图片",
                details={
                    "output_path": output_path,
                    "canvas_width": A4_WIDTH,
                    "canvas_height": A4_HEIGHT,
                },
            )
        return _build_process_result(scope, True, output_path=output_path)
    except Exception as exc:
        print(f"{tag} 处理失败:", exc)
        if logger is not None:
            logger.emit("error", scope, "write_output", "学历证书处理失败", "学历证书生成过程中发生错误")
        return _build_process_result(scope, False, error=str(exc))


def process_id_cards(front_path, back_path, output_dir, name_prefix, adjustments=None, logger=None):
    adjustments = adjustments or {}
    crop_mode = adjustments.get("crop_mode", "auto")
    front_rotate = int(adjustments.get("front_rotate", 0) or 0)
    back_rotate = int(adjustments.get("back_rotate", 0) or 0)
    expand_level = adjustments.get("expand_level")
    skip_ratio_trim = adjustments.get("skip_ratio_trim", False)
    front_manual_crop_applied = adjustments.get("front_manual_crop_applied", False)
    back_manual_crop_applied = adjustments.get("back_manual_crop_applied", False)
    # canny_scale < 1 提高边缘灵敏度（适合大面积纯黑背景 + 白色卡片），> 1 则降低噪声
    canny_scale = float(adjustments.get("canny_scale", 1.0))
    tag = "[id-card]"
    scope = "id_card"
    try:
        canvas = create_a4_canvas()
        if logger is not None:
            logger.emit("info", scope, "start", "开始处理身份证", "准备生成身份证报名材料")

        target_width = A4_WIDTH // 2
        x_offset = (A4_WIDTH - target_width) // 2

        front_img, back_img = None, None
        front_h, back_h = 0, 0

        if front_path and os.path.exists(front_path):
            front_img = read_cv_image(front_path)
            if front_img is not None:
                h0, w0 = front_img.shape[:2]
                print(f"{tag}[正面] 原图: {w0}x{h0}")
                if logger is not None:
                    logger.emit("info", "id_card_front", "read_input", "身份证正面读取成功", "已读取身份证正面原图", details=_size_details(front_img, "input"))
                if front_manual_crop_applied:
                    if logger is not None:
                        logger.emit("info", "id_card_front", "auto_crop", "使用手动确认裁剪区域", "身份证正面已按手动点位裁好，跳过自动裁剪", details={"crop_mode": crop_mode})
                elif crop_mode != "none":
                    _allow_persp = None if crop_mode == "auto" else False
                    front_img, meta = auto_crop_id_card(front_img, return_meta=True, allow_perspective=_allow_persp, expand_level=expand_level, skip_ratio_trim=skip_ratio_trim, canny_scale=canny_scale)
                    sel = meta.get("selected_candidate") or {}
                    hc, wc = front_img.shape[:2]
                    print(
                        f"{tag}[正面] 裁剪后: {wc}x{hc}  "
                        f"mode={meta.get('crop_mode')}  "
                        f"detector={sel.get('detector', 'N/A')}  "
                        f"area_ratio={sel.get('area_ratio', 0):.3f}  "
                        f"confidence={sel.get('confidence', 0):.3f}"
                    )
                    if logger is not None:
                        logger.emit(
                            "success",
                            "id_card_front",
                            "auto_crop",
                            "身份证正面裁边完成",
                            "已完成身份证正面裁边",
                            details={
                                "crop_mode": meta.get("crop_mode"),
                                "detector": sel.get("detector", "N/A"),
                                "confidence": sel.get("confidence", 0),
                                "area_ratio": sel.get("area_ratio", 0),
                                **_size_details(front_img, "cropped"),
                            },
                        )
                elif logger is not None:
                    logger.emit("info", "id_card_front", "auto_crop", "已按不裁剪模式处理", "本次保留身份证正面原图", details={"crop_mode": crop_mode})
                hc, wc = front_img.shape[:2]
                if front_rotate:
                    front_img = rotate_image_by_degrees(front_img, front_rotate)
                    print(f"{tag}[正面] 额外旋转 {front_rotate}°")
                    if logger is not None:
                        logger.emit("info", "id_card_front", "normalize_orientation", f"身份证正面额外旋转 {front_rotate}°", "已按人工设置旋转身份证正面方向", details={"rotation": int(front_rotate)})
                if not front_manual_crop_applied and not front_rotate:
                    front_img = normalize_id_card_side(front_img, "front")
                hn, wn = front_img.shape[:2]
                if (hn, wn) != (hc, wc):
                    print(f"{tag}[正面] 方向正规化后: {wn}x{hn}")
                    if logger is not None:
                        logger.emit("info", "id_card_front", "normalize_orientation", "身份证正面方向已校正", "已根据内容特征校正身份证正面方向", details=_size_details(front_img, "normalized"))
                front_img, front_h = resize_document_to_width(front_img, target_width)
                print(f"{tag}[正面] 缩放后: {target_width}x{front_h}")
                if logger is not None:
                    logger.emit("info", "id_card_front", "layout_a4", "身份证正面已适配版式", "已缩放身份证正面以便排入 A4", details={"target_width": target_width, "target_height": front_h})

        if back_path and os.path.exists(back_path):
            back_img = read_cv_image(back_path)
            if back_img is not None:
                h0, w0 = back_img.shape[:2]
                print(f"{tag}[反面] 原图: {w0}x{h0}")
                if logger is not None:
                    logger.emit("info", "id_card_back", "read_input", "身份证反面读取成功", "已读取身份证反面原图", details=_size_details(back_img, "input"))
                if back_manual_crop_applied:
                    if logger is not None:
                        logger.emit("info", "id_card_back", "auto_crop", "使用手动确认裁剪区域", "身份证反面已按手动点位裁好，跳过自动裁剪", details={"crop_mode": crop_mode})
                elif crop_mode != "none":
                    _allow_persp = None if crop_mode == "auto" else False
                    back_img, meta = auto_crop_id_card(back_img, return_meta=True, allow_perspective=_allow_persp, expand_level=expand_level, skip_ratio_trim=skip_ratio_trim, canny_scale=canny_scale)
                    sel = meta.get("selected_candidate") or {}
                    hc, wc = back_img.shape[:2]
                    print(
                        f"{tag}[反面] 裁剪后: {wc}x{hc}  "
                        f"mode={meta.get('crop_mode')}  "
                        f"detector={sel.get('detector', 'N/A')}  "
                        f"area_ratio={sel.get('area_ratio', 0):.3f}  "
                        f"confidence={sel.get('confidence', 0):.3f}"
                    )
                    if logger is not None:
                        logger.emit(
                            "success",
                            "id_card_back",
                            "auto_crop",
                            "身份证反面裁边完成",
                            "已完成身份证反面裁边",
                            details={
                                "crop_mode": meta.get("crop_mode"),
                                "detector": sel.get("detector", "N/A"),
                                "confidence": sel.get("confidence", 0),
                                "area_ratio": sel.get("area_ratio", 0),
                                **_size_details(back_img, "cropped"),
                            },
                        )
                elif logger is not None:
                    logger.emit("info", "id_card_back", "auto_crop", "已按不裁剪模式处理", "本次保留身份证反面原图", details={"crop_mode": crop_mode})
                if back_rotate:
                    back_img = rotate_image_by_degrees(back_img, back_rotate)
                    print(f"{tag}[反面] 额外旋转 {back_rotate}°")
                    if logger is not None:
                        logger.emit("info", "id_card_back", "normalize_orientation", f"身份证反面额外旋转 {back_rotate}°", "已按人工设置旋转身份证反面方向", details={"rotation": int(back_rotate)})
                if not back_manual_crop_applied and not back_rotate:
                    back_img = normalize_id_card_side(back_img, "back")
                back_img, back_h = resize_document_to_width(back_img, target_width)
                print(f"{tag}[反面] 缩放后: {target_width}x{back_h}")
                if logger is not None:
                    logger.emit("info", "id_card_back", "layout_a4", "身份证反面已适配版式", "已缩放身份证反面以便排入 A4", details={"target_width": target_width, "target_height": back_h})

        gap = max(front_h, back_h) // 2 if max(front_h, back_h) > 0 else 0
        total_height = front_h + back_h + gap
        max_height = A4_HEIGHT - 2 * CM_IN_PX
        print(f"{tag} 拼接规划: front_h={front_h}  back_h={back_h}  gap={gap}  total={total_height}  max={max_height}")

        if total_height > max_height and target_width > MIN_CROP_DIM:
            fit_scale = max_height / float(total_height)
            target_width = max(MIN_CROP_DIM, int(target_width * fit_scale))
            x_offset = (A4_WIDTH - target_width) // 2
            print(f"{tag} 高度超出，整体缩放: scale={fit_scale:.3f}  新宽={target_width}")

            if front_img is not None:
                front_img, front_h = resize_document_to_width(front_img, target_width)
            if back_img is not None:
                back_img, back_h = resize_document_to_width(back_img, target_width)

            gap = max(20, int(max(front_h, back_h) * 0.25)) if max(front_h, back_h) > 0 else 0
            total_height = front_h + back_h + gap
            print(f"{tag} 缩放后: front_h={front_h}  back_h={back_h}  gap={gap}  total={total_height}")

        if front_img is not None and back_img is not None:
            y_front = (A4_HEIGHT - total_height) // 2
            y_back = y_front + front_h + gap
            print(f"{tag} 排版: 正面 y={y_front}  反面 y={y_back}  x={x_offset}")
            canvas[y_front:y_front + front_h, x_offset:x_offset + target_width] = front_img
            canvas[y_back:y_back + back_h, x_offset:x_offset + target_width] = back_img
        elif front_img is not None:
            y_front = (A4_HEIGHT - front_h) // 2
            print(f"{tag} 排版: 仅正面 y={y_front}  x={x_offset}")
            canvas[y_front:y_front + front_h, x_offset:x_offset + target_width] = front_img
        elif back_img is not None:
            y_back = (A4_HEIGHT - back_h) // 2
            print(f"{tag} 排版: 仅反面 y={y_back}  x={x_offset}")
            canvas[y_back:y_back + back_h, x_offset:x_offset + target_width] = back_img

        if front_img is not None or back_img is not None:
            output_path = os.path.join(output_dir, f"{name_prefix}-身份证.jpg")
            write_cv_image(output_path, canvas)
            print(f"{tag} 已输出: {output_path}")
            if logger is not None:
                logger.emit(
                    "success",
                    scope,
                    "write_output",
                    "身份证输出成功",
                    "已生成身份证报名材料图片",
                    details={"output_path": output_path},
                )
            return _build_process_result(scope, True, output_path=output_path)
        if logger is not None:
            logger.emit("error", scope, "write_output", "身份证输出失败", "未读取到可用的身份证图片，无法生成输出")
        return _build_process_result(scope, False, error="no readable id card images")
    except Exception as exc:
        print(f"{tag} 处理失败:", exc)
        if logger is not None:
            logger.emit("error", scope, "write_output", "身份证处理失败", "身份证生成过程中发生错误")
        return _build_process_result(scope, False, error=str(exc))


def process_hukou(residence_path, personal_path, output_dir, name_prefix, adjustments=None, logger=None):
    adjustments = adjustments or {}
    crop_mode = adjustments.get("crop_mode", "auto")
    home_rotate = int(adjustments.get("home_rotate", 0) or 0)
    personal_rotate = int(adjustments.get("personal_rotate", 0) or 0)
    expand_level = adjustments.get("expand_level")
    skip_ratio_trim = adjustments.get("skip_ratio_trim", False)
    home_manual_crop_applied = adjustments.get("home_manual_crop_applied", False)
    personal_manual_crop_applied = adjustments.get("personal_manual_crop_applied", False)
    canny_scale = float(adjustments.get("canny_scale", 1.0))
    tag = "[hukou]"
    scope = "hukou"
    try:
        canvas = create_a4_canvas()
        if logger is not None:
            logger.emit("info", scope, "start", "开始处理户口本", "准备生成户口本报名材料")

        target_width = A4_WIDTH - 4 * CM_IN_PX
        x_offset = 2 * CM_IN_PX

        img1, img2 = None, None
        h1, h2 = 0, 0

        if residence_path and os.path.exists(residence_path):
            print(f"{tag}[首页] 开始处理: {os.path.basename(residence_path)}")
            img1 = read_cv_image(residence_path)
            if img1 is not None:
                if logger is not None:
                    logger.emit("info", "hukou_home", "read_input", "户口本首页读取成功", "已读取户口本首页原图", details=_size_details(img1, "input"))
                if logger is not None and home_manual_crop_applied:
                    logger.emit("info", "hukou_home", "auto_crop", "使用手动确认裁剪区域", "户口本首页已按手动点位裁好，跳过自动裁边和方向校正，以用户手动结果为准", details={"crop_mode": crop_mode})
                img1 = prepare_hukou_output_page(
                    img1,
                    "home",
                    crop_mode=crop_mode,
                    expand_level=expand_level,
                    skip_ratio_trim=skip_ratio_trim,
                    canny_scale=canny_scale,
                    manual_crop_applied=home_manual_crop_applied,
                )
                if logger is not None:
                    logger.emit("success", "hukou_home", "auto_crop", "户口本首页处理完成", "已完成户口本首页裁边/方向校正准备排版", details={"crop_mode": crop_mode, **_size_details(img1, "processed")})
                if home_rotate:
                    img1 = rotate_image_by_degrees(img1, home_rotate)
                    print(f"{tag}[首页] 额外旋转 {home_rotate}°")
                    if logger is not None:
                        logger.emit("info", "hukou_home", "normalize_orientation", f"户口本首页额外旋转 {home_rotate}°", "已按人工设置旋转户口本首页方向", details={"rotation": int(home_rotate)})
                img1, h1 = resize_document_to_width(img1, target_width)
                print(f"{tag}[首页] 缩放后: {target_width}x{h1}")
                if logger is not None:
                    logger.emit("info", "hukou_home", "layout_a4", "户口本首页已适配版式", "已缩放户口本首页以便排入 A4", details={"target_width": target_width, "target_height": h1})

        if personal_path and os.path.exists(personal_path):
            print(f"{tag}[本人页] 开始处理: {os.path.basename(personal_path)}")
            img2 = read_cv_image(personal_path)
            if img2 is not None:
                if logger is not None:
                    logger.emit("info", "hukou_personal", "read_input", "户口本人页读取成功", "已读取户口本人页原图", details=_size_details(img2, "input"))
                if logger is not None and personal_manual_crop_applied:
                    logger.emit("info", "hukou_personal", "auto_crop", "使用手动确认裁剪区域", "户口本人页已按手动点位裁好，跳过自动裁边和方向校正，以用户手动结果为准", details={"crop_mode": crop_mode})
                img2 = prepare_hukou_output_page(
                    img2,
                    "personal",
                    crop_mode=crop_mode,
                    expand_level=expand_level,
                    skip_ratio_trim=skip_ratio_trim,
                    canny_scale=canny_scale,
                    manual_crop_applied=personal_manual_crop_applied,
                )
                if logger is not None:
                    logger.emit("success", "hukou_personal", "auto_crop", "户口本人页处理完成", "已完成户口本人页裁边/方向校正准备排版", details={"crop_mode": crop_mode, **_size_details(img2, "processed")})
                if personal_rotate:
                    img2 = rotate_image_by_degrees(img2, personal_rotate)
                    print(f"{tag}[本人页] 额外旋转 {personal_rotate}°")
                    if logger is not None:
                        logger.emit("info", "hukou_personal", "normalize_orientation", f"户口本人页额外旋转 {personal_rotate}°", "已按人工设置旋转户口本人页方向", details={"rotation": int(personal_rotate)})
                img2, h2 = resize_document_to_width(img2, target_width)
                print(f"{tag}[本人页] 缩放后: {target_width}x{h2}")
                if logger is not None:
                    logger.emit("info", "hukou_personal", "layout_a4", "户口本人页已适配版式", "已缩放户口本人页以便排入 A4", details={"target_width": target_width, "target_height": h2})

        gap = CM_IN_PX
        total_height = h1 + h2 + gap
        max_height = A4_HEIGHT - 2 * CM_IN_PX
        print(f"{tag} 拼接规划: home_h={h1}  personal_h={h2}  gap={gap}  total={total_height}  max={max_height}")

        if total_height > max_height and target_width > MIN_CROP_DIM:
            fit_scale = max_height / float(total_height)
            target_width = max(MIN_CROP_DIM, int(target_width * fit_scale))
            x_offset = (A4_WIDTH - target_width) // 2
            print(f"{tag} 高度超出，整体缩放: scale={fit_scale:.3f}  新宽={target_width}")

            if img1 is not None:
                img1, h1 = resize_document_to_width(img1, target_width)
            if img2 is not None:
                img2, h2 = resize_document_to_width(img2, target_width)

            gap = max(20, int(CM_IN_PX * fit_scale))
            total_height = h1 + h2 + gap
            print(f"{tag} 缩放后: home_h={h1}  personal_h={h2}  gap={gap}  total={total_height}")

        if img1 is not None and img2 is not None:
            y_start = (A4_HEIGHT - total_height) // 2
            print(f"{tag} 排版: 首页 y={y_start}  本人页 y={y_start + h1 + gap}  x={x_offset}")
            canvas[y_start:y_start + h1, x_offset:x_offset + target_width] = img1
            canvas[y_start + h1 + gap:y_start + h1 + gap + h2, x_offset:x_offset + target_width] = img2
        elif img1 is not None:
            y_start = (A4_HEIGHT - h1) // 2
            print(f"{tag} 排版: 仅首页 y={y_start}  x={x_offset}")
            canvas[y_start:y_start + h1, x_offset:x_offset + target_width] = img1
        elif img2 is not None:
            y_start = (A4_HEIGHT - h2) // 2
            print(f"{tag} 排版: 仅本人页 y={y_start}  x={x_offset}")
            canvas[y_start:y_start + h2, x_offset:x_offset + target_width] = img2

        if img1 is not None or img2 is not None:
            output_path = os.path.join(output_dir, f"{name_prefix}-户口本.jpg")
            write_cv_image(output_path, canvas)
            print(f"{tag} 已输出: {output_path}")
            if logger is not None:
                logger.emit(
                    "success",
                    scope,
                    "write_output",
                    "户口本输出成功",
                    "已生成户口本报名材料图片",
                    details={"output_path": output_path},
                )
            return _build_process_result(scope, True, output_path=output_path)
        if logger is not None:
            logger.emit("error", scope, "write_output", "户口本输出失败", "未读取到可用的户口本图片，无法生成输出")
        return _build_process_result(scope, False, error="no readable hukou images")
    except Exception as exc:
        print(f"{tag} 处理失败:", exc)
        if logger is not None:
            logger.emit("error", scope, "write_output", "户口本处理失败", "户口本生成过程中发生错误")
        return _build_process_result(scope, False, error=str(exc))


def process_renewal_certificate_pages(info_page_path, records_page_path, output_dir, name_prefix, logger=None):
    scope = "renewal_certificate"
    tag = "[renewal-certificate]"
    try:
        canvas = create_a4_canvas()
        if logger is not None:
            logger.emit("info", scope, "start", "开始处理复审材料", "准备拼接原证件两页照片")

        page_specs = [
            (info_page_path, "certificate_info_page", "原证件说明和个人信息页"),
            (records_page_path, "certificate_records_page", "原证件作业项目和聘用记录页"),
        ]
        readable_pages = []
        for path, page_scope, label in page_specs:
            if not path or not os.path.exists(path):
                continue
            image = read_cv_image(path)
            if image is None:
                if logger is not None:
                    logger.emit("warning", page_scope, "read_input", f"{label}读取失败", "未能读取该原证件照片")
                continue
            if logger is not None:
                logger.emit("info", page_scope, "read_input", f"{label}读取成功", "已读取原证件照片", details=_size_details(image, "input"))
            readable_pages.append((image, page_scope, label))

        if not readable_pages:
            if logger is not None:
                logger.emit("error", scope, "write_output", "复审材料输出失败", "未读取到可用的原证件照片")
            return _build_process_result(scope, False, error="no readable renewal certificate images")

        gap = CM_IN_PX // 2 if len(readable_pages) > 1 else 0
        max_width = A4_WIDTH - 2 * CM_IN_PX
        max_total_height = A4_HEIGHT - 2 * CM_IN_PX
        max_page_height = (max_total_height - gap) // len(readable_pages)

        resized_pages = []
        total_height = gap * (len(readable_pages) - 1)
        for image, page_scope, label in readable_pages:
            resized, width, height = resize_document_to_fit(image, max_width, max_page_height)
            resized_pages.append((resized, width, height, page_scope, label))
            total_height += height
            if logger is not None:
                logger.emit(
                    "info",
                    page_scope,
                    "layout_a4",
                    f"{label}已适配版式",
                    "已缩放原证件照片以便排入 A4",
                    details={"target_width": width, "target_height": height},
                )

        y = max(0, (A4_HEIGHT - total_height) // 2)
        for image, width, height, page_scope, label in resized_pages:
            x = max(0, (A4_WIDTH - width) // 2)
            canvas[y:y + height, x:x + width] = image
            print(f"{tag} 排版: {label} x={x} y={y} w={width} h={height}")
            y += height + gap

        output_path = os.path.join(output_dir, f"{name_prefix}-复审材料.jpg")
        write_cv_image(output_path, canvas)
        if logger is not None:
            logger.emit(
                "success",
                scope,
                "write_output",
                "复审材料输出成功",
                "已生成原证件两页拼接报名材料图片",
                details={
                    "output_path": output_path,
                    "canvas_width": A4_WIDTH,
                    "canvas_height": A4_HEIGHT,
                    "page_count": len(readable_pages),
                },
            )
        return _build_process_result(scope, True, output_path=output_path)
    except Exception as exc:
        print(f"{tag} 处理失败:", exc)
        if logger is not None:
            logger.emit("error", scope, "write_output", "复审材料处理失败", "复审材料生成过程中发生错误")
        return _build_process_result(scope, False, error=str(exc))



def copy_health_form(form_path, output_dir, name_prefix, logger=None):
    scope = "training_form"
    if form_path and os.path.exists(form_path):
        ext = os.path.splitext(form_path)[1]
        output_path = os.path.join(output_dir, f"{name_prefix}-体检表{ext}")
        shutil.copy2(form_path, output_path)
        if logger is not None:
            logger.emit(
                "success",
                scope,
                "write_output",
                "体检表复制成功",
                "已复制体检表到报名材料目录",
                details={"output_path": output_path},
            )
        return _build_process_result(scope, True, output_path=output_path)
    if logger is not None:
        logger.emit("warning", scope, "write_output", "未找到体检表原文件", "本次没有可复制的体检表文件")
    return _build_process_result(scope, False, error="health form missing")


def generate_student_materials(student, base_dir, output_root):
    """
    入口函数，生成学员打包资料
    student: dictionary of student info
    """
    id_card = student.get("id_card", "")
    name = student.get("name", "")
    name_prefix = f"{id_card}-{name}"

    output_dir = os.path.join(output_root, f"{name_prefix}-报名材料")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    logger = MaterialGenerationLogger()
    logger.emit("info", "global", "start", "开始生成报名材料", f"开始为 {name_prefix} 生成报名材料")
    removed_files = cleanup_generated_outputs(output_dir, name_prefix)
    if removed_files:
        logger.emit(
            "info",
            "global",
            "cleanup",
            "已清理旧的报名材料",
            "生成前已移除旧的输出文件，避免混入历史结果",
            details={"removed_count": len(removed_files)},
        )

    def get_abs_path(key):
        rel = student.get(key)
        return os.path.join(base_dir, rel) if rel else None

    results = []
    photo_path = get_abs_path("photo_path")
    if photo_path and os.path.exists(photo_path):
        results.append(process_personal_photo(photo_path, output_dir, name_prefix, logger=logger))

    is_renewal = (
        student.get("training_type") == "special_equipment"
        and student.get("application_type", "new_exam") == "renewal"
    )
    if is_renewal:
        info_page_path = get_abs_path("certificate_info_page_path")
        records_page_path = get_abs_path("certificate_records_page_path")
        if (info_page_path and os.path.exists(info_page_path)) or (
            records_page_path and os.path.exists(records_page_path)
        ):
            results.append(process_renewal_certificate_pages(
                info_page_path,
                records_page_path,
                output_dir,
                name_prefix,
                logger=logger,
            ))

        training_form_path = get_abs_path("training_form_path")
        if training_form_path and os.path.exists(training_form_path):
            results.append(copy_health_form(training_form_path, output_dir, name_prefix, logger=logger))

        if not results:
            logger.emit("error", "global", "finish", "没有找到可处理的原始材料", "当前学员没有可用于生成的原始材料文件")
            results.append(_build_process_result("global", False, error="no source materials"))

        _sync_output_dir_to_cos(output_dir, base_dir)
        report = build_generation_report(output_dir, logger, results)
        logger.emit(
            "success" if report["success"] else "error",
            "global",
            "finish",
            "报名材料生成完成" if report["success"] else "报名材料生成未完全成功",
            "已完成本次报名材料生成流程" if report["success"] else "本次报名材料生成中有材料处理失败，请检查下方日志",
            details={
                "output_dir": output_dir,
                "result_count": len(results),
                "error_count": len(report["errors"]),
            },
        )
        return build_generation_report(output_dir, logger, results)

    diploma_path = get_abs_path("diploma_path")
    if diploma_path and os.path.exists(diploma_path):
        results.append(process_diploma(diploma_path, output_dir, name_prefix, logger=logger))

    id_card_front_path = get_abs_path("id_card_front_path")
    id_card_back_path = get_abs_path("id_card_back_path")
    if (id_card_front_path and os.path.exists(id_card_front_path)) or (
        id_card_back_path and os.path.exists(id_card_back_path)
    ):
        results.append(process_id_cards(id_card_front_path, id_card_back_path, output_dir, name_prefix, logger=logger))

    hukou_residence_path = get_abs_path("hukou_residence_path")
    hukou_personal_path = get_abs_path("hukou_personal_path")
    if (hukou_residence_path and os.path.exists(hukou_residence_path)) or (
        hukou_personal_path and os.path.exists(hukou_personal_path)
    ):
        results.append(process_hukou(hukou_residence_path, hukou_personal_path, output_dir, name_prefix, logger=logger))

    training_form_path = get_abs_path("training_form_path")
    if training_form_path and os.path.exists(training_form_path):
        results.append(copy_health_form(training_form_path, output_dir, name_prefix, logger=logger))

    if not results:
        logger.emit("error", "global", "finish", "没有找到可处理的原始材料", "当前学员没有可用于生成的原始材料文件")
        results.append(_build_process_result("global", False, error="no source materials"))

    # 生成完成后，批量同步报名材料目录内所有文件至 COS
    _sync_output_dir_to_cos(output_dir, base_dir)
    report = build_generation_report(output_dir, logger, results)
    logger.emit(
        "success" if report["success"] else "error",
        "global",
        "finish",
        "报名材料生成完成" if report["success"] else "报名材料生成未完全成功",
        "已完成本次报名材料生成流程" if report["success"] else "本次报名材料生成中有材料处理失败，请检查下方日志",
        details={
            "output_dir": output_dir,
            "result_count": len(results),
            "error_count": len(report["errors"]),
        },
    )
    return build_generation_report(output_dir, logger, results)


def regenerate_single_material(student, base_dir, output_root, material_type, adjustments=None):
    """
    重新生成单个材料文件。
    material_type: "diploma" | "id_card" | "hukou" | "photo"
    adjustments: dict，可选调整参数
    """
    adjustments = adjustments or {}

    id_card_num = student.get("id_card", "")
    name = student.get("name", "")
    name_prefix = f"{id_card_num}-{name}"

    training_type = student.get("training_type", "special_operation")
    company = student.get("company", "")
    training_type_map = {"special_operation": "特种作业", "special_equipment": "特种设备"}
    training_type_name = training_type_map.get(training_type, "特种作业")
    student_folder_name = f"{training_type_name}-{company}-{name}"

    output_dir = os.path.join(output_root, student_folder_name, f"{name_prefix}-报名材料")
    os.makedirs(output_dir, exist_ok=True)
    logger = MaterialGenerationLogger()
    logger.emit("info", "global", "start", "开始重新生成材料", f"开始重新生成 {material_type}")
    removed_files = cleanup_generated_outputs(output_dir, name_prefix, material_type=material_type)
    if removed_files:
        logger.emit(
            "info",
            "global",
            "cleanup",
            "已清理目标旧文件",
            "重新生成前已移除该材料对应的旧输出文件",
            details={"removed_count": len(removed_files), "material_type": material_type},
        )

    def get_abs_path(key):
        rel = student.get(key)
        return os.path.join(base_dir, rel) if rel else None

    results = []
    if material_type == "diploma":
        diploma_path = get_abs_path("diploma_path")
        if diploma_path and os.path.exists(diploma_path):
            results.append(process_diploma(diploma_path, output_dir, name_prefix, adjustments=adjustments, logger=logger))

    elif material_type == "id_card":
        front_path = get_abs_path("id_card_front_path")
        back_path = get_abs_path("id_card_back_path")
        if (front_path and os.path.exists(front_path)) or (back_path and os.path.exists(back_path)):
            results.append(process_id_cards(front_path, back_path, output_dir, name_prefix, adjustments=adjustments, logger=logger))

    elif material_type == "hukou":
        residence_path = get_abs_path("hukou_residence_path")
        personal_path = get_abs_path("hukou_personal_path")
        if (residence_path and os.path.exists(residence_path)) or (personal_path and os.path.exists(personal_path)):
            results.append(process_hukou(residence_path, personal_path, output_dir, name_prefix, adjustments=adjustments, logger=logger))

    elif material_type == "renewal_certificate":
        info_page_path = get_abs_path("certificate_info_page_path")
        records_page_path = get_abs_path("certificate_records_page_path")
        if (info_page_path and os.path.exists(info_page_path)) or (records_page_path and os.path.exists(records_page_path)):
            results.append(process_renewal_certificate_pages(info_page_path, records_page_path, output_dir, name_prefix, logger=logger))

    elif material_type == "photo":
        photo_path = get_abs_path("photo_path")
        if photo_path and os.path.exists(photo_path):
            results.append(process_personal_photo(photo_path, output_dir, name_prefix, adjustments=adjustments, logger=logger))

    if not results:
        logger.emit("error", "global", "finish", "未找到可重新生成的原始材料", f"没有找到 {material_type} 对应的原始附件")
        return build_generation_report(output_dir, logger, [_build_process_result(material_type, False, error="source material missing")])

    # 生成完成后，同步该目录内所有文件至 COS
    _sync_output_dir_to_cos(output_dir, base_dir)
    report = build_generation_report(output_dir, logger, results)
    logger.emit(
        "success" if report["success"] else "error",
        "global",
        "finish",
        "单项材料重新生成完成" if report["success"] else "单项材料重新生成失败",
        "已完成本次单项材料重新生成" if report["success"] else "单项材料重新生成过程中发生错误",
        details={"material_type": material_type, "error_count": len(report["errors"])},
    )
    return build_generation_report(output_dir, logger, results)


def _sync_output_dir_to_cos(output_dir, base_dir):
    """
    将本地 output_dir 目录下所有文件同步到 COS。
    仅在 STORAGE_BACKEND=cos 或 dual 时执行。
    同步失败持续处理（本地已有文件）。
    """
    import os as _os
    from services import storage_service as _ss

    backend = _ss._get_backend()
    if backend not in ('cos', 'dual'):
        return

    if not _os.path.isdir(output_dir):
        return

    synced, failed = 0, 0
    for filename in _os.listdir(output_dir):
        abs_path = _os.path.join(output_dir, filename)
        if not _os.path.isfile(abs_path):
            continue
        # 计算相对 key：将本地绝对路径转为相对于 base_dir 的路径
        rel_key = _os.path.relpath(abs_path, base_dir).replace('\\', '/')
        try:
            _ss.save_from_local(abs_path, rel_key)
            synced += 1
        except Exception as exc:
            failed += 1
            print(f'[material_service] COS 同步失败: {rel_key} -> {exc}')

    print(f'[material_service] COS 同步完成: 成功 {synced} 个，失败 {failed} 个')
