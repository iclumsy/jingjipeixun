# 培训系统重构说明

## 项目结构

重构后的项目采用模块化架构，代码组织更清晰，易于维护：

```
training_system/
├── app.py                      # 应用入口文件
├── models/                     # 数据模型层
│   ├── __init__.py
│   └── student.py             # 学员数据模型和数据库操作
├── routes/                     # 路由层（API端点）
│   ├── __init__.py
│   ├── student_routes.py      # 学员相关路由
│   ├── file_routes.py         # 文件服务路由
│   └── export_routes.py       # 导出功能路由
├── services/                   # 业务逻辑层
│   ├── __init__.py
│   ├── image_service.py       # 图片处理服务
│   └── document_service.py    # Word文档生成服务
├── utils/                      # 工具模块
│   ├── __init__.py
│   ├── logger.py              # 日志配置
│   ├── error_handlers.py      # 统一错误处理
│   └── validators.py          # 数据验证
├── templates/                  # HTML模板
├── static/                     # 静态文件
├── database/                   # 数据库文件
├── logs/                       # 日志文件（自动创建）
└── requirements.txt            # 依赖包列表
```

## 主要改进

### 1. 代码模块化
- **原来**: 所有代码在单个 1264 行的 app.py 文件中
- **现在**: 按功能拆分为多个模块，每个模块职责单一

### 2. 统一日志系统
- 所有操作都有详细的日志记录
- 日志文件自动轮转（最大 10MB，保留 5 个备份）
- 分离的错误日志文件（error.log）
- 日志位置: `training_system/logs/`

### 3. 统一错误处理
- 自定义异常类（ValidationError, NotFoundError, DatabaseError）
- 全局错误处理器
- 所有错误都会被记录到日志
- 返回统一格式的错误响应

### 4. 数据验证
- 独立的验证模块
- 可复用的验证函数
- 清晰的错误消息

### 5. 数据库操作优化
- 使用上下文管理器确保连接正确关闭
- 统一的错误处理
- 防止连接泄漏

## 启动应用

### 开发模式
```bash
cd training_system
python app.py
```

### 生产模式
```bash
export FLASK_DEBUG=False
python app.py
```

或使用 WSGI 服务器（推荐）:
```bash
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

## 日志查看

### 查看所有日志
```bash
tail -f training_system/logs/app.log
```

### 查看错误日志
```bash
tail -f training_system/logs/error.log
```

## 功能验证

所有原有功能保持不变：
- ✓ 学员信息管理（增删改查）
- ✓ 文件上传和管理
- ✓ Word文档生成
- ✓ 批量操作
- ✓ 数据导出（Excel）
- ✓ 附件打包下载

## 已清理的文件

以下文件已被删除（不再需要）：
- `main.py` - 重复的背景移除函数
- `inspect_docx.py` - 工具脚本
- `training_system/app.py.bak` - 备份文件

原始的 app.py 已备份为 `app.py.old`，如需回滚可以恢复。

## 注意事项

1. **首次启动**: 应用会自动运行数据迁移（如果需要）
2. **日志文件**: 会自动创建 logs 目录
3. **数据库**: 保持原有的 SQLite 数据库，无需重新创建
4. **文件路径**: 所有文件路径保持兼容，支持新旧格式

## 开发建议

### 添加新功能
1. 在相应的模块中添加函数
2. 在 routes 中创建新的端点
3. 使用统一的错误处理和日志记录

### 调试
- 查看 `logs/app.log` 了解应用运行情况
- 查看 `logs/error.log` 定位错误
- 使用 `current_app.logger.info()` 添加调试日志

## 性能优化建议（未来）

1. 添加数据库连接池
2. 实现 API 响应缓存
3. 添加分页功能
4. 使用异步任务处理大文件
5. 添加 Redis 缓存

## 安全建议（未来）

1. 添加用户认证系统
2. 实现 CSRF 保护
3. 添加 API 速率限制
4. 实现文件内容验证
5. 使用环境变量管理敏感配置
