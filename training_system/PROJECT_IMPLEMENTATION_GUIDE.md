# 学员培训系统项目实现文档

文档版本: `v1.0`  
最后更新: `2026-02-22`  
适用代码目录: `/Users/ditto/Documents/jingjipeixun/training_system`

---

## 1. 项目概述与架构设计

### 1.1 项目目标

本系统用于培训机构场景下的学员信息采集、审核与资料管理，核心目标如下:

1. 采集学员基础信息与证件附件。
2. 根据培训类别动态控制必传附件。
3. 管理端支持学员审核、自动保存、附件补传与下载。
4. 对特定项目在审核通过时自动生成体检表。
5. 支持 Excel 导出与附件 ZIP 打包。

### 1.2 技术栈

后端:

1. Python `3.9+`
2. Flask
3. SQLite
4. python-docx / Pillow / lxml
5. openpyxl

前端:

1. 原生 HTML/CSS/JavaScript（无前端构建工具）

文件存储:

1. 本地文件系统（`students/`）

### 1.3 总体架构

```text
[浏览器 index/admin]
        |
        v
[Flask app + Blueprints]
  | routes/*         -> API 编排
  | models/student   -> SQLite 读写
  | services/*       -> 附件/文档业务处理
  | utils/*          -> 校验、日志、异常
        |
        v
[students.db + 本地附件目录]
```

### 1.4 业务状态模型

学员状态:

1. `unreviewed` 未审核
2. `reviewed` 已审核

状态流转:

1. 新增学员 -> `unreviewed`
2. 审核通过 -> `reviewed`（可能自动生成体检表）
3. 审核不通过（已审核）-> 回退 `unreviewed`
4. 审核不通过（未审核）-> 可删除

---

## 2. 环境配置与依赖管理

### 2.1 环境要求

最低要求:

1. Python `3.9` 或更高版本
2. `pip`
3. 可写目录权限（用于 `database/`、`logs/`、`students/`）

推荐:

1. macOS / Linux / Windows 10+
2. 使用虚拟环境隔离依赖

### 2.2 Python 依赖

项目依赖文件: `requirements.txt`

```txt
Flask
python-docx
Werkzeug
Pillow
opencv-python
numpy
rembg
onnxruntime
lxml
openpyxl
```

补充说明:

1. `generate_students.py` 额外使用 `requests`，该包不在 `requirements.txt`，如需运行脚本请手动安装。
2. 若 `rembg/cv2` 不可用，系统仍可运行，但证件照背景替换会自动降级为“使用原图”。

### 2.3 配置参数

系统当前使用代码内配置（无 `.env` 依赖），关键配置在 `app.py`:

1. `BASE_DIR`: 项目根目录
2. `STUDENTS_FOLDER`: `BASE_DIR/students`
3. `DATABASE`: `BASE_DIR/database/students.db`
4. `MAX_CONTENT_LENGTH`: `16MB`
5. 运行端口: `5001`
6. 调试开关: 环境变量 `FLASK_DEBUG=true|false`

---

## 3. 详细安装部署步骤

以下步骤为“从零复现”标准流程，可直接复制执行。

### 3.1 获取代码

若已在本地目录可跳过。

```bash
cd /Users/ditto/Documents/jingjipeixun
```

### 3.2 创建虚拟环境并安装依赖

macOS/Linux:

```bash
cd /Users/ditto/Documents/jingjipeixun/training_system
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
cd /Users/ditto/Documents/jingjipeixun/training_system
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果需要生成模拟数据:

```bash
pip install requests
```

### 3.3 启动服务（开发模式）

```bash
cd /Users/ditto/Documents/jingjipeixun/training_system
export FLASK_DEBUG=true
python app.py
```

Windows PowerShell:

```powershell
cd /Users/ditto/Documents/jingjipeixun/training_system
$env:FLASK_DEBUG="true"
python app.py
```

启动成功后访问:

1. 采集页: [http://127.0.0.1:5001/](http://127.0.0.1:5001/)
2. 管理页: [http://127.0.0.1:5001/admin](http://127.0.0.1:5001/admin)

### 3.4 生产部署（Gunicorn）

安装:

```bash
pip install gunicorn
```

启动:

```bash
cd /Users/ditto/Documents/jingjipeixun/training_system
FLASK_DEBUG=false gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

### 3.5 部署验证

健康验证:

