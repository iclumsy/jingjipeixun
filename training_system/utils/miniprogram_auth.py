"""小程序认证工具。"""
import hmac
import json
import os
from urllib import parse, request
from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer


# 环境变量名常量
MINI_APPID_ENV = 'WECHAT_MINI_APPID'
MINI_SECRET_ENV = 'WECHAT_MINI_SECRET'
MINI_TOKEN_HOURS_ENV = 'TRAINING_SYSTEM_MINI_TOKEN_HOURS'
MINI_ADMIN_OPENIDS_ENV = 'TRAINING_SYSTEM_ADMIN_OPENIDS'
MINI_TOKEN_SALT = 'training-system-mini-token'


def get_mini_appid():
    """获取配置的小程序 appid。"""
    return (os.getenv(MINI_APPID_ENV, '') or '').strip()


def get_mini_secret():
    """获取配置的小程序 secret。"""
    return (os.getenv(MINI_SECRET_ENV, '') or '').strip()


def has_mini_auth_config():
    """是否已配置小程序 appid/secret。"""
    return bool(get_mini_appid() and get_mini_secret())


def parse_admin_openids():
    """从环境变量获取配置的管理员 openid 列表。"""
    raw = (os.getenv(MINI_ADMIN_OPENIDS_ENV, '') or '').strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(',') if item.strip()}


def is_admin_openid(openid):
    """检查 openid 是否在管理员列表中。"""
    candidate = (openid or '').strip()
    if not candidate:
        return False
    return candidate in parse_admin_openids()


def get_mini_token_hours():
    """获取小程序令牌有效时长（小时）。"""
    raw = os.getenv(MINI_TOKEN_HOURS_ENV, '72')
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 72


def get_mini_token_max_age_seconds():
    """获取小程序令牌最大有效期（秒）。"""
    return get_mini_token_hours() * 3600


def _build_serializer(secret_key):
    return URLSafeTimedSerializer(secret_key=secret_key, salt=MINI_TOKEN_SALT)


def sign_mini_token(secret_key, openid, is_admin=False):
    """创建签名令牌。"""
    serializer = _build_serializer(secret_key)
    payload = {
        'openid': str(openid or '').strip(),
        'is_admin': bool(is_admin)
    }
    return serializer.dumps(payload)


def verify_mini_token(secret_key, token, max_age_seconds=None):
    """验证小程序令牌并返回载荷字典。"""
    raw_token = str(token or '').strip()
    if not raw_token:
        return None

    serializer = _build_serializer(secret_key)
    max_age = max_age_seconds or get_mini_token_max_age_seconds()
    try:
        data = serializer.loads(raw_token, max_age=max_age)
    except (BadTimeSignature, BadSignature):
        return None

    if not isinstance(data, dict):
        return None

    openid = str(data.get('openid', '') or '').strip()
    if not openid:
        return None

    return {
        'openid': openid,
        'is_admin': bool(data.get('is_admin', False))
    }


def extract_mini_token(req):
    """从 Authorization/X-Mini-Token 头或查询参数提取令牌。"""
    auth_header = (req.headers.get('Authorization', '') or '').strip()
    if auth_header.lower().startswith('bearer '):
        bearer = auth_header[7:].strip()
        if bearer:
            return bearer

    header_token = (req.headers.get('X-Mini-Token', '') or '').strip()
    if header_token:
        return header_token

    query_token = (req.args.get('mini_token', '') or '').strip()
    if query_token:
        return query_token

    return ''


def exchange_code_for_openid(code, timeout_seconds=8):
    """用 wx.login 的 code 换取 openid。"""
    appid = get_mini_appid()
    secret = get_mini_secret()
    if not appid or not secret:
        return {
            'success': False,
            'message': '未配置 WECHAT_MINI_APPID 或 WECHAT_MINI_SECRET',
            'error_type': 'config'
        }

    raw_code = str(code or '').strip()
    if not raw_code:
        return {
            'success': False,
            'message': 'code 不能为空',
            'error_type': 'request'
        }

    query = parse.urlencode({
        'appid': appid,
        'secret': secret,
        'js_code': raw_code,
        'grant_type': 'authorization_code'
    })
    url = f'https://api.weixin.qq.com/sns/jscode2session?{query}'

    try:
        with request.urlopen(url, timeout=timeout_seconds) as response:
            payload = response.read().decode('utf-8')
            data = json.loads(payload)
    except Exception as err:
        return {
            'success': False,
            'message': f'请求微信接口失败: {str(err)}',
            'error_type': 'upstream'
        }

    openid = str(data.get('openid', '') or '').strip()
    if openid:
        return {
            'success': True,
            'openid': openid,
            'session_key': str(data.get('session_key', '') or '')
        }

    err_code = data.get('errcode')
    err_msg = str(data.get('errmsg', '') or '').strip()
    message = f'微信登录失败: {err_msg}' if err_msg else '微信登录失败'
    if err_code is not None:
        message = f'{message} (errcode={err_code})'
    return {
        'success': False,
        'message': message,
        'error_type': 'wechat',
        'errcode': err_code
    }


def safe_compare_openid(left, right):
    """常量时间比较 openid 文本。"""
    return hmac.compare_digest(str(left or ''), str(right or ''))
