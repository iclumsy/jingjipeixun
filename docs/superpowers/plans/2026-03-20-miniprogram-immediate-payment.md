# 小程序报名后立即支付与支付管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前“小程序提交后等待审核”的流程改成“提交后立即进入支付”，同时补齐优惠码、管理员改价、线下收款登记和审核前可反复修改资料的完整闭环。

**Architecture:** 继续沿用现有 Flask + SQLite + 微信原生小程序架构，不引入云开发。后端新增独立支付/优惠码数据层与支付路由，学员记录仍是主业务对象；前端在现有提交、详情、编辑、管理员审核页面上扩展支付状态与管理入口。审核状态和支付状态彻底分离，资料锁定条件固定为“审核通过”，不是“已支付”。

**Tech Stack:** Flask、SQLite、微信小程序原生、WeChat Pay v3 JSAPI、Python `unittest`、`cryptography`

---

## 文件结构与职责

### 需要新增的文件

- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/models/payment.py`
  - 支付订单、优惠码、金额计算、锁码/核销、线下登记的数据库与领域逻辑。
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/routes/payment_routes.py`
  - 用户支付准备、管理员支付管理、微信回调入口。
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/services/wechat_pay_service.py`
  - 微信统一下单、签名、回调验签、支付参数拼装。
- Create: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.js`
- Create: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.wxml`
- Create: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.wxss`
- Create: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.json`
  - 管理员支付管理二级页，负责订单筛选、改价、线下收款和优惠码管理。
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/__init__.py`
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_payment_models.py`
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_payment_routes.py`
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_miniprogram_student_flow.py`
  - 后端最小可用自动化测试基线。

### 需要修改的文件

- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/app.py`
  - 注册支付蓝图、初始化支付表、放行微信支付回调白名单。
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/models/__init__.py`
  - 导出支付模型能力。
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/routes/student_routes.py`
  - 提交后立即建单、未审核前允许编辑、详情/列表带支付摘要、已支付驳回不重置支付状态。
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/routes/config_routes.py`
  - 继续返回培训项目配置，但要保留 `fee_cent` 给小程序直接使用。
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/config/job_categories.json`
  - 为每个 `exam_project` 增加 `fee_cent`。
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/requirements.txt`
  - 增加微信支付验签所需依赖 `cryptography`。
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/utils/api.js`
  - 新增支付、改价、线下登记、优惠码接口封装。
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/utils/constants.js`
  - 新增支付状态、支付渠道、优惠码状态标签。
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/submit/submit.js`
  - 提交成功后直接拉起支付，失败或取消时跳到详情继续支付。
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.wxss`
  - 展示审核状态 + 支付状态 + 支付卡片，并按“审核通过前可编辑”改写入口逻辑。
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/edit/edit.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/edit/edit.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/edit/edit.wxss`
  - 已支付但未审核通过的记录可继续修改，并明确提示“支付状态不受影响”。
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/list/list.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/list/list.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/components/student-card/student-card.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/components/student-card/student-card.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/components/student-card/student-card.wxss`
  - 列表卡展示审核状态和支付状态。
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.wxss`
  - 从审核管理页进入支付管理二级页，并在列表中显示支付摘要。
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/detail/detail.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/detail/detail.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/detail/detail.wxss`
  - 审核详情展示支付摘要和订单信息。
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/app.json`
  - 注册管理员支付管理页面。
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/README.md`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/PROJECT_IMPLEMENTATION_GUIDE.md`
  - 补充新的支付流程、环境变量和人工回归说明。

### 关键实现决策

1. 审核状态继续使用 `unreviewed` / `reviewed` / `rejected`，不混入支付语义。
2. 支付状态固定为 `unpaid` / `paid`，不引入 `paying`、`refunded` 等额外状态。
3. 学员记录在 `status != reviewed` 时，提交者本人都允许修改；`reviewed` 后立即锁定。
4. 未支付订单跟随资料变化自动重算金额；已支付订单永不自动重算。
5. 管理员改价允许升价和降价；一旦改价，该订单不再允许优惠码。
6. 优惠码固定为全局一次性固定减免码，系统自动生成，无有效期，可作废。
7. 优惠码在 `payment/prepare` 成功返回支付参数时锁定；支付成功后标记为 `used`。
8. 已支付后被驳回不退款、不重付，支付状态继续保持 `paid`。

