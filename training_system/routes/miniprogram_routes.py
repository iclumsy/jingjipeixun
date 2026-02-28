"""Mini-program auth routes."""
from flask import Blueprint, current_app, jsonify, request
from utils.miniprogram_auth import (
    exchange_code_for_openid,
    get_mini_token_hours,
    has_mini_auth_config,
    is_admin_openid,
    sign_mini_token
)


miniprogram_bp = Blueprint('miniprogram', __name__)


@miniprogram_bp.route('/api/miniprogram/login', methods=['POST'])
def miniprogram_login_route():
    """Login mini-program user via wx.login code."""
    payload = request.get_json(silent=True) or {}
    code = (payload.get('code', '') or '').strip()
    if not code:
        return jsonify({
            'error': '参数错误',
            'message': 'code 不能为空'
        }), 400

    if not has_mini_auth_config():
        current_app.logger.error('Mini-program login failed: WECHAT_MINI_APPID/WECHAT_MINI_SECRET not configured')
        return jsonify({
            'error': '配置错误',
            'message': '服务端未配置微信小程序登录参数'
        }), 500

    wx_result = exchange_code_for_openid(code)
    if not wx_result.get('success'):
        return jsonify({
            'error': '登录失败',
            'message': wx_result.get('message', '微信登录失败')
        }), 401

    openid = wx_result.get('openid', '')
    is_admin = is_admin_openid(openid)
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
        'expiresInHours': get_mini_token_hours()
    })
