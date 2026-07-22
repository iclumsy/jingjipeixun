# Mini Program Admin Delete and Full Load Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Add a unified local-only student delete action to the three requested admin states and make admin student and learning-statistics lists load every matching record in one response while preserving ordinary-user pagination.

**Architecture:** Keep the existing delete endpoint and backend delete semantics. Add an opt-in `all` mode to the shared client API, use it only from the admin review page, and remove client/server pagination from the admin learning-statistics path. Keep the page's existing request sequencing, refresh, dashboard, and filter flows, replacing lists instead of appending pages.

**Tech Stack:** WeChat Mini Program JavaScript/WXML/WXSS, Node.js `assert` tests, Flask/Python `unittest` route tests, SQLite.

---

### Task 1: Add an explicit full-list mode to the shared student API

**Files:**
- Create: `miniprogram/utils/api.students.test.js`
- Modify: `miniprogram/utils/api.js:539-600`

- [ ] **Step 1: Write the failing API contract test**

Create a small Node test that stubs the module's `wx.request` transport with 120 server records, calls `getStudents({ all: true, status: 'reviewed' })`, and asserts that all 120 records are returned, the request does not send `all`, and the response still contains project counts. Add a second assertion using `{ page: 2, limit: 20 }` to prove the default API still returns exactly 20 records and retains pagination metadata.

- [ ] **Step 2: Run the test and verify it fails for the missing `all` contract**

Run:

```bash
node miniprogram/utils/api.students.test.js
```

Expected: FAIL because `getStudents({ all: true })` currently still returns only the default first 20 records and forwards no explicit full-list behavior.

- [ ] **Step 3: Implement the minimal opt-in branch**

Destructure `all = false` in `getStudents`, leave it out of the request query, keep the existing project filtering and aggregate calculations, and return `list` as the complete filtered list when `all` is truthy. For that branch set `page: 1`, `limit: list.length`, and `hasMore: false`; leave the existing slice path untouched when `all` is false. Do not change the backend request or ordinary-user callers.

- [ ] **Step 4: Run the API test and verify it passes**

Run the same command. Expected: PASS, including both the full-list and legacy pagination assertions.

- [ ] **Step 5: Commit the isolated API change**

```bash
git add miniprogram/utils/api.js miniprogram/utils/api.students.test.js
git commit -m "feat: support full student list queries"
```

### Task 2: Return the complete admin learning-statistics result

**Files:**
- Modify: `training_system/routes/student_routes.py:2741-3022`
- Modify: `training_system/tests/test_learning_stats.py`

- [ ] **Step 1: Add a regression test before changing the route**

Add a test that creates 25 reviewed students, requests `/api/miniprogram/admin/learning_stats?page=2&limit=1`, and asserts status 200, `total == 25`, `len(list) == 25`, every list item has `studyDurationSeconds`, and the response has no `page`, `limit`, or `hasMore` keys. This proves query parameters can no longer reduce the admin result.

- [ ] **Step 2: Run the targeted test and verify the expected failure**

Run:

```bash
pytest -q training_system/tests/test_learning_stats.py -k full
```

Expected: FAIL because the current route slices to one item and emits pagination fields.

- [ ] **Step 3: Remove route pagination and calculate duration for all rows**

Stop parsing `page` and `limit`; retain the existing search, status, project, permission, project-count, and list-building logic. Set `filtered_list` as the response list, run `estimate_subject_study_time` for every item in it, and return `list`, `projects`, `project_counts`, `total_matching_count`, and `total` without pagination fields. Update the route docstring to describe a complete filtered result.

- [ ] **Step 4: Run the full learning-statistics test module**

```bash
pytest -q training_system/tests/test_learning_stats.py
```

Expected: PASS, including the new full-result regression and existing project-filter tests.

- [ ] **Step 5: Commit the route change**

```bash
git add training_system/routes/student_routes.py training_system/tests/test_learning_stats.py
git commit -m "feat: return full admin learning stats"
```

### Task 3: Add delete actions and remove admin-page pagination

**Files:**
- Create: `miniprogram/pages/admin/review/review.test.js`
- Modify: `miniprogram/pages/admin/review/review.js:37-1300`
- Modify: `miniprogram/pages/admin/review/review.wxml:179-283,473-477,788-828`
- Modify: `miniprogram/pages/admin/review/review.wxss:1500-1618`

- [ ] **Step 1: Write failing page contract tests**

Add Node source-contract tests that assert:

