# 小程序原生练习系统实施计划

> **给执行代理的要求：** 实施本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按任务逐项执行。步骤使用复选框（`- [ ]`）跟踪。

**目标：** 建设数据库题库、网页端题库管理后台，以及带权限控制的小程序原生练习模块。

**架构：** JSON 文件只作为题库导入来源，正式运行读取数据库中的 `exam_banks` 和 `exam_questions`。网页管理后台负责给任意培训项目上传、重新导入、启用或停用题库。小程序通过接口动态读取可练习题库：管理员可练习所有已启用题库，普通学员只可练习本人已审核通过且匹配的项目。

**技术栈：** Flask、SQLite、unittest/pytest 兼容测试、现有网页管理后台 HTML/CSS/JS、微信小程序 WXML/WXSS/JS。

**重要约束：** 执行本计划时不要创建 git commit，除非用户明确要求。

---

## 文件分工

- 新建 `training_system/services/exam_bank_service.py`
  负责 JSON 解析、题库导入/重导、题目标准化、权限资格查询、练习进度保存、模拟考试记录保存。
- 新建 `training_system/routes/exam_bank_routes.py`
  负责网页后台题库管理接口和小程序练习接口。
- 修改 `training_system/models/student.py`
  在 `init_db` 中初始化题库、题目、练习进度、考试记录表。
- 修改 `training_system/app.py`
  注册新的题库蓝图，并确认认证白名单/保护逻辑。
- 修改 `training_system/templates/admin.html`
  给现有网页后台顶部导航增加“题库管理”入口。
- 新建 `training_system/templates/exam_banks_admin.html`
  网页端题库管理页面。
- 新建 `training_system/static/js/exam_banks_admin.js`
  处理项目选择、JSON 上传、重新导入、启停题库。
- 修改 `training_system/static/css/style.css`
  给题库管理页面添加克制、工具型样式。
- 新建 `training_system/tests/test_exam_bank_service.py`
  测试导入、重导、权限资格、进度保存等服务逻辑。
- 新建 `training_system/tests/test_exam_bank_routes.py`
  测试网页后台接口和小程序接口。
- 修改 `miniprogram/app.json`
  注册练习页面和 tabBar 项。
- 修改 `miniprogram/app.js`
  保存角色、练习开关、可练习题库摘要。
- 修改 `miniprogram/utils/api.js`
  增加练习相关 API 封装。
- 修改 `miniprogram/utils/page-helpers.js`
  用登录结果判断权限，避免旧缓存影响模块展示。
- 修改 `miniprogram/custom-tab-bar/index.js`
  登录完成后动态生成 tab：管理员显示练习，普通学员按资格显示练习。
- 新建 `miniprogram/pages/practice/index/*`
  小程序练习首页和题库列表。
- 新建 `miniprogram/pages/practice/session/*`
  小程序答题页，支持顺序、随机、错题、模拟考试。
- 新建 `miniprogram/pages/practice/result/*`
  小程序模拟考试结果页。
- 新建 `miniprogram/utils/practice.js`
  练习纯函数：答案比较、题型识别、选项格式化。

## 任务 1：数据库表结构

**文件：**
- 修改 `training_system/models/student.py`
- 测试 `training_system/tests/test_exam_bank_service.py`

- [ ] **步骤 1：先写失败测试**

新增测试：调用 `init_db(temp_db)` 后确认以下表存在：

```python
def test_init_db_creates_exam_bank_tables(app_with_temp_database):
    init_db(app_with_temp_database.config["DATABASE"])
    with sqlite3.connect(app_with_temp_database.config["DATABASE"]) as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "exam_banks" in names
    assert "exam_questions" in names
    assert "mini_practice_progress" in names
    assert "mini_exam_records" in names
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python3 -m unittest training_system.tests.test_exam_bank_service -v`

预期：失败，因为测试文件或数据库表还不存在。

- [ ] **步骤 3：实现数据库表**

在 `init_db` 中创建：

- `exam_banks`：包含 `training_project_id`、`bank_key`、`training_type`、`job_category`、`exam_project`、`project_code`、`display_name`、`source_filename`、`question_count`、`is_active`、时间字段。
- `exam_questions`：保存标准化题目字段和 `raw_json`。
- `mini_practice_progress`：保存 openid 维度的练习进度。
- `mini_exam_records`：保存模拟考试记录。

新增索引：

- `idx_exam_banks_project_active`：`(training_project_id, is_active)`
- `idx_exam_questions_bank_sort`：`(bank_id, sort_order)`
- `idx_practice_progress_openid_bank`：`(openid, bank_id)`

