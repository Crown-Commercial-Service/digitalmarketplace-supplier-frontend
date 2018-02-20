from functools import wraps

from dmutils.access_control import require_login


def login_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        return require_login(role="supplier") or func(*args, **kwargs)
    return decorated_view
