# coding=utf-8
# type: ignore

import os
import jinja2
from dmutils.status import get_version_label
from dmutils.asset_fingerprint import AssetFingerprinter


class Config(object):

    VERSION = get_version_label(
        os.path.abspath(os.path.dirname(__file__))
    )
    SESSION_COOKIE_NAME = 'dm_session'
    SESSION_COOKIE_PATH = '/'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"

    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    DM_COOKIE_PROBE_EXPECT_PRESENT = True

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    DM_DATA_API_URL = None
    DM_DATA_API_AUTH_TOKEN = None
    DM_NOTIFY_API_KEY = None
    DM_REDIS_SERVICE_NAME = None

    DM_CLARIFICATION_QUESTION_EMAIL = 'clarification-questions@example.gov.uk'
    DM_FRAMEWORK_AGREEMENTS_EMAIL = 'enquiries@example.com'
    DM_COMPANY_DETAILS_CHANGE_EMAIL = 'cloud_digital@crowncommercial.gov.uk'
    SUPPORT_EMAIL_ADDRESS = "cloud_digital@crowncommercial.gov.uk"

    NOTIFY_TEMPLATES = {
        "confirmation_of_clarification_question": "1a8a3408-49ef-486f-a6c9-8557d1a0dc63",
        "create_user_account": "84f5d812-df9d-4ab8-804a-06f64f5abd30",
        "invite_contributor": "5eefe42d-1694-4388-8908-991cdfba0a71",
        "framework_agreement_signature_page": "08929c93-f9e7-4b40-b75f-418659308324",
        'framework-application-started': '9c8237fa-d854-4388-babb-14a0f252d133',
        'framework-clarification-question': "8574484f-9907-44c0-b9d5-1120beb64ef0",
        'framework-application-question': '6681d4a1-6e30-407f-9e8b-3f6633d73546',
        'sign_framework_agreement_confirmation': 'bbc77101-4585-4d1e-80c4-43045ea9550f'
    }

    DM_AGREEMENTS_BUCKET = None
    DM_COMMUNICATIONS_BUCKET = None
    DM_DOCUMENTS_BUCKET = None
    DM_SUBMISSIONS_BUCKET = None
    DM_ASSETS_URL = None

    DM_MAILCHIMP_USERNAME = None
    DM_MAILCHIMP_API_KEY = None
    DM_MAILCHIMP_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ID = None

    DM_DNB_API_USERNAME = None
    DM_DNB_API_PASSWORD = None

    DEBUG = False

    INVITE_EMAIL_NAME = 'Digital Marketplace Admin'
    INVITE_EMAIL_FROM = 'cloud_digital@crowncommercial.gov.uk'
    INVITE_EMAIL_SUBJECT = 'Your Digital Marketplace invitation'

    CLARIFICATION_EMAIL_NAME = 'Digital Marketplace Admin'
    DM_FOLLOW_UP_EMAIL_TO = 'follow-up@example.gov.uk'

    FRAMEWORK_AGREEMENT_RETURNED_NAME = 'Digital Marketplace Admin'

    DM_ENQUIRIES_EMAIL_ADDRESS = 'cloud_digital@crowncommercial.gov.uk'
    DM_ENQUIRIES_EMAIL_ADDRESS_UUID = '24908180-b64e-513d-ab48-fdca677cec52'

    SECRET_KEY = None
    SHARED_EMAIL_KEY = None
    RESET_PASSWORD_TOKEN_NS = 'ResetPasswordSalt'
    INVITE_EMAIL_TOKEN_NS = 'InviteEmailSalt'

    STATIC_URL_PATH = '/suppliers/static'
    ASSET_PATH = STATIC_URL_PATH + '/'
    BASE_TEMPLATE_DATA = {
        'header_class': 'with-proposition',
        'asset_path': ASSET_PATH,
        'asset_fingerprinter': AssetFingerprinter(asset_root=ASSET_PATH)
    }

    # Logging
    DM_LOG_LEVEL = 'DEBUG'
    DM_PLAIN_TEXT_LOGS = False
    DM_LOG_PATH = None
    DM_APP_NAME = 'supplier-frontend'

    @staticmethod
    def init_app(app):
        repo_root = os.path.abspath(os.path.dirname(__file__))
        digitalmarketplace_govuk_frontend = os.path.join(repo_root, "node_modules", "digitalmarketplace-govuk-frontend")
        govuk_frontend = os.path.join(repo_root, "node_modules", "govuk-frontend")
        template_folders = [
            os.path.join(repo_root, "app", "templates"),
            os.path.join(digitalmarketplace_govuk_frontend),
            os.path.join(digitalmarketplace_govuk_frontend, "digitalmarketplace", "templates"),
        ]
        jinja_loader = jinja2.ChoiceLoader([
            jinja2.FileSystemLoader(template_folders),
            jinja2.PrefixLoader({'govuk': jinja2.FileSystemLoader(govuk_frontend)})
        ])
        app.jinja_loader = jinja_loader


