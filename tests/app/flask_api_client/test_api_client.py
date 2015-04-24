from app.flask_api_client.api_client import ApiClient
from flask import json
from nose.tools import assert_equal
from datetime import datetime

import requests
import requests_mock
from app import create_app


class TestApiClient():
    api_client = None

    def __init__(self):
        app = create_app('test')
        self.api_client = ApiClient(app)
        self.session = requests.Session()
        self.adapter = requests_mock.Adapter()
        self.session.mount('mock', self.adapter)

    def test_auth_is_called_with_correct_params(self):
        with requests_mock.mock() as m:
            m.post(
                'http://localhost/users/auth',
                text=json.dumps(self.user()),
                status_code=200)

            result, user = self.api_client.users_auth(
                'email_address',
                'password'
            )
            assert_equal(result, True)
            assert_equal(user.id, 'id')
            assert_equal(user.email_address, 'email_address')

    def test_auth_returns_none_on_404(self):
        with requests_mock.mock() as m:
            m.post(
                'http://localhost/users/auth',
                text=json.dumps({'authorization': False}),
                status_code=404)

            result, user = self.api_client.users_auth(
                'email_address',
                'password'
            )
            assert_equal(result, False)
            assert_equal(user, None)

    def test_auth_returns_none_on_403(self):
        with requests_mock.mock() as m:
            m.post(
                'http://localhost/users/auth',
                text=json.dumps({'authorization': False}),
                status_code=403)

            result, user = self.api_client.users_auth(
                'email_address',
                'password'
            )
            assert_equal(result, False)
            assert_equal(user, None)

    def test_auth_returns_none_on_400(self):
        with requests_mock.mock() as m:
            m.post(
                'http://localhost/users/auth',
                text=json.dumps({'authorization': False}),
                status_code=400)

            result, user = self.api_client.users_auth(
                'email_address',
                'password'
            )
            assert_equal(result, False)
            assert_equal(user, None)

    def test_auth_returns_none_on_500(self):
        with requests_mock.mock() as m:
            m.post(
                'http://localhost/users/auth',
                text=json.dumps({'authorization': False}),
                status_code=500)

            result, user = self.api_client.users_auth(
                'email_address',
                'password'
            )
            assert_equal(result, False)
            assert_equal(user, None)

    def test_user_json_to_user(self):
        result = self.api_client.user_json_to_user(self.user())
        assert_equal(result.id, 'id')
        assert_equal(result.email_address, 'email_address')

    @staticmethod
    def user():
        timestamp = datetime.now()

        return {
            'id': 'id',
            'email_address': 'email_address',
            'name': 'name',
            'role': 'role',
            'active': 'active',
            'locked': False,
            'created_at': timestamp,
            'updated_at': timestamp,
            'password_changed_at': timestamp
        }
