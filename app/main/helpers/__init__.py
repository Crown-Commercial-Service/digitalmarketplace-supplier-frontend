import base64
import hashlib
import flask_login

from datetime import datetime
from functools import wraps
from flask import current_app, flash


def hash_email(email):
    m = hashlib.sha256()
    m.update(email.encode('utf-8'))

    return base64.urlsafe_b64encode(m.digest())


def login_required(func):
    @wraps(func)
    @flask_login.login_required
    def decorated_view(*args, **kwargs):
        if flask_login.current_user.is_authenticated() and flask_login.current_user.role != 'supplier':
            flash('supplier-role-required', 'error')
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view


def new_supplier_flow_active_for_datetime(dt):
    if not current_app.config['FEATURE_FLAGS_NEW_SUPPLIER_FLOW']:
        return False
    nsf_on = datetime.strptime(current_app.config['FEATURE_FLAGS_NEW_SUPPLIER_FLOW'], "%Y-%m-%d")
    return nsf_on <= dt