class Test(Config):
    DEBUG = True
    DM_PLAIN_TEXT_LOGS = True
    DM_LOG_LEVEL = 'CRITICAL'
    WTF_CSRF_ENABLED = False
    DM_NOTIFY_API_KEY = "not_a_real_key-00000000-fake-uuid-0000-000000000000"

    SHARED_EMAIL_KEY = "KEY"

    DM_MAILCHIMP_USERNAME = 'not_a_real_username'
    DM_MAILCHIMP_API_KEY = 'not_a_real_key'  # pragma: allowlist secret
    DM_MAILCHIMP_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ID = "not_a_real_mailing_list"

    DM_DATA_API_AUTH_TOKEN = 'myToken'

    SECRET_KEY = 'not_very_secret'

    DM_ASSETS_URL = 'http://asset-host'


class Development(Config):
    DEBUG = True
    DM_PLAIN_TEXT_LOGS = True
    SESSION_COOKIE_SECURE = False

    DM_DATA_API_URL = f"http://localhost:{os.getenv('DM_API_PORT', 5000)}"
    DM_DATA_API_AUTH_TOKEN = "myToken"
    DM_API_AUTH_TOKEN = "myToken"

    DM_S3_ENDPOINT_URL = (  # use envvars to set this, defaults to using AWS
        f"http://s3.localhost.localstack.cloud:{os.environ['DM_S3_ENDPOINT_PORT']}"
        if os.getenv("DM_S3_ENDPOINT_PORT") else None
    )

    DM_SUBMISSIONS_BUCKET = "digitalmarketplace-dev-uploads"
    DM_COMMUNICATIONS_BUCKET = "digitalmarketplace-dev-uploads"
    DM_AGREEMENTS_BUCKET = "digitalmarketplace-dev-uploads"
    DM_DOCUMENTS_BUCKET = "digitalmarketplace-dev-uploads"
    DM_ASSETS_URL = (
        f"http://{DM_SUBMISSIONS_BUCKET}.s3.localhost.localstack.cloud:{os.environ['DM_S3_ENDPOINT_PORT']}"
        if os.getenv("DM_S3_ENDPOINT_PORT") else
        f"https://{DM_SUBMISSIONS_BUCKET}.s3-eu-west-1.amazonaws.com"
    )

    DM_NOTIFY_API_KEY = "not_a_real_key-00000000-fake-uuid-0000-000000000000"

    SHARED_EMAIL_KEY = "very_secret"
    SECRET_KEY = 'verySecretKey'

    DM_MAILCHIMP_USERNAME = 'not_a_real_username'
    DM_MAILCHIMP_API_KEY = 'not_a_real_key'  # pragma: allowlist secret
    DM_MAILCHIMP_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ID = "not_a_real_mailing_list"

    DM_DNB_API_USERNAME = 'not_a_real_username'
    DM_DNB_API_PASSWORD = 'not_a_real_password'  # pragma: allowlist secret


class SharedLive(Config):
    """Base config for deployed environments shared between GPaaS and AWS"""
    DEBUG = False
    DM_HTTP_PROTO = 'https'

    # use of invalid email addresses with live api keys annoys Notify
    DM_NOTIFY_REDIRECT_DOMAINS_TO_ADDRESS = {
        "example.com": "success@simulator.amazonses.com",
        "example.gov.uk": "success@simulator.amazonses.com",
        "user.marketplace.team": "success@simulator.amazonses.com",
    }

    DM_FRAMEWORK_AGREEMENTS_EMAIL = 'cloud_digital@crowncommercial.gov.uk'


class NativeAWS(SharedLive):
    DM_APP_NAME = 'supplier-frontend'
    # DM_LOGIN_URL will be read from env vars - used to avoid incorrect host/port
    # redirect from Flask-Login package
    DM_LOGIN_URL = None
    # SESSION_COOKIE_DOMAIN will be read from env vars - set to subdomain to
    # allow session share between "www.' and "admin."
    SESSION_COOKIE_DOMAIN = None


class Live(SharedLive):
    """Base config for deployed environments"""
    DM_LOG_PATH = '/var/log/digitalmarketplace/application.log'


class Preview(Live):
    pass


class Staging(Live):
    pass


class Production(Live):
    pass


configs = {
    'development': Development,
    'native-aws': NativeAWS,
    'preview': Preview,
    'staging': Staging,
    'production': Production,
    'test': Test,
}