```bash
curl -i http://127.0.0.1:5001/
curl -i http://127.0.0.1:5001/api/config/job_categories
```

---

## 4. 源代码结构与模块说明

```text
training_system/
├── app.py                       # Flask 入口，初始化配置/日志/异常/蓝图
├── requirements.txt             # Python 依赖
├── config/
│   └── job_categories.json      # 培训类别、作业类别、操作项目、附件规则配置
├── models/
│   └── student.py               # students 表结构、CRUD 与公司聚合查询
├── routes/
│   ├── student_routes.py        # 学员核心业务接口
│   ├── export_routes.py         # Excel 导出接口
│   ├── file_routes.py           # 附件静态访问接口
│   └── config_routes.py         # 配置下发接口
├── services/
│   ├── image_service.py         # 图片背景替换、附件落盘与删除
│   └── document_service.py      # 体检表模板渲染与图片写入
├── utils/
│   ├── validators.py            # 字段与文件校验
│   ├── error_handlers.py        # 统一异常响应
│   └── logger.py                # 日志初始化
├── templates/
│   ├── index.html               # 信息采集页面
│   └── admin.html               # 管理页面
├── static/
│   ├── js/script.js             # 采集页交互逻辑
│   ├── js/admin.js              # 管理页交互逻辑
│   └── css/style.css            # 样式文件
├── database/
│   └── students.db              # SQLite 数据库
├── students/                    # 学员附件与体检表目录
├── 叉车司机体检表.docx           # 模板
└── 锅炉水处理体检表.docx         # 模板
```

---

## 5. 数据库设计与初始化流程

### 5.1 数据库类型

SQLite 单文件数据库: `database/students.db`

### 5.2 表结构（students）

```sql
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gender TEXT NOT NULL,
    education TEXT NOT NULL,
    school TEXT,
    major TEXT,
    id_card TEXT NOT NULL,
    phone TEXT NOT NULL,
    company TEXT,
    company_address TEXT,
    job_category TEXT NOT NULL,
    exam_project TEXT,
    project_code TEXT,
    training_type TEXT DEFAULT 'special_operation',
    status TEXT DEFAULT 'unreviewed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    photo_path TEXT,
    diploma_path TEXT,
    id_card_front_path TEXT,
    id_card_back_path TEXT,
    hukou_residence_path TEXT,
    hukou_personal_path TEXT,
    training_form_path TEXT
);
```

### 5.3 初始化流程

服务启动时自动执行:

1. `init_db()`：确保表存在（仅建表，不做历史数据迁移）。

### 5.4 常用数据库检查命令

```bash
cd /Users/ditto/Documents/jingjipeixun/training_system
sqlite3 database/students.db ".schema students"
sqlite3 database/students.db "SELECT status, training_type, COUNT(*) FROM students GROUP BY status, training_type;"
sqlite3 database/students.db "SELECT id, name, job_category, exam_project, project_code FROM students ORDER BY id DESC LIMIT 10;"
```

---

## 6. 核心功能实现细节

### 6.1 采集页动态配置联动

数据来源: `/api/config/job_categories`

实现要点:

1. 采集页将“培训项目 + 作业类别”合并为一个下拉框（带 optgroup）。
2. 选择作业类别后自动刷新“操作项目”下拉框，并写入隐藏字段 `project_code`。
3. 根据选中的 `training_type` 动态控制附件显示与必填。

附件规则:

1. `special_operation`：`diploma`、`id_card_front`、`id_card_back`
2. `special_equipment`：`photo`、`diploma`、`id_card_front`、`id_card_back`、`hukou_residence`、`hukou_personal`

### 6.2 学员创建

接口: `POST /api/students`

关键逻辑:

1. 校验必填字段（姓名、性别、学历、身份证、手机号、单位名称、单位地址、作业类别）。
2. 规范化 `training_type`。
3. 检查该培训类型的必传附件是否齐全。
4. 校验附件格式/大小（JPG/PNG，默认 <=10MB）。
5. 附件落盘后写入数据库。

### 6.3 管理端自动保存

接口: `PUT /api/students/{id}`

实现要点:

1. 管理页字段编辑采用 debounce 自动保存（默认 1 秒）。
2. 自动保存时会根据当前作业类别推导并同步提交 `training_type`，避免数据不一致。
3. 修改作业类别后，操作项目选项会联动刷新。

### 6.4 审核通过自动生成体检表

