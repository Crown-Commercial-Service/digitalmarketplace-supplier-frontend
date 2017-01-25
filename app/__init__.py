import os
import urlparse

from flask import Flask, request
from flask_login import LoginManager

import dmapiclient
from dmutils import init_app, init_frontend_app
from dmutils.user import User

from config import configs

from react.render import render_component

data_api_client = dmapiclient.DataAPIClient()
login_manager = LoginManager()

from app.main.helpers.services import parse_document_upload_time  # noqa
from app.main.helpers.frameworks import question_references  # noqa


def create_app(config_name):
    asset_path = os.environ.get('ASSET_PATH', configs[config_name].ASSET_PATH)
    application = Flask(__name__,
                        static_folder='static/',
                        static_url_path=asset_path)

    init_app(
        application,
        configs[config_name],
        data_api_client=data_api_client,
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

    @application.context_processor
    def extra_template_variables():
        return {
            'marketplace_home': urlparse.urljoin('/', application.config['BASE_PREFIX']),
            'generic_contact_email': application.config['GENERIC_CONTACT_EMAIL'],
        }

    def component_filter(x, thing, *args, **kwargs):
        from jinja2 import Markup  # , escape
        from flask import current_app

        COMPONENTS = 'components'
        EXTENSION = '.html'

        t = current_app.jinja_env.get_template(
            COMPONENTS + '/' + thing + EXTENSION)
        return Markup(t.render(x=x, **kwargs))

    application.jinja_env.filters['as'] = component_filter
    application.jinja_env.globals.update(render_component=render_component)

    return application
