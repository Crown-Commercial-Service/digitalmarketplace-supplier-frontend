# -*- coding: utf-8 -*-
import re
from mock import patch
from app import create_app
from tests import login_for_tests
from werkzeug.http import parse_cookie
from app import data_api_client
from datetime import datetime, timedelta
from dmutils.formats import DATETIME_FORMAT
from nose.tools import assert_in, assert_not_in


FULL_G7_SUBMISSION = {
    "status": "complete",
    "PR1": "true",
    "PR2": "true",
    "PR3": "true",
    "PR4": "true",
    "PR5": "true",
    "SQ1-1i-i": "true",
    "SQ2-1abcd": "true",
    "SQ2-1e": "true",
    "SQ2-1f": "true",
    "SQ2-1ghijklmn": "true",
    "SQ2-2a": "true",
    "SQ3-1a": "true",
    "SQ3-1b": "true",
    "SQ3-1c": "true",
    "SQ3-1d": "true",
    "SQ3-1e": "true",
    "SQ3-1f": "true",
    "SQ3-1g": "true",
    "SQ3-1h-i": "true",
    "SQ3-1h-ii": "true",
    "SQ3-1i-i": "true",
    "SQ3-1i-ii": "true",
    "SQ3-1j": "true",
    "SQ3-1k": "Blah",
    "SQ4-1a": "true",
    "SQ4-1b": "true",
    "SQ5-2a": "true",
    "SQD2b": "true",
    "SQD2d": "true",
    "SQ1-1a": "Legal Supplier Name",
    "SQ1-1b": "Blah",
    "SQ1-1cii": "Blah",
    "SQ1-1d": "Blah",
    "SQ1-1d-i": "Blah",
    "SQ1-1d-ii": "Blah",
    "SQ1-1e": "Blah",
    "SQ1-1h": "999999999",
    "SQ1-1i-ii": "Blah",
    "SQ1-1j-ii": "Blah",
    "SQ1-1k": "Blah",
    "SQ1-1n": "Blah",
    "SQ1-1o": "Blah@example.com",
    "SQ1-2a": "Blah",
    "SQ1-2b": "Blah@example.com",
    "SQ2-2b": "Blah",
    "SQ4-1c": "Blah",
    "SQD2c": "Blah",
    "SQD2e": "Blah",
    "SQ1-1ci": "public limited company",
    "SQ1-1j-i": "licensed?",
    "SQ1-1m": "micro",
    "SQ1-3": "on-demand self-service. blah blah",
    "SQ5-1a": u"Yes – your organisation has, blah blah",
    "SQC2": [
        "race?",
        "sexual orientation?",
        "disability?",
        "age equality?",
        "religion or belief?",
        "gender (sex)?",
        "gender reassignment?",
        "marriage or civil partnership?",
        "pregnancy or maternity?",
        "human rights?"
    ],
    "SQC3": "true",
    "SQA2": "true",
    "SQA3": "true",
    "SQA4": "true",
    "SQA5": "true",
    "AQA3": "true",
    "SQE2a": ["as a prime contractor, using third parties (subcontractors) to provide some services"]
}


def empty_g7_draft():
    return {
        'id': 1,
        'supplierId': 1234,
        'supplierName': 'supplierName',
        'frameworkName': 'G-Cloud 7',
        'frameworkSlug': 'g-cloud-7',
        'lot': 'scs',
        'lotSlug': 'scs',
        'lotName': 'Specialist Cloud Services',
        'status': 'not-submitted',
        'links': {},
        'updatedAt': '2015-06-29T15:26:07.650368Z'
    }


