"""
应用统一错误处理。

本模块定义了应用的异常类层次结构和全局错误处理器，确保所有错误返回统一的 JSON 响应格式。

异常类层次:
    AppError            : 应用基础错误类（默认 500）
    ├─ ValidationError : 输入数据校验失败（400），支持字段级别的错误信息
    ├─ NotFoundError   : 资源不存在（404）
    └─ DatabaseError   : 数据库操作失败（500）

响应格式:
    {
        "error": "错误信息",
        "fields": { ... }      // 仅 ValidationError 包含此字段
    }

全局错误处理器注册后，任何未被路由函数捕获的异常都会被统一处理，
避免名户端看到原始的错误堆栈信息。
"""
from flask import jsonify
from werkzeug.exceptions import HTTPException
import traceback


class AppError(Exception):
    """
    应用基础错误类。

    所有自定义业务异常的父类，支持自定义 HTTP 状态码和额外载荷数据。
    路由函数中可以直接 raise AppError('xxx', status_code=403) 使用。
    """

    def __init__(self, message, status_code=500, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        """将错误转换为 JSON 响应用字典。"""
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv


class ValidationError(AppError):
    """
    输入数据校验错误（HTTP 400）。

    支持通过 fields 字典提供字段级别的错误信息，
    例如: ValidationError('校验失败', fields={'phone': '手机号格式不正确'})
    """

    def __init__(self, message, fields=None):
        super().__init__(message, status_code=400)
        self.fields = fields or {}

    def to_dict(self):
        """将校验错误转换为字典。"""
        rv = super().to_dict()
        if self.fields:
            rv['fields'] = self.fields
        return rv


class NotFoundError(AppError):
    """资源未找到错误（HTTP 404），如学员 ID 不存在。"""

    def __init__(self, message="资源未找到"):
        super().__init__(message, status_code=404)


class DatabaseError(AppError):
    """数据库操作错误（HTTP 500），如 SQL 执行失败、连接异常等。"""

    def __init__(self, message="数据库操作失败"):
        super().__init__(message, status_code=500)


def register_error_handlers(app):
    """
    为 Flask 应用注册错误处理器。

    参数:
        app: Flask 应用实例
    """

    @app.errorhandler(AppError)
    def handle_app_error(error):
        """处理自定义应用错误（包括 ValidationError、NotFoundError 等子类）。"""
        app.logger.error(f'{error.__class__.__name__}: {error.message}')
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """处理 Werkzeug HTTP 异常（如 404、405、413 等）。"""
        app.logger.warning(f'HTTP {error.code}: {error.description}')
        description = error.description
        # 对 413 错误给出更友好的提示（默认提示信息太技术化）
        if error.code == 413:
            description = '请求体过大，请压缩附件或提高服务端上传上限'
        response = jsonify({
            'error': description
        })
        response.status_code = error.code
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """捕获所有未预期的异常，避免泄露内部错误细节。"""
        app.logger.error(f'Unexpected error: {str(error)}')
        app.logger.error(traceback.format_exc())
        response = jsonify({
            'error': '服务器发生意外错误，请稍后重试'
        })
        response.status_code = 500
        return response

    app.logger.info('Error handlers registered')