接口: `POST /api/students/{id}/approve`

触发规则:

1. `project_code` 命中 `N1`（叉车司机）或 `G3`（锅炉水处理）时生成体检表。
2. 若 `project_code` 为空，则按 `exam_project` 名称模糊匹配模板关键词。

模板映射:

1. `N1 -> 叉车司机体检表.docx`
2. `G3 -> 锅炉水处理体检表.docx`

生成结果:

1. 体检表写入学员目录
2. `training_form_path` 更新到数据库
3. 学员状态更新为 `reviewed`

### 6.5 历史生成接口下线

接口: `POST /api/students/{id}/generate`

当前行为:

1. 已下线，返回 `410 Gone`
2. 提示使用“审核通过自动生成体检表”流程

### 6.6 附件上传、访问与打包

1. 单附件补传: `POST /api/students/{id}/upload`
2. 附件访问: `/students/<path:filename>`（新结构）
3. 审核后可打包下载: `GET /api/students/{id}/attachments.zip`

---

## 7. API 接口文档

统一说明:

1. Base URL: `http://127.0.0.1:5001`
2. 默认返回 `application/json`（文件下载接口除外）
3. 错误结构示例:

```json
{
  "error": "validation_failed",
  "fields": {
    "name": "必填项"
  }
}
```

### 7.1 页面路由

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 信息采集页 |
| GET | `/admin` | 管理页 |

### 7.2 配置接口

#### GET `/api/config/job_categories`

说明: 获取培训类型配置、作业类别、操作项目与附件规则。  
返回: `special_operation` 与 `special_equipment` 两个配置对象。

示例:

```bash
curl -s http://127.0.0.1:5001/api/config/job_categories
```

### 7.3 学员接口

#### POST `/api/students`

说明: 创建学员（`multipart/form-data`）。

必填文本字段:

1. `name`
2. `gender`
3. `education`
4. `id_card`
5. `phone`
6. `company`
7. `company_address`
8. `job_category`

可选文本字段:

1. `school`
2. `major`
3. `exam_project`
4. `project_code`
5. `training_type`（建议传；不传会按默认处理）

附件字段（按培训类型要求）:

1. `photo`
2. `diploma`
3. `id_card_front`
4. `id_card_back`
5. `hukou_residence`
6. `hukou_personal`

示例（特种设备）:

```bash
curl -X POST http://127.0.0.1:5001/api/students \
  -F "name=张三" \
  -F "gender=男" \
  -F "education=专科或同等学历" \
  -F "id_card=110101199001011234" \
  -F "phone=13800138000" \
  -F "company=测试公司" \
  -F "company_address=测试地址1号" \
  -F "job_category=锅炉作业" \
  -F "exam_project=锅炉水处理" \
  -F "project_code=G3" \
  -F "training_type=special_equipment" \
  -F "photo=@/absolute/path/photo.jpg" \
  -F "diploma=@/absolute/path/diploma.jpg" \
  -F "id_card_front=@/absolute/path/id_front.jpg" \
  -F "id_card_back=@/absolute/path/id_back.jpg" \
  -F "hukou_residence=@/absolute/path/hukou_res.jpg" \
  -F "hukou_personal=@/absolute/path/hukou_person.jpg"
```

成功响应:

```json
{
  "message": "Student added successfully",
  "id": 123
}
```

#### GET `/api/students`

说明: 获取学员列表。  
Query 参数:

1. `status`：`unreviewed`/`reviewed`，留空表示全部状态
2. `search`：姓名/身份证/手机号模糊搜索
3. `company`：单位模糊过滤
4. `training_type`：`special_operation`/`special_equipment`

示例:

```bash
curl "http://127.0.0.1:5001/api/students?status=unreviewed&training_type=special_equipment"
curl "http://127.0.0.1:5001/api/students?status=&company=测试"
```

#### PUT/PATCH `/api/students/{id}`

说明: 更新学员文本字段和可选附件（`multipart/form-data` 或 JSON）。

可更新字段:

1. `name`
2. `gender`
3. `education`
4. `school`
5. `major`
6. `id_card`
7. `phone`
8. `company`
9. `company_address`
10. `job_category`
11. `exam_project`
12. `project_code`（兼容 `exam_code`）
13. `training_type`

示例:

