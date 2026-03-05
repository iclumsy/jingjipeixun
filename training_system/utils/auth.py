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


def get_admin_user():
    """获取配置的管理员用户名，优先从环境变量读取。"""
    return (os.getenv(ADMIN_USER_ENV, DEFAULT_ADMIN_USER) or DEFAULT_ADMIN_USER).strip()


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
    # 时间安全比较用户名，防止通过响应时间推断用户名
    expected_user = get_admin_user()
    if not hmac.compare_digest(str(username or ''), expected_user):
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
