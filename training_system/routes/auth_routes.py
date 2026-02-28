"""Authentication routes for admin web."""
from flask import Blueprint, jsonify, redirect, render_template, request, session
from utils.auth import sanitize_next_path, verify_admin_credentials


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/login', methods=['GET', 'POST'])
def login():
    """Render login page and handle credential verification."""
    next_path = sanitize_next_path(request.args.get('next', '/admin'))

    if request.method == 'GET':
        return render_template('login.html', error='', next_path=next_path)

    data = request.get_json(silent=True) if request.is_json else request.form
    username = (data.get('username', '') if data else '').strip()
    password = data.get('password', '') if data else ''

    if verify_admin_credentials(username, password):
        session.clear()
        session['auth_verified'] = True
        session['auth_user'] = username
        session.permanent = True

        if request.is_json:
            return jsonify({
                'success': True,
                'redirect': next_path
            })
        return redirect(next_path)

    if request.is_json:
        return jsonify({
            'success': False,
            'message': '账号或密码错误'
        }), 401

    return render_template('login.html', error='账号或密码错误', next_path=next_path), 401


@auth_bp.route('/auth/logout', methods=['GET', 'POST'])
def logout():
    """Clear session and return to login page."""
    session.clear()
    if request.is_json:
        return jsonify({'success': True})
    return redirect('/auth/login')