```bash
curl -X PUT http://127.0.0.1:5001/api/students/123 \
  -F "company=新单位" \
  -F "company_address=新地址2号" \
  -F "job_category=电工作业" \
  -F "training_type=special_operation"
```

#### POST `/api/students/{id}/upload`

说明: 为已存在学员补传单个附件。  
限制: 每次请求仅识别一个附件字段。

示例:

```bash
curl -X POST http://127.0.0.1:5001/api/students/123/upload \
  -F "id_card_front=@/absolute/path/id_front.jpg"
```

#### POST `/api/students/{id}/approve`

说明: 审核通过，状态改为 `reviewed`，并按规则自动生成体检表。

```bash
curl -X POST http://127.0.0.1:5001/api/students/123/approve
```

#### POST `/api/students/{id}/reject`

说明: 审核不通过。  
请求体:

1. `{"delete": true}` 删除学员（默认）
2. `{"delete": false}` 回退到 `unreviewed`

```bash
curl -X POST http://127.0.0.1:5001/api/students/123/reject \
  -H "Content-Type: application/json" \
  -d '{"delete": false}'
```

#### GET `/api/students/{id}/attachments.zip`

说明: 打包下载该学员附件（仅 `reviewed`）。

```bash
curl -L -o attachments.zip http://127.0.0.1:5001/api/students/123/attachments.zip
```

#### POST `/api/students/batch/approve`

```bash
curl -X POST http://127.0.0.1:5001/api/students/batch/approve \
  -H "Content-Type: application/json" \
  -d '{"ids":[1,2,3]}'
```

#### POST `/api/students/batch/reject`

```bash
curl -X POST http://127.0.0.1:5001/api/students/batch/reject \
  -H "Content-Type: application/json" \
  -d '{"ids":[1,2,3]}'
```

#### POST `/api/students/batch/delete`

```bash
curl -X POST http://127.0.0.1:5001/api/students/batch/delete \
  -H "Content-Type: application/json" \
  -d '{"ids":[1,2,3]}'
```

#### GET `/api/companies`

说明: 获取单位去重列表。  
Query 参数: `status`、`company`、`training_type`

```bash
curl "http://127.0.0.1:5001/api/companies?status=reviewed&training_type=special_equipment"
```

### 7.4 导出接口

#### GET `/api/export/excel`

Query 参数:

1. `status`：可空，空表示全部状态
2. `company`：单位筛选
3. `training_type`：培训类型筛选

```bash
curl -L -o students.xlsx "http://127.0.0.1:5001/api/export/excel?status=&training_type=special_equipment"
```

### 7.5 文件访问接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/students/<path:filename>` | 访问学员目录文件 |

### 7.6 已下线接口

#### POST `/api/students/{id}/generate`

返回:

1. HTTP `410`
2. `{"error":"该接口已下线，请使用审核通过自动生成体检表流程"}`

---

## 8. 关键算法与业务逻辑说明

### 8.1 培训类型推导算法

来源:

1. 前端根据作业类别的 `option.dataset.trainingType` 推导
2. 后端 `normalize_training_type` 兜底，仅允许:
   - `special_operation`
   - `special_equipment`

无效值默认落到 `special_operation`。

### 8.2 动态附件必传规则

规则定义:

1. 后端常量 `REQUIRED_ATTACHMENTS`
2. 前端配置 `job_categories.json.attachments`

创建时:

1. 后端按培训类型检查必传附件，缺失即返回 `ValidationError`。

管理补传时:

1. 后端校验当前培训类型允许哪些附件，不允许上传不相关附件。

### 8.3 体检表触发算法

函数: `needs_health_check(exam_project, project_code)`

规则顺序:

1. 优先按 `project_code`（大小写归一）精确匹配:
   - `N1` -> 叉车司机
   - `G3` -> 锅炉水处理
2. 若代号未命中，则按 `exam_project` 文本包含关键词匹配模板名。

### 8.4 体检表模板渲染

函数链路:

1. `generate_health_check_form` 选择模板并构建目标路径
2. `generate_word_doc` 填充文字（姓名、性别、身份证号）
3. `_insert_photo_into_doc` 写入照片:
   - 优先查找含“照片/照”单元格
   - 自动按一寸照比例与单元格宽度缩放
   - 失败时保底替换文档图片关系

### 8.5 图片背景处理算法

函数: `change_id_photo_bg`

逻辑:

