import io
import os
import shutil
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image

A4_WIDTH = 2480
A4_HEIGHT = 3508
CM_IN_PX = 118  # roughly 300 DPI
ANALYSIS_MAX_SIDE = 1800
MIN_CROP_DIM = 24
ID_CARD_RATIO = 85.6 / 54.0
TESSERACT_BINARY = shutil.which("tesseract")
HUKOU_OSD_MIN_CONFIDENCE = 0.9
HUKOU_OSD_STRONG_CONFIDENCE = 1.6
HUKOU_OSD_TIMEOUT_SEC = 8

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
        "expand_px": 20,
    },
    "hukou": {
        "target_ratio": None,
        "ratio_tolerance": None,
        "post_ratio_tolerance": None,
        "min_area_ratio": 0.18,
        "max_area_ratio": 0.95,
        "preferred_area_ratio": 0.58,
        "preferred_border_margin": 0.015,
        "allow_table_suppression": True,
        "allow_perspective": True,
        "perspective_threshold": 0.68,
        "analysis_enhancement": True,
        "export_enhancement": True,
        "expand_px": 50,
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
        "expand_px": 20,
    },
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


def four_point_transform(image, pts):
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
    return cv2.warpPerspective(image, transform, (max_width, max_height))


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

    needs_enhancement = (
        stats_before["mean"] < mean_threshold
        or stats_before["dynamic_range"] < dynamic_threshold
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


def prepare_analysis_image(image, enable_low_light=True):
    analysis_image, scale = resize_for_analysis(image)
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


def detect_edges(gray, profile_name):
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    median = float(np.median(blurred))
    lower = int(max(25, 0.66 * median))
    upper = int(min(255, max(90, 1.33 * median)))
    edges = cv2.Canny(blurred, lower, upper)

    h, w = gray.shape[:2]
    kernel_size = max(5, int(round(min(h, w) * 0.008)))
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


def expand_quad(points, expand_px, image_shape):
    if expand_px <= 0:
        return points.astype(np.float32)

    center = points.mean(axis=0)
    expanded = []
    for point in points.astype(np.float32):
        direction = point - center
        norm = np.linalg.norm(direction)
        if norm <= 1e-6:
            expanded.append(point)
            continue
        expanded.append(point + direction / norm * expand_px)

    expanded = np.array(expanded, dtype=np.float32)
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
    min_area = max(1500, int(image.shape[0] * image.shape[1] * 0.01))
    components = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = max(w, h) / float(max(1, min(w, h)))
        fill_ratio = area / float(max(1, w * h))
        if aspect_ratio > 1.8 or fill_ratio < 0.15:
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


def prepare_hukou_output_page(image, page_kind):
    kind_label = "首页" if page_kind == "home" else "本人页"
    tag = f"[hukou][{kind_label}]"
    h0, w0 = image.shape[:2]
    print(f"{tag} 原图尺寸: {w0}x{h0}")

    page, meta = auto_crop_hukou_page(image, expand_px=90, return_meta=True)
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
        page_kind == "home"
        and selected.get("detector") == "foreground_mask"
        and selected.get("area_ratio", 0.0) < 0.85
    ):
        refined_page, refined_meta = auto_crop_hukou_page(page, expand_px=90, return_meta=True)
        h2, w2 = refined_page.shape[:2]
        if refined_page.shape[0] * refined_page.shape[1] < page.shape[0] * page.shape[1] * 0.96:
            print(f"{tag} 二次精细裁剪生效: {w2}x{h2}")
            page = refined_page
            meta = refined_meta
            selected = meta.get("selected_candidate") or selected
        else:
            print(f"{tag} 二次精细裁剪未生效（面积没有明显缩小），保持第一次结果")

    page = normalize_hukou_page_orientation(page, original_image=image, page_kind=page_kind)
    h3, w3 = page.shape[:2]
    if (h3, w3) != (h1, w1):
        print(f"{tag} 方向校正后: {w3}x{h3}")

    if (
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
    }


