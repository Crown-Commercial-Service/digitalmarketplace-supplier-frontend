# coding=utf-8

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

    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    DM_DATA_API_URL = None
    DM_DATA_API_AUTH_TOKEN = None
    DM_MANDRILL_API_KEY = None
    DM_NOTIFY_API_KEY = None
    DM_CLARIFICATION_QUESTION_EMAIL = 'digitalmarketplace@mailinator.com'
    DM_FRAMEWORK_AGREEMENTS_EMAIL = 'enquiries@example.com'
    DM_COMPANY_DETAILS_CHANGE_EMAIL = 'cloud_digital@crowncommercial.gov.uk'

    NOTIFY_TEMPLATES = {
        "confirmation_of_clarification_question": "1a8a3408-49ef-486f-a6c9-8557d1a0dc63",
        "create_user_account": "84f5d812-df9d-4ab8-804a-06f64f5abd30",
        "invite_contributor": "5eefe42d-1694-4388-8908-991cdfba0a71",
        "framework_agreement_signature_page": "08929c93-f9e7-4b40-b75f-418659308324",
    }

    DM_AGREEMENTS_BUCKET = None
    DM_COMMUNICATIONS_BUCKET = None
    DM_DOCUMENTS_BUCKET = None
    DM_SUBMISSIONS_BUCKET = None
    DM_ASSETS_URL = None

    DM_MAILCHIMP_USERNAME = None
    DM_MAILCHIMP_API_KEY = None
    DM_MAILCHIMP_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ID = None

    DEBUG = False

    INVITE_EMAIL_NAME = 'Digital Marketplace Admin'
    INVITE_EMAIL_FROM = 'enquiries@digitalmarketplace.service.gov.uk'
    INVITE_EMAIL_SUBJECT = 'Your Digital Marketplace invitation'

    CLARIFICATION_EMAIL_NAME = 'Digital Marketplace Admin'
    DM_FOLLOW_UP_EMAIL_TO = 'digitalmarketplace@mailinator.com'

    FRAMEWORK_AGREEMENT_RETURNED_NAME = 'Digital Marketplace Admin'

    DM_ENQUIRIES_EMAIL_ADDRESS = 'enquiries@digitalmarketplace.service.gov.uk'

    SECRET_KEY = None
    SHARED_EMAIL_KEY = None
    RESET_PASSWORD_SALT = 'ResetPasswordSalt'
    INVITE_EMAIL_SALT = 'InviteEmailSalt'

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
        template_folders = [
            os.path.join(repo_root, 'app/templates')
        ]
        jinja_loader = jinja2.FileSystemLoader(template_folders)
        app.jinja_loader = jinja_loader


class Test(Config):
    DEBUG = True
    DM_PLAIN_TEXT_LOGS = True
    DM_LOG_LEVEL = 'CRITICAL'
    WTF_CSRF_ENABLED = False
    DM_MANDRILL_API_KEY = 'MANDRILL'
    DM_NOTIFY_API_KEY = "not_a_real_key-00000000-fake-uuid-0000-000000000000"

    SHARED_EMAIL_KEY = "KEY"
    DM_CLARIFICATION_QUESTION_EMAIL = 'digitalmarketplace@mailinator.com'

    DM_MAILCHIMP_USERNAME = 'not_a_real_username'
    DM_MAILCHIMP_API_KEY = 'not_a_real_key'
    DM_MAILCHIMP_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ID = "not_a_real_mailing_list"

    DM_DATA_API_AUTH_TOKEN = 'myToken'

    SECRET_KEY = 'not_very_secret'

    DM_ASSETS_URL = 'http://asset-host'


class Development(Config):
    DEBUG = True
    DM_PLAIN_TEXT_LOGS = True
    SESSION_COOKIE_SECURE = False

    DM_DATA_API_URL = "http://localhost:5000"
    DM_DATA_API_AUTH_TOKEN = "myToken"
    DM_API_AUTH_TOKEN = "myToken"

    DM_SUBMISSIONS_BUCKET = "digitalmarketplace-dev-uploads"
    DM_COMMUNICATIONS_BUCKET = "digitalmarketplace-dev-uploads"
    DM_AGREEMENTS_BUCKET = "digitalmarketplace-dev-uploads"
    DM_DOCUMENTS_BUCKET = "digitalmarketplace-dev-uploads"
    DM_ASSETS_URL = "https://{}.s3-eu-west-1.amazonaws.com".format(DM_SUBMISSIONS_BUCKET)

    DM_MANDRILL_API_KEY = "not_a_real_key"
    DM_NOTIFY_API_KEY = "not_a_real_key-00000000-fake-uuid-0000-000000000000"

    SHARED_EMAIL_KEY = "very_secret"
    SECRET_KEY = 'verySecretKey'

    DM_MAILCHIMP_USERNAME = 'not_a_real_username'
    DM_MAILCHIMP_API_KEY = 'not_a_real_key'
    DM_MAILCHIMP_OPEN_FRAMEWORK_NOTIFICATION_MAILING_LIST_ID = "not_a_real_mailing_list"


class Live(Config):
    """Base config for deployed environments"""
    DEBUG = False
    DM_LOG_PATH = '/var/log/digitalmarketplace/application.log'
    DM_HTTP_PROTO = 'https'

    # use of invalid email addresses with live api keys annoys Notify
    DM_NOTIFY_REDIRECT_DOMAINS_TO_ADDRESS = {
        "example.com": "success@simulator.amazonses.com",
        "example.gov.uk": "success@simulator.amazonses.com",
        "user.marketplace.team": "success@simulator.amazonses.com",
    }

    DM_FRAMEWORK_AGREEMENTS_EMAIL = 'enquiries@digitalmarketplace.service.gov.uk'


class Preview(Live):
    pass


class Staging(Live):
    WTF_CSRF_ENABLED = False


class Production(Live):
    pass


configs = {
    'development': Development,
    'preview': Preview,
    'staging': Staging,
    'production': Production,
    'test': Test,
}
