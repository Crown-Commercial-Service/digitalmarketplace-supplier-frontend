import re

from datetime import timedelta
from flask import Flask, request, redirect, session
from flask_login import LoginManager
from flask._compat import string_types
from flask_wtf.csrf import CsrfProtect

from dmutils import apiclient, init_app, flask_featureflags
from dmutils.user import User

from config import configs


data_api_client = apiclient.DataAPIClient()
login_manager = LoginManager()
feature_flags = flask_featureflags.FeatureFlag()
csrf = CsrfProtect()


def create_app(config_name):
    application = Flask(__name__,
                        static_folder='static/',
                        static_url_path=configs[config_name].STATIC_URL_PATH)

    init_app(
        application,
        configs[config_name],
        data_api_client=data_api_client,
        feature_flags=feature_flags,
        login_manager=login_manager,
    )
    application.permanent_session_lifetime = timedelta(hours=1)
    from .main import main as main_blueprint
    from .status import status as status_blueprint

    application.register_blueprint(status_blueprint,
                                   url_prefix='/suppliers')
    application.register_blueprint(main_blueprint,
                                   url_prefix='/suppliers')
    login_manager.login_view = 'main.render_login'
    main_blueprint.config = application.config.copy()

    csrf.init_app(application)

    @application.before_request
    def remove_trailing_slash():
        if request.path.endswith('/'):
            return redirect(request.path[:-1], code=301)

    @application.before_request
    def refresh_session():
        session.permanent = True
        session.modified = True

    return application


@login_manager.user_loader
def load_user(user_id):
    return User.from_json(data_api_client.get_user(user_id=int(user_id)))


def config_attrs(config):
    """Returns config attributes from a Config object"""
    p = re.compile('^[A-Z_]+$')
    return filter(lambda attr: bool(p.match(attr)), dir(config))


def convert_to_boolean(value):
    """Turn strings to bools if they look like them

    Truthy things should be True
    >>> for truthy in ['true', 'on', 'yes', '1']:
    ...   assert convert_to_boolean(truthy) == True

    Falsey things should be False
    >>> for falsey in ['false', 'off', 'no', '0']:
    ...   assert convert_to_boolean(falsey) == False

    Other things should be unchanged
    >>> for value in ['falsey', 'other', True, 0]:
    ...   assert convert_to_boolean(value) == value
    """
    if isinstance(value, string_types):
        if value.lower() in ['t', 'true', 'on', 'yes', '1']:
            return True
        elif value.lower() in ['f', 'false', 'off', 'no', '0']:
            return False

    return value
