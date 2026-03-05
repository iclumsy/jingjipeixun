"""应用统一错误处理。"""
from flask import jsonify
from werkzeug.exceptions import HTTPException
import traceback


class AppError(Exception):
    """应用基础错误类。"""

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
    """输入数据校验错误。"""

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
    """资源未找到错误。"""

    def __init__(self, message="资源未找到"):
        super().__init__(message, status_code=404)


class DatabaseError(AppError):
    """数据库操作错误。"""

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
        """处理自定义应用错误。"""
        app.logger.error(f'{error.__class__.__name__}: {error.message}')
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """处理 HTTP 异常。"""
        app.logger.warning(f'HTTP {error.code}: {error.description}')
        description = error.description
        if error.code == 413:
            description = '请求体过大，请压缩附件或提高服务端上传上限'
        response = jsonify({
            'error': description
        })
        response.status_code = error.code
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """处理未预期的错误。"""
        app.logger.error(f'Unexpected error: {str(error)}')
        app.logger.error(traceback.format_exc())
        response = jsonify({
            'error': '服务器发生意外错误，请稍后重试'
        })
        response.status_code = 500
        return response

    app.logger.info('Error handlers registered')
