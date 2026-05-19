# 小程序原生练习系统设计

## 背景

小程序需要增加“练习”模块。学员审核通过后才可见该模块，进入后只能练习自己报名并审核通过的考试项目。现有网页端 `/exam` 练习系统读取 `training_system/static/data/*.json`，不适合直接承载小程序权限控制、题库上下架、导入管理和学员练习进度。

本次选择原生小程序练习系统，并将题库从 JSON 文件迁移为数据库正式数据源。JSON 只作为导入来源。

当前题库文件为：

| 文件 | 题量 |
| --- | ---: |
| `A_电梯管理.json` | 813 |
| `G1_工业锅炉司炉.json` | 1778 |
| `N1_叉车司机.json` | 2159 |
| `Q2_桥式起重机.json` | 2007 |
| `R1_快开门式压力容器操作.json` | 1924 |

当前没有 `G3_锅炉水处理`、`Q1_起重机指挥`、`Q2_门式起重机` 的题库。报名这些项目的学员即使审核通过，也不显示练习入口，直到后台导入并启用对应题库。

## 目标

- 后台可以上传 JSON、重新导入题库、启用或停用题库。
- 题库数据进入数据库，接口分页返回题目。
- 小程序根据登录后的真实角色和练习资格生成 tab，不再先读旧缓存决定模块。
- 普通学员只有在存在审核通过且有启用题库的报名项目时，才显示“练习”tab。
- 练习模块只展示该学员报名对应的题库。
- 后端强制校验 openid 和报名状态，前端显示逻辑不作为权限边界。

## 数据模型

新增 `exam_banks` 表：

- `id`
- `bank_key`，如 `N1_叉车司机`
- `training_type`
- `job_category`
- `exam_project`
- `project_code`
- `display_name`
- `source_filename`
- `question_count`
- `is_active`
- `imported_at`
- `created_at`
- `updated_at`

新增 `exam_questions` 表：

- `id`
- `bank_id`
- `source_question_id`
- `question_type`
- `type_code`
- `question`
- `question_html`
- `options_json`
- `answer_json`
- `analysis`
- `question_images_json`
- `option_images_json`
- `audio`
- `sort_order`
- `raw_json`

新增 `mini_practice_progress` 表：

- `id`
- `openid`
- `bank_id`
- `mode`
- `done_count`
- `correct_count`
- `wrong_question_ids_json`
- `last_question_id`
- `updated_at`

模拟考试记录可作为第一版进度表的扩展，也可以单独建 `mini_exam_records`，保存 `score`、`total`、`duration_seconds`、`passed`、`answers_json`。

## 题库导入

导入逻辑按文件名解析默认映射：

- `A_电梯管理.json` -> `project_code=A`, `exam_project=电梯安全管理`
- `G1_工业锅炉司炉.json` -> `project_code=G1`, `exam_project=工业锅炉司炉`
- `N1_叉车司机.json` -> `project_code=N1`, `exam_project=叉车司机`
- `Q2_桥式起重机.json` -> `project_code=Q2`, `exam_project=桥式起重机司机`
- `R1_快开门式压力容器操作.json` -> `project_code=R1`, `exam_project=快开门式压力容器操作`

后台上传时允许管理员确认或调整映射。重新导入同一 `bank_key` 时，保留题库记录，替换该题库下的题目，并刷新 `question_count/imported_at`。

JSON 字段按当前格式保存：

- `question/question_html`
- `type/type_code`
- `options`
- `answer`
- `analysis`
- `question_images/option_images`
- `audio`
- 原始题目写入 `raw_json`，方便未来兼容字段变化。

## 后台管理

在管理后台增加“题库管理”入口，页面提供：

- 题库列表：题库名称、项目代码、考试项目、题量、状态、导入时间。
- 上传题库：选择 JSON 文件，填写或确认项目代码、考试项目、作业类别。
- 重新导入：替换已有题目。
- 启用/停用：停用后小程序不再显示该题库。

第一版不做逐题编辑。题目内容以 JSON 导入为准。

## 小程序权限与 Tab

登录后端返回统一角色信息和练习资格摘要：

- `role`: `admin` 或 `student`
- `isAdmin`
- `practiceEnabled`
- `practiceBanks`

小程序启动和每次回到 tab 时先等待 `app.ensureLogin()` 完成，再设置 tab：

- 普通学员：信息采集、我的提交；如果 `practiceEnabled` 为 true，增加练习。
- 管理员：审核管理等管理入口；是否显示练习可以按管理员自身报名资格决定，不默认开放全部题库。

废弃“先读本地 `is_admin` 决定 tab”的逻辑。本地缓存只作为展示过渡，不作为最终权限来源。

## 小程序练习页面

新增页面：

- `pages/practice/index/index`：题库列表和练习首页。
- `pages/practice/session/session`：答题页。
- `pages/practice/result/result`：模拟考试结果页，可选。

练习首页展示当前可练习项目，每个项目包含题量、已练习、正确率、错题数。

第一版模式：

- 顺序练习
- 随机练习
- 模拟考试：100 题，60 分钟，80 分及格。
- 错题练习

答题页支持单选、多选、判断题。答题后展示正确答案和解析；解析为空时不显示空面板。题目图片和选项图片沿用后端返回 URL。

## 后端 API

新增小程序练习 API：

- `GET /api/miniprogram/practice/summary`
  返回当前 openid 可练习题库和进度摘要。

- `GET /api/miniprogram/practice/banks/<bank_id>/questions`
  分页或按模式返回题目。后端先校验当前 openid 是否有审核通过且匹配该题库的报名记录。

- `POST /api/miniprogram/practice/progress`
  保存练习进度、错题集合和统计。

- `POST /api/miniprogram/practice/exams`
  保存模拟考试结果。

匹配资格时，学生状态至少包含 `reviewed`。如果后续平台报名会把状态更新为 `registered`，也应视为已审核通过后的可练习状态。

## 项目匹配规则

题库和学员报名通过 `project_code + exam_project` 匹配，必要时兼容同义名称：

- `A` 题库当前只覆盖电梯安全管理，不覆盖所有 A 类安全管理项目。
- `Q2_桥式起重机` 只覆盖桥式起重机司机，不覆盖门式起重机司机。
- 未导入题库的报名项目不显示练习。

这条规则防止仅凭代码匹配导致同代码不同项目误开放。

## 测试

后端测试覆盖：

- 导入 JSON 生成题库和题目。
- 重新导入替换题目并更新题量。
- 停用题库后不出现在小程序摘要。
- 普通学员只能看到本人审核通过且匹配的题库。
- 未审核、驳回、非本人、无题库的项目都不返回题目。

小程序侧优先抽纯函数测试：

- 根据登录结果生成 tab。
- 根据练习摘要决定是否显示练习 tab。
- 单选、多选、判断答案判定。
- 题目分页和答题进度更新。

如果当前测试环境缺少小程序测试框架，至少通过后端 pytest 和静态检查验证关键逻辑。
