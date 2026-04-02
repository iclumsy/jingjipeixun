# 报名材料裁剪优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用分材料类型的候选评分裁剪替换当前统一的 `auto_crop_document`，提升身份证、户口页、毕业证书在复杂背景和低光照场景下的稳定性，同时保持报名材料导出接口与排版不变。

**Architecture:** 继续保留 `/Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py` 作为报名材料处理入口，但将内部逻辑拆成“图像统计与增强、候选生成、候选评分、裁剪兜底、输出增强”五个层次，并按 `id_card`、`hukou`、`diploma` 使用不同配置。自动化回归以 `unittest` + 合成 `numpy` 图像为主，真实照片验证放在最终人工回归阶段。

**Tech Stack:** Python、OpenCV、NumPy、Pillow、Python `unittest`

---

## 文件结构与职责

### 需要新增的文件

- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/__init__.py`
  - 建立后端测试包，供 `python3 -m unittest` 发现图像处理回归测试。
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py`
  - 用合成图像覆盖低光照增强、候选评分、身份证比例筛选、户口页表格线抑制、毕业证书页面裁剪和端到端输出文件生成。

### 需要修改的文件

- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py`
  - 新增内部 crop profile、亮度/对比度评估、候选提取与评分、材料类型专用裁剪器、保守兜底、输出增强和轻量日志。
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/PROJECT_IMPLEMENTATION_GUIDE.md`
  - 把报名材料图像处理章节从“单一 Canny + 轮廓透视”更新为“分类型候选评分 + 低光照增强 + 户口页表格线抑制”，并补充手工回归说明。

### 关键实现决策

1. 不改变 `process_diploma`、`process_id_cards`、`process_hukou`、`generate_student_materials` 的函数签名。
2. 不额外引入新运行依赖，所有增强、评分和裁剪都基于现有 `opencv-python` 与 `numpy` 实现。
3. 自动化测试全部使用合成图像或临时目录，不向仓库提交二进制图片样本。
4. 身份证宽高比约 `1.585` 作为强约束：候选先粗筛，再高权重评分，透视后再复核。
5. 低光照增强分为“检测增强”和“导出增强”两层，且必须基于图像统计触发；增强过度时要回退。
6. 户口页只对内部细长水平/垂直线做抑制，不做会破坏页面边框的激进擦除。
7. 所有失败路径都必须回到保守矩形裁剪或原图，而不是继续做错误透视。

## Task 1: 建立图像处理测试基线与低光照增强辅助函数

**Files:**
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/__init__.py`
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py`

- [ ] **Step 1: 先写低光照增强的失败测试**

在 `test_material_service.py` 中先创建 `MaterialServicePreprocessTests`，并写出最小测试图生成器：

```python
def build_dark_document(width=1200, height=900):
    image = np.full((height, width, 3), 35, dtype=np.uint8)
    cv2.rectangle(image, (180, 140), (1020, 760), (95, 95, 95), -1)
    cv2.rectangle(image, (180, 140), (1020, 760), (160, 160, 160), 6)
    return image

def test_analysis_enhancement_lifts_dark_document_contrast(self):
    image = build_dark_document()
    enhanced, meta = material_service.apply_low_light_enhancement_if_needed(image, stage="analysis")
    self.assertTrue(meta["enabled"])
    self.assertGreater(meta["mean_after"], meta["mean_before"])
```

同一组测试里再补一个“亮图不应增强”的反向断言。

- [ ] **Step 2: 运行预处理测试，确认当前实现还没有这些 helper**

Run: `python3 -m unittest training_system.tests.test_material_service.MaterialServicePreprocessTests -v`
Expected: FAIL，提示 `training_system.tests` 包不存在，或 `apply_low_light_enhancement_if_needed` 未定义。

- [ ] **Step 3: 建立测试包并在 `material_service.py` 中实现最小预处理 helper**

先把以下 helper 以内部函数形式加进 `material_service.py`：

```python
def analyze_image_stats(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return {
        "mean": float(gray.mean()),
        "std": float(gray.std()),
        "p5": float(np.percentile(gray, 5)),
        "p95": float(np.percentile(gray, 95)),
    }

def apply_low_light_enhancement_if_needed(image, stage):
    stats = analyze_image_stats(image)
    if stats["mean"] >= 120 and (stats["p95"] - stats["p5"]) >= 90:
        return image, {"enabled": False, "mean_before": stats["mean"], "mean_after": stats["mean"]}
    ...
    return enhanced, meta
```

实现里优先用 CLAHE、截断直方图拉伸或轻度 gamma，避免固定死单一算法。

