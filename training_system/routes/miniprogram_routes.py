"""
小程序认证路由。

本模块处理微信小程序的用户登录认证：
- POST /api/miniprogram/login : 通过 wx.login 获取的 code 换取 openid 并签发 JWT 令牌

认证流程:
1. 小程序端调用 wx.login() 获取临时 code
2. 小程序端将 code 发送到此接口
3. 服务端使用 code + appid + secret 调用微信 jscode2session 接口
4. 微信返回用户的 openid
5. 服务端检查 openid 是否在管理员列表中
6. 签发包含 openid 和管理员标识的 JWT 令牌
7. 返回令牌给小程序端，后续请求通过此令牌认证

错误码说明:
    400: code 为空或微信返回参数错误
    401: 微信认证失败
    500: 服务端未配置 appid/secret
    502: 微信接口请求超时或网络错误
"""
from flask import Blueprint, current_app, jsonify, request
from utils.miniprogram_auth import (
    exchange_code_for_openid,
    get_mini_token_hours,
    has_mini_auth_config,
    is_admin_openid,
    sign_mini_token
)


# 创建小程序蓝图
miniprogram_bp = Blueprint('miniprogram', __name__)


@miniprogram_bp.route('/api/miniprogram/login', methods=['POST'])
def miniprogram_login_route():
    """
    通过 wx.login 的 code 登录小程序用户。

    请求体 (JSON):
        code (str): wx.login() 返回的临时登录凭证

    返回:
        200: {
            "success": true,
            "token": "JWT令牌...",
            "openid": "用户openid",
            "isAdmin": true/false,
            "expiresInHours": 72
        }
        400/401/500/502: 登录失败
    """
    # 解析请求体中的 code 参数
    payload = request.get_json(silent=True) or {}
    code = (payload.get('code', '') or '').strip()
    if not code:
        return jsonify({
            'error': '参数错误',
            'message': 'code 不能为空'
        }), 400

    # 检查服务端是否已配置微信小程序的 appid 和 secret
    if not has_mini_auth_config():
        current_app.logger.error('Mini-program login failed: WECHAT_MINI_APPID/WECHAT_MINI_SECRET not configured')
        return jsonify({
            'error': '配置错误',
            'message': '服务端未配置微信小程序登录参数'
        }), 500

    # 调用微信 jscode2session 接口，用 code 换取 openid
    wx_result = exchange_code_for_openid(code)
    if not wx_result.get('success'):
        # 根据错误类型设置不同的 HTTP 状态码
        err_type = str(wx_result.get('error_type', '') or '')
        err_code = wx_result.get('errcode')
        err_message = wx_result.get('message', '微信登录失败')

        if err_type == 'upstream':
            status_code = 502    # 微信接口请求失败
        elif err_type == 'config':
            status_code = 500    # 服务端配置错误
        elif err_type == 'request':
            status_code = 400    # 请求参数错误
        else:
            status_code = 401    # 认证失败

        current_app.logger.warning(
            'Mini-program login rejected: type=%s errcode=%s message=%s',
            err_type or 'unknown',
            str(err_code) if err_code is not None else '-',
            err_message
        )

        return jsonify({
            'error': '登录失败',
            'message': err_message,
            'errCode': err_code
        }), status_code

    # 登录成功：签发 JWT 令牌
    openid = wx_result.get('openid', '')
    # 检查当前用户是否在管理员 openid 列表中
    is_admin = is_admin_openid(openid)
    # 使用应用密钥签名令牌，包含 openid 和管理员标识
    token = sign_mini_token(
        current_app.config['SECRET_KEY'],
        openid,
        is_admin=is_admin
    )

    return jsonify({
        'success': True,
        'token': token,
        'openid': openid,
        'isAdmin': is_admin,
        'expiresInHours': get_mini_token_hours()  # 告知客户端令牌有效时长
    })
