"""应用日志配置。"""
import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(app):
    """
    配置应用日志，包含文件和控制台处理器。

    参数:
        app: Flask 应用实例
    """
    # 创建日志目录（如不存在）
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # 根据调试模式设置日志级别
    log_level = logging.DEBUG if app.debug else logging.INFO

    # 创建格式化器
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s (%(filename)s:%(lineno)d): %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    # 文件处理器（记录所有日志）
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)

    # 文件处理器（仅记录错误）
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, 'error.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(simple_formatter)

    # 移除已有处理器以避免重复
    app.logger.handlers.clear()

    # 添加处理器到应用日志
    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)

    # 记录启动信息
    app.logger.info('Application logging initialized')

    return app.logger
