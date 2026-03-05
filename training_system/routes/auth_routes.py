"""
管理后台认证路由。

本模块提供管理后台的登录和登出功能：
- GET  /auth/login  : 渲染登录页面
- POST /auth/login  : 验证用户名和密码
- GET/POST /auth/logout : 清除会话并重定向到登录页

认证流程:
1. 用户访问受保护页面时被 app.py 的 before_request 中间件重定向到 /auth/login
2. 重定向时携带 next 参数，记录用户原始访问路径
3. 用户提交用户名和密码
4. 验证通过后设置 session['auth_verified'] = True 标记
5. 重定向回 next 参数指定的原始页面

支持两种请求格式:
- 表单提交 (application/x-www-form-urlencoded) : 传统登录页面使用
- JSON 提交 (application/json) : 前端 AJAX 调用使用
"""
from flask import Blueprint, jsonify, redirect, render_template, request, session
from utils.auth import sanitize_next_path, verify_admin_credentials


# 创建认证蓝图，前缀为空（路径在路由装饰器中指定）
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/login', methods=['GET', 'POST'])
def login():
    """
    渲染登录页面并处理账号密码验证。

    GET 请求: 返回登录页面 HTML
    POST 请求: 验证凭据，成功则设置 session 并重定向/返回成功响应

    查询参数:
        next (str): 登录成功后跳转的目标路径，默认为 /admin

    请求体 (POST):
        username (str): 管理员用户名
        password (str): 管理员密码

    返回:
        GET: 登录页面 HTML
        POST 成功 (JSON): {"success": true, "redirect": "/admin"}
        POST 成功 (表单): 302 重定向到目标页面
        POST 失败: 401 错误响应
    """
    # 从查询参数获取登录成功后的跳转路径，并进行安全校验（防止开放重定向）
    next_path = sanitize_next_path(request.args.get('next', '/admin'))

    # GET 请求：直接渲染登录页面
    if request.method == 'GET':
        return render_template('login.html', error='', next_path=next_path)

    # POST 请求：解析用户提交的凭据
    # 同时支持 JSON 和表单两种提交格式
    data = request.get_json(silent=True) if request.is_json else request.form
    username = (data.get('username', '') if data else '').strip()
    password = data.get('password', '') if data else ''

    # 验证用户名和密码
    if verify_admin_credentials(username, password):
        # 验证通过：清除旧 session 并创建新的认证会话
        session.clear()
        session['auth_verified'] = True   # 标记已通过认证
        session['auth_user'] = username   # 记录当前登录用户名
        session.permanent = True          # 使 session 遵循 PERMANENT_SESSION_LIFETIME 过期时间

        # 根据请求格式返回不同类型的响应
        if request.is_json:
            return jsonify({
                'success': True,
                'redirect': next_path
            })
        return redirect(next_path)

    # 验证失败：返回 401 错误
    if request.is_json:
        return jsonify({
            'success': False,
            'message': '账号或密码错误'
        }), 401

    return render_template('login.html', error='账号或密码错误', next_path=next_path), 401


@auth_bp.route('/auth/logout', methods=['GET', 'POST'])
def logout():
    """
    清除会话并返回登录页。

    支持 GET 和 POST 两种方式调用：
    - GET: 浏览器地址栏或链接直接访问
    - POST: 前端 AJAX 调用（返回 JSON 响应）
    """
    # 清除所有 session 数据（包括认证标记和用户信息）
    session.clear()
    if request.is_json:
        return jsonify({'success': True})
    return redirect('/auth/login')