- [ ] **Step 4: 给分析阶段补上统一入口**

在 `material_service.py` 内增加一个统一预处理入口，供后续三类材料共用：

```python
def prepare_analysis_image(image, enable_low_light=True):
    working = image.copy()
    if enable_low_light:
        working, enhancement_meta = apply_low_light_enhancement_if_needed(working, stage="analysis")
    gray = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    return working, gray, enhancement_meta
```

- [ ] **Step 5: 重新运行预处理测试**

Run: `python3 -m unittest training_system.tests.test_material_service.MaterialServicePreprocessTests -v`
Expected: PASS，暗图会触发增强，亮图保持不变或近似不变。

- [ ] **Step 6: 提交低光照测试基线**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/tests/__init__.py /Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py /Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py
git commit -m "test: add material service preprocess regression coverage"
```

## Task 2: 引入候选生成、候选评分与保守兜底骨架

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py`

- [ ] **Step 1: 先写候选评分失败测试**

在 `MaterialServiceCandidateSelectionTests` 中先从纯指标层锁住评分逻辑，不依赖真实轮廓提取：

```python
def test_id_card_profile_prefers_card_ratio_candidate_over_full_frame(self):
    candidates = [
        {"area_ratio": 0.92, "aspect_ratio": 1.33, "rectangularity": 0.98, "corner_quality": 0.97, "border_margin": 3, "edge_density_on_border": 0.95},
        {"area_ratio": 0.36, "aspect_ratio": 1.58, "rectangularity": 0.97, "corner_quality": 0.98, "border_margin": 40, "edge_density_on_border": 0.88},
    ]
    best = material_service.select_best_candidate(candidates, profile_name="id_card")
    self.assertAlmostEqual(best["aspect_ratio"], 1.58, places=2)
```

再补一个“低分候选应回退保守裁剪”的测试。

- [ ] **Step 2: 运行候选测试，确认评分 helper 尚未实现**

Run: `python3 -m unittest training_system.tests.test_material_service.MaterialServiceCandidateSelectionTests -v`
Expected: FAIL，提示 `select_best_candidate` 或 `crop_with_fallback` 未定义。

- [ ] **Step 3: 在 `material_service.py` 中实现 crop profile 与评分函数**

新增按材料类型区分的内部配置：

```python
CROP_PROFILES = {
    "id_card": {"target_ratio": 1.585, "ratio_tolerance": 0.18, "min_area_ratio": 0.12, "max_area_ratio": 0.75, "allow_table_suppression": False},
    "hukou": {"target_ratio": None, "min_area_ratio": 0.25, "max_area_ratio": 0.95, "allow_table_suppression": True},
    "diploma": {"target_ratio": None, "min_area_ratio": 0.20, "max_area_ratio": 0.95, "allow_table_suppression": False},
}
```

并实现：

```python
def score_candidate(candidate, profile_name):
    ...

def select_best_candidate(candidates, profile_name):
    ...
```

`id_card` 的 `aspect_ratio_delta` 需要同时用于粗筛和高权重评分。

- [ ] **Step 4: 实现保守兜底裁剪入口**

在同一文件实现：

```python
def crop_with_fallback(orig, candidate, *, allow_perspective, expand_px, profile_name):
    if candidate is None:
        return orig, {"mode": "original"}
    if allow_perspective and candidate["confidence"] >= candidate["perspective_threshold"]:
        ...
        return warped, {"mode": "perspective"}
    return cropped, {"mode": "rect"}
```

这一步先打通“评分 -> 透视/矩形/原图”的状态流，不急着接入具体材料。

- [ ] **Step 5: 重新运行候选评分测试**

Run: `python3 -m unittest training_system.tests.test_material_service.MaterialServiceCandidateSelectionTests -v`
Expected: PASS，身份证 profile 会偏向卡片比例候选，低分候选会走保守裁剪。

- [ ] **Step 6: 提交候选评分骨架**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py /Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py
git commit -m "feat: add document crop candidate scoring helpers"
```

## Task 3: 实现身份证专用裁剪并接入报名材料生成

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py`

- [ ] **Step 1: 先写身份证比例约束与端到端裁剪失败测试**

在 `MaterialServiceIDCardCropTests` 中先覆盖身份证强约束：

```python
def test_auto_crop_id_card_rejects_candidate_outside_ratio_gate(self):
    image = build_card_scene(background_border=True)
    result, meta = material_service.auto_crop_id_card(image, return_meta=True)
    self.assertEqual(meta["profile"], "id_card")
    self.assertAlmostEqual(meta["selected_candidate"]["aspect_ratio"], 1.585, delta=0.20)

def test_auto_crop_id_card_falls_back_when_perspective_breaks_ratio(self):
    ...
    self.assertEqual(meta["crop_mode"], "rect")
```

