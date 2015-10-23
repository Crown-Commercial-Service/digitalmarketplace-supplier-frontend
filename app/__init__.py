import re

from flask import Flask, request, redirect, session, Markup, abort
from flask_login import LoginManager
from flask_wtf.csrf import CsrfProtect

from dmutils import apiclient, init_app, flask_featureflags
from dmutils.user import User

from config import configs

from markdown import markdown


data_api_client = apiclient.DataAPIClient()
login_manager = LoginManager()
feature_flags = flask_featureflags.FeatureFlag()
csrf = CsrfProtect()


from app.main.helpers.services import parse_document_upload_time


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

    from .main import main as main_blueprint
    from .status import status as status_blueprint

    application.register_blueprint(status_blueprint,
                                   url_prefix='/suppliers')
    application.register_blueprint(main_blueprint,
                                   url_prefix='/suppliers')
    login_manager.login_view = 'main.render_login'
    login_manager.login_message_category = "must_login"
    main_blueprint.config = application.config.copy()

    csrf.init_app(application)

    @csrf.error_handler
    def csrf_handler(reason):
        if 'user_id' not in session:
            application.logger.info(
                u'csrf.session_expired: Redirecting user to log in page'
            )

            return application.login_manager.unauthorized()

        application.logger.info(
            u'csrf.invalid_token: Aborting request, user_id: {user_id}',
            extra={'user_id': session['user_id']})

        abort(400, reason)

    @application.before_request
    def remove_trailing_slash():
        if request.path.endswith('/'):
            return redirect(request.path[:-1], code=301)

    @application.before_request
    def refresh_session():
        session.permanent = True
        session.modified = True

    @application.template_filter('markdown')
    def markdown_filter(data):
        return Markup(markdown(data))

    @application.template_filter('question_references')
    def question_references_filter(data, get_question):
        return re.sub(
            r"\[\[([^\]]+)\]\]",  # anything that looks like [[nameOfQuestion]]
            lambda question_id: str(get_question(question_id.group(1))['number']),
            data
        )

    application.add_template_filter(parse_document_upload_time)

    return application


@login_manager.user_loader
def load_user(user_id):
    return User.load_user(data_api_client, user_id)


def config_attrs(config):
    """Returns config attributes from a Config object"""
    p = re.compile('^[A-Z_]+$')
    return filter(lambda attr: bool(p.match(attr)), dir(config))
