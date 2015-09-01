import os
import jinja2
from dmutils.status import enabled_since, get_version_label
from dmutils.asset_fingerprint import AssetFingerprinter


class Config(object):

    VERSION = get_version_label(
        os.path.abspath(os.path.dirname(__file__))
    )
    SESSION_COOKIE_NAME = 'dm_session'
    SESSION_COOKIE_PATH = '/'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    DM_DATA_API_URL = None
    DM_DATA_API_AUTH_TOKEN = None
    DM_MANDRILL_API_KEY = None
    DM_CLARIFICATION_QUESTION_EMAIL = 'digitalmarketplace@mailinator.com'
    G7_CLOSING_DATE = '3pm&nbsp;BST, 6 October 2015'

    DM_G7_DRAFT_DOCUMENTS_BUCKET = None
    DM_G7_DRAFT_DOCUMENTS_URL = None

    DEBUG = False

    RESET_PASSWORD_EMAIL_NAME = 'Digital Marketplace Admin'
    RESET_PASSWORD_EMAIL_FROM = 'enquiries@digitalmarketplace.service.gov.uk'
    RESET_PASSWORD_EMAIL_SUBJECT = 'Reset your Digital Marketplace password'

    INVITE_EMAIL_NAME = 'Digital Marketplace Admin'
    INVITE_EMAIL_FROM = 'enquiries@digitalmarketplace.service.gov.uk'
    INVITE_EMAIL_SUBJECT = 'Your Digital Marketplace invitation'

    CLARIFICATION_EMAIL_NAME = 'Digital Marketplace Admin'
    CLARIFICATION_EMAIL_FROM = 'do-not-reply@digitalmarketplace.service.gov.uk'
    CLARIFICATION_EMAIL_SUBJECT = 'Thanks for your clarification question'

    CREATE_USER_SUBJECT = 'Create your Digital Marketplace account'
    SECRET_KEY = os.getenv('DM_PASSWORD_SECRET_KEY')
    SHARED_EMAIL_KEY = os.getenv('DM_SHARED_EMAIL_KEY')
    RESET_PASSWORD_SALT = 'ResetPasswordSalt'
    INVITE_EMAIL_SALT = 'InviteEmailSalt'

    STATIC_URL_PATH = '/suppliers/static'
    ASSET_PATH = STATIC_URL_PATH + '/'
    BASE_TEMPLATE_DATA = {
        'header_class': 'with-proposition',
        'asset_path': ASSET_PATH,
        'asset_fingerprinter': AssetFingerprinter(asset_root=ASSET_PATH)
    }

    # Feature Flags
    RAISE_ERROR_ON_MISSING_FEATURES = True

    FEATURE_FLAGS_EDIT_SERVICE_PAGE = False
    FEATURE_FLAGS_SUPPLIER_DASHBOARD = False
    FEATURE_FLAGS_EDIT_SUPPLIER_PAGE = False
    FEATURE_FLAGS_GCLOUD7_OPEN = False
    FEATURE_FLAGS_USER_DASHBOARD = False

    # Logging
    DM_LOG_LEVEL = 'DEBUG'
    DM_APP_NAME = 'supplier-frontend'
    DM_LOG_PATH = '/var/log/digitalmarketplace/application.log'
    DM_DOWNSTREAM_REQUEST_ID_HEADER = 'X-Amz-Cf-Id'

    @staticmethod
    def init_app(app):
        repo_root = os.path.abspath(os.path.dirname(__file__))
        template_folders = [
            os.path.join(repo_root, 'app/templates')
        ]
        jinja_loader = jinja2.FileSystemLoader(template_folders)
        app.jinja_loader = jinja_loader


class Test(Config):
    DEBUG = True
    DM_LOG_LEVEL = 'CRITICAL'
    DM_API_AUTH_TOKEN = 'test'
    DM_API_URL = 'http://localhost'
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost'
    DM_MANDRILL_API_KEY = 'MANDRILL'
    SHARED_EMAIL_KEY = "KEY"
    DM_CLARIFICATION_QUESTION_EMAIL = 'digitalmarketplace@mailinator.com'

    FEATURE_FLAGS_EDIT_SERVICE_PAGE = enabled_since('2015-06-03')
    FEATURE_FLAGS_SUPPLIER_DASHBOARD = enabled_since('2015-06-10')
    FEATURE_FLAGS_EDIT_SUPPLIER_PAGE = enabled_since('2015-06-18')
    FEATURE_FLAGS_GCLOUD7_OPEN = enabled_since('2015-06-18')
    FEATURE_FLAGS_USER_DASHBOARD = enabled_since('2015-07-09')


class Development(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

    # Dates not formatted like YYYY-(0)M-(0)D will fail
    FEATURE_FLAGS_EDIT_SERVICE_PAGE = enabled_since('2015-06-03')
    FEATURE_FLAGS_SUPPLIER_DASHBOARD = enabled_since('2015-06-10')
    FEATURE_FLAGS_EDIT_SUPPLIER_PAGE = enabled_since('2015-06-18')
    FEATURE_FLAGS_GCLOUD7_OPEN = enabled_since('2015-06-18')
    FEATURE_FLAGS_USER_DASHBOARD = enabled_since('2015-07-09')


class Live(Config):
    """Base config for deployed environments"""
    DEBUG = False
    DM_HTTP_PROTO = 'https'


class Preview(Live):
    FEATURE_FLAGS_EDIT_SERVICE_PAGE = enabled_since('2015-06-03')
    FEATURE_FLAGS_SUPPLIER_DASHBOARD = enabled_since('2015-06-10')
    FEATURE_FLAGS_EDIT_SUPPLIER_PAGE = enabled_since('2015-06-18')
    FEATURE_FLAGS_GCLOUD7_OPEN = enabled_since('2015-06-18')
    FEATURE_FLAGS_USER_DASHBOARD = enabled_since('2015-07-09')


class Production(Live):
    FEATURE_FLAGS_SUPPLIER_DASHBOARD = enabled_since('2015-06-10')
    FEATURE_FLAGS_EDIT_SUPPLIER_PAGE = enabled_since('2015-06-18')
    FEATURE_FLAGS_USER_DASHBOARD = enabled_since('2015-08-20')


class Staging(Production):
    FEATURE_FLAGS_USER_DASHBOARD = enabled_since('2015-08-19')
    FEATURE_FLAGS_GCLOUD7_OPEN = enabled_since('2015-08-26')

configs = {
    'development': Development,
    'preview': Preview,
    'staging': Staging,
    'production': Production,
    'test': Test,
}
