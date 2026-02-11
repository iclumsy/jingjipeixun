"""Unified error handling for the application."""
from flask import jsonify
from werkzeug.exceptions import HTTPException
import traceback


class AppError(Exception):
    """Base application error class."""

    def __init__(self, message, status_code=500, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        """Convert error to dictionary for JSON response."""
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv


class ValidationError(AppError):
    """Validation error for input data."""

    def __init__(self, message, fields=None):
        super().__init__(message, status_code=400)
        self.fields = fields or {}

    def to_dict(self):
        """Convert validation error to dictionary."""
        rv = super().to_dict()
        if self.fields:
            rv['fields'] = self.fields
        return rv


class NotFoundError(AppError):
    """Resource not found error."""

    def __init__(self, message="Resource not found"):
        super().__init__(message, status_code=404)


class DatabaseError(AppError):
    """Database operation error."""

    def __init__(self, message="Database operation failed"):
        super().__init__(message, status_code=500)


def register_error_handlers(app):
    """
    Register error handlers for the Flask application.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(AppError)
    def handle_app_error(error):
        """Handle custom application errors."""
        app.logger.error(f'{error.__class__.__name__}: {error.message}')
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handle HTTP exceptions."""
        app.logger.warning(f'HTTP {error.code}: {error.description}')
        response = jsonify({
            'error': error.description
        })
        response.status_code = error.code
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle unexpected errors."""
        app.logger.error(f'Unexpected error: {str(error)}')
        app.logger.error(traceback.format_exc())
        response = jsonify({
            'error': 'An unexpected error occurred. Please try again later.'
        })
        response.status_code = 500
        return response

    app.logger.info('Error handlers registered')
