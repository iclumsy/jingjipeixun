"""
微信小程序认证工具。

本模块提供微信小程序端的用户认证功能：

1. Code 换取 OpenID
    - 调用微信 jscode2session 接口
    - 使用小程序的 appid + secret + 临时 code 换取用户 openid

2. JWT 令牌签发与验证
    - 签发包含 openid 和管理员标识的令牌
    - 记录过期时间，默认 72 小时
    - 使用 HMAC-SHA256 签名确保防篡改

3. 管理员 OpenID 管理
    - 通过环境变量 TRAINING_SYSTEM_ADMIN_OPENIDS 配置
    - 支持多个 openid，逗号分隔

用到的环境变量:
    WECHAT_MINI_APPID                : 小程序 AppID
    WECHAT_MINI_SECRET               : 小程序 AppSecret
    TRAINING_SYSTEM_ADMIN_OPENIDS    : 管理员 openid 列表（逗号分隔）
    TRAINING_SYSTEM_MINI_TOKEN_HOURS : 令牌有效时长（小时，默认 72）
"""
import hmac
import json
import os
from urllib import parse, request
from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer


# ======================== 环境变量名常量 ========================
ENV_APPID = 'WECHAT_MINI_APPID'       # 小程序 AppID
ENV_SECRET = 'WECHAT_MINI_SECRET'      # 小程序 AppSecret
ENV_ADMIN_OPENIDS = 'TRAINING_SYSTEM_ADMIN_OPENIDS'    # 管理员 openid 列表
ENV_TOKEN_HOURS = 'TRAINING_SYSTEM_MINI_TOKEN_HOURS'   # 令牌有效时长（小时）
DEFAULT_TOKEN_HOURS = 72  # 默认令牌有效期 3 天
MINI_TOKEN_SALT = 'training-system-mini-token'


def get_mini_appid():
    """获取配置的小程序 appid。"""
    return (os.getenv(ENV_APPID, '') or '').strip()


def get_mini_secret():
    """获取配置的小程序 secret。"""
    return (os.getenv(ENV_SECRET, '') or '').strip()


def has_mini_auth_config():
    """是否已配置小程序 appid/secret。"""
    return bool(get_mini_appid() and get_mini_secret())


def parse_admin_openids():
    """
    获取配置的管理员 openid 集合。

    管理员 openid 通过环境变量配置，支持多个 openid 逗号分隔。
    示例: TRAINING_SYSTEM_ADMIN_OPENIDS=oXXXXX1,oXXXXX2

    返回:
        set: 管理员 openid 集合（已去除空白和空字符串）
    """
    raw = (os.getenv(ENV_ADMIN_OPENIDS, '') or '').strip()
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
    raw = os.getenv(ENV_TOKEN_HOURS, str(DEFAULT_TOKEN_HOURS))
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_TOKEN_HOURS


def get_mini_token_max_age_seconds():
    """获取小程序令牌最大有效期（秒）。"""
    return get_mini_token_hours() * 3600


def _build_serializer(secret_key):
    return URLSafeTimedSerializer(secret_key=secret_key, salt=MINI_TOKEN_SALT)


def sign_mini_token(secret_key, openid, is_admin=False):
    """
    签发小程序用户的 JWT 令牌。

    令牌载荷包含：
    - openid   : 用户唯一标识
    - is_admin : 是否为管理员
    - exp      : 过期时间戳

    使用 HMAC-SHA256 签名，确保令牌不可被篡改。

    参数:
        secret_key: 签名密钥（Flask app.config['SECRET_KEY']）
        openid: 用户 openid
        is_admin: 是否为管理员

    返回:
        str: Base64 编码的 JWT 令牌
    """
    serializer = _build_serializer(secret_key)
    payload = {
        'openid': str(openid or '').strip(),
        'is_admin': bool(is_admin)
    }
    return serializer.dumps(payload)


def verify_mini_token(secret_key, token, max_age_seconds=None):
    """
    验证小程序 JWT 令牌。

    验证流程:
    1. Base64 解码令牌
    2. 拆分载荷和签名
    3. 重新计算 HMAC-SHA256 签名并比对（时间安全比较）
    4. 检查令牌是否过期

    参数:
        secret_key: 签名密钥
        token: 待验证的令牌字符串

    返回:
        dict 或 None: 验证成功返回用户信息 {'openid': '...', 'is_admin': bool}，
                       失败返回 None
    """
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


# ======================== 微信接口配置 ========================
# jscode2session 接口地址（用于用 code 换取 openid）
WX_AUTH_URL = 'https://api.weixin.qq.com/sns/jscode2session'


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
    url = f'{WX_AUTH_URL}?{query}'

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
