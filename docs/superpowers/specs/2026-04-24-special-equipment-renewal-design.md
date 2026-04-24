# 特种设备复审附件设计

## 背景

特种设备报名目前只支持“新考证”材料清单：个人照片、学历证书、身份证正反面、户口本户籍页、户口本个人页。现在需要在填写资料时区分“新考证”和“复审”。两种报名类型的基本信息、作业类别和操作项目一致，附件要求不同。

复审附件要求：

- 个人照片
- 原证件说明和个人信息页
- 原证件作业项目和聘用记录页

两张原证件照片在小程序中分别上传，生成报名材料时再拼接为类似 `training_system/logs/复审材料正反面.jpg` 的 A4 图片。

## 设计

新增 `application_type` 字段表示报名类型：

- `new_exam`: 新考证，默认值，用于兼容已有特种设备记录
- `renewal`: 复审

小程序的特种设备表单新增“新考证 / 复审”选择。切换报名类型时不改变基础信息、作业类别、操作项目，只刷新附件列表与校验规则。

新考证附件保持现状：

- `photo`: 个人照片
- `diploma`: 学历证书
- `id_card_front`: 身份证正面
- `id_card_back`: 身份证反面
- `hukou_residence`: 户口本户籍页
- `hukou_personal`: 户口本个人页

复审新增两个附件字段：

- `certificate_info_page`: 原证件说明和个人信息页
- `certificate_records_page`: 原证件作业项目和聘用记录页

复审附件清单为：

- `photo`
- `certificate_info_page`
- `certificate_records_page`

## 后端

数据库为 `students` 表新增：

- `application_type TEXT DEFAULT 'new_exam'`
- `certificate_info_page_path TEXT`
- `certificate_records_page_path TEXT`

附件字段映射、必传校验、上传白名单、临时文件归档、文件删除、附件打包都需要识别新增字段。

创建和更新学员时：

- 非特种设备报名统一按 `new_exam` 处理。
- 特种设备未传 `application_type` 时按 `new_exam` 处理。
- 特种设备复审按三项附件校验。
- 特种设备新考证沿用现有六项附件校验。

## 小程序

新增报名类型状态并随提交 payload 发送：

- 新增表单选择控件，仅在 `trainingType === 'special_equipment'` 时显示。
- 附件配置按 `trainingType + applicationType` 计算。
- 详情页、编辑页、管理员详情页展示新增附件。
- 文件上传组件继续按 `fileType` 上传，不需要改变交互模型。

## 材料生成

新考证材料生成保持当前流程。

复审材料生成时：

- 处理并输出个人照片。
- 将 `certificate_info_page_path` 和 `certificate_records_page_path` 两张原证件照片按上下布局拼接到 A4 画布。
- 输出文件名使用“复审材料”，例如 `<姓名前缀>-复审材料.jpg`。

## 测试

优先补后端单元测试，覆盖：

- 特种设备新考证要求原六项附件。
- 特种设备复审只要求个人照片和两张原证件照片。
- 复审临时文件归档生成两个新增 path 字段。
- 复审材料生成能输出拼接图片。

小程序侧补纯函数或页面逻辑测试可行时覆盖附件清单计算；否则通过静态检查和手动验证清单。
