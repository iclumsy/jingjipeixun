"""
日志配置模块。

本模块配置应用的日志系统，包括文件日志和控制台日志：

日志输出目标:
    1. 综合日志文件 (logs/app.log)
       - 记录所有级别的日志（DEBUG/INFO/WARNING/ERROR）
       - 按文件大小满 5MB 自动轮转，保留最近 5 个备份
    2. 错误日志文件 (logs/error.log)
       - 仅记录 ERROR 及以上级别的日志
       - 同样按文件大小轮转
    3. 控制台输出 (stdout)
       - 级别由 DEBUG 模式决定：调试模式下输出 DEBUG，生产模式下输出 INFO

日志格式:
    [时间戳] [级别] [模块名] 消息内容
"""
import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(app):
    """
    设置应用日志系统。

    为 Flask 应用配置文件和控制台日志处理器，
    使用 RotatingFileHandler 限制单个日志文件的大小，
    避免日志文件无限增长占满磁盘。

    参数:
        app: Flask 应用实例
    """
    # 确保日志目录存在
    log_dir = os.path.join(app.config.get('BASE_DIR', os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # 统一日志格式：[时间] [级别] [模块] 内容
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # ---- 综合日志文件 ----
    # 记录所有级别的日志，单文件最大 5MB，保留 5 个历史备份
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=5*1024*1024,   # 5MB
        backupCount=5,          # 保留 app.log.1 ~ app.log.5
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)  # 调试模式记录 DEBUG

    # ---- 错误专用日志文件 ----
    # 仅记录 ERROR 及以上级别，便于快速定位问题
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, 'error.log'),
        maxBytes=5*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)  # 仅 ERROR 和 CRITICAL

    # ---- 控制台输出 ----
    # 开发时在终端查看实时日志
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)

    # 移除已有处理器以避免重复
    app.logger.handlers.clear()

    # 将所有处理器添加到应用日志器
    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.addHandler(console_handler)
    # 设置日志器基础级别（各处理器会进一步过滤）
    app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)

    return app.logger