- [ ] **步骤 4：运行测试，确认通过**

运行：`python3 -m unittest training_system.tests.test_exam_bank_service -v`

预期：通过。

## 任务 2：题库导入服务

**文件：**
- 新建 `training_system/services/exam_bank_service.py`
- 测试 `training_system/tests/test_exam_bank_service.py`

- [ ] **步骤 1：先写失败测试**

覆盖：

- 导入 JSON 后创建一个题库和题目。
- 重新导入会替换旧题目。
- 文件名只做建议映射，明确传入的 `training_project_id` 优先。
- JSON 无效或缺少答案时返回清晰错误。

测试题目样例：

```python
SAMPLE_QUESTIONS = [
    {
        "id": 101,
        "type": "单选题",
        "type_code": 1,
        "question": "1+1=?",
        "question_html": "1+1=?",
        "options": {"A": "1", "B": "2"},
        "answer": ["B"],
        "analysis": "基础加法",
        "question_images": [],
        "option_images": {},
        "audio": "",
    }
]
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python3 -m unittest training_system.tests.test_exam_bank_service -v`

预期：失败，因为服务文件还不存在。

- [ ] **步骤 3：实现导入服务**

实现函数：

- `list_training_projects(include_inactive=False)`
- `list_exam_banks()`
- `import_exam_bank(file_stream, filename, training_project_id, display_name='', is_active=True, replace_bank_id=None)`
- `set_exam_bank_active(bank_id, is_active)`
- `get_exam_bank(bank_id)`
- `get_questions(bank_id, mode='sequential', page=1, limit=20, wrong_question_ids=None)`

题型标准化：

- `type` 为 `判断题` 或 `type_code` 为 `0`/`3` 时识别为判断题。
- `type` 为 `多选题` 或 `type_code` 为 `2` 时识别为多选题。
- 其他默认识别为单选题。

JSON 字段保存时使用 `ensure_ascii=False`。

- [ ] **步骤 4：运行测试，确认通过**

运行：`python3 -m unittest training_system.tests.test_exam_bank_service -v`

预期：通过。

## 任务 3：练习资格与进度服务

**文件：**
- 修改 `training_system/services/exam_bank_service.py`
- 测试 `training_system/tests/test_exam_bank_service.py`

- [ ] **步骤 1：先写失败测试**

覆盖：

- 管理员可以看到所有已启用题库。
- 普通学员只能看到本人 `submitter_openid` 下，状态为 `reviewed` 或 `registered`，且匹配 `training_project_id` 或 `project_code + exam_project` 的已启用题库。
- 未审核、已驳回、非本人记录不授予练习资格。
- 停用题库永远不返回。

- [ ] **步骤 2：运行测试，确认失败**

运行：`python3 -m unittest training_system.tests.test_exam_bank_service -v`

预期：失败。

- [ ] **步骤 3：实现资格与进度逻辑**

实现：

- `get_practice_summary(openid, is_admin=False)`
- `can_access_bank(openid, bank_id, is_admin=False)`
- `save_progress(openid, bank_id, payload)`
- `save_exam_record(openid, bank_id, payload)`

摘要返回结构：

```json
{
  "practiceEnabled": true,
  "banks": [
    {
      "id": 1,
      "bankKey": "N1_叉车司机",
      "displayName": "叉车司机 (N1)",
      "projectCode": "N1",
      "examProject": "叉车司机",
      "questionCount": 2159,
      "progress": {
        "doneCount": 0,
        "correctCount": 0,
        "wrongCount": 0
      }
    }
  ]
}
```

- [ ] **步骤 4：运行测试，确认通过**

运行：`python3 -m unittest training_system.tests.test_exam_bank_service -v`

预期：通过。

## 任务 4：网页后台题库接口

**文件：**
- 新建 `training_system/routes/exam_bank_routes.py`
- 修改 `training_system/app.py`
- 测试 `training_system/tests/test_exam_bank_routes.py`

- [ ] **步骤 1：先写失败测试**

覆盖：

- `GET /admin/exam-banks` 已登录网页管理员可访问。
- `GET /api/admin/exam_banks/projects` 返回可绑定培训项目。
- `POST /api/admin/exam_banks/import` 接收 multipart JSON 并创建题库。
- `POST /api/admin/exam_banks/<id>/reimport` 替换题目。
- `POST /api/admin/exam_banks/<id>/toggle` 切换启用状态。

- [ ] **步骤 2：运行测试，确认失败**

运行：`python3 -m unittest training_system.tests.test_exam_bank_routes -v`

预期：失败，因为路由还不存在。

- [ ] **步骤 3：实现蓝图**