再补一条 `process_id_cards` 生成 A4 合成图的 smoke test，确认输出文件仍叫 `-身份证.jpg`。

- [ ] **Step 2: 运行身份证测试，确认专用入口还不存在**

Run: `python3 -m unittest training_system.tests.test_material_service.MaterialServiceIDCardCropTests -v`
Expected: FAIL，提示 `auto_crop_id_card` 未定义或返回的 `meta` 字段缺失。

- [ ] **Step 3: 在 `material_service.py` 中实现身份证专用入口**

实现专用流程：

```python
def auto_crop_id_card(image, expand_px=20, return_meta=False):
    working, gray, preprocess_meta = prepare_analysis_image(image, enable_low_light=True)
    candidates = detect_document_candidates(working, gray, profile_name="id_card")
    best = select_best_candidate(candidates, profile_name="id_card")
    cropped, crop_meta = crop_with_fallback(image, best, allow_perspective=True, expand_px=expand_px, profile_name="id_card")
    ...
```

关键点：

1. 候选在进入评分前先做比例粗筛。
2. 透视完成后再复查输出比例，失败则回退矩形裁剪。
3. 元数据里记录 `profile`、`enhancement_enabled`、`crop_mode`。

- [ ] **Step 4: 接入 `process_id_cards`**

把 `process_id_cards` 中原本两处 `auto_crop_document(...)` 改成：

```python
front_img = auto_crop_id_card(front_img)
back_img = auto_crop_id_card(back_img)
```

不要改动 A4 拼版、命名和尺寸逻辑。

- [ ] **Step 5: 重新运行身份证测试**

Run: `python3 -m unittest training_system.tests.test_material_service.MaterialServiceIDCardCropTests -v`
Expected: PASS，身份证候选被比例约束锁住，输出文件仍能成功生成。

- [ ] **Step 6: 提交身份证专用裁剪**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py /Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py
git commit -m "feat: specialize id card document cropping"
```

## Task 4: 实现毕业证书与户口页专用页面裁剪

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py`

- [ ] **Step 1: 先写毕业证书与户口页失败测试**

在 `MaterialServiceDiplomaCropTests` 和 `MaterialServiceHukouCropTests` 中分别锁住两个场景：

```python
def test_auto_crop_diploma_prefers_page_candidate_over_background_frame(self):
    image = build_page_scene(include_outer_background=True, include_inner_grid=False)
    cropped, meta = material_service.auto_crop_diploma(image, return_meta=True)
    self.assertEqual(meta["profile"], "diploma")
    self.assertGreater(meta["selected_candidate"]["area_ratio"], 0.20)

def test_auto_crop_hukou_suppresses_inner_table_lines(self):
    image = build_page_scene(include_outer_background=False, include_inner_grid=True)
    suppressed = material_service.suppress_table_lines_for_hukou(image)
    self.assertLess(count_inner_grid_edges(suppressed), count_inner_grid_edges(image))
```

再补一条 `process_hukou` 输出 `-户口本.jpg` 的 smoke test。

- [ ] **Step 2: 运行页面类测试，确认专用 helper 还不存在**

Run: `python3 -m unittest training_system.tests.test_material_service.MaterialServiceDiplomaCropTests training_system.tests.test_material_service.MaterialServiceHukouCropTests -v`
Expected: FAIL，提示 `auto_crop_diploma` / `suppress_table_lines_for_hukou` / `auto_crop_hukou_page` 未定义。

- [ ] **Step 3: 实现毕业证书专用裁剪**

在 `material_service.py` 中实现：

```python
def auto_crop_diploma(image, expand_px=20, return_meta=False):
    working, gray, preprocess_meta = prepare_analysis_image(image, enable_low_light=True)
    candidates = detect_document_candidates(working, gray, profile_name="diploma")
    ...
```

毕业证书允许页面类透视，但比身份证更偏向“大面积、边界连续、少切边”的候选。

- [ ] **Step 4: 实现户口页表格线抑制与专用裁剪**

在同一文件加入：

```python
def suppress_table_lines_for_hukou(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    horizontal = cv2.morphologyEx(...)
    vertical = cv2.morphologyEx(...)
    ...
    return suppressed

def auto_crop_hukou_page(image, expand_px=50, return_meta=False):
    ...
```

