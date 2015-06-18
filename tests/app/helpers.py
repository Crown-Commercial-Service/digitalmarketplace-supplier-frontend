import re
from mock import Mock
from app import create_app
from werkzeug.http import parse_cookie
from app import data_api_client
from datetime import datetime, timedelta


class BaseApplicationTest(object):
    def setup(self):
        self.app = create_app('test')
        self.client = self.app.test_client()

    @staticmethod
    def get_cookie_by_name(response, name):
        cookies = response.headers.getlist('Set-Cookie')
        for cookie in cookies:
            if name in parse_cookie(cookie):
                return parse_cookie(cookie)
        return None

    @staticmethod
    def user(id, email_address, supplier_id, supplier_name,
             is_token_valid=True):

        hours_offset = -1 if is_token_valid else 1
        date = datetime.now() + timedelta(hours=hours_offset)
        # will be formatted like 'Mon, 15 Jun 2015 00:00:00 GMT'
        password_changed_at = date.strftime('%a, %d %b %Y %H:%M:%S GMT')

        return {
            "users": {
                "id": id,
                "emailAddress": email_address,
                "supplier": {
                    "supplierId": supplier_id,
                    "name": supplier_name,
                },
                'passwordChangedAt': password_changed_at
            }
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

    def login(self):
        data_api_client.authenticate_user = Mock(
            return_value=(self.user(
                123, "email@email.com", 1234, 'Supplier Name')))

        data_api_client.get_user = Mock(
            return_value=(self.user(
                123, "email@email.com", 1234, 'Supplier Name')))

        self.client.post("/suppliers/login", data={
            'email_address': 'valid@email.com',
            'password': '1234567890'
        })

        data_api_client.authenticate_user.assert_called_once_with(
            "valid@email.com", "1234567890")