1. 使用 `rembg` 人像分割得到 alpha
2. 使用 `opencv` 膨胀 alpha 边缘，避免衣物缺口
3. 与白底合成后输出 JPEG
4. 若依赖缺失或异常，直接回退原图

### 8.6 文件命名与目录策略

目录命名:

```text
students/<培训类型中文>-<单位名称>-<学员姓名>/
```

文件命名:

```text
<身份证号>-<姓名>-<附件中文标签>.<扩展名>
```

---

## 9. 常见问题与解决方案（FAQ）

### 9.1 启动报端口占用

现象:

1. `Address already in use`。

处理:

```bash
lsof -i :5001
kill -9 <PID>
```

或修改 `app.py` 端口。

### 9.2 上传报“文件MIME类型无效/大小超限”

原因:

1. 仅允许 JPG/PNG。
2. 单文件逻辑限制 `10MB`（应用总请求限制 `16MB`）。

处理:

1. 转换文件格式。
2. 压缩图片后重试。

### 9.3 审核通过后未生成体检表

排查:

1. 检查 `project_code` 是否为 `N1` 或 `G3`。
2. 检查模板文件是否存在:
   - `叉车司机体检表.docx`
   - `锅炉水处理体检表.docx`
3. 查看日志:

```bash
tail -f /Users/ditto/Documents/jingjipeixun/training_system/logs/app.log
tail -f /Users/ditto/Documents/jingjipeixun/training_system/logs/error.log
```

### 9.4 `rembg`/`cv2` 安装失败

影响:

1. 系统可运行。
2. 背景替换降级为原图，不影响核心业务流程。

建议:

1. 在支持的 Python 版本重新安装。
2. 或在容器/虚拟机中统一环境。

### 9.5 历史迁移已下线

当前版本不再提供历史库迁移脚本。若数据库结构与当前版本不一致，建议:

1. 先备份 `database/students.db`。
2. 使用 `sqlite3` 手动校验并补齐字段。
3. 或回退到兼容版本完成一次性迁移后再升级。

### 9.6 导出“全部状态”结果不完整

当前实现已修复:

1. `status` 为空时表示不过滤状态。
2. 若仍异常，检查前端请求 URL 是否传入了固定 `status`。

### 9.7 管理页修改作业类别后附件不一致

当前实现已修复:

1. 自动保存时会同步推导并提交 `training_type`。
2. 保存成功后若类型发生变化会重绘详情。

### 9.8 调用 `/api/students/{id}/generate` 失败

说明:

1. 该接口已下线，返回 `410`。
2. 使用 `POST /api/students/{id}/approve` 自动生成体检表。

---

## 10. 可复现验收清单

按以下顺序执行，可确认系统完整复现成功:

1. 服务可正常启动并访问 `/` 与 `/admin`。
2. 采集页可新增多个学员卡片。
3. 选择不同作业类别时，操作项目与附件区动态变化正确。
4. 必填字段和附件校验生效。
5. 学员提交后可在管理页查询到。
6. 管理页编辑任意字段后自动保存成功。
7. 修改作业类别后，`training_type` 与附件视图同步。
8. 审核通过 `G3` 或 `N1` 学员后自动生成体检表。
9. 已审核学员可附件打包下载。
10. 导出 Excel 在“全部状态/单状态”下均可正常导出。
11. 旧接口 `/api/students/{id}/generate` 返回 `410`。

---

## 11. 附录: 常用运维命令

### 11.1 查看最近 20 条学员

```bash
sqlite3 /Users/ditto/Documents/jingjipeixun/training_system/database/students.db \
  "SELECT id,name,status,training_type,job_category,exam_project,project_code,created_at FROM students ORDER BY id DESC LIMIT 20;"
```

### 11.2 导出当前数据库快照

```bash
cp /Users/ditto/Documents/jingjipeixun/training_system/database/students.db \
   /Users/ditto/Documents/jingjipeixun/training_system/database/students.db.backup.manual.$(date +%Y%m%d_%H%M%S)
```

### 11.3 清理日志（可选）

```bash
truncate -s 0 /Users/ditto/Documents/jingjipeixun/training_system/logs/app.log
truncate -s 0 /Users/ditto/Documents/jingjipeixun/training_system/logs/error.log
```

---

如需继续扩展文档（例如增加时序图、接口错误码枚举、Nginx/HTTPS 全量部署脚本、自动化回归测试说明），可在此文档基础上增补 `v1.1` 版本。
