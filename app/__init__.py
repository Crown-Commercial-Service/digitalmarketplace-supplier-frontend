import os
import re

from flask import Flask
from flask_login import LoginManager
from config import config
from flask._compat import string_types
from .flask_api_client.api_client import ApiClient

api_client = ApiClient()
login_manager = LoginManager()


def create_app(config_name):
    application = Flask(__name__,
                        static_folder='static/',
                        static_url_path=config[config_name].STATIC_URL_PATH)

    from .main import main as main_blueprint
    from .status import status as status_blueprint

    application.config.from_object(config[config_name])

    for name in config_attrs(config[config_name]):
        if name in os.environ:
            application.config[name] = convert_to_boolean(os.environ[name])

    config[config_name].init_app(application)
    api_client.init_app(application)
    login_manager.init_app(application)
    login_manager.login_view = '/suppliers/login'
    application.register_blueprint(status_blueprint)
    application.register_blueprint(main_blueprint,
                                   url_prefix='/suppliers')
    main_blueprint.config = {
        'BASE_TEMPLATE_DATA': application.config['BASE_TEMPLATE_DATA']
    }

    return application


@login_manager.user_loader
def load_user(user_id):
    return api_client.user_by_id(int(user_id))


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