户口页 profile 必须在检测前引入 `suppress_table_lines_for_hukou`，并把 `inner_line_density` 纳入评分。

- [ ] **Step 5: 接入 `process_diploma` 与 `process_hukou`**

把现有调用替换为：

```python
img = auto_crop_diploma(img)
img1 = auto_crop_hukou_page(img1, expand_px=50)
img2 = auto_crop_hukou_page(img2, expand_px=50)
```

保持导出命名与排版尺寸不变。

- [ ] **Step 6: 重新运行页面类测试**

Run: `python3 -m unittest training_system.tests.test_material_service.MaterialServiceDiplomaCropTests training_system.tests.test_material_service.MaterialServiceHukouCropTests -v`
Expected: PASS，毕业证书会优先选页面候选，户口页表格线被抑制后仍能保住外框。

- [ ] **Step 7: 提交页面类专用裁剪**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py /Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py
git commit -m "feat: specialize hukou and diploma document cropping"
```

## Task 5: 完成导出增强、端到端回归与文档更新

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/PROJECT_IMPLEMENTATION_GUIDE.md`

- [ ] **Step 1: 先写导出增强与端到端生成失败测试**

在 `MaterialServiceExportEnhancementTests` 中补两类测试：

```python
def test_export_enhancement_keeps_bright_document_stable(self):
    image = build_bright_document()
    enhanced, meta = material_service.enhance_document_output_if_needed(image)
    self.assertFalse(meta["enabled"])

def test_generate_student_materials_writes_all_expected_outputs(self):
    student = build_student_dict_with_temp_files(...)
    output_dir = material_service.generate_student_materials(student, base_dir, output_root)
    self.assertTrue(os.path.exists(os.path.join(output_dir, f"{student['id_card']}-{student['name']}-身份证.jpg")))
```

端到端测试用 `tempfile.TemporaryDirectory()` 生成临时附件路径，不依赖仓库外样本。

- [ ] **Step 2: 运行最终回归测试，确认导出增强 helper 仍缺失**

Run: `python3 -m unittest training_system.tests.test_material_service.MaterialServiceExportEnhancementTests -v`
Expected: FAIL，提示 `enhance_document_output_if_needed` 未定义，或输出元数据不完整。

- [ ] **Step 3: 实现导出增强与轻量日志**

在 `material_service.py` 中新增：

```python
def enhance_document_output_if_needed(image):
    ...
    return enhanced, {"enabled": enabled, "stage": "export"}

def log_crop_decision(profile_name, meta):
    print(f"[material_crop] profile={profile_name} mode={meta['crop_mode']} enhanced={meta['enhancement_enabled']}")
```

把三类专用裁剪都改成在输出前调用 `enhance_document_output_if_needed`，并记录最终选择的候选数量、裁剪模式、是否启用增强。

- [ ] **Step 4: 更新项目实现文档**

把 `PROJECT_IMPLEMENTATION_GUIDE.md` 中涉及报名材料图像处理的章节更新为：

1. 三类材料分型处理：身份证 / 户口页 / 毕业证书。
2. 候选评分与保守兜底。
3. 低光照增强与导出色阶优化。
4. 户口页表格线抑制。
5. 自动化测试与人工回归方式。

不要在文档里保留旧的“找到第一个四边形即透视”的表述。

- [ ] **Step 5: 运行完整自动化回归**

Run: `python3 -m unittest training_system.tests.test_material_service -v`
Expected: PASS，覆盖预处理、候选评分、三类材料专用裁剪和端到端输出生成。

- [ ] **Step 6: 运行最终后端测试发现命令**

Run: `python3 -m unittest discover -s /Users/Ditto/Documents/jingjipeixun/training_system/tests -v`
Expected: PASS；如果仓库里只有这一个测试文件，也要确认 discover 能正常找到并通过。

- [ ] **Step 7: 做一次真实链路人工回归**

在本地启动后，通过管理员端现有“生成报名材料”入口分别验证：

1. 一组复杂背景身份证样本
2. 一组表格线明显的户口页样本
3. 一组低光照毕业证书样本

确认点：

1. 输出文件名仍是 `-身份证.jpg`、`-户口本.jpg`、`-学历证书.jpg`
2. A4 排版未被破坏
3. 暗图更清楚，但没有明显过曝或偏色
4. 低置信场景走保守裁剪，而不是错误透视

- [ ] **Step 8: 提交最终裁剪优化**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/services/material_service.py /Users/Ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py /Users/Ditto/Documents/jingjipeixun/training_system/PROJECT_IMPLEMENTATION_GUIDE.md
git commit -m "feat: improve material document cropping"
```