### 支付配置约定

实现时统一使用以下环境变量名，不再临时命名：

- `WECHAT_PAY_MCH_ID`
- `WECHAT_PAY_CERT_SERIAL_NO`
- `WECHAT_PAY_PRIVATE_KEY_PATH`
- `WECHAT_PAY_API_V3_KEY`
- `WECHAT_PAY_NOTIFY_URL`
- `WECHAT_PAY_PLATFORM_CERT_PATH`
- `WECHAT_PAY_PLATFORM_CERT_SERIAL_NO`

`WECHAT_MINI_APPID` 继续复用现有小程序登录配置。

## Task 1: 建立支付数据层与测试基线

**Files:**
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/models/payment.py`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/models/__init__.py`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/app.py`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/requirements.txt`
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/__init__.py`
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_payment_models.py`

- [ ] **Step 1: 先写支付模型测试，锁定表结构和核心规则**

在 `test_payment_models.py` 中先覆盖以下行为：

```python
def test_create_unpaid_order_uses_student_fee_snapshot(self):
    ...

def test_paid_order_keeps_amount_after_student_changes(self):
    ...

def test_coupon_can_only_be_locked_once_globally(self):
    ...

def test_override_price_disables_coupon_usage(self):
    ...
```

重点断言：

1. 每个学员只有一笔当前订单。
2. 未支付订单会更新 `base_amount_cent` / `final_amount_cent`。
3. 已支付订单不会被后续资料修改回写金额。
4. 优惠码状态必须经历 `active -> locked -> used` 或 `active -> disabled`。

- [ ] **Step 2: 运行模型测试，确认当前实现还不具备这些能力**

Run: `python3 -m unittest training_system.tests.test_payment_models -v`
Expected: FAIL，报出 `payment.py` 不存在或相关函数未定义。

- [ ] **Step 3: 在 `payment.py` 中实现数据表与领域函数**

在新文件中实现：

1. `init_payment_db(database_path)`
2. `create_or_refresh_order_for_student(student, force_reprice=False)`
3. `get_order_by_student_id(student_id)`
4. `get_order_by_order_no(order_no)`
5. `mark_order_paid(...)`
6. `mark_order_offline_paid(...)`
7. `override_order_price(...)`
8. `create_discount_code(...)`
9. `lock_discount_code(...)`
10. `use_discount_code(...)`
11. `disable_discount_code(...)`
12. `release_locked_discount_code(...)`

表结构固定为：

```sql
CREATE TABLE payment_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL UNIQUE,
    order_no TEXT NOT NULL UNIQUE,
    base_amount_cent INTEGER NOT NULL,
    final_amount_cent INTEGER NOT NULL,
    discount_amount_cent INTEGER NOT NULL DEFAULT 0,
    override_amount_cent INTEGER,
    payment_status TEXT NOT NULL DEFAULT 'unpaid',
    payment_channel TEXT NOT NULL DEFAULT '',
    coupon_code TEXT NOT NULL DEFAULT '',
    payer_openid TEXT NOT NULL DEFAULT '',
    prepay_id TEXT NOT NULL DEFAULT '',
    transaction_id TEXT NOT NULL DEFAULT '',
    paid_at TEXT NOT NULL DEFAULT '',
    offline_marked_by TEXT NOT NULL DEFAULT '',
    override_updated_by TEXT NOT NULL DEFAULT '',
    notify_payload TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

```sql
CREATE TABLE discount_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    discount_cent INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    locked_order_no TEXT NOT NULL DEFAULT '',
    used_order_no TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    disabled_by TEXT NOT NULL DEFAULT '',
    used_at TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

- [ ] **Step 4: 把支付表初始化接到应用启动流程**

在 `app.py` 的数据库初始化阶段同时调用 `init_db(...)` 和 `init_payment_db(...)`，确保旧库启动时会自动补表，不需要外部迁移工具。

- [ ] **Step 5: 补上微信支付验签依赖**

在 `requirements.txt` 增加：

```txt
cryptography
```

不要在这一阶段引入额外 ORM 或迁移工具。

- [ ] **Step 6: 重新运行模型测试**

Run: `python3 -m unittest training_system.tests.test_payment_models -v`
Expected: PASS，至少覆盖订单建单、改价、锁码和支付后金额冻结规则。