def build_candidate_from_contour(contour, edges, image_shape, scale, line_mask=None, detector="edge"):
    hull = cv2.convexHull(contour)
    contour_area = cv2.contourArea(hull)
    if contour_area <= 0:
        return None

    perimeter = cv2.arcLength(hull, True)
    approx = cv2.approxPolyDP(hull, 0.02 * perimeter, True)
    if len(approx) == 4:
        points = approx.reshape(4, 2).astype(np.float32)
        source = "approx"
    else:
        rect = cv2.minAreaRect(hull)
        points = cv2.boxPoints(rect).astype(np.float32)
        source = "min_rect"

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
    _, bright_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    h, w = gray.shape[:2]
    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(9, w // 120), max(9, h // 120)),
    )
    open_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(5, w // 200), max(5, h // 200)),
    )
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
    contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contours


def detect_background_color_contours(image):
    h, w = image.shape[:2]
    sigma = max(3.0, min(h, w) / 120.0)
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma)
    lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB).astype(np.float32)
    chroma = lab[:, :, 1:3]

    margin = max(12, min(h, w) // 18)
    border = np.concatenate(
        [
            chroma[:margin, :, :].reshape(-1, 2),
            chroma[-margin:, :, :].reshape(-1, 2),
            chroma[:, :margin, :].reshape(-1, 2),
            chroma[:, -margin:, :].reshape(-1, 2),
        ],
        axis=0,
    )
    background_chroma = np.median(border, axis=0)
    distance = np.linalg.norm(chroma - background_chroma, axis=2)
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


def detect_document_candidates(analysis_image, gray, profile_name, scale=1.0, line_mask=None):
    edges = detect_edges(gray, profile_name)
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
    return candidates


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
    preferred_area_score = preferred_score(
        candidate["area_ratio"],
        profile["preferred_area_ratio"],
        max(
            profile["preferred_area_ratio"] - profile["min_area_ratio"],
            profile["max_area_ratio"] - profile["preferred_area_ratio"],
            0.08,
        ),
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
            0.24 * area_score
            + 0.18 * preferred_area_score
            + 0.21 * rect_score
            + 0.18 * edge_score
            + 0.11 * corner_score
            + 0.08 * border_score
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
                if item["area_ratio"] >= 0.45
                and item["rectangularity"] >= 0.95
                and item["corner_quality"] >= 0.85
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


def crop_with_fallback(orig, candidate, *, allow_perspective, expand_px, profile_name):
    meta = {"crop_mode": "original"}
    if candidate is None:
        return orig.copy(), meta

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


def auto_crop_with_profile(image, profile_name, expand_px=None, return_meta=False):
    try:
        profile = CROP_PROFILES[profile_name]
        analysis_image, gray, preprocess_meta, scale = prepare_analysis_image(
            image,
            enable_low_light=profile.get("analysis_enhancement", True),
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
        )
        best = select_best_candidate(candidates, profile_name)
        cropped, crop_meta = crop_with_fallback(
            image,
            best,
            allow_perspective=profile.get("allow_perspective", True),
            expand_px=expand_px if expand_px is not None else profile["expand_px"],
            profile_name=profile_name,
        )

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


def auto_crop_id_card(image, expand_px=20, return_meta=False):
    return auto_crop_with_profile(image, "id_card", expand_px=expand_px, return_meta=return_meta)


def auto_crop_hukou_page(image, expand_px=50, return_meta=False):
    return auto_crop_with_profile(image, "hukou", expand_px=expand_px, return_meta=return_meta)


def auto_crop_diploma(image, expand_px=20, return_meta=False):
    return auto_crop_with_profile(image, "diploma", expand_px=expand_px, return_meta=return_meta)


def auto_crop_document(image, expand_px=20):
    return auto_crop_diploma(image, expand_px=expand_px)


def read_cv_image(path):
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


def process_personal_photo(input_path, output_dir, name_prefix):
    """个人照片处理为 1MB 以下"""
    try:
        img = Image.open(input_path)
        if img.mode != "RGB":
            img = img.convert("RGB")

        output_path = os.path.join(output_dir, f"{name_prefix}-个人照片.jpg")

        quality = 95
        while True:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            size_kb = len(buffer.getvalue()) / 1024
            if size_kb < 1000 or quality <= 30:
                with open(output_path, "wb") as file_obj:
                    file_obj.write(buffer.getvalue())
                break
            quality -= 10

    except Exception as exc:
        print("Error processing personal photo:", exc)


def process_diploma(input_path, output_dir, name_prefix):
    """学历证书照片，裁边，A4白色底，水平居中，宽两边留 1cm，水平校正"""
    tag = "[diploma]"
    try:
        print(f"{tag} 开始处理: {os.path.basename(input_path)}")
        img = read_cv_image(input_path)
        if img is None:
            print(f"{tag} 读图失败，终止")
            return
        h0, w0 = img.shape[:2]
        print(f"{tag} 原图尺寸: {w0}x{h0}")

        img, meta = auto_crop_diploma(img, return_meta=True)
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

        target_width = A4_WIDTH - 2 * CM_IN_PX
        img_resized, target_height = resize_document_to_width(img, target_width)
        print(f"{tag} 缩放腧50第 A4 画布: 宽={target_width}px  高={target_height}px")

        canvas = create_a4_canvas()
        x_offset = CM_IN_PX
        y_offset = max(0, (A4_HEIGHT - target_height) // 2)

        canvas_h = canvas.shape[0]
        if y_offset + target_height > canvas_h:
            target_height = canvas_h - y_offset
            img_resized = img_resized[:target_height, :]
            print(f"{tag} 高度超出画布，功成截断到: {target_height}px")

        canvas[y_offset:y_offset + target_height, x_offset:x_offset + target_width] = img_resized
        print(f"{tag} 排版位置: x={x_offset}  y={y_offset}")

        output_path = os.path.join(output_dir, f"{name_prefix}-学历证书.jpg")
        write_cv_image(output_path, canvas)
        print(f"{tag} 已输出: {output_path}")
    except Exception as exc:
        print(f"{tag} 处理失败:", exc)


def process_id_cards(front_path, back_path, output_dir, name_prefix):
    tag = "[id-card]"
    try:
        canvas = create_a4_canvas()

        target_width = A4_WIDTH // 2
        x_offset = (A4_WIDTH - target_width) // 2

        front_img, back_img = None, None
        front_h, back_h = 0, 0

        if front_path and os.path.exists(front_path):
            front_img = read_cv_image(front_path)
            if front_img is not None:
                h0, w0 = front_img.shape[:2]
                print(f"{tag}[正面] 原图: {w0}x{h0}")
                front_img, meta = auto_crop_id_card(front_img, return_meta=True)
                sel = meta.get("selected_candidate") or {}
                hc, wc = front_img.shape[:2]
                print(
                    f"{tag}[正面] 裁剪后: {wc}x{hc}  "
                    f"mode={meta.get('crop_mode')}  "
                    f"detector={sel.get('detector', 'N/A')}  "
                    f"area_ratio={sel.get('area_ratio', 0):.3f}  "
                    f"confidence={sel.get('confidence', 0):.3f}"
                )
                front_img = normalize_id_card_side(front_img, "front")
                hn, wn = front_img.shape[:2]
                if (hn, wn) != (hc, wc):
                    print(f"{tag}[正面] 方向正规化后: {wn}x{hn}")
                front_img, front_h = resize_document_to_width(front_img, target_width)
                print(f"{tag}[正面] 缩放后: {target_width}x{front_h}")

        if back_path and os.path.exists(back_path):
            back_img = read_cv_image(back_path)
            if back_img is not None:
                h0, w0 = back_img.shape[:2]
                print(f"{tag}[反面] 原图: {w0}x{h0}")
                back_img, meta = auto_crop_id_card(back_img, return_meta=True)
                sel = meta.get("selected_candidate") or {}
                hc, wc = back_img.shape[:2]
                print(
                    f"{tag}[反面] 裁剪后: {wc}x{hc}  "
                    f"mode={meta.get('crop_mode')}  "
                    f"detector={sel.get('detector', 'N/A')}  "
                    f"area_ratio={sel.get('area_ratio', 0):.3f}  "
                    f"confidence={sel.get('confidence', 0):.3f}"
                )
                back_img = normalize_id_card_side(back_img, "back")
                hn, wn = back_img.shape[:2]
                if (hn, wn) != (hc, wc):
                    print(f"{tag}[反面] 方向正规化后: {wn}x{hn}")
                back_img, back_h = resize_document_to_width(back_img, target_width)
                print(f"{tag}[反面] 缩放后: {target_width}x{back_h}")

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
    except Exception as exc:
        print(f"{tag} 处理失败:", exc)


def process_hukou(residence_path, personal_path, output_dir, name_prefix):
    tag = "[hukou]"
    try:
        canvas = create_a4_canvas()

        target_width = A4_WIDTH - 4 * CM_IN_PX
        x_offset = 2 * CM_IN_PX

        img1, img2 = None, None
        h1, h2 = 0, 0

        if residence_path and os.path.exists(residence_path):
            print(f"{tag}[首页] 开始处理: {os.path.basename(residence_path)}")
            img1 = read_cv_image(residence_path)
            if img1 is not None:
                img1 = prepare_hukou_output_page(img1, "home")
                img1, h1 = resize_document_to_width(img1, target_width)
                print(f"{tag}[首页] 缩放后: {target_width}x{h1}")

        if personal_path and os.path.exists(personal_path):
            print(f"{tag}[本人页] 开始处理: {os.path.basename(personal_path)}")
            img2 = read_cv_image(personal_path)
            if img2 is not None:
                img2 = prepare_hukou_output_page(img2, "personal")
                img2, h2 = resize_document_to_width(img2, target_width)
                print(f"{tag}[本人页] 缩放后: {target_width}x{h2}")

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
    except Exception as exc:
        print(f"{tag} 处理失败:", exc)



def copy_health_form(form_path, output_dir, name_prefix):
    if form_path and os.path.exists(form_path):
        ext = os.path.splitext(form_path)[1]
        output_path = os.path.join(output_dir, f"{name_prefix}-体检表{ext}")
        shutil.copy2(form_path, output_path)


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

    def get_abs_path(key):
        rel = student.get(key)
        return os.path.join(base_dir, rel) if rel else None

    photo_path = get_abs_path("photo_path")
    if photo_path and os.path.exists(photo_path):
        process_personal_photo(photo_path, output_dir, name_prefix)

    diploma_path = get_abs_path("diploma_path")
    if diploma_path and os.path.exists(diploma_path):
        process_diploma(diploma_path, output_dir, name_prefix)

    id_card_front_path = get_abs_path("id_card_front_path")
    id_card_back_path = get_abs_path("id_card_back_path")
    if (id_card_front_path and os.path.exists(id_card_front_path)) or (
        id_card_back_path and os.path.exists(id_card_back_path)
    ):
        process_id_cards(id_card_front_path, id_card_back_path, output_dir, name_prefix)

    hukou_residence_path = get_abs_path("hukou_residence_path")
    hukou_personal_path = get_abs_path("hukou_personal_path")
    if (hukou_residence_path and os.path.exists(hukou_residence_path)) or (
        hukou_personal_path and os.path.exists(hukou_personal_path)
    ):
        process_hukou(hukou_residence_path, hukou_personal_path, output_dir, name_prefix)

    training_form_path = get_abs_path("training_form_path")
    if training_form_path and os.path.exists(training_form_path):
        copy_health_form(training_form_path, output_dir, name_prefix)

    return output_dir
