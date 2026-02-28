"""Authentication helpers for web admin and API access."""
import hmac
import os
from urllib.parse import quote
from werkzeug.security import check_password_hash


DEFAULT_ADMIN_USER = 'admin'
DEFAULT_ADMIN_PASSWORD = 'admin123456'

ADMIN_USER_ENV = 'TRAINING_SYSTEM_ADMIN_USER'
ADMIN_PASSWORD_ENV = 'TRAINING_SYSTEM_ADMIN_PASSWORD'
ADMIN_PASSWORD_HASH_ENV = 'TRAINING_SYSTEM_ADMIN_PASSWORD_HASH'
API_KEY_ENV = 'TRAINING_SYSTEM_API_KEY'


def get_admin_user():
    """Return configured admin username."""
    return (os.getenv(ADMIN_USER_ENV, DEFAULT_ADMIN_USER) or DEFAULT_ADMIN_USER).strip()


def get_admin_password_hash():
    """Return configured password hash if available."""
    return (os.getenv(ADMIN_PASSWORD_HASH_ENV, '') or '').strip()


def get_admin_password():
    """Return configured plain password (or fallback default)."""
    return os.getenv(ADMIN_PASSWORD_ENV, DEFAULT_ADMIN_PASSWORD)


def using_default_admin_password():
    """Whether default password is being used."""
    has_hash = bool(get_admin_password_hash())
    has_plain = bool((os.getenv(ADMIN_PASSWORD_ENV, '') or '').strip())
    return not has_hash and not has_plain


def verify_admin_credentials(username, password):
    """Validate admin username/password."""
    expected_user = get_admin_user()
    if not hmac.compare_digest(str(username or ''), expected_user):
        return False

    raw_password = str(password or '')
    password_hash = get_admin_password_hash()
    if password_hash:
        return check_password_hash(password_hash, raw_password)

    return hmac.compare_digest(raw_password, str(get_admin_password() or ''))


def get_api_key():
    """Return configured backend API key."""
    return (os.getenv(API_KEY_ENV, '') or '').strip()


def has_api_key():
    """Whether API key has been configured."""
    return bool(get_api_key())


def verify_api_key(candidate):
    """Validate API key."""
    expected = get_api_key()
    if not expected:
        return False
    return hmac.compare_digest(str(candidate or ''), expected)


def sanitize_next_path(next_path):
    """Prevent open redirects and keep only in-site paths."""
    raw = str(next_path or '').strip()
    if not raw:
        return '/admin'
    if not raw.startswith('/'):
        return '/admin'
    if raw.startswith('//'):
        return '/admin'
    return raw


def build_login_redirect_target(path, query_string):
    """Build login redirect URL with next parameter."""
    target = str(path or '/admin')
    if query_string:
        target = f'{target}?{query_string}'
    return f"/auth/login?next={quote(target, safe='/?=&')}"
