"""
应用主入口。

本模块是整个培训管理系统后端的入口文件，负责：
1. 从 .env 配置文件加载环境变量
2. 创建并配置 Flask 应用实例
3. 注册所有蓝图（路由模块）
4. 配置全局请求认证中间件
5. 启动 Web 服务

系统架构概览:
  - 路由层 (routes/) : 处理 HTTP 请求与响应
  - 模型层 (models/) : 数据库表定义与 CRUD 操作
  - 服务层 (services/) : 文档生成、图片处理等业务逻辑
  - 工具层 (utils/) : 认证、校验、日志、错误处理等通用工具

认证机制:
  - 管理后台页面：基于 session 的密码登录认证
  - API 接口：支持 session、API Key、小程序 JWT 令牌三种认证方式
"""
import os
from datetime import timedelta
from flask import Flask, g, jsonify, redirect, render_template, request, session
from models.student import init_db
from routes.auth_routes import auth_bp
from routes.miniprogram_routes import miniprogram_bp
from routes.student_routes import student_bp
from routes.file_routes import file_bp
from routes.export_routes import export_bp
from routes.config_routes import config_bp
from utils.miniprogram_auth import extract_mini_token, has_mini_auth_config, verify_mini_token
from utils.auth import (
    build_login_redirect_target,
    has_api_key,
    using_default_admin_password,
    verify_api_key
)
from utils.logger import setup_logger
from utils.error_handlers import register_error_handlers


def _strip_wrapping_quotes(value):
    """
    去除值两端匹配的单引号或双引号。

    .env 文件中的值可能被引号包裹（如 KEY="value" 或 KEY='value'），
    此函数用于清理这些引号，确保提取到纯净的值文本。

    参数:
        value: 原始字符串值

    返回:
        str: 去除两端引号后的字符串
    """
    text = str(value or '').strip()
    # 仅当首尾字符为同一种引号时才移除
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _resolve_env_file_path(base_dir):
    """
    从环境变量 TRAINING_SYSTEM_ENV_FILE 解析配置文件路径，默认为 .env。

    支持以下场景：
    - 未设置环境变量：使用项目根目录下的 .env
    - 设置了绝对路径：直接使用该路径
    - 设置了相对路径：相对于项目根目录解析

    参数:
        base_dir: 项目根目录路径（app.py 所在目录）

    返回:
        str: 配置文件的绝对路径
    """
    configured = (os.getenv('TRAINING_SYSTEM_ENV_FILE', '') or '').strip()
    if not configured:
        return os.path.join(base_dir, '.env')
    if os.path.isabs(configured):
        return configured
    return os.path.join(base_dir, configured)


def load_env_file(base_dir):
    """
    从配置文件加载环境变量。

    读取 .env 格式的配置文件，将其中的键值对设置为进程环境变量。
    已存在的进程环境变量不会被覆盖（通过 os.environ.setdefault 实现），
    确保命令行或系统级设置的环境变量优先级最高。

    支持的 .env 文件语法:
    - KEY=VALUE          标准键值对
    - export KEY=VALUE   shell 导出格式
    - # 注释行           以 # 开头的行将被忽略
    - 空行               自动跳过
    - KEY="VALUE"        带引号的值会自动去除引号

    参数:
        base_dir: 项目根目录路径

    返回:
        dict: 加载结果，包含以下字段：
            - path (str): 配置文件路径
            - loaded (int): 成功加载的变量数量
            - exists (bool): 配置文件是否存在
            - error (str): 错误信息（如有）
    """
    env_file = _resolve_env_file_path(base_dir)
    result = {
        'path': env_file,
        'loaded': 0,
        'exists': os.path.isfile(env_file),
        'error': ''
    }
    # 文件不存在时直接返回，不视为错误
    if not result['exists']:
        return result

    try:
        with open(env_file, 'r', encoding='utf-8') as fp:
            for raw_line in fp:
                line = raw_line.strip()
                # 跳过空行和注释行
                if not line or line.startswith('#'):
                    continue
                # 移除 shell 的 export 前缀
                if line.startswith('export '):
                    line = line[7:].strip()
                # 跳过不含等号的行（无效格式）
                if '=' not in line:
                    continue

                # 拆分键值对（仅在第一个等号处分割）
                key, value = line.split('=', 1)
                key = key.strip()
                if not key:
                    continue

                # setdefault 确保不覆盖已有的环境变量
                os.environ.setdefault(key, _strip_wrapping_quotes(value))
                result['loaded'] += 1
    except OSError as err:
        result['error'] = str(err)

    return result