- [ ] **Step 7: 提交数据层与测试基线**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/models/payment.py /Users/Ditto/Documents/jingjipeixun/training_system/models/__init__.py /Users/Ditto/Documents/jingjipeixun/training_system/app.py /Users/Ditto/Documents/jingjipeixun/training_system/requirements.txt /Users/Ditto/Documents/jingjipeixun/training_system/tests/__init__.py /Users/Ditto/Documents/jingjipeixun/training_system/tests/test_payment_models.py
git commit -m "feat: add payment order and discount code models"
```

## Task 2: 补齐培训费配置与公开配置输出

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/config/job_categories.json`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/routes/config_routes.py`
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_miniprogram_student_flow.py`

- [ ] **Step 1: 先写配置输出测试**

在 `test_miniprogram_student_flow.py` 中增加配置接口测试，断言 `GET /api/config/job_categories` 返回的每个 `exam_projects[]` 都包含 `fee_cent`。

- [ ] **Step 2: 运行配置测试，确认当前配置未包含金额**

Run: `python3 -m unittest training_system.tests.test_miniprogram_student_flow.MiniprogramConfigTests -v`
Expected: FAIL，断言 `fee_cent` 缺失。

- [ ] **Step 3: 为所有培训项目补齐 `fee_cent`**

在 `job_categories.json` 中给每一个 `exam_projects` 节点都加整数金额，例如：

```json
{"name": "低压电工作业", "code": "", "fee_cent": 0}
```

实现时不要留空值或字符串金额；统一使用“分”为单位的整数。

- [ ] **Step 4: 保持配置接口透传金额字段**

`config_routes.py` 本身已直接返回 JSON，除非有字段过滤逻辑，否则只需要补充注释和错误信息，不要再做额外转换。

- [ ] **Step 5: 重新运行配置测试**

Run: `python3 -m unittest training_system.tests.test_miniprogram_student_flow.MiniprogramConfigTests -v`
Expected: PASS，金额字段可直接被小程序消费。

- [ ] **Step 6: 提交培训费配置**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/config/job_categories.json /Users/Ditto/Documents/jingjipeixun/training_system/routes/config_routes.py /Users/Ditto/Documents/jingjipeixun/training_system/tests/test_miniprogram_student_flow.py
git commit -m "feat: add project fee configuration"
```

## Task 3: 接通学员生命周期、支付接口与微信回调

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/routes/student_routes.py`
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/routes/payment_routes.py`
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/services/wechat_pay_service.py`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/app.py`
- Create: `/Users/Ditto/Documents/jingjipeixun/training_system/tests/test_payment_routes.py`

- [ ] **Step 1: 先写路由测试，锁定接口行为**

在 `test_payment_routes.py` 中先覆盖：

```python
def test_submit_student_creates_unpaid_order(self):
    ...

def test_prepare_payment_locks_coupon_and_returns_payment_args(self):
    ...

def test_owner_can_edit_until_reviewed(self):
    ...

def test_reviewed_student_is_locked_for_owner(self):
    ...

def test_admin_can_mark_order_offline_paid(self):
    ...

def test_wechat_notify_is_idempotent(self):
    ...
