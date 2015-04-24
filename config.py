import os
import jinja2

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    DEBUG = False
    SECRET_KEY = 'this is not secret'
    STATIC_URL_PATH = '/suppliers/static'
    ASSET_PATH = STATIC_URL_PATH + '/'
    BASE_TEMPLATE_DATA = {
        'asset_path': ASSET_PATH,
        'header_class': 'with-proposition'
    }

    # Logging
    DM_LOG_LEVEL = 'DEBUG'
    DM_APP_NAME = 'buyer-frontend'
    DM_LOG_PATH = '/var/log/digitalmarketplace/application.log'
    DM_DOWNSTREAM_REQUEST_ID_HEADER = 'X-Amz-Cf-Id'

    @staticmethod
    def init_app(app):
        repo_root = os.path.abspath(os.path.dirname(__file__))
        template_folders = [
            os.path.join(repo_root,
                         'bower_components/govuk_template/views/layouts'),
            os.path.join(repo_root, 'app/templates')
        ]
        jinja_loader = jinja2.FileSystemLoader(template_folders)
        app.jinja_loader = jinja_loader


class Test(Config):
    DEBUG = True


class Development(Config):
    DEBUG = True,


class Live(Config):
    DEBUG = False


config = {
    'development': Development,
    'preview': Development,
    'staging': Live,
    'production': Live,
    'test': Test,
}
