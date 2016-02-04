import hashlib
import base64
import six
from functools import wraps
from flask import current_app, flash
from flask_login import current_user


def hash_email(email):
    m = hashlib.sha256()
    m.update(email.encode('utf-8'))

    return base64.urlsafe_b64encode(m.digest())


def supplier_role_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_user.is_authenticated() and current_user.role != 'supplier':
            flash('supplier-role-required', 'error')
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view
