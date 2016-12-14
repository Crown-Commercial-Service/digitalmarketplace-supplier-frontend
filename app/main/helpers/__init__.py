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


def applicant_login_required(func):
    @wraps(func)
    @flask_login.login_required
    def decorated_view(*args, **kwargs):
        if current_user.is_authenticated and current_user.role != 'applicant':
            flash('applicant-role-required', 'error')
            return current_app.login_manager.unauthorized()
        return func(*args, **kwargs)
    return decorated_view


def role_required(*roles):
    """Ensure that logged in user has one of the required roles.

    Return 403 if the user doesn't have a required role.

    Should be applied before the `@login_required` decorator:

        @login_required
        @role_required('admin', 'admin-ccs-category')
        def view():
            ...

    """

    def role_decorator(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            if not any(current_user.has_role(role) for role in roles):
                return abort(403, "One of {} roles required".format(", ".join(roles)))
            return func(*args, **kwargs)

        return decorated_view

    return role_decorator


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