class BaseApplicationTest(object):
    def setup(self):
        self.app = create_app('test')
        self.app.register_blueprint(login_for_tests)
        self.client = self.app.test_client()
        self.get_user_patch = None

    def teardown(self):
        self.teardown_login()

    @staticmethod
    def get_cookie_by_name(response, name):
        cookies = response.headers.getlist('Set-Cookie')
        for cookie in cookies:
            if name in parse_cookie(cookie):
                return parse_cookie(cookie)
        return None

    @staticmethod
    def supplier():
        return {
            "suppliers": {
                "id": 12345,
                "name": "Supplier Name",
                'description': 'Supplier Description',
                'dunsNumber': '999999999',
                'companiesHouseId': 'SC009988',
                'contactInformation': [{
                    'id': 1234,
                    'contactName': 'contact name',
                    'phoneNumber': '099887',
                    'email': 'email@email.com',
                    'website': 'http://myweb.com',
                }],
                'clients': ['one client', 'two clients']
            }
        }

    @staticmethod
    def user(id, email_address, supplier_id, supplier_name, name,
             is_token_valid=True, locked=False, active=True, role='buyer'):

        hours_offset = -1 if is_token_valid else 1
        date = datetime.utcnow() + timedelta(hours=hours_offset)
        password_changed_at = date.strftime(DATETIME_FORMAT)

        user = {
            "id": id,
            "emailAddress": email_address,
            "name": name,
            "role": role,
            "locked": locked,
            'active': active,
            'passwordChangedAt': password_changed_at
        }

        if supplier_id:
            supplier = {
                "supplierId": supplier_id,
                "name": supplier_name,
            }
            user['role'] = 'supplier'
            user['supplier'] = supplier
        return {
            "users": user
        }

    @staticmethod
    def strip_all_whitespace(content):
        pattern = re.compile(r'\s+')
        return re.sub(pattern, '', content)

    @staticmethod
    def services():
        return {
            'services': [
                {
                    'id': 'id',
                    'serviceName': 'serviceName',
                    'frameworkName': 'frameworkName',
                    'lot': 'lot',
                    'serviceSummary': 'serviceSummary'
                }
            ]
        }

    @staticmethod
    def framework(
            status='open',
            name='G-Cloud 7',
            slug='g-cloud-7',
            clarification_questions_open=True,
            framework_agreement_version=None
    ):
        if 'g-cloud-' in slug:
            lots = [
                {'id': 1, 'slug': 'iaas', 'name': 'Infrastructure as a Service', 'oneServiceLimit': False,
                 'unitSingular': 'service', 'unitPlural': 'service'},
                {'id': 2, 'slug': 'scs', 'name': 'Specialist Cloud Services', 'oneServiceLimit': False,
                 'unitSingular': 'service', 'unitPlural': 'service'},
                {'id': 3, 'slug': 'paas', 'name': 'Platform as a Service', 'oneServiceLimit': False,
                 'unitSingular': 'service', 'unitPlural': 'service'},
                {'id': 4, 'slug': 'saas', 'name': 'Software as a Service', 'oneServiceLimit': False,
                 'unitSingular': 'service', 'unitPlural': 'service'},
            ]
        elif slug == 'digital-outcomes-and-specialists':
            lots = [
                {'id': 1, 'slug': 'digital-specialists', 'name': 'Digital specialists', 'oneServiceLimit': True,
                 'unitSingular': 'service', 'unitPlural': 'service'},
            ]

        return {
            'frameworks': {
                'status': status,
                'clarificationQuestionsOpen': clarification_questions_open,
                'name': name,
                'slug': slug,
                'lots': lots,
                'frameworkAgreementVersion': framework_agreement_version
            }
        }

    @staticmethod
    def supplier_framework(declaration='default', status=None, on_framework=False,
                           agreement_returned=False, agreement_returned_at=None):
        if declaration == 'default':
            declaration = FULL_G7_SUBMISSION.copy()
        if status is not None:
            declaration['status'] = status
        return {
            'frameworkInterest': {
                'declaration': declaration,
                'onFramework': on_framework,
                'agreementReturned': agreement_returned,
                'agreementReturnedAt': agreement_returned_at,
            }
        }

    def teardown_login(self):
        if self.get_user_patch is not None:
            self.get_user_patch.stop()

    def login(self):
        with patch('app.main.views.login.data_api_client') as login_api_client:
            login_api_client.authenticate_user.return_value = self.user(
                123, "email@email.com", 1234, 'Supplier Name', 'Name')

            self.get_user_patch = patch.object(
                data_api_client,
                'get_user',
                return_value=self.user(123, "email@email.com", 1234, 'Supplier Name', 'Name')
            )
            self.get_user_patch.start()

            response = self.client.get("/auto-login")
            assert response.status_code == 200

    def login_as_buyer(self):
        with patch('app.main.views.login.data_api_client') as login_api_client:

            login_api_client.authenticate_user.return_value = self.user(
                234, "buyer@email.com", None, None, 'Buyer', role='buyer')

            self.get_user_patch = patch.object(
                data_api_client,
                'get_user',
                return_value=self.user(234, "buyer@email.com", None, None, 'Buyer', role='buyer')
            )
            self.get_user_patch.start()

            response = self.client.get("/auto-buyer-login")
            assert response.status_code == 200

    def assert_in_strip_whitespace(self, needle, haystack):
        return assert_in(self.strip_all_whitespace(needle), self.strip_all_whitespace(haystack))

    def assert_not_in_strip_whitespace(self, needle, haystack):
        return assert_not_in(self.strip_all_whitespace(needle), self.strip_all_whitespace(haystack))

    # Method to test flashes taken from http://blog.paulopoiati.com/2013/02/22/testing-flash-messages-in-flask/
    def assert_flashes(self, expected_message, expected_category='message'):
        with self.client.session_transaction() as session:
            try:
                category, message = session['_flashes'][0]
            except KeyError:
                raise AssertionError('nothing flashed')
            assert expected_message in message
            assert expected_category == category


class FakeMail(object):
    """An object that equals strings containing all of the given substrings

    Can be used in mock.call comparisons (eg to verify email templates).

    """
    def __init__(self, *substrings):
        self.substrings = substrings

    def __eq__(self, other):
        return all(substring in other for substring in self.substrings)

    def __repr__(self):
        return "<FakeMail: {}>".format(self.substrings)
