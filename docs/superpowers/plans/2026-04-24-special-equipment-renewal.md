# 特种设备复审附件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add “新考证 / 复审” support for special equipment applications, with renewal-specific attachments and renewal material stitching.

**Architecture:** Keep `training_type` as the top-level category and add `application_type` for the special equipment sub-type. Centralize attachment rules in the backend route layer and mirror those rules in miniprogram utilities so form display, validation, upload, storage, preview, and material generation stay consistent.

**Tech Stack:** Flask, SQLite, Python `unittest`, Pillow/OpenCV, WeChat miniprogram JavaScript/WXML/WXSS

---

## File Structure

- Modify: `/Users/ditto/Documents/jingjipeixun/training_system/models/student.py`
  - Add columns and persist `application_type` plus renewal attachment paths.
- Modify: `/Users/ditto/Documents/jingjipeixun/training_system/routes/student_routes.py`
  - Add renewal attachment fields, rule selection, validation, upload whitelist, ZIP download support.
- Modify: `/Users/ditto/Documents/jingjipeixun/training_system/routes/config_routes.py`
  - Return attachment config with special equipment renewal profile.
- Modify: `/Users/ditto/Documents/jingjipeixun/training_system/services/image_service.py`
  - Add renewal attachment labels and deletion support.
- Modify: `/Users/ditto/Documents/jingjipeixun/training_system/services/material_service.py`
  - Generate a stitched renewal material image.
- Modify: `/Users/ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py`
  - Test renewal material stitching.
- Create: `/Users/ditto/Documents/jingjipeixun/training_system/tests/test_renewal_attachments.py`
  - Test attachment rule selection and temporary file commit labels.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/utils/validators.js`
  - Add renewal labels and required file logic.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/utils/api.js`
  - Include `application_type`, new file fields, renewal allowed attachment normalization.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/components/student-form/student-form.js`
  - Emit application type change events.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/components/student-form/student-form.wxml`
  - Show “新考证 / 复审” selector for special equipment.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/components/student-form/student-form.wxss`
  - Style the selector using existing segmented control patterns.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/pages/user/submit/submit.js`
  - Track application type and compute enabled attachments.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/pages/user/edit/edit.js`
  - Load, edit, and resubmit application type and renewal attachments.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.js`
  - Build download URLs for new fields.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.wxml`
  - Preview renewal attachments.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/pages/admin/detail/detail.js`
  - Admin edit support for application type and renewal attachments.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.js`
  - Include new download URL fields.
- Modify: `/Users/ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.wxml`
  - Preview renewal attachments in admin review.

## Task 1: Backend Attachment Rules

- [ ] **Step 1: Write failing tests**

Create `/Users/ditto/Documents/jingjipeixun/training_system/tests/test_renewal_attachments.py`:

```python
import unittest

from routes import student_routes
from services import image_service


class RenewalAttachmentRuleTests(unittest.TestCase):
    def test_special_equipment_new_exam_keeps_existing_required_files(self):
        self.assertEqual(
            student_routes.get_required_attachments("special_equipment", "new_exam"),
            ["photo", "diploma", "id_card_front", "id_card_back", "hukou_residence", "hukou_personal"],
        )

    def test_special_equipment_renewal_requires_photo_and_certificate_pages(self):
        self.assertEqual(
            student_routes.get_required_attachments("special_equipment", "renewal"),
            ["photo", "certificate_info_page", "certificate_records_page"],
        )

    def test_renewal_certificate_labels_are_human_readable(self):
        self.assertEqual(image_service.get_attachment_label("certificate_info_page"), "原证件说明和个人信息页")
        self.assertEqual(image_service.get_attachment_label("certificate_records_page"), "原证件作业项目和聘用记录页")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest training_system.tests.test_renewal_attachments -v`
Expected: FAIL because helpers/new fields do not exist.

- [ ] **Step 3: Implement minimal backend rule helpers and labels**

Add `APPLICATION_TYPES`, `REQUIRED_ATTACHMENTS_BY_APPLICATION`, `normalize_application_type()`, and `get_required_attachments()` in `student_routes.py`. Add label helpers in `image_service.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest training_system.tests.test_renewal_attachments -v`
Expected: PASS.

## Task 2: Backend Persistence And Upload Flow

- [ ] **Step 1: Write failing persistence-focused tests**

Extend `/Users/ditto/Documents/jingjipeixun/training_system/tests/test_renewal_attachments.py` with checks for `FILE_MAP` containing `certificate_info_page` and `certificate_records_page`, and for `delete_student_files()` recognizing the new path keys.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest training_system.tests.test_renewal_attachments -v`
Expected: FAIL until new fields are wired.

- [ ] **Step 3: Implement DB columns and route flow**

Update model creation/compat columns, `create_student()`, route allowed text, create/update validation, upload route, safe path handling, ZIP download file list, and JSON response behavior.

- [ ] **Step 4: Run focused tests**

Run: `python3 -m unittest training_system.tests.test_renewal_attachments -v`
Expected: PASS.

## Task 3: Renewal Material Stitching

- [ ] **Step 1: Write failing material generation test**

Add to `/Users/ditto/Documents/jingjipeixun/training_system/tests/test_material_service.py`:

```python
def test_process_renewal_certificate_pages_stitches_two_pages_on_a4(self):
    with tempfile.TemporaryDirectory() as tmp_dir:
        front = os.path.join(tmp_dir, "front.jpg")
        back = os.path.join(tmp_dir, "back.jpg")
        Image.new("RGB", (1200, 800), "white").save(front)
        Image.new("RGB", (1200, 800), "white").save(back)

        result = material_service.process_renewal_certificate_pages(front, back, tmp_dir, "123-张三")

        self.assertTrue(result["success"])
        self.assertTrue(os.path.exists(result["output_path"]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest training_system.tests.test_material_service.MaterialServiceTests.test_process_renewal_certificate_pages_stitches_two_pages_on_a4 -v`
Expected: FAIL because function is missing.

- [ ] **Step 3: Implement stitching and generation branching**

Add `process_renewal_certificate_pages()` and branch `generate_student_materials()` for `application_type === "renewal"` to output personal photo plus stitched renewal material.

- [ ] **Step 4: Run material tests**

Run: `python3 -m unittest training_system.tests.test_material_service -v`
Expected: PASS.

## Task 4: Miniprogram Form And Preview

- [ ] **Step 1: Add application type state**

Update create/edit/admin pages to initialize `application_type: "new_exam"` and include new file keys.

- [ ] **Step 2: Add selector and event flow**

Update `student-form` component to render the selector for special equipment and emit `applicationtypechange`.

- [ ] **Step 3: Mirror attachment rules**

Update validators/API helpers to label and normalize renewal attachments.

- [ ] **Step 4: Add detail/review previews**

Update detail and admin review WXML/JS to show the two renewal attachments when present.

## Task 5: Verification

- [ ] Run: `python3 -m unittest training_system.tests.test_renewal_attachments -v`
- [ ] Run: `python3 -m unittest training_system.tests.test_material_service -v`
- [ ] Run static scans: `rg -n "certificate_info_page|certificate_records_page|application_type" training_system miniprogram`
- [ ] Manual miniprogram sanity: create special equipment new exam and renewal records, confirm attachment list switches correctly.
