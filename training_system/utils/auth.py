"""
管理后台与 API 访问的认证工具。

本模块提供以下认证相关功能：

1. 管理员账号密码验证
    - 支持明文密码和哈希密码两种模式
    - 使用 hmac.compare_digest 进行时间安全比较，防止计时攻击
    - 配置先通过环境变量读取，未配置时使用默认值

2. API Key 验证
    - 用于非浏览器客户端（如脚本、第三方服务）访问 API

3. 重定向安全
    - 防止开放重定向攻击，确保 next 参数仅指向站内路径

用到的环境变量:
    TRAINING_SYSTEM_ADMIN_USER          : 管理员用户名（默认 admin）
    TRAINING_SYSTEM_ADMIN_PASSWORD      : 管理员明文密码
    TRAINING_SYSTEM_ADMIN_PASSWORD_HASH : 管理员密码的 Werkzeug 哈希值（优先级更高）
    TRAINING_SYSTEM_ADMIN_NAME          : 单管理员真实姓名（日志显示用）
    TRAINING_SYSTEM_ADMIN_DISPLAY_NAMES : 多管理员真实姓名映射，如 admin=单利亚,cc=程超
    TRAINING_SYSTEM_API_KEY             : API 访问密钥
"""
import hmac
import os
from urllib.parse import quote
from werkzeug.security import check_password_hash


# ======================== 默认凭据配置 ========================
# 仅用于未设置环境变量时的回退，生产环境必须通过环境变量配置
DEFAULT_ADMIN_USER = 'admin'
DEFAULT_ADMIN_PASSWORD = 'admin123456'

# 环境变量名常量
ADMIN_USER_ENV = 'TRAINING_SYSTEM_ADMIN_USER'
ADMIN_PASSWORD_ENV = 'TRAINING_SYSTEM_ADMIN_PASSWORD'
ADMIN_PASSWORD_HASH_ENV = 'TRAINING_SYSTEM_ADMIN_PASSWORD_HASH'
API_KEY_ENV = 'TRAINING_SYSTEM_API_KEY'
ADMIN_DISPLAY_NAMES_ENV = 'TRAINING_SYSTEM_ADMIN_DISPLAY_NAMES'
ADMIN_NAME_ENV = 'TRAINING_SYSTEM_ADMIN_NAME'
DEFAULT_ADMIN_DISPLAY_NAMES = {
    'admin': '单利亚',
    'cc': '程超',
}


def get_admin_user():
    """获取配置的管理员用户名，优先从环境变量读取。"""
    return (os.getenv(ADMIN_USER_ENV, DEFAULT_ADMIN_USER) or DEFAULT_ADMIN_USER).strip()


def get_admin_users():
    """获取允许登录的管理员用户名列表，支持逗号或分号分隔。"""
    raw = get_admin_user()
    normalized = raw.replace('，', ',').replace(';', ',')
    users = [
        item.strip()
        for item in normalized.split(',')
        if item.strip()
    ]
    return users or [DEFAULT_ADMIN_USER]


def get_admin_password_hash():
    """获取配置的密码哈希值（如已配置），用于安全密码校验。"""
    return (os.getenv(ADMIN_PASSWORD_HASH_ENV, '') or '').strip()


def get_admin_password():
    """获取配置的明文密码（或回退到默认值）。"""
    return os.getenv(ADMIN_PASSWORD_ENV, DEFAULT_ADMIN_PASSWORD)


def using_default_admin_password():
    """是否正在使用默认密码。"""
    has_hash = bool(get_admin_password_hash())
    has_plain = bool((os.getenv(ADMIN_PASSWORD_ENV, '') or '').strip())
    return not has_hash and not has_plain