```

- [ ] **Step 2: 运行路由测试，确认当前接口不满足计划**

Run: `python3 -m unittest training_system.tests.test_payment_routes -v`
Expected: FAIL，缺少支付路由、回调入口和新的编辑权限。

- [ ] **Step 3: 改造 `student_routes.py` 的提交、详情、更新规则**

把以下行为写死：

1. `POST /api/students` 创建学员后立即创建或刷新一笔 `unpaid` 订单。
2. 学员详情和列表都附带支付摘要字段。
3. 小程序普通用户在 `status != reviewed` 时允许修改自己的记录。
4. 如果订单未支付且未被管理员改价，修改后自动根据最新资料重算金额。
5. 如果订单已支付，只更新学员资料，不回写订单金额。
6. 如果订单未支付但管理员已改价，只刷新 `base_amount_cent`，保留 `final_amount_cent` 为管理员价格。
7. 驳回已支付记录时不触碰订单支付状态。

- [ ] **Step 4: 在 `payment_routes.py` 中实现用户支付入口和管理员管理入口**

按下列接口固定实现：

1. `POST /api/students/<id>/payment/prepare`
2. `GET /api/payments`
3. `POST /api/payments/<order_no>/override-price`
4. `POST /api/payments/<order_no>/mark-offline-paid`
5. `GET /api/discount-codes`
6. `POST /api/discount-codes`
7. `POST /api/discount-codes/<id>/disable`
8. `POST /api/payments/wechat/notify`

其中：

1. `prepare` 仅允许学员本人对自己的记录调用。
2. 改价和线下登记仅允许管理员。
3. 微信回调不依赖 session、mini_token 或 API key。

- [ ] **Step 5: 在 `wechat_pay_service.py` 中实现 WeChat Pay v3 JSAPI**

新服务文件中至少实现：

1. 构建统一下单请求体。
2. 使用商户私钥签名请求。
3. 将微信返回的 `prepay_id` 转成小程序 `wx.requestPayment` 所需参数。
4. 使用平台证书验签回调。
5. 校验通知中的 `out_trade_no`、金额、交易状态。

金额、订单号或签名任一不匹配时必须拒绝回调，不允许“容错接受”。

- [ ] **Step 6: 在 `app.py` 中注册支付蓝图并开放回调白名单**

要求：

1. 注册 `payment_bp`。
2. 在 `before_request` 白名单里放行 `/api/payments/wechat/notify`。
3. 其他支付接口继续走现有登录/管理员鉴权逻辑。

- [ ] **Step 7: 重新运行支付路由测试**

Run: `python3 -m unittest training_system.tests.test_payment_routes -v`
Expected: PASS，接口行为与编辑权限符合计划。

- [ ] **Step 8: 提交后端支付主流程**

```bash
git add /Users/Ditto/Documents/jingjipeixun/training_system/routes/student_routes.py /Users/Ditto/Documents/jingjipeixun/training_system/routes/payment_routes.py /Users/Ditto/Documents/jingjipeixun/training_system/services/wechat_pay_service.py /Users/Ditto/Documents/jingjipeixun/training_system/app.py /Users/Ditto/Documents/jingjipeixun/training_system/tests/test_payment_routes.py
git commit -m "feat: add immediate payment flow and payment APIs"
```

## Task 4: 改造学员端提交流程、详情页和编辑权限

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/utils/api.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/utils/constants.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/submit/submit.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.wxss`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/edit/edit.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/edit/edit.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/edit/edit.wxss`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/list/list.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/list/list.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/components/student-card/student-card.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/components/student-card/student-card.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/components/student-card/student-card.wxss`

- [ ] **Step 1: 先扩展 API 封装，给前端一个稳定的支付接口层**

在 `api.js` 中新增并导出：

1. `prepareStudentPayment(studentId, options = {})`
2. `markOfflinePaid(orderNo, payload = {})`
3. `overrideOrderPrice(orderNo, amountCent)`
4. `getPaymentOrders(params = {})`
5. `getDiscountCodes(params = {})`
6. `createDiscountCode(discountCent)`
7. `disableDiscountCode(codeId)`

同时让 `getStudents()` / `getStudentDetail()` 保留服务端返回的支付摘要，不要再丢弃这些字段。

- [ ] **Step 2: 改写提交页，让提交成功后直接进入支付**

`submit.js` 中按下面顺序重构：

1. 提交资料成功后拿到 `studentId`。
2. 立即调用 `prepareStudentPayment(studentId)`。
3. 使用返回参数执行 `wx.requestPayment(...)`。
4. 支付成功后跳转到详情页。
5. 支付取消或失败时也跳转详情页，但提示“可稍后继续支付”。

不要再弹“提交成功，等待审核”后直接回列表。

- [ ] **Step 3: 改写详情页，让它同时承担支付与状态中心**

在 `detail.js/wxml/wxss` 中新增支付卡片，展示：

1. 审核状态
2. 支付状态
3. 原价
4. 改价后金额
5. 优惠码输入框
6. 优惠结果
7. 最终应付
8. `继续支付` 按钮

显示规则固定为：

1. `payment_status == unpaid` 时显示支付按钮。
2. `status != reviewed` 时显示“继续编辑”入口。
3. `status == reviewed` 时隐藏编辑入口并显示锁定提示。

- [ ] **Step 4: 改写编辑页，让已支付未审核记录也可修改**

在 `edit.js` 中去掉“只有驳回可编辑”的前端限制，改成按服务端返回的 `can_edit` 或 `status != reviewed` 控制。

页面上新增一条明确提示：

