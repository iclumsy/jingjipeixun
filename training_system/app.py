"""Main application entry point."""
import os
from flask import Flask, render_template
from models.student import init_db
from routes.student_routes import student_bp
from routes.file_routes import file_bp
from routes.export_routes import export_bp
from routes.config_routes import config_bp
from utils.logger import setup_logger
from utils.error_handlers import register_error_handlers


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Configuration
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    app.config['BASE_DIR'] = BASE_DIR
    app.config['STUDENTS_FOLDER'] = os.path.join(BASE_DIR, 'students')
    app.config['DATABASE'] = os.path.join(BASE_DIR, 'database/students.db')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    # Ensure directories exist
    os.makedirs(app.config['STUDENTS_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'database'), exist_ok=True)

    # Initialize database
    init_db(app.config['DATABASE'])

    # Setup logging
    setup_logger(app)

    # Register error handlers
    register_error_handlers(app)

    # Register blueprints
    app.register_blueprint(student_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(config_bp)

    # Main routes
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/admin')
    def admin():
        return render_template('admin.html', training_type='special_equipment')

    app.logger.info('Application initialized successfully')

    return app

# Create application instance
app = create_app()


if __name__ == '__main__':
    # Use environment variable for debug mode
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5001) 