def verify_admin_credentials(username, password):
    """
    验证管理员用户名和密码。

    验证策略：
    1. 先比对用户名（时间安全比较）
    2. 如果配置了密码哈希，使用 Werkzeug 的 check_password_hash
    3. 否则回退到明文密码比对（开发/测试用）

    参数:
        username: 用户输入的用户名
        password: 用户输入的密码

    返回:
        bool: 验证是否通过
    """
    # 时间安全比较用户名，防止通过响应时间推断用户名。
    # TRAINING_SYSTEM_ADMIN_USER 支持 "admin,cc" 形式，多账号共用密码配置。
    candidate_user = str(username or '')
    if not any(hmac.compare_digest(candidate_user, expected_user) for expected_user in get_admin_users()):
        return False

    raw_password = str(password or '')
    password_hash = get_admin_password_hash()
    if password_hash:
        # 使用 Werkzeug 哈希校验（推荐方式，更安全）
        return check_password_hash(password_hash, raw_password)

    # 回退到明文密码比对（仅开发环境使用）
    return hmac.compare_digest(raw_password, str(get_admin_password() or ''))


def get_api_key():
    """获取配置的后端 API 密钥。"""
    return (os.getenv(API_KEY_ENV, '') or '').strip()


def has_api_key():
    """是否已配置 API 密钥。"""
    return bool(get_api_key())


def verify_api_key(candidate):
    """
    验证 API 密钥。

    使用时间安全比较防止计时攻击。
    如果未配置 API Key（环境变量为空），则始终拒绝访问。

    参数:
        candidate: 客户端提供的 API 密钥

    返回:
        bool: 验证是否通过
    """
    expected = get_api_key()
    if not expected:
        return False
    return hmac.compare_digest(str(candidate or ''), expected)


def sanitize_next_path(next_path):
    """
    防止开放重定向攻击，仅保留站内路径。

    开放重定向漏洞：攻击者构造如 /auth/login?next=//evil.com 的链接，
    用户登录后被重定向到恶意网站。此函数通过校验确保
    路径始终以单个 '/' 开头。

    参数:
        next_path: 登录成功后跳转的目标路径

    返回:
        str: 安全的站内路径，无效路径回退到 /admin
    """
    raw = str(next_path or '').strip()
    if not raw:
        return '/admin'
    if not raw.startswith('/'):
        return '/admin'        # 非绝对路径，拒绝
    if raw.startswith('//'):
        return '/admin'        # 协议相对 URL（如 //evil.com），拒绝
    return raw


def build_login_redirect_target(path, query_string):
    """
    构建带 next 参数的登录重定向 URL。

    用于 before_request 中将未认证用户重定向到登录页，
    并携带原始访问路径，登录成功后自动跳回。

    参数:
        path: 用户原始访问的路径
        query_string: 原始的查询字符串

    返回:
        str: 如 /auth/login?next=/admin
    """
    target = str(path or '/admin')
    if query_string:
        target = f'{target}?{query_string}'
    return f"/auth/login?next={quote(target, safe='/?=&')}"


# ======================== 日志辅助工具 ========================

# 已知小程序用户 openid → 真实姓名映射表
# 新增用户时直接在此处追加一行即可
OPENID_NAME_MAP = {
    'oQRQz3VglMF63fWRtTCX8gbl21jo': '程超',
    'oQRQz3amHUiSlU5RYNqu-r4GBJlk': '单利亚',
    'oQRQz3SPn9tEiMy74NxfrzV1ZzJE': '霍玉萍',
}


def resolve_openid_name(openid: str) -> str:
    """
    将小程序用户 openid 解析为可读姓名。

    命中映射表时返回 "姓名(openid)"，未命中时原样返回 openid。
    openid 为空时返回 "-"。

    参数:
        openid: 小程序用户 openid 字符串

    返回:
        str: 可读标识字符串
    """
    if not openid:
        return '-'
    name = OPENID_NAME_MAP.get(openid)
    if name:
        return f'{name}({openid})'
    return openid


def _parse_admin_display_names(raw: str) -> dict:
    """
    解析网页端管理员账号到真实姓名的映射。

    支持格式:
        admin=程超,reviewer=单利亚
        admin:程超;reviewer:单利亚
    """
    mapping = {}
    for item in str(raw or '').replace(';', ',').split(','):
        item = item.strip()
        if not item:
            continue
        if '=' in item:
            key, value = item.split('=', 1)
        elif ':' in item:
            key, value = item.split(':', 1)
        else:
            continue
        key = key.strip()
        value = value.strip()
        if key and value:
            mapping[key] = value
    return mapping


