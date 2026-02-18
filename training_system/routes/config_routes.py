"""Configuration routes."""
from flask import Blueprint, jsonify, current_app
import json
import os

config_bp = Blueprint('config', __name__)


@config_bp.route('/api/config/job_categories', methods=['GET'])
def get_job_categories():
    """Get job categories configuration."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'job_categories.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        current_app.logger.error(f'Error loading job categories config: {str(e)}')
        return jsonify({'error': str(e)}), 500