def get_max_content_length():
    """
    根据环境变量 MAX_CONTENT_LENGTH_MB 构建请求体大小限制。

    用于限制客户端上传文件的最大体积。默认 64MB，
    以支持多附件同步上传场景（如一次性上传照片、学历证书、身份证等）。

    环境变量格式: MAX_CONTENT_LENGTH_MB=64（单位为兆字节）

    返回:
        int: 请求体大小限制（字节）
    """
    raw_mb = os.getenv('MAX_CONTENT_LENGTH_MB', '64')
    try:
        mb = int(raw_mb)
    except (TypeError, ValueError):
        # 环境变量值格式错误时回退到默认值
        mb = 64

    # 确保值为正数
    if mb <= 0:
        mb = 64

    return mb * 1024 * 1024  # 转换为字节


def create_app():
    """
    创建并配置 Flask 应用（应用工厂函数）。

    此函数执行以下初始化步骤：
    1. 加载 .env 环境变量
    2. 设置应用配置（数据库路径、session、安全选项等）
    3. 创建必要的文件系统目录
    4. 初始化 SQLite 数据库
    5. 配置日志系统
    6. 注册全局错误处理器
    7. 注册所有 Blueprint 路由
    8. 配置请求级别的认证中间件
    9. 定义页面路由

    返回:
        Flask: 配置完成的 Flask 应用实例
    """
    app = Flask(__name__)

    # ======================== 应用配置 ========================
    # 获取项目根目录（app.py 所在目录）
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # 加载 .env 配置文件中的环境变量
    env_load = load_env_file(BASE_DIR)

    # 文件系统路径配置
    app.config['BASE_DIR'] = BASE_DIR                                       # 项目根目录
    app.config['STUDENTS_FOLDER'] = os.path.join(BASE_DIR, 'students')      # 学员附件存储目录
    app.config['DATABASE'] = os.path.join(BASE_DIR, 'database/students.db') # SQLite 数据库文件

    # 请求体大小限制（防止恶意大文件上传）
    app.config['MAX_CONTENT_LENGTH'] = get_max_content_length()

    # Session 安全配置
    app.config['SECRET_KEY'] = os.getenv('TRAINING_SYSTEM_SECRET_KEY') or os.urandom(32)  # 未配置时使用随机密钥（重启后 session 将失效）
    app.config['SESSION_COOKIE_HTTPONLY'] = True   # 禁止 JavaScript 读取 cookie，防止 XSS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # 限制跨站请求携带 cookie，防止 CSRF
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('TRAINING_SYSTEM_SECURE_COOKIE', 'false').lower() == 'true'  # HTTPS 环境下启用

    # Session 有效期配置（默认 12 小时）
    raw_session_hours = os.getenv('TRAINING_SYSTEM_SESSION_HOURS', '12')
    try:
        session_hours = max(1, int(raw_session_hours))  # 最少 1 小时
    except (TypeError, ValueError):
        session_hours = 12
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=session_hours)

    # ======================== 目录初始化 ========================
    # 确保学员附件目录存在
    os.makedirs(app.config['STUDENTS_FOLDER'], exist_ok=True)
    # 确保数据库目录存在
    os.makedirs(os.path.join(BASE_DIR, 'database'), exist_ok=True)

    # ======================== 数据库初始化 ========================
    # 创建 students 表及索引（如果尚未存在）
    init_db(app.config['DATABASE'])

    # ======================== 日志初始化 ========================
    setup_logger(app)
    # 记录 .env 文件加载结果
    if env_load.get('error'):
        app.logger.warning(
            'Failed to load env file %s: %s',
            env_load.get('path', ''),
            env_load.get('error', '')
        )
    elif env_load.get('exists'):
        app.logger.info(
            'Loaded env config from %s (%s entries)',
            env_load.get('path', ''),
            env_load.get('loaded', 0)
        )
    else:
        app.logger.info(
            'Env config file not found, skipped: %s',
            env_load.get('path', '')
        )

    # ======================== 错误处理器 ========================
    # 注册统一的 HTTP 异常和应用异常处理器
    register_error_handlers(app)

    # ======================== 路由蓝图注册 ========================
    app.register_blueprint(auth_bp)          # /auth/*       管理后台登录/登出
    app.register_blueprint(miniprogram_bp)   # /api/miniprogram/*  小程序认证
    app.register_blueprint(student_bp)       # /api/students/*     学员 CRUD 及审核
    app.register_blueprint(file_bp)          # /students/*         静态文件服务
    app.register_blueprint(export_bp)        # /api/export/*       数据导出
    app.register_blueprint(config_bp)        # /api/config/*       配置接口

    # ======================== 认证中间件 ========================
    @app.before_request
    def require_authentication():
        """
        全局请求拦截器：通过会话或 API Key 保护管理页面和 API 路由。

        认证逻辑优先级：
        1. 白名单路径（静态资源、首页、登录页、公开 API）直接放行
        2. 已通过 session 认证的用户直接放行
        3. API 路径尝试以下认证方式（按优先级）:
           a. 小程序 JWT 令牌（Bearer token / X-Mini-Token 头）
           b. API Key（X-API-Key 头 / 查询参数）
        4. 非 API 的页面路径：重定向到登录页
        """
        # 初始化小程序用户信息为空（后续验证成功后会赋值）
        g.mini_user = None
        path = request.path or '/'
        protected_api = path.startswith('/api/')  # 标记是否为 API 请求

        # ---------- 白名单路径直接放行 ----------
        # 静态资源和 favicon 无需认证
        if path.startswith('/static/') or path == '/favicon.ico':
            return None
        # 首页（学员信息采集页）公开访问
        if path == '/':
            return None
        # 登录/登出路由无需认证
        if path.startswith('/auth/'):
            return None
        # 学员附件文件公开访问（路径由 file_routes 提供）
        if path.startswith('/students/'):
            return None
        # 小程序登录接口无需认证（登录本身就是获取认证）
        if path == '/api/miniprogram/login':
            return None
        # 作业类别配置接口公开访问（表单下拉列表需要）
        if path == '/api/config/job_categories':
            return None

        # ---------- Session 认证 ----------
        # 管理后台登录成功后 session 中会设置 auth_verified=True
        if session.get('auth_verified') is True:
            return None

        # ---------- API 认证 ----------
        if protected_api:
            # 方式一：小程序 JWT 令牌验证
            mini_token = extract_mini_token(request)
            mini_user = verify_mini_token(app.config['SECRET_KEY'], mini_token)
            if mini_user:
                # 将小程序用户信息存入请求上下文，供后续路由使用
                g.mini_user = mini_user
                return None

            # 方式二：API Key 验证（支持请求头和查询参数两种方式）
            candidate_api_key = (
                request.headers.get('X-API-Key', '')
                or request.headers.get('x-api-key', '')
                or request.args.get('api_key', '')
            )
            if verify_api_key(candidate_api_key):
                return None

            # 所有 API 认证方式均失败，返回 401
            return jsonify({
                'error': 'unauthorized',
                'message': '未授权访问，请先登录或提供有效 API Key'
            }), 401

        # ---------- 页面路径：重定向到登录页 ----------
        # 将当前页面路径作为 next 参数传递，登录成功后自动跳转回来
        query_string = request.query_string.decode('utf-8', errors='ignore')
        return redirect(build_login_redirect_target(path, query_string))

    # ======================== 页面路由 ========================
    @app.route('/')
    def index():
        """渲染学员信息采集首页（公开访问，无需登录）。"""
        return render_template('index.html')

    @app.route('/admin')
    def admin():
        """渲染管理后台页面（需要登录认证）。"""
        return render_template('admin.html', training_type='special_equipment')

    # ======================== 启动警告 ========================
    # 检查是否使用默认密码并发出警告
    if using_default_admin_password():
        app.logger.warning('Using default admin password, please set TRAINING_SYSTEM_ADMIN_PASSWORD or TRAINING_SYSTEM_ADMIN_PASSWORD_HASH')
    # 检查 API Key 是否已配置
    if not has_api_key():
        app.logger.warning('TRAINING_SYSTEM_API_KEY is not configured, non-session API access will be blocked')
    # 检查小程序配置是否完整
    if not has_mini_auth_config():
        app.logger.warning('WECHAT_MINI_APPID/WECHAT_MINI_SECRET not configured, mini-program direct login will fail')

    app.logger.info('Application initialized successfully')

    return app

# ======================== 应用启动 ========================
# 创建全局应用实例（供 WSGI 服务器或命令行直接使用）
app = create_app()


if __name__ == '__main__':
    # 开发模式：直接运行此文件启动内置服务器
    # 从环境变量读取调试模式开关
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    # 监听所有网络接口的 5001 端口
    app.run(debug=debug_mode, host='0.0.0.0', port=5001) 
