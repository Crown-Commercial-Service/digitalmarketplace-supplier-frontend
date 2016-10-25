import os
from dmutils.status import enabled_since, get_version_label


class Config(object):
    VERSION = get_version_label(
        os.path.abspath(os.path.dirname(__file__))
    )
    SESSION_COOKIE_NAME = 'dm_session'
    SESSION_COOKIE_PATH = '/'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True

    BASE_PREFIX = ''
    URL_PREFIX = BASE_PREFIX + '/sellers'

    CSRF_ENABLED = True
    CSRF_TIME_LIMIT = 8*3600

    PERMANENT_SESSION_LIFETIME = 4*3600
    DM_DEFAULT_CACHE_MAX_AGE = 48*3600

    DM_TIMEZONE = 'Australia/Sydney'

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
    DM_SEND_EMAIL_TO_STDERR = False
    DM_CACHE_TYPE = 'dev'

    DEBUG = False

    GENERIC_CONTACT_EMAIL = 'marketplace@digital.gov.au'
    DM_GENERIC_NOREPLY_EMAIL = 'no-reply@marketplace.digital.gov.au'
    DM_GENERIC_ADMIN_NAME = 'Digital Marketplace Admin'

    RESET_PASSWORD_EMAIL_NAME = DM_GENERIC_ADMIN_NAME
    RESET_PASSWORD_EMAIL_FROM = 'no-reply@marketplace.digital.gov.au'
    RESET_PASSWORD_EMAIL_SUBJECT = 'Reset your Digital Marketplace password'

    INVITE_EMAIL_NAME = DM_GENERIC_ADMIN_NAME
    INVITE_EMAIL_FROM = 'no-reply@marketplace.digital.gov.au'
    INVITE_EMAIL_SUBJECT = 'Your Digital Marketplace invitation'

    NEW_SUPPLIER_INVITE_SUBJECT = 'Digital Marketplace - invitation to create seller account'

    CLARIFICATION_EMAIL_NAME = DM_GENERIC_ADMIN_NAME
    CLARIFICATION_EMAIL_FROM = 'no-reply@marketplace.digital.gov.au'
    CLARIFICATION_EMAIL_SUBJECT = 'Thanks for your clarification question'
    DM_FOLLOW_UP_EMAIL_TO = 'digitalmarketplace@mailinator.com'

    FRAMEWORK_AGREEMENT_RETURNED_NAME = DM_GENERIC_ADMIN_NAME

    CREATE_USER_SUBJECT = 'Create your Digital Marketplace account'
    SECRET_KEY = None
    SHARED_EMAIL_KEY = None
    RESET_PASSWORD_SALT = 'ResetPasswordSalt'
    SUPPLIER_INVITE_TOKEN_SALT = 'SupplierInviteEmail'

    ASSET_PATH = URL_PREFIX + '/static'

    FEATURE_FLAGS = {
        'EDIT_SECTIONS': True,
    }

    # Logging
    DM_LOG_LEVEL = 'DEBUG'
    DM_LOG_PATH = None
    DM_APP_NAME = 'supplier-frontend'
    DM_DOWNSTREAM_REQUEST_ID_HEADER = 'X-Amz-Cf-Id'

    REACT_BUNDLE_URL = 'https://dm-dev-frontend.apps.staging.digital.gov.au/bundle/'
    REACT_RENDER_URL = 'https://dm-dev-frontend.apps.staging.digital.gov.au/render'
    REACT_RENDER = not DEBUG


class Test(Config):
    DEBUG = True
    CSRF_ENABLED = False
    CSRF_FAKED = True
    DM_LOG_LEVEL = 'CRITICAL'
    SERVER_NAME = 'localhost'

    # Throw an exception in dev when a feature flag is used in code but not defined. Otherwise it is assumed False.
    RAISE_ERROR_ON_MISSING_FEATURES = True

    # Used a fixed timezone for tests. Using Sydney timezone will catch more timezone bugs than London.
    DM_TIMEZONE = 'Australia/Sydney'

    DM_DATA_API_AUTH_TOKEN = 'myToken'

    SECRET_KEY = 'TestKeyTestKeyTestKeyTestKeyTestKeyTestKeyX='
    SHARED_EMAIL_KEY = SECRET_KEY

    DM_SUBMISSIONS_BUCKET = 'digitalmarketplace-submissions-dev-dev'
    DM_COMMUNICATIONS_BUCKET = 'digitalmarketplace-communications-dev-dev'
    DM_ASSETS_URL = 'http://asset-host'


class Development(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

    # Throw an exception in dev when a feature flag is used in code but not defined. Otherwise it is assumed False.
    RAISE_ERROR_ON_MISSING_FEATURES = True

    DM_DATA_API_URL = "http://localhost:5000"
    DM_DATA_API_AUTH_TOKEN = "myToken"
    DM_API_AUTH_TOKEN = "myToken"

    DM_SUBMISSIONS_BUCKET = "digitalmarketplace-submissions-dev-dev"
    DM_COMMUNICATIONS_BUCKET = "digitalmarketplace-communications-dev-dev"
    DM_AGREEMENTS_BUCKET = "digitalmarketplace-agreements-dev-dev"
    DM_DOCUMENTS_BUCKET = "digitalmarketplace-documents-dev-dev"
    DM_ASSETS_URL = "https://{}.s3-eu-west-1.amazonaws.com".format(DM_SUBMISSIONS_BUCKET)

    SECRET_KEY = 'DevKeyDevKeyDevKeyDevKeyDevKeyDevKeyDevKeyX='
    SHARED_EMAIL_KEY = SECRET_KEY


class Live(Config):
    """Base config for deployed environments"""
    DEBUG = False
    DM_HTTP_PROTO = 'https'
    DM_CACHE_TYPE = 'prod'
    SERVER_NAME = 'marketplace.service.gov.au'

    DM_FRAMEWORK_AGREEMENTS_EMAIL = 'no-reply@marketplace.digital.gov.au'

    FEATURE_FLAGS = {
        'EDIT_SECTIONS': False,
    }


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