```text
资料修改不会影响已完成的支付状态；若订单尚未支付，应付金额会按最新资料自动更新。
```

- [ ] **Step 5: 在列表和卡片中加入支付状态**

让“我的提交”列表卡同时显示：

1. 审核状态标签
2. 支付状态标签
3. 待支付记录的入口文案改为“继续支付 / 查看详情”

点击行为固定为：

1. `status != reviewed` 时允许进入编辑页。
2. `status == reviewed` 时进入详情页。

- [ ] **Step 6: 进行小程序学员端手工回归**

手工检查以下场景：

1. 新提交后立即拉起支付。
2. 取消支付后可从详情继续支付。
3. 已支付但未审核通过记录可进入编辑页修改。
4. 审核通过后记录不可编辑。
5. 未支付记录修改培训项目后，详情金额随之变化。

- [ ] **Step 7: 提交学员端支付体验改造**

```bash
git add /Users/Ditto/Documents/jingjipeixun/miniprogram/utils/api.js /Users/Ditto/Documents/jingjipeixun/miniprogram/utils/constants.js /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/submit/submit.js /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.js /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.wxml /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/detail/detail.wxss /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/edit/edit.js /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/edit/edit.wxml /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/edit/edit.wxss /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/list/list.js /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/user/list/list.wxml /Users/Ditto/Documents/jingjipeixun/miniprogram/components/student-card/student-card.js /Users/Ditto/Documents/jingjipeixun/miniprogram/components/student-card/student-card.wxml /Users/Ditto/Documents/jingjipeixun/miniprogram/components/student-card/student-card.wxss
git commit -m "feat: add immediate payment flow to miniprogram user pages"
```

## Task 5: 增加管理员支付管理二级页