使用 `app.py` 里现有 session 认证逻辑。新增并注册蓝图。

路由：

- `GET /admin/exam-banks`
- `GET /api/admin/exam_banks/projects`
- `GET /api/admin/exam_banks`
- `POST /api/admin/exam_banks/import`
- `POST /api/admin/exam_banks/<int:bank_id>/reimport`
- `POST /api/admin/exam_banks/<int:bank_id>/toggle`

错误统一返回 `success: false` 和 `message`。

- [ ] **步骤 4：运行测试，确认通过**

运行：`python3 -m unittest training_system.tests.test_exam_bank_routes -v`

预期：通过。

## 任务 5：小程序练习接口

**文件：**
- 修改 `training_system/routes/exam_bank_routes.py`
- 测试 `training_system/tests/test_exam_bank_routes.py`

- [ ] **步骤 1：先写失败测试**

覆盖：

- 管理员 `summary` 返回所有已启用题库。
- 普通学员 `summary` 只返回符合资格的题库。
- 管理员可获取任意已启用题库题目。
- 普通学员访问无资格题库返回 403。
- 停用题库保持不可访问。
- 保存进度和提交模拟考试都必须先通过题库访问校验。

- [ ] **步骤 2：运行测试，确认失败**

运行：`python3 -m unittest training_system.tests.test_exam_bank_routes -v`

预期：失败。

- [ ] **步骤 3：实现小程序接口**

路由：

- `GET /api/miniprogram/practice/summary`
- `GET /api/miniprogram/practice/banks/<int:bank_id>/questions`
- `POST /api/miniprogram/practice/progress`
- `POST /api/miniprogram/practice/exams`

从 `g.mini_user` 读取 `openid` 和 `is_admin`。不要信任客户端传来的角色字段。

- [ ] **步骤 4：运行测试，确认通过**

运行：`python3 -m unittest training_system.tests.test_exam_bank_routes -v`

预期：通过。

## 任务 6：网页端题库管理页面

**文件：**
- 修改 `training_system/templates/admin.html`
- 新建 `training_system/templates/exam_banks_admin.html`
- 新建 `training_system/static/js/exam_banks_admin.js`
- 修改 `training_system/static/css/style.css`

- [ ] **步骤 1：搭建页面结构**

页面是管理工具，不做宣传页。包含：

- 与现有后台一致的顶部导航。
- 项目选择和上传表单。
- 题库列表表格。
- 每行提供重新导入和启用/停用操作。

- [ ] **步骤 2：实现前端数据交互**

实现：

- 加载培训项目。
- 加载题库列表。
- 使用 `FormData` 提交导入表单。
- 使用 `FormData` 提交单行重新导入。
- 切换启用状态。
- 显示内联成功/失败消息。

- [ ] **步骤 3：人工验证网页后台**

按项目现有方式启动 Flask 应用，登录网页后台，打开 `/admin/exam-banks`。

验证：

- 培训项目能加载。
- 未选择项目或文件时上传被拦截。
- 题库列表能加载。
- 启用/停用按钮能刷新状态。

不要提交 git。

## 任务 7：登录状态与动态 Tab

**文件：**
- 修改 `miniprogram/app.js`
- 修改 `miniprogram/utils/api.js`
- 修改 `miniprogram/utils/page-helpers.js`
- 修改 `miniprogram/custom-tab-bar/index.js`
- 修改 `miniprogram/app.json`

- [ ] **步骤 1：增加 API 封装**

在 `api.js` 中增加：

- `getPracticeSummary()`
- `getPracticeQuestions(bankId, params)`
- `savePracticeProgress(payload)`
- `savePracticeExam(payload)`

- [ ] **步骤 2：扩展全局状态**

增加：

- `role`
- `practiceEnabled`
- `practiceBanks`

登录成功拿到 token 后调用 `getPracticeSummary()`。如果摘要失败，登录仍算成功，但 `practiceEnabled=false`，并在练习页展示可重试错误。

- [ ] **步骤 3：修复 tab 生成逻辑**

自定义 tab bar：

- 等待 `getApp().ensureLogin()` 完成后再生成最终 tab。
- 管理员 tab 包含 `审核管理` 和 `练习`。
- 普通学员 tab 包含 `信息采集`、`我的提交`，有练习资格时增加 `练习`。
- 不再把本地旧 `is_admin` 缓存作为最终权限来源。

- [ ] **步骤 4：注册页面和 tabBar 项**

新增页面：

- `pages/practice/index/index`
- `pages/practice/session/session`
- `pages/practice/result/result`

