import hashlib
import base64
import flask_login
import six
from functools import wraps
from flask import abort, current_app, flash, request
from flask_login import current_user


def hash_email(email):
    m = hashlib.sha256()
    m.update(email.encode('utf-8'))

    return base64.urlsafe_b64encode(m.digest())


def login_required(func):
    @wraps(func)
    @flask_login.login_required
    def decorated_view(*args, **kwargs):
        if current_user.is_authenticated and current_user.role != 'supplier':
            flash('supplier-role-required', 'error')
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view


def debug_only(func):
    """
    Allows a handler to be used in development and testing, without being made live.
    """
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_app.config['DEBUG']:
            abort(404)
        current_app.logger.warn('This endpoint disabled in live builds: {}'.format(request.url))
        return func(*args, **kwargs)
    return decorated_view
