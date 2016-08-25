import os
import urlparse

from flask import Flask, request
from flask_login import LoginManager

import dmapiclient
from dmutils import init_app, init_frontend_app, flask_featureflags
from dmutils.user import User
from dmutils.forms import valid_csrf_or_abort

from config import configs


data_api_client = dmapiclient.DataAPIClient()
login_manager = LoginManager()
feature_flags = flask_featureflags.FeatureFlag()

from app.main.helpers.services import parse_document_upload_time
from app.main.helpers.frameworks import question_references


def create_app(config_name):
    asset_path = os.environ.get('ASSET_PATH', configs[config_name].ASSET_PATH)
    application = Flask(__name__,
                        static_folder='static/',
                        static_url_path=asset_path)

    init_app(
        application,
        configs[config_name],
        data_api_client=data_api_client,
        feature_flags=feature_flags,
        login_manager=login_manager,
    )

    from .main import main as main_blueprint
    from .status import status as status_blueprint

    url_prefix = application.config['URL_PREFIX']
    application.register_blueprint(status_blueprint,
                                   url_prefix=url_prefix)
    application.register_blueprint(main_blueprint,
                                   url_prefix=url_prefix)
    login_manager.login_message_category = "must_login"
    main_blueprint.config = application.config.copy()

    application.add_template_filter(question_references)
    application.add_template_filter(parse_document_upload_time)

    init_frontend_app(application, data_api_client, login_manager)

    @application.before_request
    def check_csrf_token():
        if request.method in ('POST', 'PATCH', 'DELETE'):
            valid_csrf_or_abort()

    @application.context_processor
    def extra_template_variables():
        return {
            'marketplace_home': urlparse.urljoin('/', application.config['BASE_PREFIX']),
        }

    return application
