# 微信小程序培训管理系统 - 开发进度

## 项目概述

这是一个基于微信云开发的培训管理系统小程序，包含学员信息采集和管理审核两大功能模块。

## 已完成的工作

### 1. 项目基础结构 ✅

- [x] 项目目录结构
- [x] app.js - 全局逻辑和云开发初始化
- [x] app.json - 全局配置和页面路由
- [x] app.wxss - 全局样式（包含CSS变量、组件样式）
- [x] project.config.json - 项目配置
- [x] sitemap.json - 索引配置

### 2. 工具函数 ✅

- [x] utils/api.js - API封装（云函数调用、文件上传下载）
- [x] utils/validators.js - 表单验证工具
- [x] utils/constants.js - 常量定义

### 3. 云函数 ✅（核心功能）

已创建以下云函数：

- [x] **login** - 用户登录，获取openid和角色
- [x] **submitStudent** - 批量提交学员信息
- [x] **getStudents** - 获取学员列表（支持分页、筛选、搜索）
- [x] **getStudentDetail** - 获取学员详情和附件临时链接
- [x] **reviewStudent** - 审核学员（通过/驳回）
- [x] **getCompanies** - 获取公司列表（去重）

### 4. 页面 ✅（部分）

- [x] pages/index - 首页（角色判断和跳转）

## 待完成的工作

### 1. 云函数（剩余）

需要创建以下云函数：

- [ ] **batchReview** - 批量审核
- [ ] **exportExcel** - 导出Excel（需要安装 node-xlsx）
- [ ] **generateHealthCheck** - 生成体检表（需要安装 docxtemplater）
- [ ] **downloadAttachments** - 打包下载附件（需要安装 jszip）
- [ ] **updateStudent** - 更新学员信息
- [ ] **deleteStudent** - 删除学员

### 2. 公共组件

需要创建以下组件：

- [ ] **student-form-item** - 学员表单项组件
- [ ] **file-uploader** - 文件上传组件
- [ ] **image-cropper** - 图片裁剪组件
- [ ] **filter-bar** - 筛选栏组件
- [ ] **student-card** - 学员卡片组件

### 3. 用户页面

- [ ] **pages/user/submit** - 信息采集表单（核心页面）
- [ ] **pages/user/list** - 我的提交记录
- [ ] **pages/user/detail** - 提交详情

### 4. 管理员页面

- [ ] **pages/admin/review** - 审核列表（核心页面）
- [ ] **pages/admin/detail** - 学员详情
- [ ] **pages/admin/batch** - 批量操作
- [ ] **pages/admin/export** - 导出功能

### 5. 图标资源

需要准备以下图标（放在 images/ 目录）：

- [ ] submit.png / submit-active.png - 信息采集图标
- [ ] list.png / list-active.png - 我的提交图标
- [ ] admin.png / admin-active.png - 审核管理图标

### 6. 云开发配置

需要在微信开发者工具中完成：

- [ ] 创建云数据库集合（students, admins, config）
- [ ] 配置数据库索引
- [ ] 配置数据库权限规则
- [ ] 导入配置数据（job_categories）
- [ ] 添加管理员账号
- [ ] 创建云存储目录
- [ ] 上传体检表模板

## 核心功能实现说明

### 1. 信息采集表单（pages/user/submit）

**功能要点**：
- 选择培训类型（特种作业/特种设备）
- 动态添加/删除学员
- 根据培训类型显示不同的必填附件
- 表单验证（身份证、手机号格式）
- 文件上传（支持进度显示）
- 照片裁剪（一寸照片）
- 批量提交

**实现步骤**：
1. 加载作业类别配置（从 config 集合）
2. 渲染学员表单（使用 student-form-item 组件）
3. 文件上传（使用 file-uploader 组件）
4. 表单验证（使用 validators.js）
5. 批量提交（调用 submitStudent 云函数）

### 2. 审核列表（pages/admin/review）

**功能要点**：
- 学员列表展示
- 多条件筛选（状态、培训类型、公司）
- 搜索（姓名、身份证、手机号）
- 分页加载
- 下拉刷新
- 点击查看详情

**实现步骤**：
1. 调用 getStudents 云函数获取列表
2. 渲染学员卡片（使用 student-card 组件）
3. 筛选栏（使用 filter-bar 组件）
4. 分页加载（onReachBottom）
5. 跳转到详情页

### 3. 学员详情（pages/admin/detail）

**功能要点**：
- 显示学员详细信息
- 预览所有附件
- 审核通过/驳回
- 生成体检表
- 下载附件压缩包

**实现步骤**：
1. 调用 getStudentDetail 云函数获取详情
2. 显示学员信息
3. 显示附件（使用临时链接）
4. 审核操作（调用 reviewStudent 云函数）
5. 生成体检表（调用 generateHealthCheck 云函数）
6. 下载附件（调用 downloadAttachments 云函数）

## 部署步骤

### 1. 开发环境准备

1. 安装微信开发者工具
2. 注册微信小程序账号并获取 AppID
3. 修改 `project.config.json` 中的 appid
4. 修改 `app.js` 中的云开发环境ID

### 2. 云开发配置

1. 在微信开发者工具中开通云开发
2. 创建云数据库集合：
   - students（学员信息）
   - admins（管理员）
   - config（配置信息）