在 `tabBar.list` 中增加练习页，因为自定义 tabBar 仍要求 tab 页面在原生 tabBar 中注册。

## 任务 8：小程序练习首页

**文件：**
- 新建 `miniprogram/pages/practice/index/index.js`
- 新建 `miniprogram/pages/practice/index/index.wxml`
- 新建 `miniprogram/pages/practice/index/index.wxss`
- 新建 `miniprogram/pages/practice/index/index.json`

- [ ] **步骤 1：实现加载和空状态**

状态：

- 正在加载摘要。
- 管理员看到已启用题库。
- 普通学员看到有资格题库。
- 普通学员无资格题库：显示“暂无可练习题库”。
- 摘要加载失败：显示重试按钮。

- [ ] **步骤 2：渲染题库列表**

每个题库展示：

- 题库显示名称。
- 项目代码。
- 题量。
- 已练习数、正确率、错题数。
- 模式按钮：顺序、随机、模拟、错题。

- [ ] **步骤 3：跳转答题页**

通过 URL query 传递 `bankId`、`mode`、`title`。

## 任务 9：小程序答题工具函数

**文件：**
- 新建 `miniprogram/utils/practice.js`

- [ ] **步骤 1：实现纯函数**

实现：

- `normalizeQuestionType(question)`
- `normalizeAnswer(answer)`
- `isCorrectAnswer(question, selectedKeys)`
- `formatOptionList(options)`
- `shuffleQuestions(questions)`

- [ ] **步骤 2：如有 JS 测试环境则补轻量测试**

如果项目没有 JS 测试框架，保持函数小而清晰，通过答题页人工验证。

## 任务 10：小程序答题页

**文件：**
- 新建 `miniprogram/pages/practice/session/session.js`
- 新建 `miniprogram/pages/practice/session/session.wxml`
- 新建 `miniprogram/pages/practice/session/session.wxss`
- 新建 `miniprogram/pages/practice/session/session.json`

- [ ] **步骤 1：按模式加载题目**

第一版：

- 顺序练习：按顺序分页拉题。
- 随机练习：后端随机或前端洗牌。
- 错题练习：使用进度中的错题 ID。
- 模拟考试：随机 100 题。

- [ ] **步骤 2：实现答题 UI**

支持：

- 单选。
- 多选。
- 判断。
- 题目图片和选项图片。
- 确认答案。
- 解析为空时不显示解析面板。

- [ ] **步骤 3：保存练习进度**

答题后或离开页面时保存：

- 已练习数。
- 正确数。
- 错题 ID。
- 模拟考试提交时保存考试记录。

- [ ] **步骤 4：实现模拟考试倒计时**

模拟考试模式：

- 60 分钟倒计时。
- 时间到自动交卷。
- 倒计时布局固定，避免数字变化造成抖动。

## 任务 11：小程序结果页

**文件：**
- 新建 `miniprogram/pages/practice/result/result.js`
- 新建 `miniprogram/pages/practice/result/result.wxml`
- 新建 `miniprogram/pages/practice/result/result.wxss`
- 新建 `miniprogram/pages/practice/result/result.json`

- [ ] **步骤 1：展示考试结果**

展示：

- 分数。
- 是否及格。
- 正确数。
- 错误数。
- 用时。

- [ ] **步骤 2：增加操作**

操作：

- 返回练习首页。
- 有错题时查看错题。
- 重新考试。

## 任务 12：最终验证

**文件：**
- 所有改动文件。

- [ ] **步骤 1：运行后端测试**

运行：

```bash
python3 -m unittest training_system.tests.test_exam_bank_service -v
python3 -m unittest training_system.tests.test_exam_bank_routes -v
```

预期：通过。

- [ ] **步骤 2：运行可用的现有测试**

如果环境安装了 `pytest`：

```bash
python3 -m pytest training_system/tests -q
```

如果没有安装，则运行目标 unittest，并在最终说明中注明 pytest 不可用。

- [ ] **步骤 3：人工验证网页后台**

验证 `/admin/exam-banks`：

- 上传当前 JSON 题库。
- 重新导入一个题库。
- 停用再启用一个题库。
- 确认题量与已知题量一致。

- [ ] **步骤 4：人工验证小程序**

验证：

- 管理员看到练习 tab 和所有已启用题库。
- 管理员可以顺序练习和模拟考试。
- 有已审核匹配报名的普通学员只看到对应题库。
- 无资格普通学员不显示练习 tab。
- 本地旧 `is_admin` 缓存不能覆盖服务端角色。

- [ ] **步骤 5：最终汇报**

汇报改动文件、测试命令和结果、未完成的人工验证。除非用户明确要求，不要提交 git。
