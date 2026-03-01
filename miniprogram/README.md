# 培训管理小程序（直连服务器 API）

本项目为微信小程序端，当前架构已切换为：

- 不使用微信云函数
- 不使用微信云数据库
- 小程序直接请求网页后端 API

## 技术架构

- 前端：微信小程序原生
- 后端：`training_system` 提供 HTTP/HTTPS API
- 鉴权：小程序登录后获取 `mini_token`，后续请求通过 `Authorization` 与 `X-Mini-Token` 发送
- 附件：上传到后端并返回相对路径（`students/...`），前端按需转绝对地址预览

## 关键目录

- `app.js`：全局配置（API 地址、登录初始化）
- `utils/api.js`：统一 API 封装
- `utils/page-helpers.js`：页面公共方法（管理员判断、时间格式化）
- `pages/user/*`：信息采集、我的提交、详情/编辑
- `pages/admin/*`：审核管理、审核详情
- `components/student-form/*`：提交与详情复用表单组件
- `components/file-uploader/*`：附件上传组件

## 本地开发

1. 使用微信开发者工具导入 `miniprogram/`
2. 在 `project.config.json` 配置真实 `appid`
3. 在 `app.js` 配置后端地址（`globalData.apiBaseUrl`）
4. 在微信开发者工具中编译、预览、真机调试

## 环境配置要点

- 开发调试可临时使用 HTTP（需同时满足小程序侧允许配置）
- 体验版/正式版建议使用 HTTPS 合法域名
- 小程序后台需配置业务域名与上传/下载合法域名

## 登录与权限

- 普通用户：可访问 `信息采集`、`我的提交`
- 管理员用户：额外可访问 `审核管理`
- 管理员判定来自登录接口返回 `is_admin`（并缓存到本地）

## 常见接口

- `POST /api/miniprogram/login`
- `GET /api/students`
- `POST /api/students`
- `PUT /api/students/{id}`
- `POST /api/students/{id}/approve`
- `POST /api/students/{id}/reject`
- `GET /api/students/{id}`
- `GET /api/companies`
- `GET /api/config/job_categories`
- `POST /api/miniprogram/upload`

## 说明

历史云开发文档和云函数目录已移除，后续请以本 README 与后端 API 为准。
