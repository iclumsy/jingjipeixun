"""Main application entry point."""
import os
from datetime import timedelta
from flask import Flask, jsonify, redirect, render_template, request, session
from models.student import init_db
from routes.auth_routes import auth_bp
from routes.student_routes import student_bp
from routes.file_routes import file_bp
from routes.export_routes import export_bp
from routes.config_routes import config_bp
from utils.auth import (
    build_login_redirect_target,
    has_api_key,
    using_default_admin_password,
    verify_api_key
)
from utils.logger import setup_logger
from utils.error_handlers import register_error_handlers


def _strip_wrapping_quotes(value):
    """Strip a matching pair of wrapping single/double quotes."""
    text = str(value or '').strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _resolve_env_file_path(base_dir):
    """Resolve env file path from TRAINING_SYSTEM_ENV_FILE or default .env."""
    configured = (os.getenv('TRAINING_SYSTEM_ENV_FILE', '') or '').strip()
    if not configured:
        return os.path.join(base_dir, '.env')
    if os.path.isabs(configured):
        return configured
    return os.path.join(base_dir, configured)


def load_env_file(base_dir):
    """
    Load env vars from config file.
    Existing process env has priority and will not be overridden.
    """
    env_file = _resolve_env_file_path(base_dir)
    result = {
        'path': env_file,
        'loaded': 0,
        'exists': os.path.isfile(env_file),
        'error': ''
    }
    if not result['exists']:
        return result

    try:
        with open(env_file, 'r', encoding='utf-8') as fp:
            for raw_line in fp:
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('export '):
                    line = line[7:].strip()
                if '=' not in line:
                    continue

                key, value = line.split('=', 1)
                key = key.strip()
                if not key:
                    continue

                os.environ.setdefault(key, _strip_wrapping_quotes(value))
                result['loaded'] += 1
    except OSError as err:
        result['error'] = str(err)

    return result


def get_max_content_length():
    """
    Build MAX_CONTENT_LENGTH from env var MAX_CONTENT_LENGTH_MB.
    Default 64MB to support multi-attachment sync uploads.
    """
    raw_mb = os.getenv('MAX_CONTENT_LENGTH_MB', '64')
    try:
        mb = int(raw_mb)
    except (TypeError, ValueError):
        mb = 64

    if mb <= 0:
        mb = 64

    return mb * 1024 * 1024


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Configuration
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    env_load = load_env_file(BASE_DIR)
    app.config['BASE_DIR'] = BASE_DIR
    app.config['STUDENTS_FOLDER'] = os.path.join(BASE_DIR, 'students')
    app.config['DATABASE'] = os.path.join(BASE_DIR, 'database/students.db')
    app.config['MAX_CONTENT_LENGTH'] = get_max_content_length()
    app.config['SECRET_KEY'] = os.getenv('TRAINING_SYSTEM_SECRET_KEY') or os.urandom(32)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('TRAINING_SYSTEM_SECURE_COOKIE', 'false').lower() == 'true'
    raw_session_hours = os.getenv('TRAINING_SYSTEM_SESSION_HOURS', '12')
    try:
        session_hours = max(1, int(raw_session_hours))
    except (TypeError, ValueError):
        session_hours = 12
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=session_hours)

    # Ensure directories exist
    os.makedirs(app.config['STUDENTS_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'database'), exist_ok=True)

    # Initialize database
    init_db(app.config['DATABASE'])

    # Setup logging
    setup_logger(app)
    if env_load.get('error'):
        app.logger.warning(
            'Failed to load env file %s: %s',
            env_load.get('path', ''),
            env_load.get('error', '')
        )
    elif env_load.get('exists'):
        app.logger.info(
            'Loaded env config from %s (%s entries)',
            env_load.get('path', ''),
            env_load.get('loaded', 0)
        )
    else:
        app.logger.info(
            'Env config file not found, skipped: %s',
            env_load.get('path', '')
        )

    # Register error handlers
    register_error_handlers(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(config_bp)

    @app.before_request
    def require_authentication():
        """Protect admin pages and API routes with session or API key."""
        path = request.path or '/'
        protected_api = path.startswith('/api/') or path.startswith('/students/')

        if path.startswith('/static/') or path == '/favicon.ico':
            return None

        if path.startswith('/auth/'):
            return None

        if session.get('auth_verified') is True:
            return None

        if protected_api:
            candidate_api_key = (
                request.headers.get('X-API-Key', '')
                or request.headers.get('x-api-key', '')
                or request.args.get('api_key', '')
            )
            if verify_api_key(candidate_api_key):
                return None
            return jsonify({
                'error': 'unauthorized',
                'message': '未授权访问，请先登录或提供有效 API Key'
            }), 401

        query_string = request.query_string.decode('utf-8', errors='ignore')
        return redirect(build_login_redirect_target(path, query_string))

    # # Main routes
    # @app.route('/')
    # def index():
    #     return render_template('index.html')

    @app.route('/admin')
    def admin():
        return render_template('admin.html', training_type='special_equipment')

    if using_default_admin_password():
        app.logger.warning('Using default admin password, please set TRAINING_SYSTEM_ADMIN_PASSWORD or TRAINING_SYSTEM_ADMIN_PASSWORD_HASH')
    if not has_api_key():
        app.logger.warning('TRAINING_SYSTEM_API_KEY is not configured, non-session API access will be blocked')

    app.logger.info('Application initialized successfully')

    return app

# Create application instance
app = create_app()


if __name__ == '__main__':
    # Use environment variable for debug mode
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5001) 
