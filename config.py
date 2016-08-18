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

    BASE_PREFIX = '/marketplace'
    URL_PREFIX = BASE_PREFIX + '/suppliers'

    CSRF_ENABLED = True
    CSRF_TIME_LIMIT = 8*3600

    PERMANENT_SESSION_LIFETIME = 4*3600
    DM_DEFAULT_CACHE_MAX_AGE = 48*3600

    DM_DATA_API_URL = None
    DM_DATA_API_AUTH_TOKEN = None
    DM_CLARIFICATION_QUESTION_EMAIL = 'no-reply@marketplace.digital.gov.au'
    DM_FRAMEWORK_AGREEMENTS_EMAIL = 'enquiries@example.com'

    DM_AGREEMENTS_BUCKET = None
    DM_COMMUNICATIONS_BUCKET = None
    DM_DOCUMENTS_BUCKET = None
    DM_SUBMISSIONS_BUCKET = None
    DM_ASSETS_URL = None

    DM_HTTP_PROTO = 'http'

    DEBUG = False

    RESET_PASSWORD_EMAIL_NAME = 'Digital Marketplace Admin'
    RESET_PASSWORD_EMAIL_FROM = 'no-reply@marketplace.digital.gov.au'
    RESET_PASSWORD_EMAIL_SUBJECT = 'Reset your Digital Marketplace password'

    INVITE_EMAIL_NAME = 'Digital Marketplace Admin'
    INVITE_EMAIL_FROM = 'no-reply@marketplace.digital.gov.au'
    INVITE_EMAIL_SUBJECT = 'Your Digital Marketplace invitation'

    CLARIFICATION_EMAIL_NAME = 'Digital Marketplace Admin'
    CLARIFICATION_EMAIL_FROM = 'no-reply@marketplace.digital.gov.au'
    CLARIFICATION_EMAIL_SUBJECT = 'Thanks for your clarification question'
    DM_FOLLOW_UP_EMAIL_TO = 'digitalmarketplace@mailinator.com'

    FRAMEWORK_AGREEMENT_RETURNED_NAME = 'Digital Marketplace Admin'

    DM_GENERIC_NOREPLY_EMAIL = 'no-reply@marketplace.digital.gov.au'

    CREATE_USER_SUBJECT = 'Create your Digital Marketplace account'
    SECRET_KEY = None
    SHARED_EMAIL_KEY = None
    RESET_PASSWORD_SALT = 'ResetPasswordSalt'
    INVITE_EMAIL_SALT = 'InviteEmailSalt'

    STATIC_URL_PATH = URL_PREFIX + '/static'
    ASSET_PATH = STATIC_URL_PATH + '/'
    BASE_TEMPLATE_DATA = {
        'header_class': 'with-proposition',
        'asset_path': ASSET_PATH,
        'asset_fingerprinter': AssetFingerprinter(asset_root=ASSET_PATH)
    }

    # Feature Flags
    RAISE_ERROR_ON_MISSING_FEATURES = True

    FEATURE_FLAGS_EDIT_SECTIONS = False

    # Logging
    DM_LOG_LEVEL = 'DEBUG'
    DM_LOG_PATH = None
    DM_APP_NAME = 'supplier-frontend'
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
    CSRF_ENABLED = False
    CSRF_FAKED = True
    DM_LOG_LEVEL = 'CRITICAL'
    SERVER_NAME = 'localhost'
    SHARED_EMAIL_KEY = "KEY"

    FEATURE_FLAGS_EDIT_SECTIONS = enabled_since('2015-06-03')

    DM_DATA_API_AUTH_TOKEN = 'myToken'

    SECRET_KEY = 'not_very_secret'

    DM_SUBMISSIONS_BUCKET = 'digitalmarketplace-submissions-dev-dev'
    DM_COMMUNICATIONS_BUCKET = 'digitalmarketplace-communications-dev-dev'
    DM_ASSETS_URL = 'http://asset-host'


class Development(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    DM_SEND_EMAIL_TO_STDERR = False

    # Dates not formatted like YYYY-(0)M-(0)D will fail
    FEATURE_FLAGS_EDIT_SECTIONS = enabled_since('2015-06-03')

    DM_DATA_API_URL = "http://localhost:5000"
    DM_DATA_API_AUTH_TOKEN = "myToken"
    DM_API_AUTH_TOKEN = "myToken"

    DM_SUBMISSIONS_BUCKET = "digitalmarketplace-submissions-dev-dev"
    DM_COMMUNICATIONS_BUCKET = "digitalmarketplace-communications-dev-dev"
    DM_AGREEMENTS_BUCKET = "digitalmarketplace-agreements-dev-dev"
    DM_DOCUMENTS_BUCKET = "digitalmarketplace-documents-dev-dev"
    DM_ASSETS_URL = "https://{}.s3-eu-west-1.amazonaws.com".format(DM_SUBMISSIONS_BUCKET)

    SHARED_EMAIL_KEY = "very_secret"
    SECRET_KEY = 'verySecretKey'


class Live(Config):
    """Base config for deployed environments"""
    DEBUG = False
    DM_LOG_PATH = '/var/log/digitalmarketplace/application.log'
    DM_HTTP_PROTO = 'https'

    DM_FRAMEWORK_AGREEMENTS_EMAIL = 'no-reply@marketplace.digital.gov.au'


class Preview(Live):
    pass


class Production(Live):
    pass


class Staging(Production):
    pass

configs = {
    'development': Development,
    'preview': Preview,
    'staging': Staging,
    'production': Production,
    'test': Test,
}