def resolve_web_admin_name(username: str) -> str:
    """
    将网页端管理员用户名解析为可读姓名。

    生产环境可通过 TRAINING_SYSTEM_ADMIN_DISPLAY_NAMES 配置多账号映射，
    或通过 TRAINING_SYSTEM_ADMIN_NAME 配置单账号真实姓名。未配置时回退用户名。
    """
    username = str(username or '').strip()
    if not username:
        return '-'

    mapping = _parse_admin_display_names(os.environ.get(ADMIN_DISPLAY_NAMES_ENV, ''))
    display_name = mapping.get(username)
    if display_name:
        return f'{display_name}({username})'

    default_display_name = DEFAULT_ADMIN_DISPLAY_NAMES.get(username)
    if default_display_name:
        return f'{default_display_name}({username})'

    single_name = os.environ.get(ADMIN_NAME_ENV, '').strip()
    if single_name and username in get_admin_users():
        return f'{single_name}({username})'

    return username


def get_current_actor_name() -> str:
    """返回当前请求的操作人可读名称。"""
    try:
        from flask import g, has_request_context, session
        if not has_request_context():
            return '-'
        mini_user = getattr(g, 'mini_user', None)
        if mini_user and mini_user.get('openid'):
            return resolve_openid_name(mini_user.get('openid'))
        return resolve_web_admin_name(session.get('auth_user', ''))
    except Exception:
        return '-'


def get_current_actor_source() -> str:
    """返回当前请求来源：小程序、网页端或系统。"""
    try:
        from flask import g, has_request_context, request, session
        if not has_request_context():
            return '系统'
        if getattr(g, 'mini_user', None) or request.path.startswith('/api/miniprogram/'):
            return '小程序'
        if session.get('auth_verified') is True or session.get('auth_user'):
            return '网页端'
        return '系统'
    except Exception:
        return '系统'


def get_client_ip(request) -> str:
    """
    获取客户端真实 IP，兼容 Nginx 等反向代理。

    优先读取 X-Forwarded-For 头的第一个地址，
    其次读取 X-Real-IP，最后回退到 remote_addr。

    参数:
        request: Flask request 对象

    返回:
        str: IP 地址字符串，无法获取时返回 "unknown"
    """
    forwarded = (request.headers.get('X-Forwarded-For', '') or '').strip()
    if forwarded:
        return forwarded.split(',')[0].strip()
    real_ip = (request.headers.get('X-Real-IP', '') or '').strip()
    if real_ip:
        return real_ip
    return request.remote_addr or 'unknown'


def resolve_ip_location(ip: str) -> str:
    """
    查询 IP 的物理地址信息。
    
    使用 ip-api.com 的免费接口进行查询。
    为避免阻塞主线程，设置了极短的超时时间，查询失败则静默衰退。
    
    参数:
        ip: IP 地址字符串
        
    返回:
        str: 位置信息字符串（如 "(中国 广东 深圳)"），无效或失败则返回空字符串。
    """
    if not ip or ip == 'unknown' or ip == '127.0.0.1' or ip == '::1':
        return ''
    
    # 简单过滤常见局域网 IPv4
    if ip.startswith(('192.168.', '10.', '172.16.', '172.17.', '172.18.', '172.19.', '172.2', '172.30.', '172.31.')):
        return '(局域网)'
        
    try:
        import urllib.request
        import json
        url = f"http://ip-api.com/json/{ip}?lang=zh-CN"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=1.5) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data and data.get('status') == 'success':
                parts = []
                country = data.get('country', '')
                region = data.get('regionName', '')
                city = data.get('city', '')
                
                if country and country != '中国':
                    parts.append(country)
                if region:
                    parts.append(region)
                if city and city != region:
                    parts.append(city)
                    
                loc = " ".join(parts).strip()
                if loc:
                    return f"({loc})"
    except Exception:
        pass
    return ""
