from app.flask_api_client.api_client import ApiClient
from flask import json
from nose.tools import assert_equal
from datetime import datetime

import requests
import requests_mock
from app import create_app
from app.model import User


class TestApiClient():
    api_client = None

    def __init__(self):
        self.app = create_app('test')
        self.api_client = ApiClient(self.app)
        self.session = requests.Session()
        self.adapter = requests_mock.Adapter()
        self.session.mount('mock', self.adapter)

    def test_auth_is_called_with_correct_params(self):
        with requests_mock.mock() as m:
            m.post(
                'http://localhost/users/auth',
                text=json.dumps(self.user()),
                status_code=200)

            user = self.api_client.users_auth(
                'email_address',
                'password'
            )
            assert_equal(user.id, 'id')
            assert_equal(user.email_address, 'email_address')
            assert_equal(user.supplier_id, 1234)
            assert_equal(user.supplier_name, 'name')

    def test_auth_returns_none_on_404(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/auth',
                    text=json.dumps({'authorization': False}),
                    status_code=404)

                user = self.api_client.users_auth(
                    'email_address',
                    'password'
                )
                assert_equal(user, None)

    def test_auth_returns_none_on_403(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/auth',
                    text=json.dumps({'authorization': False}),
                    status_code=403)

                user = self.api_client.users_auth(
                    'email_address',
                    'password'
                )
                assert_equal(user, None)

    def test_auth_returns_none_on_a_non_supplier_user(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                user_with_no_supplier = self.user()
                del user_with_no_supplier["users"]["supplier"]

                m.post(
                    'http://localhost/users/auth',
                    text=json.dumps(user_with_no_supplier),
                    status_code=200)

                user = self.api_client.users_auth(
                    'email_address',
                    'password'
                )
                assert_equal(user, None)

    def test_auth_returns_none_on_400(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/auth',
                    text=json.dumps({'authorization': False}),
                    status_code=400)

                user = self.api_client.users_auth(
                    'email_address',
                    'password'
                )
                assert_equal(user, None)

    def test_auth_returns_none_on_500(self):
        with requests_mock.mock() as m:
            with self.app.app_context():
                m.post(
                    'http://localhost/users/auth',
                    text=json.dumps({'authorization': False}),
                    status_code=500)

                user = self.api_client.users_auth(
                    'email_address',
                    'password'
                )
                assert_equal(user, None)

    def test_user_json_to_user(self):
        result = User.from_json(self.user())
        assert_equal(result.id, 'id')
        assert_equal(result.email_address, 'email_address')

    @staticmethod
    def user():
        timestamp = datetime.now()

        return {'users': {
            'id': 'id',
            'emailAddress': 'email_address',
            'name': 'name',
            'role': 'role',
            'active': 'active',
            'locked': False,
            'createdAt': timestamp,
            'updatedAt': timestamp,
            'passwordChangedAt': timestamp,
            'supplier': {
                'supplierId': 1234,
                'name': 'name'
            }
        }}
