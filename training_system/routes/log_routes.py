"""
后台日志查看路由。

本模块提供管理后台的系统日志查看功能：
- GET /admin/logs      : 渲染日志查看器页面
- GET /api/logs/content: 获取最新的日志内容（支持普通 app.log 和错误 error.log）
"""
import os
from flask import Blueprint, current_app, jsonify, render_template, request

log_bp = Blueprint('logs', __name__)

@log_bp.route('/admin/logs')
def admin_logs():
    """渲染日志查看管理页面（受统一登录保护）。"""
    return render_template('logs_admin.html')

@log_bp.route('/api/logs/content')
def get_log_content():
    """
    获取服务器的日志文件内容。
    默认读取末尾 500 行，以确保性能。
    查询参数:
        type: 'app' (默认) | 'error'
        lines: 行数限制 (默认 500)
    """
    log_type = request.args.get('type', 'app')
    if log_type not in ('app', 'error'):
        log_type = 'app'
        
    try:
        lines_limit = int(request.args.get('lines', 500))
        lines_limit = max(10, min(lines_limit, 5000))
    except ValueError:
        lines_limit = 500

    log_dir = os.path.join(current_app.config.get('BASE_DIR', ''), 'logs')
    log_file = os.path.join(log_dir, f'{log_type}.log')

    if not os.path.isfile(log_file):
        return jsonify({
            'success': True,
            'lines': [f"[系统提示] 尚未生成 {log_type}.log 本地日志文件"]
        })

    lines = []
    try:
        # 使用 deque 读取最后 N 行 (如果不用 deque 的话可以使用标准实现)
        # 为避免读取超大文件导致内存问题，这里简单使用文件指针或直接 readlines 获取尾部
        # 因为我们的 log 配置单个文件上限就只有 5MB，直接全部读取再切片在现代计算机上是可以接受的
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            # 截取最后 lines_limit 行
            lines = [line.rstrip('\\n') for line in all_lines[-lines_limit:]]
            
    except Exception as e:
        current_app.logger.error(f"读取日志文件失败: {str(e)}")
        lines = [f"[系统错误] 读取日志文件时发生异常: {str(e)}"]

    return jsonify({
        'success': True,
        'lines': lines
    })