1. `review.wxml` contains a `更多操作` button in both the `unreviewed` and `registered` blocks, and a red `删除学员` item in the shared sheet.
2. `review.js` defines a `canDeleteFromList` guard for exactly `unreviewed`, `reviewed`, and `registered`, uses `api.deleteStudent`, includes the registered warning text about not changing provincial registration, and refreshes with `refreshAll(true)` after success.
3. The page no longer contains `onReachBottom`, `reportPage`, `reportLimit`, `reportHasMore`, `loadRecords(false)`, `loadReportRecords(false)`, or the two pagination-end messages; review requests use `all: true`, and report requests omit `page`/`limit`.

The test may also instantiate the page through a minimal `global.Page` shim to exercise the guard and delete confirmation flow: cancellation must not call the API; confirmation must call the selected ID once and invoke the full refresh; a rejected API promise must leave `records` unchanged and clear the deleting lock.

- [ ] **Step 2: Run the page test and verify it fails**

```bash
node miniprogram/pages/admin/review/review.test.js
```

Expected: FAIL because the two missing list buttons, delete handler, and existing pagination references are still present.

- [ ] **Step 3: Implement delete UI and behavior**

Add `更多操作` to the unreviewed and registered card action blocks. Add a red `删除学员` item to the existing sheet, conditioned on a page-level guard that returns true only for the three target statuses and `moreActionsStudent.actions.canDelete`. Add `deletingStudentId` to page data and implement `onMoreDelete`: close the sheet, show a confirmation containing the student name and permanent local-record/attachment deletion text, append the explicit provincial-registration warning for registered records, ignore a second request while locked, call `api.deleteStudent(id)`, show success, and call `refreshAll(true)`. On failure keep the current list, clear the lock, and show the backend error.

- [ ] **Step 4: Remove pagination from the review tab**

Delete review `page`, `limit`, and `hasMore` state and the `onReachBottom` implementation. Make `loadRecords` issue `api.getStudents({ ...filters, all: true })`, map the returned list, and replace `records` on every successful request. Remove page resets and the review “已显示全部记录” footer. Keep loading/error/refresh behavior and aggregate fields unchanged.

- [ ] **Step 5: Remove pagination from the learning-statistics tab**

Delete report page/limit/hasMore state and the `onReachBottom` branch. Make `refreshReportAll` trigger one full request, make `loadReportRecords` send only search/status/project, and replace `reportList` with the mapped response. Remove pagination metadata updates and the “已显示全部学习记录” footer. Preserve request-sequence protection and duration formatting.

- [ ] **Step 6: Style the shared delete item and run the page test**

Use the existing `.more-action-delete` selectors for the red label/icon treatment, adding only missing layout rules if needed. Run `node miniprogram/pages/admin/review/review.test.js`; expected: PASS.

- [ ] **Step 7: Commit the admin page change**

```bash
git add miniprogram/pages/admin/review/review.js miniprogram/pages/admin/review/review.wxml miniprogram/pages/admin/review/review.wxss miniprogram/pages/admin/review/review.test.js
git commit -m "feat: add admin student deletion and full lists"
```

### Task 4: Verify scope, regressions, and repository cleanliness

**Files:** No new files; inspect all modified files and preserve `miniprogram/pages/user/list/list.js` pagination.

- [ ] **Step 1: Run focused JavaScript tests**

```bash
node miniprogram/utils/api.students.test.js
node miniprogram/pages/admin/review/review.test.js
```

Expected: both exit 0.

- [ ] **Step 2: Run backend regression tests**

```bash
pytest -q training_system/tests/test_learning_stats.py
pytest -q training_system/tests/test_student_serializer.py
```

Expected: all tests pass.

- [ ] **Step 3: Check pagination scope and whitespace**

```bash
rg -n "onReachBottom|reportPage|reportLimit|reportHasMore|已显示全部|loadRecords\(false\)|loadReportRecords\(false\)" miniprogram/pages/admin/review
rg -n "page|limit|hasMore|onReachBottom" miniprogram/pages/user/list/list.js
git diff --check
```

Expected: the first command returns no matches, the second still shows ordinary-user pagination, and `git diff --check` is clean.

- [ ] **Step 4: Run the broader existing checks and report unrelated failures accurately**

Run the repository's available Mini Program and backend test commands. The known pre-existing `tabbar-selection` expectation mismatch (`审核管理` vs `学员管理`) is outside this change and must be reported separately if it remains.