3. 配置数据库索引（参考部署方案文档）
4. 配置数据库权限规则
5. 导入配置数据

### 3. 云函数部署

1. 右键点击 cloudfunctions 目录
2. 选择"上传并部署：云端安装依赖（全部云函数）"
3. 等待部署完成

### 4. 测试

1. 编译小程序
2. 真机调试
3. 测试各项功能

### 5. 发布

1. 上传代码
2. 提交审核
3. 发布正式版

## 技术栈

- **前端**：微信小程序原生开发
- **后端**：微信云开发（云函数、云数据库、云存储）
- **语言**：JavaScript
- **依赖**：
  - wx-server-sdk（云函数SDK）
  - axios（同步提交HTTP请求）
  - form-data（构造multipart请求）
  - node-xlsx（Excel导出）
  - docxtemplater（Word文档生成）
  - jszip（文件压缩）

## 目录结构

```
training-miniprogram/
├── cloudfunctions/          # 云函数目录
│   ├── login/              # 用户登录
│   ├── submitStudent/      # 提交学员信息
│   ├── getStudents/        # 获取学员列表
│   ├── getStudentDetail/   # 获取学员详情
│   ├── reviewStudent/      # 审核学员
│   ├── getCompanies/       # 获取公司列表
│   ├── batchReview/        # 批量审核（待创建）
│   ├── exportExcel/        # 导出Excel（待创建）
│   ├── generateHealthCheck/# 生成体检表（待创建）
│   ├── downloadAttachments/# 下载附件（待创建）
│   ├── updateStudent/      # 更新学员（待创建）
│   └── deleteStudent/      # 删除学员（待创建）
├── components/             # 组件目录（待创建）
│   ├── student-form-item/
│   ├── file-uploader/
│   ├── image-cropper/
│   ├── filter-bar/
│   └── student-card/
├── pages/                  # 页面目录
│   ├── index/             # 首页 ✅
│   ├── user/              # 用户模块（待创建）
│   │   ├── submit/
│   │   ├── list/
│   │   └── detail/
│   └── admin/             # 管理员模块（待创建）
│       ├── review/
│       ├── detail/
│       ├── batch/
│       └── export/
├── utils/                  # 工具函数 ✅
│   ├── api.js
│   ├── validators.js
│   └── constants.js
├── images/                 # 图标资源（待添加）
├── app.js                  # 全局逻辑 ✅
├── app.json                # 全局配置 ✅
├── app.wxss                # 全局样式 ✅
├── project.config.json     # 项目配置 ✅
└── sitemap.json            # 索引配置 ✅
```

## 注意事项

1. **环境ID配置**：需要在 `app.js` 中替换为实际的云开发环境ID
2. **AppID配置**：需要在 `project.config.json` 中替换为实际的小程序AppID
3. **管理员配置**：需要在 admins 集合中手动添加管理员的 openid
4. **文件大小限制**：单个文件最大10MB
5. **云函数超时**：默认超时时间为20秒，复杂操作需要注意
6. **数据库权限**：需要正确配置数据库权限规则
7. **临时链接有效期**：文件临时链接有效期为1小时

## 原系统同步配置（新增）

`submitStudent` 云函数已支持“提交到小程序系统后，同步提交到原信息采集系统”。

可在 `config` 集合新增文档：

```json
{
  "_id": "origin_system_sync",
  "data": {
    "enabled": true,
    "base_url": "https://your-origin-system.example.com",
    "submit_path": "/api/students",
    "timeout_ms": 20000
  }
}
```

也支持使用云函数环境变量覆盖：
- `ORIGIN_SYSTEM_SYNC_ENABLED`
- `ORIGIN_SYSTEM_BASE_URL`
- `ORIGIN_SYSTEM_SUBMIT_PATH`
- `ORIGIN_SYSTEM_TIMEOUT_MS`

## 下一步工作

建议按以下顺序完成剩余工作：

1. **创建公共组件**（优先级：高）
   - file-uploader（文件上传）
   - student-form-item（学员表单）
   - student-card（学员卡片）
   - filter-bar（筛选栏）
   - image-cropper（图片裁剪）

2. **创建用户页面**（优先级：高）
   - pages/user/submit（信息采集）
   - pages/user/list（我的提交）
   - pages/user/detail（提交详情）

3. **创建管理员页面**（优先级：高）
   - pages/admin/review（审核列表）
   - pages/admin/detail（学员详情）
   - pages/admin/batch（批量操作）
   - pages/admin/export（导出功能）

4. **创建剩余云函数**（优先级：中）
   - batchReview
   - updateStudent
   - deleteStudent
   - exportExcel
   - generateHealthCheck
   - downloadAttachments

5. **准备图标资源**（优先级：低）
   - TabBar图标

6. **测试和优化**（优先级：高）
   - 功能测试
   - 性能优化
   - 用户体验优化

## 参考文档

- [微信小程序开发文档](https://developers.weixin.qq.com/miniprogram/dev/framework/)
- [微信云开发文档](https://developers.weixin.qq.com/miniprogram/dev/wxcloud/basis/getting-started.html)
- [部署方案文档](../微信小程序部署方案.md)
- [实现计划文档](../.claude/plans/concurrent-kindling-parasol.md)

## 联系方式

如有问题，请随时询问。
