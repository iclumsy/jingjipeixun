# 报名材料生成日志与功能修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复报名材料生成链路里“参数与实际处理不一致、失败仍报成功、旧文件残留、手动裁剪影响未调整页”等功能问题，并新增混合型的详细日志体验。

**Architecture:** 后端在 `material_service.py` 中增加结构化日志收集与结果汇总能力，把“原始文本日志”和“结构化日志事件”一起返回；同时把手动裁剪与自动生成链路重新对齐，确保只有用户真正确认点位时才走 manual 分支，且 manual 分支尊重 `rect_only` 并只覆盖被调整的页面。前端在 `admin.js` 中新增统一日志弹窗和最近一次折叠日志展示，并修正点位状态机。

**Tech Stack:** Flask、Python `unittest`、OpenCV、原生前端 JavaScript

---

### Task 1: 补后端最小回归测试骨架

**Files:**
- Create: `training_system/tests/test_material_service.py`
- Test: `training_system/tests/test_material_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_log_collector_builds_summary_counts(self):
    ...

def test_rect_only_manual_crop_uses_bounding_box(self):
    ...

def test_cleanup_generated_files_removes_stale_outputs(self):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest training_system.tests.test_material_service -v`
Expected: FAIL because new logging helpers / cleanup helpers do not exist yet

- [ ] **Step 3: Write minimal implementation scaffolding**

Add small helper APIs in `services/material_service.py` for:
- structure log collection
- cleaning stale generated files
- manual crop mode handling

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest training_system.tests.test_material_service -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add training_system/tests/test_material_service.py training_system/services/material_service.py
git commit -m "test: add material service regression coverage"
```

### Task 2: 修复后端生成链路功能问题并输出结构化日志

**Files:**
- Modify: `training_system/services/material_service.py`
- Modify: `training_system/routes/student_routes.py`
- Test: `training_system/tests/test_material_service.py`

- [ ] **Step 1: Write the failing tests for behavior changes**

Add tests covering:
- full generation removes stale outputs before rewriting
- per-material regenerate only clears target output
- process failure increments error summary and marks generation failed
- manual crop `rect_only` uses rectangular crop, not perspective warp

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest training_system.tests.test_material_service -v`
Expected: FAIL on missing generation report / stale file cleanup / manual crop behavior

- [ ] **Step 3: Write minimal implementation**

Implement in `material_service.py`:
- `MaterialGenerationLogger` or equivalent collector
- structured event emission in generate / regenerate / process functions
- explicit process result objects instead of swallowing all failures
- helper to remove stale outputs before full generation and targeted regenerate
- per-side/per-page manual crop flags so manually调整的页跳过自动裁剪，未调整页仍按当前参数自动处理
- manual crop helper that respects `rect_only`

Update `student_routes.py`:
- routes return `log_summary` and `log_events`
- routes return non-200 when requested generation fails
- `manual_crop_material` stops globally forcing all pages to `crop_mode=none`

- [ ] **Step 4: Run tests to verify it passes**

Run: `python -m unittest training_system.tests.test_material_service -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add training_system/services/material_service.py training_system/routes/student_routes.py training_system/tests/test_material_service.py
git commit -m "fix: align material generation behavior and reporting"
```

### Task 3: 修复前端点位状态机并接入新日志体验

**Files:**
- Modify: `training_system/static/js/admin.js`

- [ ] **Step 1: Write the failing behavioral checklist**

Manual checklist to guide implementation:
- AI 推荐框显示后，不拖点直接提交，应走自动生成接口
- 选择 `不裁剪` 后，应清空手动点位并走自动生成接口
- 真正拖过点位后，才走 manual 接口
- 生成成功后弹出结构化日志弹窗
- 页面保留最近一次日志折叠面板

- [ ] **Step 2: Implement minimal front-end changes**

In `admin.js`:
- split “AI 推荐点位” and “用户确认点位”
- collect manual points only after real drag interaction
- choosing `crop_mode=none` clears manual state
- add log modal renderer using `log_summary` + `log_events`
- keep latest log block collapsed under materials section
- preserve raw log folding inside modal/panel

- [ ] **Step 3: Verify manually against route payload rules**

Check generated request payloads in code paths:
- `generate_materials`
- `regenerate_material`
- `manual_crop_material`

Expected:
- manual endpoint only used when user-confirmed points exist
- `none` mode does not submit stale points

- [ ] **Step 4: Commit**

```bash
git add training_system/static/js/admin.js
git commit -m "feat: add readable material generation logs"
```

### Task 4: 全链路验证

**Files:**
- Verify: `training_system/services/material_service.py`
- Verify: `training_system/routes/student_routes.py`
- Verify: `training_system/static/js/admin.js`
- Verify: `training_system/tests/test_material_service.py`

- [ ] **Step 1: Run automated verification**

Run: `python -m unittest training_system.tests.test_material_service -v`
Expected: PASS

- [ ] **Step 2: Run quick syntax verification**

Run: `python -m py_compile training_system/services/material_service.py training_system/routes/student_routes.py`
Expected: PASS

- [ ] **Step 3: Review implementation against requirements**

Checklist:
- only user-confirmed points trigger manual crop
- manual `rect_only` respected
- stale generated files cleaned
- failed processing no longer reports full success
- structured logs returned and rendered
- latest log collapses but remains available

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-04-08-material-generation-logs-design.md docs/superpowers/plans/2026-04-08-material-generation-logs-and-fixes.md
git commit -m "docs: add material generation logging spec and plan"
```
