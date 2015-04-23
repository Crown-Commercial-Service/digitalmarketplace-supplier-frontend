from flask import Flask
from config import config


def create_app(config_name):
    application = Flask(__name__)
    application.config.from_object(config[config_name])
    config[config_name].init_app(application)
    from .main import main as main_blueprint
    application.register_blueprint(main_blueprint)
    return application
