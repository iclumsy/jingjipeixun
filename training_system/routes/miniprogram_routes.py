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
        err_type = str(wx_result.get('error_type', '') or '')
        err_code = wx_result.get('errcode')
        err_message = wx_result.get('message', '微信登录失败')

        if err_type == 'upstream':
            status_code = 502
        elif err_type == 'config':
            status_code = 500
        elif err_type == 'request':
            status_code = 400
        else:
            status_code = 401

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