**Files:**
- Create: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.js`
- Create: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.wxml`
- Create: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.wxss`
- Create: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.json`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/app.json`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.wxss`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/detail/detail.js`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/detail/detail.wxml`
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/detail/detail.wxss`

- [ ] **Step 1: 在审核管理页增加“支付管理”入口**

入口要求：

1. 仅管理员可见。
2. 放在当前审核管理页头部或筛选区域，不新增主 Tab。
3. 点击后进入 `/pages/admin/payment/payment`。

- [ ] **Step 2: 实现管理员支付管理页的订单区**

订单区至少支持：

1. 按支付状态筛选 `unpaid` / `paid`
2. 按培训类型筛选
3. 按公司或姓名搜索
4. 查看订单金额摘要
5. 对未支付订单执行“改价”
6. 对未支付订单执行“标记线下已支付”

改价弹窗中只接收“分”为单位的正整数，不接受浮点或空值。

- [ ] **Step 3: 在同一页面实现优惠码管理区**

优惠码管理区至少支持：

1. 单个生成优惠码
2. 输入固定减免金额
3. 查看状态 `active` / `locked` / `used` / `disabled`
4. 作废未使用优惠码

系统生成码值时统一使用短横线分隔的大写字母数字，例如：

```text
JKPX-8F2Q-7M4N
```

- [ ] **Step 4: 在审核详情页展示支付摘要**

详情页中增加只读区块，显示：

1. 当前支付状态
2. 原价
3. 最终应付
4. 改价信息
5. 是否使用优惠码
6. 支付渠道
7. 支付时间

该区块只读，不在审核详情页直接执行管理动作，避免页面职责混乱。

- [ ] **Step 5: 进行管理员端手工回归**

重点检查：

1. 审核管理能进入支付管理二级页。
2. 未支付订单能改价。
3. 未支付订单能标记线下已支付。
4. 优惠码能生成、锁定、使用和作废。
5. 审核详情里能看到支付信息，但不会和审核按钮互相干扰。

- [ ] **Step 6: 提交管理员支付管理能力**

```bash
git add /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.js /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.wxml /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.wxss /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/payment/payment.json /Users/Ditto/Documents/jingjipeixun/miniprogram/app.json /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.js /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.wxml /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/review/review.wxss /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/detail/detail.js /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/detail/detail.wxml /Users/Ditto/Documents/jingjipeixun/miniprogram/pages/admin/detail/detail.wxss
git commit -m "feat: add miniprogram payment management for admins"
```

## Task 6: 文档、联调与最终验收

**Files:**
- Modify: `/Users/Ditto/Documents/jingjipeixun/miniprogram/README.md`
- Modify: `/Users/Ditto/Documents/jingjipeixun/training_system/PROJECT_IMPLEMENTATION_GUIDE.md`
- Reference: `/Users/Ditto/Documents/jingjipeixun/docs/superpowers/plans/2026-03-20-miniprogram-immediate-payment.md`

- [ ] **Step 1: 更新小程序 README**

补充：

1. 提交后立即支付的新用户流程
2. 继续支付入口
3. 管理员支付管理页入口
4. 合法域名与支付回调的配置注意事项

- [ ] **Step 2: 更新后端实现说明**

在 `PROJECT_IMPLEMENTATION_GUIDE.md` 中新增：

1. 新的业务状态图：审核状态 + 支付状态
2. 订单与优惠码表结构说明
3. 需要的微信支付环境变量
4. 未支付改价、已支付驳回、审核通过锁定的规则

- [ ] **Step 3: 进行后端自动化测试总跑**

Run: `python3 -m unittest discover -s /Users/Ditto/Documents/jingjipeixun/training_system/tests -v`
Expected: PASS，支付模型、路由和提交流程测试全部通过。

- [ ] **Step 4: 进行联调回归**

按顺序手工走完：

1. 新建记录 -> 立即支付成功 -> 审核前修改 -> 审核通过锁定
2. 新建记录 -> 取消支付 -> 回详情继续支付
3. 新建记录 -> 使用优惠码支付
4. 新建记录 -> 管理员改价 -> 学员支付
5. 新建记录 -> 管理员线下标记已支付 -> 正常审核
6. 已支付记录 -> 驳回 -> 学员修改 -> 再审核
7. 未支付记录 -> 先审核通过 -> 后续继续支付

- [ ] **Step 5: 提交文档和收尾**

```bash
git add /Users/Ditto/Documents/jingjipeixun/miniprogram/README.md /Users/Ditto/Documents/jingjipeixun/training_system/PROJECT_IMPLEMENTATION_GUIDE.md
git commit -m "docs: document immediate payment workflow"
```

## 验收标准

实现完成后，必须同时满足以下条件才算交付：

1. 学员提交资料后会立即进入支付流程。
2. 取消支付不会丢记录，后续可从详情继续支付。
3. 学员在审核通过前都可以继续修改资料。
4. 审核通过后资料锁定，不再允许学员自行修改。
5. 已支付记录后续被驳回时，不会变回未支付。
6. 未支付记录修改后金额按最新资料重算。
7. 管理员可在小程序里改价、标记线下已支付、生成和作废优惠码。
8. 微信回调具备签名校验和幂等处理。
9. 自动化测试和联调回归都通过。

## 备注

1. 本计划默认不实现退款、部分支付、自动关单、线下支付复杂收款单据。
2. 如后续要扩展“审核通过后才能支付”或“先付后审”之外的第三种模式，应在支付数据层保留订单状态扩展空间，但本期不提前实现。





# 提交后立即支付并保留后续修改能力方案

**Summary**
- 流程改为：学员提交资料后先创建记录并立即拉起支付；支付和审核解耦，审核不再是支付前置条件。
- 学员记录在“审核通过”之前都允许本人继续修改；一旦管理员审核通过，该记录立即锁定，不能再由学员自行修改。
- 支付状态独立维护。已付款被驳回时不退款、不重付，学员修改资料后继续沿用原支付状态；未付款记录修改后，下次支付按最新资料自动重算金额。

**Key Changes**
- 学员提交链路改为两段式：
  - `POST /api/students` 保存正式记录，默认进入 `unreviewed` 审核状态，并同步创建/更新未支付订单。
  - 前端提交成功后立即调用支付准备接口并拉起 `wx.requestPayment`；若用户取消或失败，记录保留为未支付，可在“我的提交”里继续支付。
- 编辑权限从“仅驳回可改”改为“审核通过前可改”：
  - 小程序普通用户可修改自己名下所有 `unreviewed` / `rejected` 记录，不论是否已支付。
  - `reviewed` 记录一律锁定，只能查看和继续支付（如果仍未支付）。
- 审核与支付拆开：
  - 管理员可以查看、驳回、通过未支付记录。
  - 未支付记录也允许直接“审核通过”。
  - 审核通过只锁定资料，不改变支付状态；因此会出现“已审核但未支付”的记录。
- 订单金额规则固定为：
  - 基础价来自培训项目配置 `fee_cent`。
  - 未支付订单如果学员修改了影响价格的字段，系统按最新资料自动重算应付金额。
  - 已支付订单即使后续修改资料导致理论价格变化，也不补差、不退款，支付状态保持 `paid`，最终按管理员认定处理。
  - 管理员可对未支付订单手动改价，允许升价或降价；一旦改价，该订单不可再使用优惠码。
- 优惠码规则沿用并适配新流程：
  - 全局通用、固定减免、单码全局仅一次、系统自动生成、支持作废。
  - 学员在支付卡片中手动输入优惠码。
  - 优惠码在支付准备成功时锁定到订单；如果订单后来被管理员改价或主动移除优惠码，系统释放该优惠码锁定并恢复可用。
- 线下支付管理保留：
  - 管理员在小程序“审核管理”内进入支付管理二级页。
  - 对未支付订单可直接标记为线下已支付。
  - 前端只暴露“标记已支付”，系统内部自动记录渠道 `offline`、操作人和操作时间。

**Public APIs / Interfaces**
- `GET /api/config/job_categories` 的 `exam_projects[]` 新增 `fee_cent`。
- `GET /api/students`、`GET /api/students/<id>` 响应新增支付摘要：
  - `payment_status`
  - `base_amount_cent`
  - `final_amount_cent`
  - `discount_amount_cent`
  - `override_amount_cent`
  - `payment_channel`
  - `paid_at`
  - `can_pay`
  - `can_edit`
- 新增 `POST /api/students/<id>/payment/prepare`：
  - 学员提交后立即调用
  - 入参可带 `coupon_code`
  - 返回 `wx.requestPayment` 所需参数和当前订单金额摘要
- 新增 `POST /api/payments/wechat/notify`：
  - 微信支付回调
  - 做签名校验、金额校验、幂等回写
- 新增管理员支付接口：
  - `GET /api/admin/payments`
  - `POST /api/admin/payments/<order_no>/override-price`
  - `POST /api/admin/payments/<order_no>/mark-offline-paid`
  - `GET /api/admin/discount-codes`
  - `POST /api/admin/discount-codes`
  - `POST /api/admin/discount-codes/<id>/disable`

**UI / Behavior Changes**
- 学员端：
  - 提交成功后不再停留在“提交成功等待审核”，而是立即进入支付流程。
  - 支付取消或失败后跳转到该记录详情页，显示“继续支付”入口。
  - 详情页在审核通过前始终提供“编辑资料”入口；审核通过后隐藏编辑入口，仅保留查看和支付状态展示。
  - “我的提交”列表同时显示审核状态和支付状态。
- 管理员小程序：
  - 审核列表增加支付状态标识与筛选，便于区分“未付/已付/线下已付”。
  - 审核详情展示订单金额、支付状态、是否使用优惠码、是否被改价。
  - `审核管理` 增加“支付管理”二级页，用于改价、线下标记已支付、优惠码生成和作废。

**Test Plan**
- 后端接口测试覆盖：
  - 提交后能创建学员记录和未支付订单
  - 支付准备接口可被新建记录立即调用
  - 支付取消后记录仍存在且可继续支付
  - 未支付记录修改影响价格字段后，订单金额按最新资料重算
  - 已支付记录修改影响价格字段后，支付状态保持 `paid` 且金额不重算
  - 管理员可审核未支付记录并直接通过
  - 审核通过后学员更新接口返回禁止修改
  - 优惠码单次锁定、使用、作废、改价释放逻辑正确
  - 线下标记已支付后渠道和审计字段正确写入
- 小程序回归覆盖：
  - 提交后立即拉起支付
  - 取消支付后可在详情页继续支付
  - 审核通过前可反复编辑并重新保存
  - 审核通过后记录锁定不可编辑
  - 已付款被驳回后仍显示已支付，修改后重新进入审核
  - 未付款被通过后不可编辑但仍可继续支付

**Assumptions**
- 审核和支付完全解耦，管理员是否先审不受支付状态限制。
- 学员记录的唯一锁定条件是“审核通过”；不是“已支付”。
- 已支付后资料再修改，不做补差价或退款，管理员最终认定有效信息。
- 线下支付只做状态登记，不录入复杂收款单据字段。
- 优惠码只作用于未支付在线订单；已支付订单和已改价订单都不再适用优惠码。
