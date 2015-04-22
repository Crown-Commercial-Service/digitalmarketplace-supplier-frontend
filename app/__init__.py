from flask import Flask
from config import config

from .main import main as main_blueprint
from .status import status as status_blueprint


def create_app(config_name):

    application = Flask(__name__,
                        static_folder='static/',
                        static_url_path=config[config_name].STATIC_URL_PATH)

    application.config.from_object(config[config_name])
    config[config_name].init_app(application)

    application.register_blueprint(status_blueprint)
    application.register_blueprint(main_blueprint,
                                   url_prefix='/suppliers')
    main_blueprint.config = {
        'BASE_TEMPLATE_DATA': application.config['BASE_TEMPLATE_DATA']
    }

    return application
