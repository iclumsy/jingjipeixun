"""管理后台与 API 访问的认证工具。"""
import hmac
import os
from urllib.parse import quote
from werkzeug.security import check_password_hash


DEFAULT_ADMIN_USER = 'admin'          # 默认管理员用户名
DEFAULT_ADMIN_PASSWORD = 'admin123456' # 默认管理员密码

# 环境变量名常量
ADMIN_USER_ENV = 'TRAINING_SYSTEM_ADMIN_USER'
ADMIN_PASSWORD_ENV = 'TRAINING_SYSTEM_ADMIN_PASSWORD'
ADMIN_PASSWORD_HASH_ENV = 'TRAINING_SYSTEM_ADMIN_PASSWORD_HASH'
API_KEY_ENV = 'TRAINING_SYSTEM_API_KEY'


def get_admin_user():
    """获取配置的管理员用户名。"""
    return (os.getenv(ADMIN_USER_ENV, DEFAULT_ADMIN_USER) or DEFAULT_ADMIN_USER).strip()


def get_admin_password_hash():
    """获取配置的密码哈希值（如有）。"""
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
    """验证管理员用户名和密码。"""
    expected_user = get_admin_user()
    if not hmac.compare_digest(str(username or ''), expected_user):
        return False

    raw_password = str(password or '')
    password_hash = get_admin_password_hash()
    if password_hash:
        return check_password_hash(password_hash, raw_password)

    return hmac.compare_digest(raw_password, str(get_admin_password() or ''))


def get_api_key():
    """获取配置的后端 API 密钥。"""
    return (os.getenv(API_KEY_ENV, '') or '').strip()


def has_api_key():
    """是否已配置 API 密钥。"""
    return bool(get_api_key())


def verify_api_key(candidate):
    """验证 API 密钥。"""
    expected = get_api_key()
    if not expected:
        return False
    return hmac.compare_digest(str(candidate or ''), expected)


def sanitize_next_path(next_path):
    """防止开放重定向，仅保留站内路径。"""
    raw = str(next_path or '').strip()
    if not raw:
        return '/admin'
    if not raw.startswith('/'):
        return '/admin'
    if raw.startswith('//'):
        return '/admin'
    return raw


def build_login_redirect_target(path, query_string):
    """构建带 next 参数的登录重定向 URL。"""
    target = str(path or '/admin')
    if query_string:
        target = f'{target}?{query_string}'
    return f"/auth/login?next={quote(target, safe='/?=&')}"
